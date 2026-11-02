"""GitHub OIDC token for the Anthropic workload identity federation (agent job, trusted step, runner user).

The runner user asks GitHub for a short-lived OIDC token (audience from the repository variable
ANTHROPIC_OIDC_AUDIENCE) and hands it to the agent user as a 0400 file. The agent user never receives the
ACTIONS_ID_TOKEN_REQUEST_* values, so it cannot ask for another token. The token is never printed.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

TARGET = "/home/devfactory-agent/.anthropic/id_token"


def main() -> int:
    url, bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"), os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    audience = os.environ.get("ANTHROPIC_OIDC_AUDIENCE", "")
    if not (url and bearer and audience):
        print("refused: OIDC not available (id-token permission, audience variable)", file=sys.stderr)
        return 2
    request = urllib.request.Request(f"{url}&audience={urllib.parse.quote(audience)}",
                                     headers={"Authorization": f"Bearer {bearer}"})
    token = json.loads(urllib.request.urlopen(request, timeout=30).read())["value"]
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(token)
    try:
        subprocess.run(["sudo", "install", "-o", "devfactory-agent", "-g", "devfactory-agent", "-m", "0400", f.name,
                        TARGET], check=True)
    finally:
        os.unlink(f.name)
    print("identity token handed to the agent user")
    return 0


if __name__ == "__main__":
    sys.exit(main())
