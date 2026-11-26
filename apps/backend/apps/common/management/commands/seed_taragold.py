import os
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import Branch, Organization, OrganizationMembership


class Command(BaseCommand):
    help = (
        "Bootstrap only: definition tables + platform HQ + admin memberships. "
        "Does NOT seed catalog products, demo dealers, or market rates."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.definitions.services import seed_definition_tables

        seeded = seed_definition_tables()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tanım tabloları: {seeded['tables']} tablo / {seeded['items']} kalem."
            )
        )

        hq, _ = Organization.objects.get_or_create(
            code="TG-HQ",
            defaults={
                "name": "Tara Gold Merkez Operasyon A.Ş.",
                "org_type": Organization.OrgType.PLATFORM_OWNER,
                "approval_status": Organization.ApprovalStatus.APPROVED,
                "partner_roles": ["PLATFORM"],
                "tax_office_and_no": "",
                "contact_name": "Emre Gönel",
                "city": "İstanbul",
                "credit_limit_usd": Decimal("0"),
                "used_credit_usd": Decimal("0"),
                "has_limit_gram": Decimal("0"),
                "used_has_gram": Decimal("0"),
            },
        )
        br_kk, _ = Branch.objects.get_or_create(
            organization=hq,
            code="TG-KK",
            defaults={"name": "Kuyumcukent Merkez", "city": "İstanbul", "is_default": True},
        )

        seed_password = os.environ.get("SEED_ADMIN_PASSWORD", "").strip()
        user, created = User.objects.get_or_create(
            email="emre.gonel@pigomass.com",
            defaults={"full_name": "Emre Gönel", "is_staff": True, "is_superuser": True},
        )
        if seed_password:
            user.set_password(seed_password)
            user.save(update_fields=["password"])
        elif created:
            self.stdout.write(
                self.style.WARNING(
                    "SEED_ADMIN_PASSWORD boş bırakıldığı için emre.gonel@pigomass.com parolası ayarlanmadı; "
                    "giriş için .env dosyasında SEED_ADMIN_PASSWORD tanımlayıp komutu tekrar çalıştırın."
                )
            )

        OrganizationMembership.objects.get_or_create(
            user=user, organization=None, role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER
        )
        m_hq, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=hq,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            defaults={"default_branch": br_kk},
        )
        m_hq.branches.set([br_kk])

        from apps.inventory.models import Warehouse

        Warehouse.objects.get_or_create(
            code="WH-MERKEZ",
            defaults={"name": "Kuyumcukent Merkez Kasa", "branch": br_kk, "is_active": True},
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Bootstrap OK (definitions + TG-HQ + admin). "
                "No demo dealers / products / rates seeded."
            )
        )
