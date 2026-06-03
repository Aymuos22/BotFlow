#!/usr/bin/env bash
# Run on the frontend EC2 (Ubuntu) after the GitHub Action has rsync'd dist/ to DEPLOY_PATH.
# Usage: sudo bash install-frontend-nginx.sh [path-to-wa-dashboard.nginx.conf]
set -euo pipefail

CONF_SRC="${1:-$(dirname "$0")/wa-dashboard.nginx.conf}"
DEST="/etc/nginx/sites-available/wa-dashboard"

if [[ ! -f "$CONF_SRC" ]]; then
  echo "Config not found: $CONF_SRC" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx

install -m 0644 "$CONF_SRC" "$DEST"
ln -sf "$DEST" /etc/nginx/sites-enabled/wa-dashboard
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl restart nginx
echo "nginx is running. Test: curl -sI http://127.0.0.1/"
