from django.test import TestCase
from rest_framework.test import APIClient

from apps.definitions.models import DefinitionItem, DefinitionTable


class StorefrontDefinitionsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.kategori = DefinitionTable.objects.create(
            code="kategori", name="Kategori", is_system=True, is_active=True, sort_order=10
        )
        self.metal_rengi = DefinitionTable.objects.create(
            code="metal_rengi", name="Metal Rengi", is_system=True, is_active=True, sort_order=20
        )
        self.hidden = DefinitionTable.objects.create(
            code="ayar_kodu", name="Ayar", is_system=True, is_active=True, sort_order=30
        )
        DefinitionItem.objects.create(
            table=self.kategori, code="YUZUK", label="Yüzük", is_system=True, is_active=True, sort_order=10
        )
        DefinitionItem.objects.create(
            table=self.kategori,
            code="KOLYE_DRAFT",
            label="Kolye Draft",
            is_system=False,
            is_active=False,
            sort_order=20,
        )
        DefinitionItem.objects.create(
            table=self.metal_rengi, code="BEYAZ", label="Beyaz", is_system=True, is_active=True, sort_order=10
        )
        DefinitionItem.objects.create(
            table=self.hidden, code="14K", label="14 Ayar", is_system=True, is_active=True, sort_order=10
        )

    def test_public_definitions_no_auth(self):
        # Production enables SECURE_SSL_REDIRECT; hit as HTTPS in tests.
        res = self.client.get("/api/v1/storefront/definitions", secure=True)
        self.assertEqual(res.status_code, 200)
        tables = res.json()["data"]["tables"]
        codes = {t["code"] for t in tables}
        self.assertIn("kategori", codes)
        self.assertIn("metal_rengi", codes)
        self.assertNotIn("ayar_kodu", codes)

        kategori = next(t for t in tables if t["code"] == "kategori")
        item_codes = {i["code"] for i in kategori["items"]}
        self.assertIn("YUZUK", item_codes)
        self.assertNotIn("KOLYE_DRAFT", item_codes)
        self.assertEqual(kategori["usage"]["valueStrategy"], "code")

    def test_tables_query_filters_whitelist(self):
        res = self.client.get(
            "/api/v1/storefront/definitions?tables=kategori,ayar_kodu",
            secure=True,
        )
        self.assertEqual(res.status_code, 200)
        codes = {t["code"] for t in res.json()["data"]["tables"]}
        self.assertEqual(codes, {"kategori"})
