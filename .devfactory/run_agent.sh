#!/bin/bash
# Run the agent as the isolated user (agent job, root wrapper). Only listed variables reach it (env -i): no GitHub
# token, no OIDC request token, no runner variable. DRY_RUN=true runs the deterministic script (no AI).
set -euo pipefail
AGENT_USER=devfactory-agent
HOME_DIR="/home/$AGENT_USER"
cd "$HOME_DIR/work"
common=(PATH=/opt/devfactory/venv/bin:/usr/bin:/bin HOME="$HOME_DIR" LANG=C.UTF-8)
if [ "${DRY_RUN:-false}" = true ]; then
  exec sudo -u "$AGENT_USER" -H env -i "${common[@]}" ROLE="$ROLE" timeout 120 \
    python3 /opt/devfactory/dryrun_agent.py
fi
python3 "$(dirname "$0")/prompt.py" > /opt/devfactory/prompt.txt   # trusted: role rules + ticket (data)
chmod 0644 /opt/devfactory/prompt.txt
sudo -u "$AGENT_USER" -H env -i "${common[@]}" \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1 DISABLE_AUTOUPDATER=1 \
  ANTHROPIC_FEDERATION_RULE_ID="$ANTHROPIC_FEDERATION_RULE_ID" ANTHROPIC_ORGANIZATION_ID="$ANTHROPIC_ORGANIZATION_ID" \
  ANTHROPIC_IDENTITY_TOKEN_FILE="$HOME_DIR/.anthropic/id_token" \
  timeout 840 /opt/devfactory/claude -p "$(cat /opt/devfactory/prompt.txt)" --model claude-sonnet-5-5 \
  --max-turns "$MAX_TURNS" --allowedTools "Read,Edit,Write,Glob,Grep,Bash(python3 -m pytest:*)" \
  --output-format json > "$HOME_DIR/out/execution.json"
