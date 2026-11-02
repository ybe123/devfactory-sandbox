"""Deterministic check of an agent's patch before it is published (Dev Factory lot 2).

Standard library only. The SAME file is copied into the sandbox repository (.devfactory/patchcheck.py, a test checks
that both copies are identical): the publication job runs this check from the repository's default branch, never
from the patch itself, and the control plane runs it again on the downloaded artifact.

Refused: workflow, tooling and ownership files; symlinks, submodules, binaries, mode changes, renames and deletions
outside the role's area; paths escaping the repository; patches over the size limits; anything that looks like a
secret; a developer touching the acceptance tests; a reviewer touching anything else.
"""
import re

MAX_PATCH_BYTES = 200_000
MAX_FILES = 50
# Never changed by an agent: CI and automation, the trusted publication tooling, ownership and repository settings.
PROTECTED = re.compile(r"^(\.github/|\.devfactory/|\.trusted/|CODEOWNERS$|docs/CODEOWNERS$|\.gitattributes$"
                       r"|\.gitmodules$|\.gitignore$|CLAUDE\.md$|\.devfactory-verdicts\.json$)")
# Test configuration and interpreter start-up hooks could change how the trusted test step behaves: only the
# reviewer may configure its own acceptance tests (tests/acceptance/conftest.py).
TEST_HOOKS = re.compile(r"(^|/)(conftest\.py|pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|sitecustomize\.py"
                        r"|usercustomize\.py|[^/]*\.pth)$")
ACCEPTANCE = re.compile(r"^tests/acceptance/")
SAFE_PATH = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]*$")
SECRETS = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{32,}"
    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,})")
ROLES = ("developer", "reviewer")

def _paths(header: str) -> tuple[str, str]:
    m = re.match(r"^diff --git a/(\S+) b/(\S+)$", header)
    if not m:
        raise ValueError("unparsable diff header")
    return m.group(1), m.group(2)

def check(patch: str, role: str) -> list[str]:
    """Violations of `patch` (git diff text) for `role` ('developer' or 'reviewer'); [] means publishable."""
    if role not in ROLES:
        return [f"unknown role {role!r}"]
    problems: list[str] = []
    if len(patch.encode()) > MAX_PATCH_BYTES:
        problems.append("patch too large")
    if not patch.strip():
        # A review may conclude with no new test (verdict only); a developer run must change something.
        return problems + (["empty patch"] if role == "developer" else [])
    blocks = re.split(r"(?m)^(?=diff --git )", patch)
    if blocks[0].strip():
        problems.append("text before the first file")
    files = [b for b in blocks if b.startswith("diff --git ")]
    if len(files) > MAX_FILES:
        problems.append("too many files")
    for block in files:
        header = block.splitlines()[0]
        try:
            old, new = _paths(header)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        for path in {old, new}:
            if not SAFE_PATH.match(path) or ".." in path.split("/") or "//" in path or path.endswith("/"):
                problems.append(f"{path}: unsafe path")
            elif PROTECTED.match(path):
                problems.append(f"{path}: protected file")
            elif TEST_HOOKS.search(path) and not (role == "reviewer" and path == "tests/acceptance/conftest.py"):
                problems.append(f"{path}: test configuration or start-up hook")
            elif role == "developer" and ACCEPTANCE.match(path):
                problems.append(f"{path}: acceptance tests belong to the reviewer")
            elif role == "reviewer" and not ACCEPTANCE.match(path):
                problems.append(f"{path}: a reviewer only adds acceptance tests")
        meta = block.split("\n@@", 1)[0]
        if re.search(r"(?m)^(new file mode|deleted file mode|old mode|new mode) (120000|160000)", meta):
            problems.append(f"{new}: symlinks and submodules are refused")
        if re.search(r"(?m)^(old mode|new mode) ", meta):
            problems.append(f"{new}: mode changes are refused")
        if re.search(r"(?m)^(new file mode|deleted file mode) (?!100644$)\d+$", meta):
            problems.append(f"{new}: only regular, non-executable files")
        if re.search(r"(?m)^(rename|copy) (from|to) ", meta):
            problems.append(f"{new}: renames and copies are refused")
        if re.search(r"(?m)^deleted file mode ", meta):
            problems.append(f"{old}: deletions are refused")
        if "GIT binary patch" in block or re.search(r"(?m)^Binary files ", block):
            problems.append(f"{new}: binary content is refused")
        added = "\n".join(line[1:] for line in block.splitlines() if line.startswith("+") and not line.startswith("+++"))
        if SECRETS.search(added):
            problems.append(f"{new}: looks like a secret")
    return sorted(set(problems))
