#!/usr/bin/env bash
set -euo pipefail

IP="169.58.5.103"
DOMAIN="estorks.com"
REPO_DIR="/opt/xau001"
WWW_ROOT="/var/www/taragold"
SECRETS_FILE="/root/.taragold_secrets"

# Portal map: subdomain -> dist folder
declare -A PORTALS=(
  [ops]=ops
  [b2b]=b2b
  [erp]=corporate
)

need_dns=()
for sub in "${!PORTALS[@]}"; do
  host="${sub}.${DOMAIN}"
  resolved=$(dig +short "$host" A | head -1 || true)
  echo "DNS ${host} -> ${resolved:-NONE}"
  if [[ "$resolved" != "$IP" ]]; then
    need_dns+=("$host")
  fi
done

if ((${#need_dns[@]} > 0)); then
  echo "WAITING_DNS: ${need_dns[*]}"
  echo "Create Contabo DNS A records -> ${IP}, then re-run."
  # Still write nginx configs so certbot can work as soon as DNS propagates
fi

# shellcheck disable=SC1090
source "$SECRETS_FILE"

ORIGIN_ROOT="https://${DOMAIN}"
ORIGIN_WWW="https://www.${DOMAIN}"
ORIGIN_OPS="https://ops.${DOMAIN}"
ORIGIN_B2B="https://b2b.${DOMAIN}"
ORIGIN_ERP="https://erp.${DOMAIN}"

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
DJANGO_ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},ops.${DOMAIN},b2b.${DOMAIN},erp.${DOMAIN},${IP},localhost,127.0.0.1
DJANGO_SESSION_COOKIE_AGE=43200
CORS_ALLOWED_ORIGINS=${ORIGIN_ROOT},${ORIGIN_WWW},${ORIGIN_OPS},${ORIGIN_B2B},${ORIGIN_ERP}
CSRF_TRUSTED_ORIGINS=${ORIGIN_ROOT},${ORIGIN_WWW},${ORIGIN_OPS},${ORIGIN_B2B},${ORIGIN_ERP}

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

write_http_site() {
  local name="$1"
  local root="$2"
  shift 2
  local server_names
  server_names=$(printf '%s ' "$@")
  cat > "/etc/nginx/sites-available/taragold-${name}" <<NGX
server {
    listen 80;
    listen [::]:80;
    server_name ${server_names};

    root ${root};
    index index.html;
    client_max_body_size 25m;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

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

mkdir -p /var/www/html
rm -f /etc/nginx/sites-enabled/taragold-ops /etc/nginx/sites-enabled/taragold-b2b \
      /etc/nginx/sites-enabled/taragold-corporate /etc/nginx/sites-enabled/taragold-erp \
      /etc/nginx/sites-enabled/taragold-*-port

# Keep existing storefront TLS site; refresh portal HTTP sites for certbot
for sub in ops b2b erp; do
  write_http_site "$sub" "$WWW_ROOT/${PORTALS[$sub]}" "${sub}.${DOMAIN}"
done

chmod -R a+rX "$WWW_ROOT"
nginx -t
systemctl reload nginx

echo "=== Rebuild frontends ==="
cd "$REPO_DIR"
npm ci --prefer-offline || npm install
npm run build
rsync -a --delete apps/frontend/storefront/dist/ "$WWW_ROOT/storefront/"
rsync -a --delete apps/frontend/b2b/dist/ "$WWW_ROOT/b2b/"
rsync -a --delete apps/frontend/ops/dist/ "$WWW_ROOT/ops/"
rsync -a --delete apps/frontend/corporate/dist/ "$WWW_ROOT/corporate/"
chmod -R a+rX "$WWW_ROOT"

docker compose --env-file .env -f infrastructure/docker-compose.yml up -d web celery_worker celery_beat

echo "=== Wait for DNS (up to ~3 min) ==="
deadline=$((SECONDS + 180))
while (( SECONDS < deadline )); do
  pending=0
  for sub in ops b2b erp; do
    resolved=$(dig +short "${sub}.${DOMAIN}" A | head -1 || true)
    if [[ "$resolved" != "$IP" ]]; then
      pending=1
      break
    fi
  done
  if (( pending == 0 )); then
    echo "DNS_OK"
    break
  fi
  sleep 10
done

for sub in ops b2b erp; do
  resolved=$(dig +short "${sub}.${DOMAIN}" A | head -1 || true)
  if [[ "$resolved" != "$IP" ]]; then
    echo "DNS_MISSING ${sub}.${DOMAIN} (got '${resolved}')"
    echo "PARTIAL_OK: nginx ready; add A records then: certbot --nginx -d ${sub}.${DOMAIN}"
    exit 2
  fi
done

echo "=== Issue / expand TLS ==="
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect \
  -d "ops.${DOMAIN}" -d "b2b.${DOMAIN}" -d "erp.${DOMAIN}" \
  || certbot certonly --nginx --non-interactive --agree-tos --register-unsafely-without-email \
       -d "ops.${DOMAIN}" -d "b2b.${DOMAIN}" -d "erp.${DOMAIN}"

# Expand main cert is separate; portal certs are fine as one SAN cert or individual
nginx -t
systemctl reload nginx

echo "=== Verify ==="
for url in \
  "https://ops.${DOMAIN}/ops/giris" \
  "https://b2b.${DOMAIN}/b2b/giris" \
  "https://erp.${DOMAIN}/" \
  "https://${DOMAIN}/health"
do
  code=$(curl -fsS -o /dev/null -w "%{http_code}" "$url" || echo FAIL)
  echo "$url -> $code"
done

echo "SUBDOMAIN_SSL_OK"
