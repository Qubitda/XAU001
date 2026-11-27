from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent, has_active_consent
from apps.customers.models import Customer
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.social_commerce.adapters.base import ProviderResult
from apps.social_commerce.models import (
    AffiliateCode,
    AffiliateConversion,
    SocialAttribution,
    SocialCampaign,
    SocialCatalog,
    SocialChannel,
    SocialInboxConversation,
    SocialInboxMessage,
    SocialInfluencer,
    SocialPlatform,
    SocialPost,
    SocialPostChannel,
    SocialWhatsAppTemplate,
)
from apps.social_commerce.services import (
    FORBIDDEN_SOCIAL_FIELDS,
    SocialCommerceError,
    adjust_affiliate_conversion_for_partial_refund,
    build_b2b_social_catalog_items,
    build_oauth_authorize_url,
    build_social_b2c_product_dto,
    connect_social_channel,
    decrypt_connection_token,
    get_social_analytics_summary,
    handle_oauth_callback,
    publish_post_to_channel,
    record_affiliate_conversion,
    record_verified_order_attribution,
    refresh_channel_token,
    refresh_post_publish_status,
    reply_to_inbox_conversation,
    resolve_social_checkout_discount,
    sync_social_catalog,
)

User = get_user_model()


class SocialCommerceHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-SOC-1",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
        )
        self.org_a = Organization.objects.create(code="BAYI-A", name="Bayi A Kuyumculuk")
        self.org_b = Organization.objects.create(code="BAYI-B", name="Bayi B Kuyumculuk")

        self.product = ProductModel.objects.create(
            parent_sku="SOC-RING-01",
            seo_slug="soc-ring-01",
            title="1.00 Karat Tektaş Yüzük",
            description="Sertifikalı pırlanta yüzük",
            category="YUZUK",
            metal_name="Altın",
            purity_code="18K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("4.20"),
            fire_rate_pct=Decimal("8.50"),
            stone_type="Pırlanta",
            stone_measure_unit="ct",
            stock_status=ProductModel.StockStatus.IN_STOCK,
            stock_qty=3,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2B", "B2B_API", "B2C_API"],
            erp_code="ERP-SECRET-99",
            supplier_name="Gizli Tedarikçi A.Ş.",
            warehouse_location="Kasa-3B",
        )
        self.recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode=PricingRecipe.PricingMode.SUPPLIER,
            lc_currency="TRY",
            last_snapshot=self.snap,
        )
        CostLine.objects.create(
            recipe=self.recipe,
            line_type=CostLine.LineType.TEDARIKCI,
            fc_currency="TRY",
            fc_price=Decimal("25000.00"),
        )
        ChannelRule.objects.create(
            recipe=self.recipe,
            channel=ChannelRule.Channel.B2C_API,
            profit_value=Decimal("40.0000"),
        )
        ChannelRule.objects.create(
            recipe=self.recipe,
            channel=ChannelRule.Channel.B2B,
            profit_value=Decimal("10.0000"),
        )
        self.recipe.status = PricingRecipe.Status.PUBLISHED
        self.recipe.save(update_fields=["status", "updated_at"])

        # Dealer-B exclusive product (must never appear in B2C or Dealer-A catalog)
        self.org_b_product = ProductModel.objects.create(
            parent_sku="BAYI-B-ONLY",
            seo_slug="bayi-b-only",
            title="Bayi B Özel Ürün",
            description="Sadece Bayi B",
            category="YUZUK",
            metal_name="Altın",
            purity_code="14K",
            metal_color="Sarı",
            gross_weight_gram=Decimal("3.00"),
            stone_type="Taşsız",
            stone_measure_unit="ct",
            stock_status=ProductModel.StockStatus.IN_STOCK,
            stock_qty=2,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2B"],
            owner_organization=self.org_b,
        )
        self.client = APIClient()

    def test_blind_pool_and_b2b_isolation_and_pricing(self):
        b2c_dto = build_social_b2c_product_dto(self.product)
        for field in FORBIDDEN_SOCIAL_FIELDS:
            self.assertNotIn(field, b2c_dto)

        # B2C must reject dealer-owned product
        with self.assertRaises(SocialCommerceError):
            build_social_b2c_product_dto(self.org_b_product)

        # B2B catalog for org_a uses B2B pricing (lower than B2C) and excludes org_b_product
        b2b_items = build_b2b_social_catalog_items(organization=self.org_a)
        skus = [item["id"] for item in b2b_items]
        self.assertIn("SOC-RING-01", skus)
        self.assertNotIn("BAYI-B-ONLY", skus)
        self.assertLess(Decimal(b2b_items[0]["b2bPriceTry"]), Decimal(b2c_dto["priceTry"]))

    def test_webhook_requires_signature_and_handles_opt_out_and_delivery_status(self):
        ch = SocialChannel.objects.create(
            platform=SocialPlatform.WHATSAPP,
            name="Tara WhatsApp",
            external_account_id="wa-phone-1",
            country_code="TR",
        )
        # Unsigned / missing secret must be rejected (403)
        unsigned_resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=json.dumps({"externalAccountId": "wa-phone-1", "text": "Merhaba"}).encode("utf-8"),
            content_type="application/json",
        )
        self.assertEqual(unsigned_resp.status_code, 403)

        secret = "wh-secret-key-123"
        connect_social_channel(channel=ch, access_token="secret-oauth-token", webhook_secret=secret)

        cust = Customer.objects.create(full_name="Ayşe Yılmaz", phone="+905551112233")
        append_consent(
            customer=cust,
            purpose=ConsentPurpose.COMMERCIAL_WHATSAPP,
            channel=ConsentChannel.WHATSAPP,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.INTEGRATION,
        )
        self.assertTrue(has_active_consent(customer=cust, purpose=ConsentPurpose.COMMERCIAL_WHATSAPP, channel=ConsentChannel.WHATSAPP))

        payload = {
            "externalAccountId": "wa-phone-1",
            "messageId": "msg-uniq-001",
            "threadId": "thread-1",
            "from": "905551112233",
            "phone": "+905551112233",
            "senderName": "Ayşe Yılmaz",
            "text": "STOP",
            "productSku": "SOC-RING-01",
        }
        raw = json.dumps(payload).encode("utf-8")
        good_sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()

        ok_resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=good_sig,
        )
        self.assertEqual(ok_resp.status_code, 200)
        self.assertFalse(ok_resp.json()["data"]["duplicate"])
        # Opt-out keyword STOP revoked WhatsApp marketing consent
        self.assertFalse(has_active_consent(customer=cust, purpose=ConsentPurpose.COMMERCIAL_WHATSAPP, channel=ConsentChannel.WHATSAPP))

        # Delivery status webhook updates message status
        st_payload = {"externalAccountId": "wa-phone-1", "statuses": [{"id": "msg-uniq-001", "status": "read"}]}
        st_raw = json.dumps(st_payload).encode("utf-8")
        st_sig = "sha256=" + hmac.new(secret.encode("utf-8"), st_raw, hashlib.sha256).hexdigest()
        st_resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=st_raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=st_sig,
        )
        self.assertEqual(st_resp.status_code, 200)
        self.assertEqual(SocialInboxMessage.objects.get(external_message_id="msg-uniq-001").delivery_status, "READ")

    def test_whatsapp_24h_window_requires_template_outside_window(self):
        ch = SocialChannel.objects.create(platform=SocialPlatform.WHATSAPP, name="WA", external_account_id="wa-1")
        conv = SocialInboxConversation.objects.create(
            channel=ch,
            platform=SocialPlatform.WHATSAPP,
            external_thread_id="t-24h",
            last_inbound_at=timezone.now() - timedelta(hours=30),
        )
        with self.assertRaises(SocialCommerceError) as ctx:
            reply_to_inbox_conversation(conversation=conv, body="Merhaba")
        self.assertEqual(ctx.exception.code, "WHATSAPP_TEMPLATE_REQUIRED")

    def test_tiktok_publishing_vs_published_lifecycle(self):
        ch = SocialChannel.objects.create(platform=SocialPlatform.TIKTOK, name="Tara TikTok", external_account_id="tt-1")
        connect_social_channel(channel=ch, access_token="tt-token")
        post = SocialPost.objects.create(
            product=self.product,
            post_type=SocialPost.PostType.TIKTOK_VIDEO,
            title="Tektaş Video",
            media_urls=["https://cdn.taradiamond.com.tr/v.mp4"],
        )
        target = SocialPostChannel.objects.create(post=post, channel=ch)

        with patch(
            "apps.social_commerce.adapters.tiktok.TikTokBusinessAdapter.publish_post",
            return_value=ProviderResult(ok=True, status="PUBLISHING", external_id="pub-123"),
        ):
            publish_post_to_channel(target)
        self.assertEqual(target.publish_status, SocialPostChannel.PublishStatus.PUBLISHING)
        self.assertIsNone(target.published_at)

        with patch(
            "apps.social_commerce.adapters.tiktok.TikTokBusinessAdapter.check_publish_status",
            return_value=ProviderResult(ok=True, status="PUBLISHED", external_id="pub-123"),
        ):
            refresh_post_publish_status(target)
        self.assertEqual(target.publish_status, SocialPostChannel.PublishStatus.PUBLISHED)
        self.assertIsNotNone(target.published_at)

    def test_public_attribution_rejects_client_order_events(self):
        resp = self.client.post(
            "/api/v1/storefront/social/attribution/",
            data=json.dumps({"platform": "INSTAGRAM", "eventType": "ORDER", "revenueTry": "99999"}).encode("utf-8"),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        ok = self.client.post(
            "/api/v1/storefront/social/attribution/",
            data=json.dumps({"platform": "INSTAGRAM", "eventType": "CLICK", "parentSku": "SOC-RING-01"}).encode("utf-8"),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 201)

    def test_concurrent_catalog_sync_lock(self):
        ch = SocialChannel.objects.create(platform=SocialPlatform.INSTAGRAM, name="Tara IG")
        cat = SocialCatalog.objects.create(channel=ch, name="IG Catalog")
        cache.set(f"soc_cat_sync_lock:{cat.id}", "1", timeout=60)
        with self.assertRaises(SocialCommerceError) as ctx:
            sync_social_catalog(cat)
        self.assertEqual(ctx.exception.code, "SYNC_IN_PROGRESS")

    def test_affiliate_refund_excluded_from_analytics(self):
        inf = SocialInfluencer.objects.create(full_name="Test Influencer")
        ac = AffiliateCode.objects.create(influencer=inf, code="TARA10")
        AffiliateConversion.objects.create(
            affiliate_code=ac,
            order_no="ORD-OK",
            gross_amount_try=Decimal("10000.00"),
            net_amount_try=Decimal("10000.00"),
            commission_amount_try=Decimal("500.00"),
            status=AffiliateConversion.Status.APPROVED,
        )
        AffiliateConversion.objects.create(
            affiliate_code=ac,
            order_no="ORD-REF",
            gross_amount_try=Decimal("5000.00"),
            net_amount_try=Decimal("5000.00"),
            commission_amount_try=Decimal("250.00"),
            status=AffiliateConversion.Status.CANCELLED_REFUNDED,
        )
        SocialAttribution.objects.create(
            platform=SocialPlatform.INSTAGRAM,
            event_type="ORDER",
            order_no="ORD-OK",
            revenue_try=Decimal("10000.00"),
        )
        summary = get_social_analytics_summary()
        self.assertEqual(summary["affiliate"]["conversions"], 1)
        self.assertEqual(summary["affiliate"]["netSalesTry"], "10000.00")
        self.assertEqual(summary["affiliate"]["commissionTry"], "500.00")

    def test_empty_catalog_not_marked_synced_and_b2b_catalog_isolated(self):
        ch_b2b = SocialChannel.objects.create(
            platform=SocialPlatform.INSTAGRAM,
            name="Bayi A IG",
            organization=self.org_a,
        )
        cat_b2b = SocialCatalog.objects.create(channel=ch_b2b, name="Bayi A Catalog", audience="B2B")
        res = sync_social_catalog(cat_b2b)
        self.assertEqual(res["audience"], "B2B")
        self.assertEqual(res["itemCount"], 1)
        self.assertNotEqual(res["syncStatus"], SocialCatalog.SyncStatus.SYNCED)

        # Empty catalog (all products archived) must remain IDLE, never SYNCED
        ProductModel.objects.update(catalog_status=ProductModel.CatalogStatus.ARCHIVED)
        ch_empty = SocialChannel.objects.create(platform=SocialPlatform.INSTAGRAM, name="Empty IG")
        cat_empty = SocialCatalog.objects.create(channel=ch_empty, name="Empty Catalog", audience="B2C")
        empty_res = sync_social_catalog(cat_empty)
        self.assertEqual(empty_res["itemCount"], 0)
        self.assertEqual(empty_res["syncStatus"], SocialCatalog.SyncStatus.IDLE)

    def test_whatsapp_backend_enforces_consent_on_marketing_template(self):
        cust = Customer.objects.create(full_name="Zeynep Kaya", phone="+905559998877")
        ch = SocialChannel.objects.create(platform=SocialPlatform.WHATSAPP, name="WA", external_account_id="wa-2")
        conv = SocialInboxConversation.objects.create(
            channel=ch,
            platform=SocialPlatform.WHATSAPP,
            external_thread_id="t-mkt",
            customer=cust,
            last_inbound_at=timezone.now(),
        )
        with self.assertRaises(SocialCommerceError) as ctx:
            reply_to_inbox_conversation(
                conversation=conv,
                body="",
                template_name="promo_winter_2026",
            )
        self.assertEqual(ctx.exception.code, "CONSENT_REQUIRED")

    def test_affiliate_double_commission_prevented_and_order_attribution(self):
        inf = SocialInfluencer.objects.create(full_name="Influencer X")
        AffiliateCode.objects.create(influencer=inf, code="TARA20", commission_pct=Decimal("10.00"))
        c1 = record_affiliate_conversion(
            code_str="TARA20",
            order_no="ORD-DUP-1",
            gross_amount_try=Decimal("10000.00"),
            net_amount_try=Decimal("10000.00"),
        )
        c2 = record_affiliate_conversion(
            code_str="TARA20",
            order_no="ORD-DUP-1",
            gross_amount_try=Decimal("10000.00"),
            net_amount_try=Decimal("10000.00"),
        )
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(AffiliateConversion.objects.filter(order_no="ORD-DUP-1").count(), 1)

        SocialAttribution.objects.create(
            platform=SocialPlatform.INSTAGRAM,
            session_key="sess-1",
            event_type="CLICK",
        )
        attr = record_verified_order_attribution(
            order_no="ORD-DUP-1",
            revenue_try=Decimal("10000.00"),
            session_key="sess-1",
        )
        self.assertIsNotNone(attr)
        self.assertEqual(attr.platform, SocialPlatform.INSTAGRAM)
        self.assertIsNone(
            record_verified_order_attribution(
                order_no="ORD-DUP-1",
                revenue_try=Decimal("10000.00"),
                session_key="sess-1",
            )
        )

    def test_expired_campaign_excluded_from_storefront(self):
        SocialCampaign.objects.create(
            name="Eski Kampanya",
            code="EXPIRED10",
            audience="B2C",
            ends_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        SocialCampaign.objects.create(
            name="Aktif Kampanya",
            code="ACTIVE10",
            audience="B2C",
            discount_pct=Decimal("10.00"),
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )
        resp = self.client.get("/api/v1/storefront/social/campaigns/")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["data"]
        codes = [c["code"] for c in items]
        self.assertIn("ACTIVE10", codes)
        self.assertNotIn("EXPIRED10", codes)
        active_item = next(c for c in items if c["code"] == "ACTIVE10")
        self.assertTrue(active_item["pricingApplied"])

    def test_oauth_redirect_fail_closed_and_callback_redirect_match(self):
        ch = SocialChannel.objects.create(platform=SocialPlatform.INSTAGRAM, name="Tara IG")
        with override_settings(
            SOCIAL_OAUTH_ALLOWED_REDIRECT_URIS=[],
            CORS_ALLOWED_ORIGINS=[],
            FRONTEND_STOREFRONT_URL="",
            META_APP_ID="meta-app-1",
            META_APP_SECRET="meta-sec-1",
        ):
            with self.assertRaises(SocialCommerceError) as ctx:
                build_oauth_authorize_url(channel=ch, redirect_uri="https://evil.example/cb")
            self.assertEqual(ctx.exception.code, "UNTRUSTED_REDIRECT_URI")

        with override_settings(
            SOCIAL_OAUTH_ALLOWED_REDIRECT_URIS=["https://ops.taradiamond.com.tr"],
            CORS_ALLOWED_ORIGINS=[],
            FRONTEND_STOREFRONT_URL="",
            META_APP_ID="meta-app-1",
            META_APP_SECRET="meta-sec-1",
        ):
            auth_data = build_oauth_authorize_url(
                channel=ch, redirect_uri="https://ops.taradiamond.com.tr/oauth/cb1"
            )
            with self.assertRaises(SocialCommerceError) as mm:
                handle_oauth_callback(
                    channel=ch,
                    code="code-1",
                    state=auth_data["state"],
                    redirect_uri="https://ops.taradiamond.com.tr/oauth/cb2",
                )
            self.assertEqual(mm.exception.code, "REDIRECT_URI_MISMATCH")

    def test_meta_token_refresh_without_refresh_token(self):
        ch = SocialChannel.objects.create(platform=SocialPlatform.INSTAGRAM, name="Tara IG")
        connect_social_channel(channel=ch, access_token="old-long-lived-token")
        mock_resp = MagicMock(status_code=200, content=b"{}")
        mock_resp.json.return_value = {"access_token": "new-long-lived-token", "expires_in": 5184000}
        with (
            override_settings(META_APP_ID="meta-app-1", META_APP_SECRET="meta-sec-1"),
            patch("apps.social_commerce.services.oauth.requests.get", return_value=mock_resp) as mock_get,
        ):
            refresh_channel_token(channel=ch)
        self.assertEqual(mock_get.call_args.kwargs["params"]["fb_exchange_token"], "old-long-lived-token")
        ch.refresh_from_db()
        self.assertEqual(decrypt_connection_token(ch.connection), "new-long-lived-token")

    def test_whatsapp_template_category_classification(self):
        cust = Customer.objects.create(full_name="Elif Demir", phone="+905554443322")
        ch = SocialChannel.objects.create(platform=SocialPlatform.WHATSAPP, name="WA", external_account_id="wa-cat")
        conv = SocialInboxConversation.objects.create(
            channel=ch,
            platform=SocialPlatform.WHATSAPP,
            external_thread_id="t-cat",
            customer=cust,
            last_inbound_at=timezone.now() - timedelta(hours=30),
        )
        SocialWhatsAppTemplate.objects.create(
            channel=ch,
            name="order_shipped_tr",
            language_code="tr",
            category=SocialWhatsAppTemplate.Category.UTILITY,
            status=SocialWhatsAppTemplate.Status.APPROVED,
        )
        SocialWhatsAppTemplate.objects.create(
            channel=ch,
            name="vip_collection_drop",
            language_code="tr",
            category=SocialWhatsAppTemplate.Category.MARKETING,
            status=SocialWhatsAppTemplate.Status.APPROVED,
        )
        SocialWhatsAppTemplate.objects.create(
            channel=ch,
            name="pending_tpl",
            language_code="tr",
            category=SocialWhatsAppTemplate.Category.UTILITY,
        )
        # PENDING template must be rejected before Meta approval
        with self.assertRaises(SocialCommerceError) as pend_ctx:
            reply_to_inbox_conversation(conversation=conv, body="", template_name="pending_tpl")
        self.assertEqual(pend_ctx.exception.code, "TEMPLATE_NOT_APPROVED")
        # MARKETING template without promo_ prefix still enforces KVKK consent
        with self.assertRaises(SocialCommerceError) as ctx:
            reply_to_inbox_conversation(conversation=conv, body="", template_name="vip_collection_drop")
        self.assertEqual(ctx.exception.code, "CONSENT_REQUIRED")

        # UTILITY template outside 24h window is transactional and does NOT require marketing consent
        with patch(
            "apps.social_commerce.adapters.whatsapp.WhatsAppCloudAdapter.send_template",
            return_value=ProviderResult(ok=True, status="SENT", external_id="wamid-util-1"),
        ):
            msg = reply_to_inbox_conversation(conversation=conv, body="", template_name="order_shipped_tr")
        self.assertEqual(msg.delivery_status, "SENT")

    def test_social_discount_checkout_resolution_and_dedup(self):
        SocialCampaign.objects.create(
            name="Yaz İndirimi",
            code="YAZ15",
            audience="B2C",
            discount_pct=Decimal("15.00"),
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        inf = SocialInfluencer.objects.create(full_name="Inf Discount")
        AffiliateCode.objects.create(influencer=inf, code="VIP40", discount_pct=Decimal("40.00"))
        # Capped at MAX_SOCIAL_DISCOUNT_PCT (30%) and non-stacking
        res = resolve_social_checkout_discount(
            subtotal_final_try=Decimal("10000.00"),
            campaign_code="YAZ15",
            affiliate_code="VIP40",
            audience="B2C",
        )
        self.assertEqual(res["discountPct"], Decimal("30.00"))
        self.assertEqual(res["discountTry"], Decimal("3000.00"))
        self.assertEqual(res["sourceType"], "AFFILIATE")

        # Burst dedup on public attribution endpoint
        p1 = self.client.post(
            "/api/v1/storefront/social/attribution/",
            data=json.dumps({"platform": "INSTAGRAM", "eventType": "CLICK", "sessionKey": "s-burst"}).encode("utf-8"),
            content_type="application/json",
        )
        p2 = self.client.post(
            "/api/v1/storefront/social/attribution/",
            data=json.dumps({"platform": "INSTAGRAM", "eventType": "CLICK", "sessionKey": "s-burst"}).encode("utf-8"),
            content_type="application/json",
        )
        self.assertEqual(p1.status_code, 201)
        self.assertEqual(p2.status_code, 200)
        self.assertTrue(p2.json()["data"]["deduplicated"])

    def test_whatsapp_cloud_webhook_parser_template_status_and_partial_refund(self):
        ch = SocialChannel.objects.create(
            platform=SocialPlatform.WHATSAPP,
            name="WA Cloud",
            external_account_id="10987654321",
        )
        secret = "wa-cloud-sec"
        connect_social_channel(channel=ch, access_token="wa-tok", webhook_secret=secret)

        # Official WhatsApp Cloud API inbound message payload
        wa_payload = {
            "entry": [
                {
                    "id": "waba-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "10987654321"},
                                "contacts": [{"profile": {"name": "Merve Aksoy"}, "wa_id": "905552223344"}],
                                "messages": [
                                    {
                                        "from": "905552223344",
                                        "id": "wamid.HBgMOTA1",
                                        "text": {"body": "Fiyat bilgisi alabilir miyim?"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        raw = json.dumps(wa_payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(SocialInboxMessage.objects.filter(external_message_id="wamid.HBgMOTA1").exists())

        # Meta message_template_status_update webhook promotes ONLY matching language (tr -> APPROVED, en stays PENDING)
        tpl = SocialWhatsAppTemplate.objects.create(
            channel=ch,
            name="order_update_v2",
            language_code="tr",
            category=SocialWhatsAppTemplate.Category.UTILITY,
        )
        tpl_en = SocialWhatsAppTemplate.objects.create(
            channel=ch,
            name="order_update_v2",
            language_code="en",
            category=SocialWhatsAppTemplate.Category.UTILITY,
        )
        self.assertEqual(tpl.status, SocialWhatsAppTemplate.Status.PENDING)
        tpl_payload = {
            "entry": [
                {
                    "id": "waba-1",
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "event": "APPROVED",
                                "message_template_name": "order_update_v2",
                                "message_template_language": "tr",
                            },
                        }
                    ],
                }
            ]
        }
        # Note: externalAccountId fallback works because only 1 active WHATSAPP channel exists
        tpl_raw = json.dumps(tpl_payload).encode("utf-8")
        tpl_sig = "sha256=" + hmac.new(secret.encode("utf-8"), tpl_raw, hashlib.sha256).hexdigest()
        tpl_resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=tpl_raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=tpl_sig,
        )
        self.assertEqual(tpl_resp.status_code, 200)
        tpl.refresh_from_db()
        tpl_en.refresh_from_db()
        self.assertEqual(tpl.status, SocialWhatsAppTemplate.Status.APPROVED)
        self.assertEqual(tpl_en.status, SocialWhatsAppTemplate.Status.PENDING)

        # Partial refund adjusts affiliate net & commission idempotently via refund_reference
        inf = SocialInfluencer.objects.create(full_name="Partial Inf")
        AffiliateCode.objects.create(influencer=inf, code="PART10", commission_pct=Decimal("10.00"))
        conv = record_affiliate_conversion(
            code_str="PART10",
            order_no="ORD-PART-1",
            gross_amount_try=Decimal("10000.00"),
            net_amount_try=Decimal("10000.00"),
        )
        self.assertEqual(conv.commission_amount_try, Decimal("1000.00"))
        adjust_affiliate_conversion_for_partial_refund(
            order_no="ORD-PART-1",
            refunded_amount_try=Decimal("4000.00"),
            refund_reference="ref-log-1",
        )
        # Duplicate delivery with same refund_reference must NOT deduct again
        adjust_affiliate_conversion_for_partial_refund(
            order_no="ORD-PART-1",
            refunded_amount_try=Decimal("4000.00"),
            refund_reference="ref-log-1",
        )
        conv.refresh_from_db()
        self.assertEqual(conv.net_amount_try, Decimal("6000.00"))
        self.assertEqual(conv.commission_amount_try, Decimal("600.00"))
        self.assertEqual(conv.status, AffiliateConversion.Status.APPROVED)

        # Analytics separates CLICK / VIEW / SHARE
        SocialAttribution.objects.create(platform=SocialPlatform.INSTAGRAM, event_type="VIEW")
        SocialAttribution.objects.create(platform=SocialPlatform.INSTAGRAM, event_type="SHARE")
        SocialAttribution.objects.create(
            platform=SocialPlatform.INSTAGRAM,
            event_type="ORDER",
            order_no="ORD-PART-1",
            revenue_try=Decimal("6000.00"),
        )
        summary = get_social_analytics_summary()
        ig = next(c for c in summary["channels"] if c["platform"] == SocialPlatform.INSTAGRAM)
        self.assertEqual(ig["views"], 1)
        self.assertEqual(ig["shares"], 1)
        self.assertEqual(ig["clicks"], 0)

    def test_multi_event_webhook_and_tiktok_pinterest_catalog_sync(self):
        ch = SocialChannel.objects.create(
            platform=SocialPlatform.WHATSAPP,
            name="WA Batch",
            external_account_id="wa-batch-1",
        )
        secret = "wa-batch-sec"
        connect_social_channel(channel=ch, access_token="wa-tok", webhook_secret=secret)

        batch_payload = {
            "entry": [
                {
                    "id": "waba-batch",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "wa-batch-1"},
                                "messages": [
                                    {"from": "905550001111", "id": "wamid.b1", "text": {"body": "İlk mesaj"}},
                                    {"from": "905550002222", "id": "wamid.b2", "text": {"body": "İkinci mesaj"}},
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        raw = json.dumps(batch_payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        resp = self.client.post(
            "/api/v1/storefront/social/webhooks/whatsapp/",
            data=raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["processed"], 2)
        self.assertTrue(SocialInboxMessage.objects.filter(external_message_id="wamid.b1").exists())
        self.assertTrue(SocialInboxMessage.objects.filter(external_message_id="wamid.b2").exists())

        # TikTok & Pinterest catalog sync via real batch API payloads
        ch_tt = SocialChannel.objects.create(platform=SocialPlatform.TIKTOK, name="TT Cat")
        connect_social_channel(channel=ch_tt, access_token="tt-tok")
        cat_tt = SocialCatalog.objects.create(channel=ch_tt, name="TT Cat", external_catalog_id="tt-cat-1")
        tt_mock = MagicMock(status_code=200, content=b"{}")
        tt_mock.json.return_value = {"code": 0, "data": {"feed_id": "tt-feed-1"}}
        with patch("apps.social_commerce.adapters.tiktok.requests.post", return_value=tt_mock):
            tt_res = sync_social_catalog(cat_tt)
        self.assertEqual(tt_res["syncStatus"], SocialCatalog.SyncStatus.SYNCED)

        ch_pin = SocialChannel.objects.create(platform=SocialPlatform.PINTEREST, name="Pin Cat")
        connect_social_channel(channel=ch_pin, access_token="pin-tok")
        cat_pin = SocialCatalog.objects.create(channel=ch_pin, name="Pin Cat", external_catalog_id="pin-cat-1")
        pin_mock = MagicMock(status_code=200, content=b"{}")
        pin_mock.json.return_value = {"batch_id": "pin-batch-1"}
        with patch("apps.social_commerce.adapters.pinterest.requests.post", return_value=pin_mock):
            pin_res = sync_social_catalog(cat_pin)
        self.assertEqual(pin_res["syncStatus"], SocialCatalog.SyncStatus.SYNCED)
