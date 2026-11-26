"""Keep definitions (+ TG-HQ). Wipe demo dealers, catalog leftovers, rate snapshots."""
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.organizations.models import Branch, Organization, OrganizationMembership

print(
    "BEFORE orgs",
    list(Organization.objects.values_list("code", flat=True)),
)

dealer_ids = list(Organization.objects.exclude(code="TG-HQ").values_list("id", flat=True))
OrganizationMembership.objects.filter(organization_id__in=dealer_ids).delete()
Branch.objects.filter(organization_id__in=dealer_ids).delete()
n, _ = Organization.objects.exclude(code="TG-HQ").delete()
print("deleted_dealers", n)

hq = Organization.objects.filter(code="TG-HQ").first()
if hq:
    hq.credit_limit_usd = 0
    hq.used_credit_usd = 0
    hq.has_limit_gram = 0
    hq.used_has_gram = 0
    hq.city = "İstanbul"
    hq.contact_name = hq.contact_name or "Emre Gönel"
    hq.save()

for label, model in [
    ("inventory", "StockMovement"),
    ("inventory", "WarehouseStock"),
    ("catalog", "ProductMedia"),
    ("catalog", "ProductVariant"),
    ("catalog", "ProductModel"),
]:
    try:
        M = apps.get_model(label, model)
        d, _ = M.objects.all().delete()
        print("del", model, d)
    except Exception as exc:  # noqa: BLE001
        print("skip", model, exc)

try:
    RateSnapshot = apps.get_model("market", "RateSnapshot")
    rn, _ = RateSnapshot.objects.all().delete()
    print("deleted_rates", rn)
except Exception as exc:  # noqa: BLE001
    print("skip_rates", exc)

User = get_user_model()
user = User.objects.filter(email="emre.gonel@pigomass.com").first()
if user and hq:
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

from apps.definitions.models import DefinitionItem, DefinitionTable
from apps.catalog.models import ProductModel
from apps.market.models import RateSnapshot

print("AFTER orgs", list(Organization.objects.values_list("code", "name")))
print("tables", DefinitionTable.objects.count(), "items", DefinitionItem.objects.count())
print("products", ProductModel.objects.count(), "rates", RateSnapshot.objects.count())
print("WIPE_OK")
