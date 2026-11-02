#!/bin/bash
# Stop every agent process, then bring the agent's REGULAR files back into the pristine work tree (runner user's git,
# never the agent's) and freeze the patch (agent job, root wrapper). Data files go to RUNNER_TEMP, size-bounded.
set -euo pipefail
AGENT_USER=devfactory-agent
HOME_DIR="/home/$AGENT_USER"
WORK="${GITHUB_WORKSPACE:-$PWD}/work"
alive() { ps -u "$AGENT_USER" -o stat= 2>/dev/null | grep -qv '^Z'; }   # zombies run nothing
pkill -KILL -u "$AGENT_USER" || true
for _ in 1 2 3 4 5; do alive || break; sleep 1; done
alive && { echo "refused: agent processes still running" >&2; exit 2; }
python3 "$(dirname "$0")/copy_back.py" "$HOME_DIR/work" "$WORK"
RUNNER_USER=$(stat -c %U "$WORK")
chown -R "$RUNNER_USER" "$WORK"
for f in execution.json junit.xml; do
  src="$HOME_DIR/out/$f"
  if [ -f "$src" ] && [ ! -L "$src" ] && [ "$(stat -c %s "$src")" -le 2000000 ]; then
    install -o "$RUNNER_USER" -m 0600 "$src" "$RUNNER_TEMP/$f"
  fi
done
v="$HOME_DIR/work/.devfactory-verdicts.json"
if [ -f "$v" ] && [ ! -L "$v" ] && [ "$(stat -c %s "$v")" -le 100000 ]; then install -o "$RUNNER_USER" -m 0600 "$v" "$RUNNER_TEMP/verdicts.json"; fi
sudo -u "$RUNNER_USER" git -C "$WORK" -c core.hooksPath=/dev/null add -A -- . ':!.devfactory-verdicts.json'
sudo -u "$RUNNER_USER" git -C "$WORK" -c core.hooksPath=/dev/null diff --cached --binary "$BASE" > "$RUNNER_TEMP/patch.diff"
chown "$RUNNER_USER" "$RUNNER_TEMP/patch.diff"
echo "patch frozen: $(wc -c < "$RUNNER_TEMP/patch.diff") bytes"
