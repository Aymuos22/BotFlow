#!/usr/bin/env bash
# Install Caddy on EC2 and enable HTTPS (Let's Encrypt) for the Twilio webhook.
#
# Usage (on the server, as root):
#   sudo DOMAIN=api.example.com bash deploy/https/install-caddy.sh
#
# Requires:
#   - DNS A record for DOMAIN already pointing at this instance's public IP
#   - Ports 80 and 443 open in the security group
#   - FastAPI listening on 127.0.0.1:8000 (docker compose API container)
#
set -euo pipefail

DOMAIN="${DOMAIN:-}"
if [[ -z "${DOMAIN}" ]]; then
  echo "Set DOMAIN, e.g.  sudo DOMAIN=api.example.com $0" >&2
  exit 1
fi

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

install_caddy_apt() {
  apt-get update -y
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
}

install_caddy_dnf() {
  dnf install -y 'dnf-command(copr)'
  dnf copr enable -y @caddy/caddy epel-9-$(arch) 2>/dev/null || dnf copr enable -y @caddy/caddy epel-9-"$(arch)"
  dnf install -y caddy
}

if command -v apt-get &>/dev/null; then
  install_caddy_apt
elif command -v dnf &>/dev/null; then
  install_caddy_dnf
else
  echo "Install Caddy manually: https://caddyserver.com/docs/install" >&2
  exit 1
fi

cat >/etc/caddy/Caddyfile <<EOF
${DOMAIN} {
	reverse_proxy 127.0.0.1:8000
}
EOF

systemctl enable --now caddy
systemctl reload caddy || systemctl restart caddy

echo "HTTPS should be available at https://${DOMAIN}/health"
echo "Twilio webhook: https://${DOMAIN}/api/v1/webhooks/twilio/messages"
