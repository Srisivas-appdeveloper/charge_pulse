#!/usr/bin/env bash
# Production deploy to a Hetzner CPX31 (Ubuntu 24.04).
# Run on the server, in /opt/chargepulse, with .env.prod populated.

set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

require_env() {
    local var=$1
    if [ -z "${!var:-}" ]; then
        echo "FATAL: $var is required (set in .env.prod)" >&2; exit 1
    fi
}

if [ ! -f .env.prod ]; then
    echo "FATAL: .env.prod missing. Copy .env.example and fill in production secrets." >&2
    exit 1
fi
set -a; source .env.prod; set +a
for v in POSTGRES_PASSWORD JWT_SECRET_KEY; do require_env "$v"; done

# 1. Pull latest
if [ -d .git ]; then git pull --ff-only; fi

# 2. Build + migrate + restart
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --remove-orphans
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 'db reachable' AS ok;"

# 3. SSL bootstrap (idempotent) — uses certbot from the host
if [ ! -d ./nginx/ssl/live ]; then
    echo "[bootstrap] no SSL certs found — issuing via certbot"
    sudo apt-get update -y && sudo apt-get install -y certbot
    for d in chargepulse.in www.chargepulse.in app.chargepulse.in api.chargepulse.in csms.chargepulse.in; do
        sudo certbot certonly --webroot -w /var/www/certbot -d "$d" --non-interactive --agree-tos -m "${LETSENCRYPT_EMAIL:-admin@chargepulse.in}"
    done
    sudo cp -r /etc/letsencrypt ./nginx/ssl
    docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx
fi

echo "OK. Status:"
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
