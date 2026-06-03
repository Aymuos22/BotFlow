#!/usr/bin/env bash
# Run on EC2 at /opt/chatbot-engine after scp'ing a tarball to /tmp/chatbot-engine-sync.tgz
set -euo pipefail
cd /opt/chatbot-engine
test -f /tmp/chatbot-engine-sync.tgz
tar -xzf /tmp/chatbot-engine-sync.tgz
rm -f /tmp/chatbot-engine-sync.tgz

if docker info &>/dev/null 2>&1; then
  DC="docker compose"
else
  DC="sudo -E docker compose"
fi
COMPOSE_FILE="/opt/chatbot-engine/deploy/docker-compose.ec2.yml"
ENV_FILE="/opt/chatbot-engine/.env"
export DOCKER_BUILDKIT=1
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build api whatsapp-worker migrate
# Weaviate Cloud only — no local weaviate service (see deploy/docker-compose.ec2.yml).
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d api whatsapp-worker
echo "Waiting for API..."
for i in $(seq 1 15); do
  if $DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    &>/dev/null 2>&1; then
    echo "API is ready."
    break
  fi
  echo "  attempt $i/15"
  sleep 3
done
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api alembic upgrade head
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api python data/scripts/migrate.py || true
$DC -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
