from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.definitions.models import DefinitionItem, DefinitionTable
from apps.definitions.services import (
    create_definition_item,
    merge_item_meta,
    purity_fineness_map,
)
from apps.organizations.models import Organization, OrganizationMembership
from config.exceptions import DomainError


class DefinitionItemGuardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ops-defs@test.local",
            password="test-pass-1234",
            is_staff=True,
            full_name="Ops Defs",
        )
        self.org = Organization.objects.create(code="OPS", name="Ops Org")
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        self.parent_table = DefinitionTable.objects.create(
            code="metal_adi", name="Metal Adı", is_system=True
        )
        self.table = DefinitionTable.objects.create(
            code="ayar_kodu",
            name="Ayar Kodu",
            is_system=True,
            parent_table=self.parent_table,
        )
        self.gold = DefinitionItem.objects.create(
            table=self.parent_table, code="ALTIN", label="Altın", is_system=True
        )
        self.item = DefinitionItem.objects.create(
            table=self.table,
            code="585",
            label="14 Ayar",
            is_system=True,
            meta={"fineness": 0.585},
        )
        self.item.parents.set([self.gold])

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        session = self.client.session
        session["active_membership_id"] = str(self.membership.id)
        session.save()

    def test_system_code_locked(self):
        response = self.client.patch(
            f"/api/v1/ops/definition-items/{self.item.id}",
            {"code": "HACKED"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.code, "585")

    def test_system_fineness_preserved(self):
        response = self.client.patch(
            f"/api/v1/ops/definition-items/{self.item.id}",
            {"meta": {"note": "x"}, "label": "14 Ayar Altın"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.label, "14 Ayar Altın")
        self.assertEqual(self.item.meta.get("fineness"), 0.585)
        self.assertEqual(self.item.meta.get("note"), "x")

    def test_service_create_requires_parent(self):
        with self.assertRaises(DomainError):
            create_definition_item(self.table, code="750", label="18 Ayar", parent_ids=[])
        item = create_definition_item(
            self.table,
            code="750",
            label="18 Ayar",
            meta={"fineness": 0.750},
            parent_ids=[self.gold.id],
        )
        self.assertEqual(item.code, "750")
        self.assertEqual(list(item.parents.all()), [self.gold])

    def test_merge_meta_and_fineness_map(self):
        merged = merge_item_meta({"fineness": 0.585}, {"note": "y"}, is_system=True)
        self.assertEqual(merged["fineness"], 0.585)
        self.assertEqual(merged["note"], "y")
        locked = merge_item_meta({"fineness": 0.585}, {"fineness": 0.999}, is_system=True)
        self.assertEqual(locked["fineness"], 0.585)
        fmap = purity_fineness_map()
        self.assertEqual(fmap["585"], 0.585)

    def test_soft_delete_deactivates(self):
        response = self.client.delete(f"/api/v1/ops/definition-items/{self.item.id}?soft=1")
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_hard_delete_removes_row(self):
        custom = DefinitionItem.objects.create(
            table=self.parent_table,
            code="OZEL",
            label="Özel Metal",
            is_system=False,
        )
        response = self.client.delete(f"/api/v1/ops/definition-items/{custom.id}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DefinitionItem.objects.filter(id=custom.id).exists())
