#!/bin/bash
# Run the tests of the result as the isolated user, under the network lock (agent job, root wrapper). The JUnit file
# is data for the trusted report; nothing written by the agent is executed by the runner user.
set -uo pipefail
AGENT_USER=devfactory-agent
HOME_DIR="/home/$AGENT_USER"
cd "$HOME_DIR/work"
sudo -u "$AGENT_USER" -H env -i PATH=/opt/devfactory/venv/bin:/usr/bin:/bin HOME="$HOME_DIR" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  timeout 200 python3 -m pytest -q -p no:cacheprovider --junitxml="$HOME_DIR/out/junit.xml" >/dev/null 2>&1
exit 0   # the result is in the JUnit file; a failing test is a verdict, not a job failure
