#!/usr/bin/env bash
# HTTPS without buying a domain: use nip.io (free DNS that encodes your public IP).
#
# Example for EC2 at 54.252.233.98 → hostname 54.252.233.98.nip.io
# Let's Encrypt + Caddy can obtain a certificate for that hostname because
# nip.io resolves to your IP and you control the server at that IP.
#
# Usage (on the server, as root):
#   sudo PUBLIC_IP=54.252.233.98 bash deploy/https/install-caddy-nip.sh
#
# Requires:
#   - PUBLIC_IP is this instance's *public* IPv4 (curl -s ifconfig.me)
#   - Security group: TCP 80 and 443 open to the world (for ACME + HTTPS)
#   - API on 127.0.0.1:8000 (docker compose with 127.0.0.1:8000:8000)
#
# Tip: In AWS, allocate an Elastic IP and attach it so your IP (and nip URL)
# does not change when you stop/start the instance.
#
set -euo pipefail

PUBLIC_IP="${PUBLIC_IP:-}"
if [[ -z "${PUBLIC_IP}" ]]; then
  echo "Set PUBLIC_IP to this server's public IPv4, e.g." >&2
  echo "  sudo PUBLIC_IP=\$(curl -s ifconfig.me) bash $0" >&2
  exit 1
fi

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

DOMAIN="${PUBLIC_IP}.nip.io"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="${DOMAIN}" bash "${SCRIPT_DIR}/install-caddy.sh"

echo ""
echo "nip.io hostname: ${DOMAIN}"
echo "Twilio webhook:  https://${DOMAIN}/api/v1/webhooks/twilio/messages"
echo ""
echo "Redeploy without dropping HTTPS: set ZERO_DOWNTIME=1 when running scripts/deploy-remote.sh"
echo "  (see deploy/https/zero-downtime-rollout.sh — requires this Caddyfile line: reverse_proxy 127.0.0.1:8000)"
