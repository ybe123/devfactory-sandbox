#!/bin/bash
# Isolated agent user (agent job, trusted step, root). The agent gets a COPY of the work tree without .git (so no git
# configuration can be planted against the privileged runner), a private home, no sudo, no group, no login shell.
# Test tooling lives in a root-owned virtual environment the agent can use but not change.
set -euo pipefail
AGENT_USER=devfactory-agent
ROOT=/opt/devfactory
id "$AGENT_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/home/$AGENT_USER" \
  --shell /usr/sbin/nologin "$AGENT_USER"
if id -nG "$AGENT_USER" | grep -qwE 'sudo|admin|docker|adm'; then echo "refused: agent user has privileged groups" >&2; exit 2; fi
install -d -o root -g root -m 0755 "$ROOT"
if [ ! -x "$ROOT/venv/bin/python" ]; then
  python3 -m venv "$ROOT/venv"
  "$ROOT/venv/bin/pip" install -q --disable-pip-version-check pytest==9.1.1
fi
install -o root -g root -m 0644 "$(dirname "$0")/dryrun_agent.py" "$ROOT/dryrun_agent.py"
HOME_DIR="/home/$AGENT_USER"
chmod 0700 "$HOME_DIR"
rm -rf "$HOME_DIR/work" && install -d -o "$AGENT_USER" -g "$AGENT_USER" -m 0700 "$HOME_DIR/work"
git -C "${GITHUB_WORKSPACE:-.}/work" archive --format=tar HEAD | tar -x -C "$HOME_DIR/work"
chown -R "$AGENT_USER:$AGENT_USER" "$HOME_DIR/work"
install -d -o "$AGENT_USER" -g "$AGENT_USER" -m 0700 "$HOME_DIR/.anthropic" "$HOME_DIR/out"
# Runner temporary files (GITHUB_ENV, step outputs...) are not for the agent.
[ -n "${RUNNER_TEMP:-}" ] && chmod 0700 "$RUNNER_TEMP" || true
echo "agent user ready"
