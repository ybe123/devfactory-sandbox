"""Install the pinned Claude Code CLI (agent job, trusted step, root). Standard library only.

Downloads ONE native tarball, checks its sha512 against the value pinned here (npm registry integrity, read
30/10/2026), and extracts ONLY `package/claude` to /opt/devfactory/claude (root-owned, not writable by the agent).
No package manager and no install script run.
"""
import base64
import hashlib
import io
import os
import sys
import tarfile
import urllib.request

VERSION = "2.1.301"   # published 15/10/2026 (>= 2 weeks before pinning)
URL = f"https://registry.npmjs.org/@anthropic-ai/claude-code-linux-x64/-/claude-code-linux-x64-{VERSION}.tgz"
SHA512 = "sha512-JNe0VzIuXdaBrtlh+fY2SX5AQLDf8BDfIKrylOWK528AZ/aAq2bJt4SBkPikZ0CvecUbL0YN22Xe7eltAWCJGg=="
TARGET = "/opt/devfactory/claude"


def main() -> int:
    data = urllib.request.urlopen(URL, timeout=120).read()
    digest = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if digest != SHA512:
        print("refused: Claude Code tarball digest mismatch", file=sys.stderr)
        return 2
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = tar.getmember("package/claude")
        if not member.isfile():
            print("refused: unexpected tarball content", file=sys.stderr)
            return 2
        binary = tar.extractfile(member).read()
    os.makedirs(os.path.dirname(TARGET), mode=0o755, exist_ok=True)
    with open(TARGET, "wb") as f:
        f.write(binary)
    os.chmod(TARGET, 0o755)
    os.chown(TARGET, 0, 0)
    print(f"Claude Code {VERSION} installed ({digest[:20]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
