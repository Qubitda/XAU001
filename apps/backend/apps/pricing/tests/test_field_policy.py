from django.test import SimpleTestCase

from apps.pricing.field_policy import PRICE_AFFECTING_FIELDS, payload_affects_price


class PriceFieldPolicyTests(SimpleTestCase):
    def test_price_affecting_fields_trigger_true(self):
        for field in PRICE_AFFECTING_FIELDS:
            with self.subTest(field=field):
                self.assertTrue(payload_affects_price({field: "value"}))

    def test_non_price_fields_return_false(self):
        non_price_payload = {
            "title": "Yeni Başlık",
            "description": "Güncel açıklama",
            "seoSlug": "yeni-baslik",
            "metaTitle": "SEO",
            "galleryImages": ["https://example.com/a.jpg"],
            "warrantyMonths": 24,
        }
        self.assertFalse(payload_affects_price(non_price_payload))

    def test_mixed_payload_returns_true(self):
        self.assertTrue(
            payload_affects_price({"title": "Başlık", "grossWeightGram": "4.50"})
        )
