#!/usr/bin/env bash
# Run on the EC2 instance (or via CI over SSH) from the repository root.
# Usage: bash scripts/deploy-remote.sh [git_ref]
#
# Optional: ZERO_DOWNTIME=1 — use blue-green API swap (Caddy nip.io / HTTPS stays up).
# Requires /etc/caddy/Caddyfile with:  reverse_proxy 127.0.0.1:8000
# See: deploy/https/zero-downtime-rollout.sh
set -euo pipefail

REF="${1:-HEAD}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -d .git ]]; then
  export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o StrictHostKeyChecking=accept-new}"
  git remote prune origin 2>/dev/null || true
  git fetch origin --prune

  if git rev-parse --verify --quiet "$REF" >/dev/null; then
    git checkout -f "$REF"
  elif git rev-parse --verify --quiet "origin/$REF" >/dev/null; then
    git checkout -f -B "$REF" "origin/$REF"
  else
    echo "Unknown git ref: $REF" >&2
    exit 1
  fi

  if git symbolic-ref -q HEAD >/dev/null; then
    git pull --ff-only origin "$(git rev-parse --abbrev-ref HEAD)" 2>/dev/null || true
  fi
fi

ENV_FILE="$ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env in $ROOT" >&2
  exit 1
fi

COMPOSE_FILE="$ROOT/deploy/docker-compose.ec2.yml"
export DOCKER_BUILDKIT=1

# Use sudo if the current user cannot reach the Docker socket directly
if docker info &>/dev/null 2>&1; then
  DC="docker compose"
else
  DC="sudo -E docker compose"
fi

if [[ "${ZERO_DOWNTIME:-}" == "1" ]] && [[ -f "/etc/caddy/Caddyfile" ]] \
  && grep -q 'reverse_proxy 127.0.0.1:8000' /etc/caddy/Caddyfile 2>/dev/null; then
  echo "ZERO_DOWNTIME=1 — running deploy/https/zero-downtime-rollout.sh"
  bash "$ROOT/deploy/https/zero-downtime-rollout.sh"
  exit $?
fi

# Build and restart only the API — Caddy (on the host) and other services stay up.
# First-time deploy: no api container yet → bring the stack up.
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build api
if [[ -z "$($DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q api 2>/dev/null)" ]]; then
  echo "First deploy: starting stack (API)..."
  $DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans
else
  echo "Rolling API only (Caddy on host untouched)..."
  $DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps api
fi
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

# ── Run DB migrations ────────────────────────────────────────────────────────
# Wait briefly for the API container to reach healthy state before migrating.
echo "Waiting for API to be ready..."
for i in $(seq 1 15); do
  if $DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
       python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
       &>/dev/null 2>&1; then
    echo "API is ready."
    break
  fi
  echo "  attempt $i/15 — waiting 3s..."
  sleep 3
done

echo "Running Alembic schema migrations..."
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
  alembic upgrade head \
  && echo "Alembic migration: OK" \
  || echo "Alembic migration: WARNING — check logs above"

echo "Running data-defaults migration..."
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
  python data/scripts/migrate.py \
  && echo "Data migration: OK" \
  || echo "Data migration: WARNING — check logs above"

echo "Health: curl -sS http://127.0.0.1:8000/health"
