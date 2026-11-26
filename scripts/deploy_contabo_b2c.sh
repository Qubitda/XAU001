#!/usr/bin/env bash
set -euo pipefail

IP="169.58.5.103"
REPO_DIR="/opt/xau001"
WWW_ROOT="/var/www/taragold"

mkdir -p "$REPO_DIR" "$WWW_ROOT"/{storefront,b2b,ops,corporate}

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone https://github.com/Qubitda/XAU001.git "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin
  git -C "$REPO_DIR" reset --hard origin/main
fi

cd "$REPO_DIR"

# Persist generated secrets across redeploys
SECRETS_FILE="/root/.taragold_secrets"
if [[ ! -f "$SECRETS_FILE" ]]; then
  umask 077
  cat > "$SECRETS_FILE" <<EOF
DJANGO_SECRET_KEY=$(openssl rand -hex 48)
API_KEY_HASH_PEPPER=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SEED_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
MAIL_ENCRYPTION_KEY=$(openssl rand -hex 32)
EOF
fi
# shellcheck disable=SC1090
source "$SECRETS_FILE"

ORIGIN_80="http://${IP}"
ORIGIN_3000="http://${IP}:3000"
ORIGIN_3001="http://${IP}:3001"
ORIGIN_3002="http://${IP}:3002"
ORIGIN_3003="http://${IP}:3003"
API_ORIGIN="http://${IP}:8000"

umask 077
cat > "$REPO_DIR/.env" <<EOF
VITE_API_BASE_URL=${API_ORIGIN}
VITE_ENABLE_DEMO_MODE=false
VITE_STOREFRONT_URL=${ORIGIN_80}/
VITE_B2B_URL=${ORIGIN_3001}/b2b/giris
VITE_OPS_URL=${ORIGIN_3002}/ops/giris
VITE_ENABLE_B2C_STOREFRONT=true
VITE_ENABLE_B2B_PORTAL=true
VITE_ENABLE_OPS_PORTAL=true
VITE_ENABLE_IYZICO_PAYMENTS=true
VITE_ENABLED_SALES_CHANNELS=B2B,B2B_API,B2C_API

DJANGO_DEBUG=0
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
API_KEY_HASH_PEPPER=${API_KEY_HASH_PEPPER}
DJANGO_SECURE_COOKIES=0
DJANGO_ALLOWED_HOSTS=${IP},localhost,127.0.0.1
DJANGO_SESSION_COOKIE_AGE=43200
CORS_ALLOWED_ORIGINS=${ORIGIN_80},${ORIGIN_3000},${ORIGIN_3001},${ORIGIN_3002},${ORIGIN_3003}
CSRF_TRUSTED_ORIGINS=${ORIGIN_80},${ORIGIN_3000},${ORIGIN_3001},${ORIGIN_3002},${ORIGIN_3003}

DRF_THROTTLE_ANON=60/min
DRF_THROTTLE_USER=300/min
DRF_THROTTLE_LOGIN=10/min
DRF_THROTTLE_API_KEY=120/min
NUM_PROXIES=1

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=taragold
POSTGRES_USER=taragold
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgresql://taragold:${POSTGRES_PASSWORD}@db:5432/taragold

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

SEED_ADMIN_PASSWORD=${SEED_ADMIN_PASSWORD}
ENABLE_B2C_SELF_REGISTER=1
ENFORCE_EMAIL_VERIFICATION=0
FRONTEND_STOREFRONT_URL=${ORIGIN_80}

ENABLE_IYZICO_PAYMENTS=1
IYZICO_API_KEY=
IYZICO_SECRET_KEY=
IYZICO_BASE_URL=sandbox-api.iyzipay.com
IYZICO_CALLBACK_BASE_URL=${API_ORIGIN}

DEFAULT_FROM_EMAIL=noreply@taragold.local
EMAIL_HOST=localhost
EMAIL_PORT=587
EMAIL_USE_TLS=1
MAIL_ENCRYPTION_KEY=${MAIL_ENCRYPTION_KEY}

DOCUMENT_HARD_DELETE_DAYS=0
LOG_LEVEL=INFO
EOF

echo "=== Docker compose up ==="
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d --build

echo "=== npm install + build ==="
npm ci --prefer-offline || npm install
npm run build

rsync -a --delete apps/frontend/storefront/dist/ "$WWW_ROOT/storefront/"
rsync -a --delete apps/frontend/b2b/dist/ "$WWW_ROOT/b2b/"
rsync -a --delete apps/frontend/ops/dist/ "$WWW_ROOT/ops/"
rsync -a --delete apps/frontend/corporate/dist/ "$WWW_ROOT/corporate/"
chmod -R a+rX "$WWW_ROOT"

# SPA helper included in each site
write_site() {
  local name="$1" port="$2" root="$3"
  cat > "/etc/nginx/sites-available/taragold-${name}" <<NGX
server {
    listen ${port};
    listen [::]:${port};
    server_name _;
    root ${root};
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }
    location /media/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGX
  ln -sfn "/etc/nginx/sites-available/taragold-${name}" "/etc/nginx/sites-enabled/taragold-${name}"
}

rm -f /etc/nginx/sites-enabled/default
write_site storefront 80 "$WWW_ROOT/storefront"
write_site storefront-alt 3000 "$WWW_ROOT/storefront"
write_site b2b 3001 "$WWW_ROOT/b2b"
write_site ops 3002 "$WWW_ROOT/ops"
write_site corporate 3003 "$WWW_ROOT/corporate"

nginx -t
systemctl reload nginx

echo "=== Waiting for API health ==="
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "API healthy"
    break
  fi
  sleep 5
  if [[ "$i" -eq 60 ]]; then
    echo "API health timeout"
    docker compose --env-file .env -f infrastructure/docker-compose.yml ps
    docker compose --env-file .env -f infrastructure/docker-compose.yml logs --tail=80 web || true
    exit 1
  fi
done

curl -fsS "http://127.0.0.1:8000/health?deep=1" || true
echo
curl -fsSI "http://127.0.0.1/" | head -5 || true
docker compose --env-file .env -f infrastructure/docker-compose.yml ps

echo
echo "=== DEPLOY_OK ==="
echo "Storefront: ${ORIGIN_80}/"
echo "B2B:        ${ORIGIN_3001}/b2b/giris"
echo "OPS:        ${ORIGIN_3002}/ops/giris"
echo "Corporate:  ${ORIGIN_3003}/"
echo "API:        ${API_ORIGIN}/api/v1/"
echo "Admin seed password is in ${SECRETS_FILE} (SEED_ADMIN_PASSWORD)"
grep '^SEED_ADMIN_PASSWORD=' "$SECRETS_FILE"
