from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.contracts.models import LegalDocument
from apps.organizations.models import OrganizationMembership


class StorefrontLegalCmsTests(TestCase):
    def setUp(self):
        LegalDocument.objects.filter(code=LegalDocument.Code.KVKK).update(is_published=False)
        self.doc = LegalDocument.objects.create(
            code=LegalDocument.Code.KVKK,
            version="9.9-test",
            title="KVKK Test",
            body_html="<p>Aydınlatma içeriği</p>",
            is_published=True,
            audience=LegalDocument.Audience.ALL,
            effective_from=timezone.now(),
        )
        self.client = APIClient()

    def test_public_detail(self):
        res = self.client.get("/api/v1/storefront/legal-documents/KVKK")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["code"], "KVKK")
        self.assertIn("Aydınlatma", res.data["data"]["bodyHtml"])

    def test_unpublished_404(self):
        LegalDocument.objects.filter(code="KVKK").update(is_published=False)
        res = self.client.get("/api/v1/storefront/legal-documents/KVKK")
        self.assertEqual(res.status_code, 404)


class OpsLegalPatchTests(TestCase):
    def setUp(self):
        self.ops = User.objects.create_user(
            email="legal-ops@test.local", password="pass-1234", full_name="Ops"
        )
        OrganizationMembership.objects.create(
            user=self.ops,
            organization=None,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        self.doc = LegalDocument.objects.create(
            code=LegalDocument.Code.PRIVACY,
            version="9.9-test",
            title="Gizlilik",
            body_html="<p>eski</p>",
            is_published=False,
            audience=LegalDocument.Audience.ALL,
            effective_from=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_login(self.ops)

    def test_patch_publish(self):
        res = self.client.patch(
            f"/api/v1/ops/legal-documents/{self.doc.id}",
            {"bodyHtml": "<p>yeni</p>", "isPublished": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.is_published)
        self.assertIn("yeni", self.doc.body_html)

    def test_title_patch_recomputes_content_hash(self):
        self.doc.refresh_from_db()
        old_hash = self.doc.content_hash
        self.assertTrue(old_hash)
        res = self.client.patch(
            f"/api/v1/ops/legal-documents/{self.doc.id}",
            {"title": "Gizlilik Güncel"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "Gizlilik Güncel")
        self.assertNotEqual(self.doc.content_hash, old_hash)
        self.assertEqual(
            self.doc.content_hash,
            self.doc.compute_content_hash(),
        )
