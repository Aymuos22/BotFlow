#!/usr/bin/env bash
# Push local env files to EC2 (run from repo root on your machine).
# - web/.env → frontend: ~/wa-dashboard.env (NOT under nginx root — not served)
# - .env      → backend:  /opt/chatbot-engine/.env (CRLF stripped, API restarted)
#
# Usage:
#   export FRONTEND_HOST=52.65.65.205
#   export BACKEND_HOST=54.252.233.98
#   export SSH_KEY=secrets/sec-key.pem
#   bash scripts/push_env_to_ec2.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${SSH_KEY:-$ROOT/secrets/sec-key.pem}"
FRONT="${FRONTEND_HOST:-52.65.65.205}"
BACK="${BACKEND_HOST:-54.252.233.98}"
USER="${EC2_USER:-ubuntu}"
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new)
SCP=(scp -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new)

test -f "$KEY" || { echo "Missing key: $KEY"; exit 1; }
test -f "$ROOT/web/.env" || { echo "Missing $ROOT/web/.env"; exit 1; }
test -f "$ROOT/.env" || { echo "Missing $ROOT/.env"; exit 1; }

echo "[push] web/.env -> ${USER}@${FRONT}:~/wa-dashboard.env"
"${SCP[@]}" "$ROOT/web/.env" "${USER}@${FRONT}:wa-dashboard.env"
"${SSH[@]}" "${USER}@${FRONT}" "chmod 600 ~/wa-dashboard.env && wc -l ~/wa-dashboard.env | awk '{print \"web env lines:\", \$1}'"

echo "[push] .env -> ${USER}@${BACK}:/opt/chatbot-engine/.env"
"${SCP[@]}" "$ROOT/.env" "${USER}@${BACK}:/tmp/mindorax-api.env"
"${SCP[@]}" "$ROOT/scripts/normalize_api_env.py" "${USER}@${BACK}:/tmp/normalize_api_env.py"
"${SSH[@]}" "${USER}@${BACK}" 'set -e
  python3 /tmp/normalize_api_env.py /tmp/mindorax-api.env
  rm -f /tmp/normalize_api_env.py
  grep -q "^DATABASE_URL=" /tmp/mindorax-api.env || { echo "missing DATABASE_URL"; exit 1; }
  grep -q "^SUPABASE_JWT_SECRET=" /tmp/mindorax-api.env || { echo "missing SUPABASE_JWT_SECRET"; exit 1; }
  cp /opt/chatbot-engine/.env "/opt/chatbot-engine/.env.bak-push-$(date -u +%Y%m%d%H%M%S)" 2>/dev/null || true
  sudo install -m 0600 -o ubuntu -g ubuntu /tmp/mindorax-api.env /opt/chatbot-engine/.env
  rm -f /tmp/mindorax-api.env
  cd /opt/chatbot-engine && docker compose -f deploy/docker-compose.ec2.yml up -d --force-recreate
  echo "backend API recreated"'
echo "[push] done. Rebuild & rsync the SPA for Vite vars (or set GitHub Actions secrets); ~/wa-dashboard.env on frontend is for ops reference only."
