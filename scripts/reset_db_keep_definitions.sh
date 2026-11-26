#!/usr/bin/env bash
# Reset Contabo Postgres: keep definitions_* rows, wipe everything else, recreate admin.
# Does NOT re-run seed_taragold demo catalog.
set -euo pipefail

cd /opt/xau001
COMPOSE=(docker compose --env-file .env -f infrastructure/docker-compose.yml)

# Prevent auto demo reseed on every web boot
if grep -q 'seed_taragold' infrastructure/docker-compose.yml; then
  cp infrastructure/docker-compose.yml "infrastructure/docker-compose.yml.bak.$(date +%s)"
  python3 - <<'PY'
from pathlib import Path
p = Path("infrastructure/docker-compose.yml")
text = p.read_text()
text = text.replace("python manage.py seed_taragold &&\n             ", "")
p.write_text(text)
print("compose_seed_removed")
PY
fi

echo "=== Snapshot definitions ==="
"${COMPOSE[@]}" up -d web
sleep 8
"${COMPOSE[@]}" exec -T web python manage.py dumpdata definitions \
  --natural-foreign --natural-primary -o /tmp/definitions_keep.json
"${COMPOSE[@]}" cp web:/tmp/definitions_keep.json /tmp/definitions_keep.json
wc -c /tmp/definitions_keep.json
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("/tmp/definitions_keep.json").read_text())
print("definitions_objects", len(data))
PY

echo "=== Stop app containers ==="
"${COMPOSE[@]}" stop web celery_worker celery_beat || true

echo "=== Drop & recreate public schema ==="
"${COMPOSE[@]}" exec -T db psql -U taragold -d taragold -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO taragold;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "=== Migrate + restore definitions (one-off) ==="
"${COMPOSE[@]}" run --rm --no-deps --entrypoint sh web -c \
  "python manage.py migrate --noinput && python manage.py collectstatic --noinput"

"${COMPOSE[@]}" up -d web
sleep 6
"${COMPOSE[@]}" cp /tmp/definitions_keep.json web:/tmp/definitions_keep.json
"${COMPOSE[@]}" exec -T web python manage.py loaddata /tmp/definitions_keep.json

echo "=== Minimal admin + HQ org only ==="
"${COMPOSE[@]}" exec -T web python <<'PY'
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()
email = "emre.gonel@pigomass.com"
password = os.environ.get("SEED_ADMIN_PASSWORD", "").strip()
user, created = User.objects.get_or_create(
    email=email,
    defaults={"full_name": "Emre Gönel", "is_staff": True, "is_superuser": True},
)
user.full_name = "Emre Gönel"
user.is_staff = True
user.is_superuser = True
if password:
    user.set_password(password)
user.save()
print("ADMIN", user.email, "created" if created else "updated")

hq, _ = Organization.objects.get_or_create(
    code="TG-HQ",
    defaults={
        "name": "Tara Gold Merkez Operasyon A.Ş.",
        "org_type": Organization.OrgType.PLATFORM_OWNER,
        "approval_status": Organization.ApprovalStatus.APPROVED,
        "partner_roles": ["PLATFORM"],
        "city": "İstanbul",
    },
)
OrganizationMembership.objects.get_or_create(
    user=user,
    organization=hq,
    role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
)
OrganizationMembership.objects.get_or_create(
    user=user,
    organization=None,
    role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
)
print("HQ_MEMBERSHIP_OK", hq.code)
PY

echo "=== Restart celery ==="
"${COMPOSE[@]}" up -d web celery_worker celery_beat
sleep 10

echo "=== Verify ==="
curl -fsS http://127.0.0.1:8000/health || true
echo
"${COMPOSE[@]}" exec -T web python <<'PY'
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from apps.definitions.models import DefinitionTable, DefinitionItem
from django.contrib.auth import get_user_model
from apps.catalog.models import ProductModel
print("tables", DefinitionTable.objects.count())
print("items", DefinitionItem.objects.count())
print("users", get_user_model().objects.count())
print("products", ProductModel.objects.count())
PY

echo "RESET_KEEP_DEFINITIONS_OK"
echo "Login: emre.gonel@pigomass.com / (SEED_ADMIN_PASSWORD in /root/.taragold_secrets)"
