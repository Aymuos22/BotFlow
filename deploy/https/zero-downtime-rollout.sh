#!/usr/bin/env bash
# Zero-downtime API rollout when Caddy terminates TLS on the host (nip.io / real domain).
#
# Idea: start a second API container on 127.0.0.1:8001, switch Caddy to it, replace the
# old container on 8000, switch Caddy back, remove the temporary container.
# Caddy keeps listening on 443 the whole time (only reload).
#
# Usage (repo root on EC2, after normal docker compose has run at least once):
#   bash deploy/https/zero-downtime-rollout.sh
#
# Requires:
#   - /etc/caddy/Caddyfile with:  reverse_proxy 127.0.0.1:8000
#   - sudo for: systemctl reload caddy, sed on Caddyfile
#   - Same compose file / .env as usual (deploy/docker-compose.ec2.yml)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

CADDYFILE="/etc/caddy/Caddyfile"
COMPOSE_FILE="$ROOT/deploy/docker-compose.ec2.yml"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env in $ROOT" >&2
  exit 1
fi

if docker info &>/dev/null 2>&1; then
  DC="docker compose"
else
  DC="sudo -E docker compose"
fi

if [[ ! -f "$CADDYFILE" ]]; then
  echo "No $CADDYFILE — run deploy/https/install-caddy-nip.sh first (or install Caddy manually)." >&2
  exit 1
fi

if ! grep -q 'reverse_proxy 127.0.0.1:8000' "$CADDYFILE" 2>/dev/null; then
  echo "Caddyfile must contain exactly:  reverse_proxy 127.0.0.1:8000" >&2
  echo "Edit $CADDYFILE to use that form (no host:port variants) for this script." >&2
  exit 1
fi

if command -v ss &>/dev/null && ss -tln 2>/dev/null | grep -qE ':8001\s'; then
  echo "Port 8001 is already in use — finish or remove the previous rollout container." >&2
  exit 1
fi

ROLL_NAME="api_rollout_$$"

cleanup_rollout() {
  $DOCKER rm -f "$ROLL_NAME" 2>/dev/null || true
}

trap 'cleanup_rollout' EXIT

echo "==> Building API image..."
export DOCKER_BUILDKIT=1
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build api

echo "==> Starting temporary API on 127.0.0.1:8001 ($ROLL_NAME)..."
# Same image & network as stack; no-deps so we don't restart unrelated services.
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run -d \
  --name "$ROLL_NAME" \
  --no-deps \
  -p 127.0.0.1:8001:8000 \
  api

echo "==> Waiting for health on :8001..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8001/health" &>/dev/null; then
    echo "    OK"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "Temporary API never became healthy. Check: docker logs $ROLL_NAME" >&2
    exit 1
  fi
  sleep 2
done

BACKUP="$(mktemp)"
sudo cp "$CADDYFILE" "$BACKUP"

rollback_caddy() {
  sudo cp "$BACKUP" "$CADDYFILE"
  sudo systemctl reload caddy || true
}

echo "==> Pointing Caddy at 127.0.0.1:8001..."
sudo sed -i 's/reverse_proxy 127.0.0.1:8000/reverse_proxy 127.0.0.1:8001/' "$CADDYFILE"
if ! sudo systemctl reload caddy; then
  echo "Caddy reload failed; restoring Caddyfile." >&2
  rollback_caddy
  exit 1
fi

sleep 2

echo "==> Replacing primary API container on :8000..."
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop api || true
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" rm -f api || true
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps api

echo "==> Waiting for health on :8000..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" &>/dev/null; then
    echo "    OK"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "Primary API unhealthy — Caddy still on 8001; fix manually. Backup Caddyfile: $BACKUP" >&2
    exit 1
  fi
  sleep 2
done

echo "==> Pointing Caddy back at 127.0.0.1:8000..."
sudo sed -i 's/reverse_proxy 127.0.0.1:8001/reverse_proxy 127.0.0.1:8000/' "$CADDYFILE"
sudo systemctl reload caddy

cleanup_rollout
trap - EXIT

echo "==> Running DB migrations..."
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
  python data/scripts/migrate.py \
  && echo "    DB migration: OK" \
  || echo "    DB migration: WARNING — check logs above"

echo "==> Done. HTTPS endpoint unchanged; Caddy did not stop."
echo "    Health: curl -fsS http://127.0.0.1:8000/health"
