#!/usr/bin/env bash
# Easiest HTTPS with no domain: Cloudflare Quick Tunnel (temporary public URL).
#
#   ./deploy/https/cloudflared-quick-tunnel.sh
#
# Prints a URL like https://random-words.trycloudflare.com — use that as the
# Twilio webhook base. No port 80/443 on the security group required (outbound
# HTTPS only).
#
# Downsides:
#   - The URL usually changes when you restart cloudflared (not ideal for prod).
#   - For production, prefer nip.io + Caddy (install-caddy-nip.sh) or a real domain.
#
# Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
#
set -euo pipefail

TARGET="${1:-http://127.0.0.1:8000}"

if ! command -v cloudflared &>/dev/null; then
  echo "cloudflared not found. Install:" >&2
  echo "  curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared" >&2
  echo "  chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/" >&2
  echo "(Use cloudflared-linux-arm64 on Graviton.)" >&2
  exit 1
fi

echo "Starting quick tunnel → ${TARGET}"
echo "Copy the https://….trycloudflare.com URL into Twilio:"
echo "  …/api/v1/webhooks/twilio/messages"
echo ""
exec cloudflared tunnel --url "${TARGET}"
