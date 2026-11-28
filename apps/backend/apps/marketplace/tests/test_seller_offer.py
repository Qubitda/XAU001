"""Marketplace SellerOffer creation and status regression tests."""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.catalog.models import ProductModel
from apps.marketplace.models import SellerOffer
from apps.organizations.models import Organization


class MarketplaceSellerOfferTests(TestCase):
    def setUp(self) -> None:
        self.seller = Organization.objects.create(
            code="MKT-SEL",
            name="Pazaryeri Satıcı",
            org_type=Organization.OrgType.SUPPLIER,
        )
        self.product = ProductModel.objects.create(
            parent_sku="MKT-001",
            title="Pazaryeri Test Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="mkt-001",
        )

    def test_create_seller_offer_defaults_to_draft(self) -> None:
        offer = SellerOffer.objects.create(
            seller_organization=self.seller,
            product=self.product,
            unit_price=Decimal("12500.00"),
        )
        self.assertEqual(offer.status, SellerOffer.Status.DRAFT)
        self.assertEqual(offer.currency, "TRY")

    def test_seller_offer_requires_positive_or_non_null_unit_price(self) -> None:
        with self.assertRaises(IntegrityError):
            SellerOffer.objects.create(
                seller_organization=self.seller,
                product=self.product,
                unit_price=None,
            )
