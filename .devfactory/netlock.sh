#!/bin/bash
# Network lock of the agent user (agent job, trusted step, root).
#
#   netlock.sh apply    resolve the API host (as root, before the lock), REFUSE any address outside the published
#                       Anthropic ranges, pin it in /etc/hosts, then allow the agent user (iptables owner match) ONLY
#                       those addresses on 443, IPv4 and IPv6. Everything else from that user is rejected, loopback
#                       INCLUDED: the local DNS stub (127.0.0.53 on GitHub runners) would otherwise forward the agent's
#                       queries upstream (DNS exfiltration). Other users (the runner, GitHub services) are not affected.
#   netlock.sh canary   prove it: the agent user reaches the API host, and does NOT reach another host, resolve a
#                       name or reach GitHub; the runner user still reaches GitHub. Any failure stops the job.
#
# Ranges: https://platform.claude.com/docs/en/api/ip-addresses (read 30/10/2026). The resolved addresses are
# checked against them at every run, so a change on Anthropic's side fails closed instead of opening the network.
# NETLOCK_* overrides exist for the local rehearsal only (docs/devfactory/P1_SANDBOX.md).
set -euo pipefail
AGENT_USER=devfactory-agent
HOST=${NETLOCK_HOST:-api.anthropic.com}
PORT=${NETLOCK_PORT:-443}
RANGES=${NETLOCK_RANGES:-"160.79.104.0/23 2607:6bc0::/48"}
OUTSIDE_HOST=${NETLOCK_OUTSIDE_HOST:-api.github.com}
OUTSIDE_IP=${NETLOCK_OUTSIDE_IP:-1.1.1.1}
STATE=/opt/devfactory/netlock.addresses

in_ranges() {  # $1 = address
  python3 - "$1" "$RANGES" <<'PY'
import ipaddress, sys
ip = ipaddress.ip_address(sys.argv[1])
sys.exit(0 if any(ip in ipaddress.ip_network(r) for r in sys.argv[2].split()) else 1)
PY
}

as_agent() { sudo -u "$AGENT_USER" -H env -i PATH=/usr/bin:/bin HOME="/home/$AGENT_USER" "$@"; }

connects() {  # $1 = host or address, run as the agent user
  as_agent python3 -c "import socket,sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5)" "$1" "$PORT" \
    >/dev/null 2>&1
}

apply() {
  local uid addresses=() a
  uid=$(id -u "$AGENT_USER")
  mapfile -t addresses < <(getent ahosts "$HOST" | awk '{print $1}' | sort -u)
  [ "${#addresses[@]}" -gt 0 ] || { echo "refused: $HOST does not resolve" >&2; exit 2; }
  for a in "${addresses[@]}"; do
    in_ranges "$a" || { echo "refused: $HOST resolves to $a, outside the published ranges" >&2; exit 2; }
  done
  printf '%s\n' "${addresses[@]}" > "$STATE"
  # Rewritten in place (no rename): /etc/hosts may be a mount point.
  { grep -vE "[[:space:]]$HOST\$" /etc/hosts || true; for a in "${addresses[@]}"; do echo "$a $HOST"; done; } > /tmp/hosts.devfactory
  cat /tmp/hosts.devfactory > /etc/hosts && rm -f /tmp/hosts.devfactory
  for cmd in iptables ip6tables; do
    "$cmd" -N DEVFACTORY_AGENT 2>/dev/null || "$cmd" -F DEVFACTORY_AGENT
    "$cmd" -C OUTPUT -m owner --uid-owner "$uid" -j DEVFACTORY_AGENT 2>/dev/null || \
      "$cmd" -I OUTPUT 1 -m owner --uid-owner "$uid" -j DEVFACTORY_AGENT
  done
  for a in "${addresses[@]}"; do
    if [[ "$a" == *:* ]]; then cmd=ip6tables; else cmd=iptables; fi
    "$cmd" -A DEVFACTORY_AGENT -d "$a" -p tcp --dport "$PORT" -j ACCEPT
  done
  iptables -A DEVFACTORY_AGENT -j REJECT
  ip6tables -A DEVFACTORY_AGENT -j REJECT
  echo "network lock applied: $AGENT_USER -> $HOST:$PORT (${#addresses[@]} address(es)), nothing else"
}

canary() {
  local failed=0
  connects "$HOST" || { echo "canary: the agent user cannot reach $HOST:$PORT" >&2; failed=1; }
  if connects "$OUTSIDE_IP"; then echo "canary: the agent user reaches $OUTSIDE_IP" >&2; failed=1; fi
  if as_agent getent hosts example.com >/dev/null 2>&1; then echo "canary: the agent user resolves names" >&2; failed=1; fi
  if connects "$OUTSIDE_HOST"; then echo "canary: the agent user reaches $OUTSIDE_HOST" >&2; failed=1; fi
  if as_agent sudo -n true >/dev/null 2>&1; then echo "canary: the agent user has sudo" >&2; failed=1; fi
  python3 -c "import socket,sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5)" \
    "$OUTSIDE_HOST" "$PORT" >/dev/null 2>&1 || { echo "canary: the runner itself lost the network" >&2; failed=1; }
  [ "$failed" = 0 ] || exit 3
  echo "canaries passed: API reachable; other hosts, DNS and sudo refused to the agent user; runner unaffected"
}

case "${1:-}" in
  apply) apply ;;
  canary) canary ;;
  *) echo "usage: netlock.sh apply|canary" >&2; exit 64 ;;
esac
