import uuid
from decimal import Decimal

from django.db import migrations
from django.db.models import Max, Sum
from django.utils import timezone


def backfill(apps, schema_editor):
    B2cCart = apps.get_model("commerce", "B2cCart")
    B2cCartItem = apps.get_model("commerce", "B2cCartItem")
    User = apps.get_model("accounts", "User")

    user_ids = (
        B2cCartItem.objects.filter(cart__isnull=True)
        .values_list("user_id", flat=True)
        .distinct()
    )
    now = timezone.now()
    for user_id in user_ids:
        if B2cCart.objects.filter(user_id=user_id, status="ACTIVE").exists():
            cart = B2cCart.objects.filter(user_id=user_id, status="ACTIVE").first()
        else:
            items = B2cCartItem.objects.filter(user_id=user_id)
            last_act = items.aggregate(m=Max("updated_at"))["m"] or now
            total = Decimal("0.00")
            list_total = Decimal("0.00")
            count = 0
            for item in items:
                total += item.unit_final_price_try * item.qty
                list_total += item.unit_list_price_try * item.qty
                count += 1
            cart = B2cCart.objects.create(
                id=uuid.uuid4(),
                external_id=f"backfill-{user_id}-{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                status="ACTIVE",
                checkout_state="NONE",
                currency="TRY",
                subtotal_try=list_total.quantize(Decimal("0.01")),
                discount_try=max(Decimal("0.00"), list_total - total).quantize(Decimal("0.01")),
                tax_try=Decimal("0.00"),
                total_try=total.quantize(Decimal("0.01")),
                line_count=count,
                last_activity_at=last_act,
                created_at=now,
                updated_at=now,
            )
        B2cCartItem.objects.filter(user_id=user_id, cart__isnull=True).update(cart_id=cart.id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0008_b2c_cart_header_faz_b"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
