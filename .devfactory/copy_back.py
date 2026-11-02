"""Copy the agent's regular files back into the pristine work tree (agent job, trusted step, root). Standard library.

Only regular files with safe relative paths are copied: no symlink, no device, no .git, nothing outside the tree,
bounded count and size. Deletions are not carried over (the patch check refuses them anyway).
"""
import os
import re
import shutil
import sys

SAFE = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]*$")
MAX_FILES, MAX_BYTES = 500, 5_000_000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}   # repository metadata and caches are never carried back


def main(source: str, target: str) -> int:
    copied, total = 0, 0
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(root, d))]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, source)
            if os.path.islink(path) or not os.path.isfile(path) or not SAFE.match(rel) or ".." in rel.split("/"):
                continue
            size = os.path.getsize(path)
            copied, total = copied + 1, total + size
            if copied > MAX_FILES or total > MAX_BYTES:
                print("refused: too many files or bytes", file=sys.stderr)
                return 2
            dest = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.islink(dest):
                os.unlink(dest)
            shutil.copyfile(path, dest, follow_symlinks=False)
    print(f"{copied} file(s) copied back")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
