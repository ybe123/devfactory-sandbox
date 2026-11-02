"""Deterministic publication of an agent's patch (Dev Factory lot 2, `publish` job). Standard library + git only.

Runs from the DEFAULT branch's checkout, on a machine that never ran the agent. The patch is DATA: it is checked
(patchcheck.py), applied with git (hooks disabled), committed and pushed to `agent/<TASK>` only, then ONE draft pull
request is opened or updated. Nothing from the patch is executed: no install, no test, no script.
Never merges, approves, reviews, tags, releases or touches another branch.

    publish.py --check-only --patch P --report R      # refuse early (before the App token exists)
    publish.py --patch P --report R                    # needs GH_TOKEN, REPOSITORY, DEFAULT_BRANCH, KEY, ROLE, BASE, BRANCH
"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patchcheck  # noqa: E402  (same directory, default branch)

MARKER = "<!-- devfactory -->"
BRANCH = re.compile(r"^agent/[A-Z][A-Z0-9-]{0,15}$")
KEY = re.compile(r"^devfactory:[0-9]{1,9}:[0-9]{1,4}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
AUTHOR = ("Artisana Dev Factory", "devfactory@users.noreply.invalid")

class Refused(Exception):
    pass

def load(patch_path: str, report_path: str) -> tuple[str, dict]:
    env = os.environ
    with open(patch_path, encoding="utf-8", newline="") as f:  # byte-exact: the digest must match
        patch = f.read()
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    if not KEY.match(env.get("KEY", "")) or env.get("ROLE") not in patchcheck.ROLES:
        raise Refused("invalid key or role")
    if not SHA1.match(env.get("BASE", "")) or not BRANCH.match(env.get("BRANCH", "")):
        raise Refused("invalid base or branch")
    if (report.get("key"), report.get("role"), report.get("base")) != (env["KEY"], env["ROLE"], env["BASE"]):
        raise Refused("report does not match the run")
    data = patch.encode()
    if report.get("patch_sha256") != hashlib.sha256(data).hexdigest() or report.get("patch_bytes") != len(data):
        raise Refused("patch digest mismatch")
    problems = patchcheck.check(patch, env["ROLE"])
    if problems:
        raise Refused("; ".join(problems)[:500])
    return patch, report

def _git_env() -> dict:
    """The token travels in an environment-provided git config, never on a command line or in a URL."""
    env = {k: v for k, v in os.environ.items() if k != "GH_TOKEN"}
    token = os.environ.get("GH_TOKEN", "")
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraheader",
                    "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}"})
    env.update({"GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1], "GIT_COMMITTER_NAME": AUTHOR[0],
                "GIT_COMMITTER_EMAIL": AUTHOR[1], "GIT_TERMINAL_PROMPT": "0"})
    return env

def git(cwd: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                           "-c", "protocol.file.allow=always", *args], cwd=cwd, env=_git_env(), check=check,
                          capture_output=True, text=True, timeout=120)

def api(method: str, path: str, body: dict | None = None):
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request = urllib.request.Request(f"{base}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                                              "Accept": "application/vnd.github+json",
                                              "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as r:
        return json.loads(r.read() or b"null")

def publish(patch_path: str) -> dict:
    env = os.environ
    repo, default, branch, base, key = env["REPOSITORY"], env["DEFAULT_BRANCH"], env["BRANCH"], env["BASE"], env["KEY"]
    remote = env.get("REMOTE_URL", f"https://github.com/{repo}.git")
    with tempfile.TemporaryDirectory() as work:
        git(work, "init", "-q")
        git(work, "remote", "add", "origin", remote)
        git(work, "fetch", "-q", "--no-tags", "origin", f"+refs/heads/{default}:refs/remotes/origin/{default}")
        has_branch = git(work, "fetch", "-q", "--no-tags", "origin",
                         f"+refs/heads/{branch}:refs/remotes/origin/{branch}", check=False).returncode == 0
        lease = git(work, "rev-parse", f"refs/remotes/origin/{branch}").stdout.strip() if has_branch else ""
        # The agent started from the default branch or from this task's branch: nothing else.
        on_default = git(work, "merge-base", "--is-ancestor", base, f"refs/remotes/origin/{default}",
                         check=False).returncode == 0
        if not (on_default or (lease and base == lease)):
            raise Refused("base is neither on the default branch nor the task branch head")
        git(work, "checkout", "-q", "--detach", base)
        applied = git(work, "apply", "--index", "--whitespace=nowarn", os.path.abspath(patch_path), check=False)
        if applied.returncode != 0:
            raise Refused("patch does not apply")
        git(work, "commit", "-q", "-m", f"Dev Factory {key}", "-m", "Agent change, checked and published by "
            "the deterministic job. Draft: a human review is required.")
        head = git(work, "rev-parse", "HEAD").stdout.strip()
        pushed = git(work, "push", "-q", f"--force-with-lease=refs/heads/{branch}:{lease}", "origin",
                     f"HEAD:refs/heads/{branch}", check=False)
        if pushed.returncode != 0:
            raise Refused("push refused (branch moved or protected)")
    owner = repo.split("/", 1)[0]
    pulls = api("GET", f"/repos/{repo}/pulls?head={owner}:{branch}&state=open") or []
    line = f"- `{key}` → `{head[:12]}`"
    if pulls:
        number = pulls[0]["number"]
        body = (pulls[0].get("body") or MARKER)
        api("PATCH", f"/repos/{repo}/pulls/{number}", {"body": (body + "\n" + line)[-60000:]})
    else:
        number = api("POST", f"/repos/{repo}/pulls", {
            "title": f"[Dev Factory] {branch.split('/', 1)[1]}", "head": branch, "base": default, "draft": True,
            "body": f"{MARKER}\nProposition d'agent Artisana Dev Factory (données fictives). **Brouillon : revue "
                    f"humaine obligatoire, aucune fusion automatique.**\n\n{line}"})["number"]
    return {"branch": branch, "head": head, "pull_request": number}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        patch, _ = load(args.patch, args.report)
        if not patch.strip():
            print(json.dumps({"published": False, "reason": "verdict only, no change"}))
        elif not args.check_only:
            print(json.dumps(publish(args.patch)))
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except (urllib.error.URLError, subprocess.SubprocessError) as exc:
        print(f"publication failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
