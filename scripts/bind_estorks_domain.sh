#!/usr/bin/env bash
set -euo pipefail

IP="169.58.5.103"
DOMAIN="estorks.com"
REPO_DIR="/opt/xau001"
WWW_ROOT="/var/www/taragold"
SECRETS_FILE="/root/.taragold_secrets"

echo "=== DNS check ==="
for h in "$DOMAIN" "www.$DOMAIN" "ops.$DOMAIN" "b2b.$DOMAIN" "corporate.$DOMAIN"; do
  printf '%s -> ' "$h"
  dig +short "$h" A | paste -sd' ' -
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null
apt-get install -y certbot python3-certbot-nginx dig >/dev/null 2>&1 || apt-get install -y certbot python3-certbot-nginx dnsutils >/dev/null

# shellcheck disable=SC1090
source "$SECRETS_FILE"

ORIGIN_ROOT="https://${DOMAIN}"
ORIGIN_WWW="https://www.${DOMAIN}"
ORIGIN_OPS="https://ops.${DOMAIN}"
ORIGIN_B2B="https://b2b.${DOMAIN}"
ORIGIN_CORP="https://corporate.${DOMAIN}"

umask 077
cat > "$REPO_DIR/.env" <<EOF
VITE_API_BASE_URL=${ORIGIN_ROOT}
VITE_ENABLE_DEMO_MODE=false
VITE_STOREFRONT_URL=${ORIGIN_ROOT}/
VITE_B2B_URL=${ORIGIN_B2B}/b2b/giris
VITE_OPS_URL=${ORIGIN_OPS}/ops/giris
VITE_ENABLE_B2C_STOREFRONT=true
VITE_ENABLE_B2B_PORTAL=true
VITE_ENABLE_OPS_PORTAL=true
VITE_ENABLE_IYZICO_PAYMENTS=true
VITE_ENABLED_SALES_CHANNELS=B2B,B2B_API,B2C_API

DJANGO_DEBUG=0
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
API_KEY_HASH_PEPPER=${API_KEY_HASH_PEPPER}
DJANGO_SECURE_COOKIES=1
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},ops.${DOMAIN},b2b.${DOMAIN},corporate.${DOMAIN},${IP},localhost,127.0.0.1
DJANGO_SESSION_COOKIE_AGE=43200
CORS_ALLOWED_ORIGINS=${ORIGIN_ROOT},${ORIGIN_WWW},${ORIGIN_OPS},${ORIGIN_B2B},${ORIGIN_CORP}
CSRF_TRUSTED_ORIGINS=${ORIGIN_ROOT},${ORIGIN_WWW},${ORIGIN_OPS},${ORIGIN_B2B},${ORIGIN_CORP}

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
FRONTEND_STOREFRONT_URL=${ORIGIN_ROOT}

ENABLE_IYZICO_PAYMENTS=1
IYZICO_API_KEY=
IYZICO_SECRET_KEY=
IYZICO_BASE_URL=sandbox-api.iyzipay.com
IYZICO_CALLBACK_BASE_URL=${ORIGIN_ROOT}

DEFAULT_FROM_EMAIL=noreply@${DOMAIN}
EMAIL_HOST=localhost
EMAIL_PORT=587
EMAIL_USE_TLS=1
MAIL_ENCRYPTION_KEY=${MAIL_ENCRYPTION_KEY}

DOCUMENT_HARD_DELETE_DAYS=0
LOG_LEVEL=INFO
EOF

write_site() {
  local name="$1"
  local root="$2"
  shift 2
  local names=("$@")
  local server_names
  server_names=$(printf '%s ' "${names[@]}")

  cat > "/etc/nginx/sites-available/taragold-${name}" <<NGX
server {
    listen 80;
    listen [::]:80;
    server_name ${server_names};

    root ${root};
    index index.html;

    client_max_body_size 25m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location /media/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGX
  ln -sfn "/etc/nginx/sites-available/taragold-${name}" "/etc/nginx/sites-enabled/taragold-${name}"
}

# Drop port-based sites; switch to domain vhosts
rm -f /etc/nginx/sites-enabled/taragold-* /etc/nginx/sites-enabled/default

write_site storefront "$WWW_ROOT/storefront" "$DOMAIN" "www.$DOMAIN"
write_site ops "$WWW_ROOT/ops" "ops.$DOMAIN"
write_site b2b "$WWW_ROOT/b2b" "b2b.$DOMAIN"
write_site corporate "$WWW_ROOT/corporate" "corporate.$DOMAIN"

# Keep direct IP access on :80 as storefront fallback
cat > /etc/nginx/sites-available/taragold-ip <<NGX
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${IP} _;
    root ${WWW_ROOT}/storefront;
    index index.html;
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    location /health { proxy_pass http://127.0.0.1:8000; }
    location /media/ { proxy_pass http://127.0.0.1:8000; }
    location /static/ { proxy_pass http://127.0.0.1:8000; }
    location / { try_files \$uri \$uri/ /index.html; }
}
NGX
ln -sfn /etc/nginx/sites-available/taragold-ip /etc/nginx/sites-enabled/taragold-ip

chmod -R a+rX "$WWW_ROOT"
nginx -t
systemctl reload nginx

echo "=== Rebuild frontends for domain URLs ==="
cd "$REPO_DIR"
npm ci --prefer-offline || npm install
npm run build
rsync -a --delete apps/frontend/storefront/dist/ "$WWW_ROOT/storefront/"
rsync -a --delete apps/frontend/b2b/dist/ "$WWW_ROOT/b2b/"
rsync -a --delete apps/frontend/ops/dist/ "$WWW_ROOT/ops/"
rsync -a --delete apps/frontend/corporate/dist/ "$WWW_ROOT/corporate/"
chmod -R a+rX "$WWW_ROOT"

echo "=== Restart API with new env ==="
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d web celery_worker celery_beat

echo "=== TLS certificates ==="
# Cert only for hosts that already resolve here
CERT_HOSTS=(-d "$DOMAIN" -d "www.$DOMAIN")
for sub in ops b2b corporate; do
  resolved=$(dig +short "${sub}.${DOMAIN}" A | head -1 || true)
  if [[ "$resolved" == "$IP" ]]; then
    CERT_HOSTS+=(-d "${sub}.${DOMAIN}")
  else
    echo "SKIP cert for ${sub}.${DOMAIN} (DNS=$resolved, need A -> $IP)"
  fi
done

certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
  --redirect "${CERT_HOSTS[@]}" || {
  echo "CERTBOT_FAILED — HTTP domain binding remains active"
}

nginx -t
systemctl reload nginx

echo "=== Wait API ==="
for i in $(seq 1 30); do
  if curl -fsS -H "Host: ${DOMAIN}" "http://127.0.0.1/health" >/dev/null 2>&1 \
     || curl -fkSs "https://${DOMAIN}/health" >/dev/null 2>&1; then
    echo API_OK
    break
  fi
  sleep 3
done

echo
echo "=== DOMAIN_BIND_OK ==="
echo "Storefront: ${ORIGIN_ROOT}/"
echo "OPS:        ${ORIGIN_OPS}/ops/giris"
echo "B2B:        ${ORIGIN_B2B}/b2b/giris"
echo "Corporate:  ${ORIGIN_CORP}/"
echo
echo "Subdomain DNS (Contabo DNS / A record -> ${IP}):"
echo "  ops.${DOMAIN}"
echo "  b2b.${DOMAIN}"
echo "  corporate.${DOMAIN}"
