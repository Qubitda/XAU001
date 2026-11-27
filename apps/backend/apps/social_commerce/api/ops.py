from __future__ import annotations

from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import IsOpsUser
from apps.catalog.models import ProductModel
from apps.common.responses import envelope_response

from ..adapters import get_adapter
from ..models import (
    AffiliateCode,
    AffiliateConversion,
    SocialAutomationRule,
    SocialCampaign,
    SocialCatalog,
    SocialChannel,
    SocialInboxConversation,
    SocialInfluencer,
    SocialMediaAsset,
    SocialPlatform,
    SocialPost,
    SocialPostChannel,
    SocialProductMapping,
    SocialWhatsAppTemplate,
)
from ..services import (
    SocialCommerceError,
    build_oauth_authorize_url,
    connect_social_channel,
    generate_catalog_feed_items,
    get_social_analytics_summary,
    handle_oauth_callback,
    publish_post_to_channel,
    refresh_channel_token,
    refresh_post_publish_status,
    reply_to_inbox_conversation,
    revoke_channel_connection,
    sync_social_catalog,
)


def _err_response(exc: SocialCommerceError, request: Request):
    return envelope_response(
        {"error": {"code": exc.code, "message": exc.message}},
        request=request,
        status=exc.status_code,
    )


def _serialize_channel(ch: SocialChannel) -> dict:
    conn = getattr(ch, "connection", None)
    caps = get_adapter(ch.platform).capabilities(ch.country_code).to_dict()
    return {
        "id": str(ch.id),
        "platform": ch.platform,
        "name": ch.name,
        "accountHandle": ch.account_handle,
        "externalAccountId": ch.external_account_id,
        "countryCode": ch.country_code,
        "isActive": ch.is_active,
        "connectionStatus": conn.status if conn else "PENDING_SETUP",
        "tokenExpiresAt": conn.token_expires_at.isoformat() if conn and conn.token_expires_at else None,
        "scopes": conn.scopes if conn else [],
        "lastSyncedAt": conn.last_synced_at.isoformat() if conn and conn.last_synced_at else None,
        "capabilities": caps,
        "createdAt": ch.created_at.isoformat(),
    }


class _ChannelCreateSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=SocialPlatform.choices)
    name = serializers.CharField(max_length=120)
    accountHandle = serializers.CharField(max_length=120, required=False, default="", allow_blank=True)
    externalAccountId = serializers.CharField(max_length=128, required=False, default="", allow_blank=True)
    countryCode = serializers.CharField(max_length=8, required=False, default="TR")


class _ChannelConnectSerializer(serializers.Serializer):
    accessToken = serializers.CharField(min_length=4, write_only=True)
    refreshToken = serializers.CharField(required=False, default="", allow_blank=True, write_only=True)
    webhookSecret = serializers.CharField(required=False, default="", allow_blank=True, write_only=True)
    scopes = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class OpsSocialChannelListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List connected social commerce channels")
    def get(self, request: Request):
        qs = SocialChannel.objects.select_related("connection").filter(organization__isnull=True)
        return envelope_response([_serialize_channel(c) for c in qs], request=request)

    @extend_schema(tags=["OPS Social"], summary="Create social commerce channel", request=_ChannelCreateSerializer)
    def post(self, request: Request):
        ser = _ChannelCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        caps = get_adapter(d["platform"]).capabilities(d["countryCode"])
        ch = SocialChannel.objects.create(
            platform=d["platform"],
            name=d["name"],
            account_handle=d["accountHandle"],
            external_account_id=d["externalAccountId"],
            country_code=d["countryCode"],
            supports_catalog_feed=caps.supports_catalog_feed,
            supports_direct_publish=caps.supports_direct_publish,
            supports_inbox_api=caps.supports_inbox_api,
            supports_in_app_shop=caps.supports_in_app_shop,
        )
        return envelope_response(_serialize_channel(ch), request=request, status=status.HTTP_201_CREATED)


class OpsSocialChannelConnectView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Store encrypted OAuth/API credentials", request=_ChannelConnectSerializer)
    def post(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        ser = _ChannelConnectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        connect_social_channel(
            channel=ch,
            access_token=d["accessToken"],
            refresh_token=d["refreshToken"],
            webhook_secret=d["webhookSecret"],
            scopes=d["scopes"],
            actor=request.user,
        )
        ch.refresh_from_db()
        return envelope_response(_serialize_channel(ch), request=request)


class OpsSocialChannelOAuthAuthorizeView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Generate OAuth authorize URL with CSRF state")
    def get(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        redirect_uri = str(request.query_params.get("redirectUri") or "").strip()
        if not redirect_uri:
            return envelope_response(
                {"error": {"code": "MISSING_REDIRECT_URI", "message": "redirectUri zorunludur."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return envelope_response(
                build_oauth_authorize_url(channel=ch, redirect_uri=redirect_uri),
                request=request,
            )
        except SocialCommerceError as exc:
            return _err_response(exc, request)


class OpsSocialChannelOAuthCallbackView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Exchange OAuth code for encrypted tokens")
    def post(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        code = str(request.data.get("code") or "").strip()
        state = str(request.data.get("state") or "").strip()
        redirect_uri = str(request.data.get("redirectUri") or "").strip()
        if not code or not state or not redirect_uri:
            return envelope_response(
                {"error": {"code": "VALIDATION_ERROR", "message": "code, state ve redirectUri zorunludur."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            handle_oauth_callback(
                channel=ch, code=code, state=state, redirect_uri=redirect_uri, actor=request.user
            )
            ch.refresh_from_db()
            return envelope_response(_serialize_channel(ch), request=request)
        except SocialCommerceError as exc:
            return _err_response(exc, request)


class OpsSocialChannelOAuthRefreshView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Refresh OAuth access token")
    def post(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        try:
            refresh_channel_token(channel=ch, actor=request.user)
            ch.refresh_from_db()
            return envelope_response(_serialize_channel(ch), request=request)
        except SocialCommerceError as exc:
            return _err_response(exc, request)


class OpsSocialChannelOAuthRevokeView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Revoke OAuth connection and clear encrypted tokens")
    def post(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        revoke_channel_connection(channel=ch, actor=request.user)
        ch.refresh_from_db()
        return envelope_response(_serialize_channel(ch), request=request)


class OpsSocialChannelCapabilitiesView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Get platform regional API capabilities")
    def get(self, request: Request, channel_id: str):
        ch = get_object_or_404(SocialChannel, id=channel_id)
        return envelope_response(
            get_adapter(ch.platform).capabilities(ch.country_code).to_dict(),
            request=request,
        )


class _CatalogCreateSerializer(serializers.Serializer):
    channelId = serializers.UUIDField()
    name = serializers.CharField(max_length=120)
    externalCatalogId = serializers.CharField(max_length=128, required=False, default="", allow_blank=True)


class OpsSocialCatalogListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List social product catalogs")
    def get(self, request: Request):
        qs = SocialCatalog.objects.select_related("channel").all()
        data = [
            {
                "id": str(cat.id),
                "channelId": str(cat.channel_id),
                "platform": cat.channel.platform,
                "name": cat.name,
                "externalCatalogId": cat.external_catalog_id,
                "syncStatus": cat.sync_status,
                "lastSyncedAt": cat.last_synced_at.isoformat() if cat.last_synced_at else None,
                "lastError": cat.last_error,
            }
            for cat in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create social product catalog", request=_CatalogCreateSerializer)
    def post(self, request: Request):
        ser = _CatalogCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ch = get_object_or_404(SocialChannel, id=d["channelId"])
        cat = SocialCatalog.objects.create(
            channel=ch,
            name=d["name"],
            external_catalog_id=d["externalCatalogId"],
        )
        return envelope_response(
            {"id": str(cat.id), "channelId": str(ch.id), "name": cat.name, "syncStatus": cat.sync_status},
            request=request,
            status=status.HTTP_201_CREATED,
        )


class OpsSocialCatalogSyncView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Sync central B2C products into social catalog")
    def post(self, request: Request, catalog_id: str):
        cat = get_object_or_404(SocialCatalog.objects.select_related("channel"), id=catalog_id)
        try:
            res = sync_social_catalog(cat, actor=request.user)
            return envelope_response(res, request=request)
        except SocialCommerceError as exc:
            return _err_response(exc, request)


class OpsSocialCatalogFeedView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Generate paginated blind-pool-safe social product feed")
    def get(self, request: Request, catalog_id: str):
        cat = get_object_or_404(SocialCatalog, id=catalog_id)
        limit = min(500, max(1, int(request.query_params.get("limit") or 200)))
        offset = max(0, int(request.query_params.get("offset") or 0))
        items = generate_catalog_feed_items(cat, limit=limit, offset=offset)
        return envelope_response(
            {"catalogId": str(cat.id), "limit": limit, "offset": offset, "items": items},
            request=request,
        )


class OpsSocialProductMappingListView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List product-to-channel mappings and sync errors")
    def get(self, request: Request):
        qs = SocialProductMapping.objects.select_related("catalog", "product")[:200]
        data = [
            {
                "id": str(m.id),
                "catalogId": str(m.catalog_id),
                "parentSku": m.product.parent_sku,
                "externalProductId": m.external_product_id,
                "syncStatus": m.sync_status,
                "rejectionReason": m.rejection_reason,
                "lastSyncedPriceTry": str(m.last_synced_price_try) if m.last_synced_price_try is not None else None,
                "lastSyncedAt": m.last_synced_at.isoformat() if m.last_synced_at else None,
            }
            for m in qs
        ]
        return envelope_response(data, request=request)


class _MediaAssetCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=64)
    formatKind = serializers.ChoiceField(choices=SocialMediaAsset.FormatKind.choices, default=SocialMediaAsset.FormatKind.IG_FEED_4_5)
    sourceUrl = serializers.URLField(max_length=512)
    outputUrl = serializers.URLField(max_length=512, required=False, default="", allow_blank=True)
    captionDraft = serializers.CharField(required=False, default="", allow_blank=True)
    hashtags = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class OpsSocialMediaAssetListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List social media assets (Content Studio)")
    def get(self, request: Request):
        qs = SocialMediaAsset.objects.select_related("product").all()[:100]
        data = [
            {
                "id": str(a.id),
                "parentSku": a.product.parent_sku,
                "formatKind": a.format_kind,
                "sourceUrl": a.source_url,
                "outputUrl": a.output_url,
                "captionDraft": a.caption_draft,
                "hashtags": a.hashtags,
                "isApproved": a.is_approved,
                "createdAt": a.created_at.isoformat(),
            }
            for a in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Register social media asset", request=_MediaAssetCreateSerializer)
    def post(self, request: Request):
        ser = _MediaAssetCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        product = get_object_or_404(ProductModel, parent_sku=d["parentSku"])
        asset = SocialMediaAsset.objects.create(
            product=product,
            format_kind=d["formatKind"],
            source_url=d["sourceUrl"],
            output_url=d["outputUrl"],
            caption_draft=d["captionDraft"],
            hashtags=d["hashtags"],
        )
        return envelope_response(
            {"id": str(asset.id), "formatKind": asset.format_kind, "sourceUrl": asset.source_url},
            request=request,
            status=status.HTTP_201_CREATED,
        )


class OpsSocialInboxDetailView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Get inbox conversation detail & message history")
    def get(self, request: Request, conversation_id: str):
        conv = get_object_or_404(SocialInboxConversation.objects.select_related("channel", "customer", "product"), id=conversation_id)
        msgs = [
            {
                "id": str(m.id),
                "direction": m.direction,
                "body": m.body,
                "deliveryStatus": m.delivery_status,
                "createdAt": m.created_at.isoformat(),
            }
            for m in conv.messages.all()[:200]
        ]
        return envelope_response(
            {
                "id": str(conv.id),
                "platform": conv.platform,
                "status": conv.status,
                "senderDisplayName": conv.sender_display_name,
                "senderPhone": conv.sender_phone,
                "messages": msgs,
            },
            request=request,
        )

    @extend_schema(tags=["OPS Social"], summary="Update inbox conversation status")
    def patch(self, request: Request, conversation_id: str):
        conv = get_object_or_404(SocialInboxConversation, id=conversation_id)
        next_status = str(request.data.get("status") or "").upper()
        if next_status and next_status in SocialInboxConversation.Status.values:
            conv.status = next_status
            conv.save(update_fields=["status", "updated_at"])
        return envelope_response({"id": str(conv.id), "status": conv.status}, request=request)


class _PostCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(required=False, default="", allow_blank=True)
    postType = serializers.ChoiceField(choices=SocialPost.PostType.choices, default=SocialPost.PostType.POST)
    title = serializers.CharField(max_length=200)
    caption = serializers.CharField(required=False, default="", allow_blank=True)
    hashtags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    mediaUrls = serializers.ListField(child=serializers.URLField(), required=False, default=list)
    targetUrl = serializers.URLField(required=False, default="", allow_blank=True)
    channelIds = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class OpsSocialPostListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List social posts & publishing targets")
    def get(self, request: Request):
        posts = SocialPost.objects.prefetch_related("channel_targets__channel").select_related("product")[:100]
        data = [
            {
                "id": str(p.id),
                "parentSku": p.product.parent_sku if p.product else None,
                "postType": p.post_type,
                "title": p.title,
                "caption": p.caption,
                "hashtags": p.hashtags,
                "mediaUrls": p.media_urls,
                "targets": [
                    {
                        "id": str(t.id),
                        "channelId": str(t.channel_id),
                        "platform": t.channel.platform,
                        "status": t.publish_status,
                        "scheduledAt": t.scheduled_at.isoformat() if t.scheduled_at else None,
                        "publishedAt": t.published_at.isoformat() if t.published_at else None,
                        "errorMessage": t.error_message,
                    }
                    for t in p.channel_targets.all()
                ],
            }
            for p in posts
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create social post draft", request=_PostCreateSerializer)
    def post(self, request: Request):
        ser = _PostCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        product = ProductModel.objects.filter(parent_sku=d["parentSku"]).first() if d["parentSku"] else None
        post = SocialPost.objects.create(
            product=product,
            post_type=d["postType"],
            title=d["title"],
            caption=d["caption"],
            hashtags=d["hashtags"],
            media_urls=d["mediaUrls"],
            target_url=d["targetUrl"],
            created_by=request.user,
        )
        for ch_id in d["channelIds"]:
            ch = SocialChannel.objects.filter(id=ch_id).first()
            if ch:
                SocialPostChannel.objects.get_or_create(post=post, channel=ch)
        return envelope_response(
            {"id": str(post.id), "title": post.title, "postType": post.post_type},
            request=request,
            status=status.HTTP_201_CREATED,
        )


class OpsSocialPostScheduleView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Schedule social post for channels")
    def post(self, request: Request, post_id: str):
        post = get_object_or_404(SocialPost, id=post_id)
        dt = parse_datetime(str(request.data.get("scheduledAt") or ""))
        if dt is None:
            return envelope_response(
                {"error": {"code": "INVALID_DATETIME", "message": "Geçerli ISO scheduledAt gereklidir."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = SocialPostChannel.objects.filter(post=post).update(
            publish_status=SocialPostChannel.PublishStatus.SCHEDULED,
            scheduled_at=dt,
        )
        return envelope_response({"postId": str(post.id), "scheduledTargets": updated}, request=request)


class OpsSocialPostPublishView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Publish social post to attached channels")
    def post(self, request: Request, post_id: str):
        post = get_object_or_404(SocialPost, id=post_id)
        targets = SocialPostChannel.objects.select_related("channel", "channel__connection", "post").filter(post=post)
        results = []
        for target in targets:
            res = publish_post_to_channel(target, actor=request.user)
            results.append(
                {
                    "targetId": str(res.id),
                    "platform": res.channel.platform,
                    "status": res.publish_status,
                    "errorMessage": res.error_message,
                }
            )
        return envelope_response({"postId": str(post.id), "results": results}, request=request)


class OpsSocialPostStatusRefreshView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Refresh async publish status (e.g., TikTok)")
    def post(self, request: Request, post_id: str):
        post = get_object_or_404(SocialPost, id=post_id)
        targets = SocialPostChannel.objects.select_related("channel", "channel__connection", "post").filter(post=post)
        results = []
        for target in targets:
            res = refresh_post_publish_status(target)
            results.append(
                {
                    "targetId": str(res.id),
                    "platform": res.channel.platform,
                    "status": res.publish_status,
                    "errorMessage": res.error_message,
                }
            )
        return envelope_response({"postId": str(post.id), "results": results}, request=request)


class OpsSocialInboxListView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List unified DM / WhatsApp inbox conversations")
    def get(self, request: Request):
        convs = SocialInboxConversation.objects.select_related("customer", "product", "channel")[:100]
        data = [
            {
                "id": str(c.id),
                "platform": c.platform,
                "status": c.status,
                "senderDisplayName": c.sender_display_name,
                "senderPhone": c.sender_phone,
                "customerId": str(c.customer_id) if c.customer_id else None,
                "parentSku": c.product.parent_sku if c.product else None,
                "lastMessageAt": c.last_message_at.isoformat() if c.last_message_at else None,
                "lastInboundAt": c.last_inbound_at.isoformat() if c.last_inbound_at else None,
            }
            for c in convs
        ]
        return envelope_response(data, request=request)


class OpsSocialInboxReplyView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Reply to social inbox conversation (consent + 24h window aware)")
    def post(self, request: Request, conversation_id: str):
        conv = get_object_or_404(SocialInboxConversation.objects.select_related("channel", "customer"), id=conversation_id)
        body = str(request.data.get("body") or "").strip()
        template_name = str(request.data.get("templateName") or "").strip()
        if not body and not template_name:
            return envelope_response(
                {"error": {"code": "EMPTY_BODY", "message": "Mesaj metni veya templateName gereklidir."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            msg = reply_to_inbox_conversation(
                conversation=conv,
                body=body,
                attached_product_sku=str(request.data.get("productSku") or ""),
                template_name=template_name,
                language_code=str(request.data.get("languageCode") or "tr"),
                actor=request.user,
            )
            return envelope_response(
                {"id": str(msg.id), "deliveryStatus": msg.delivery_status},
                request=request,
                status=status.HTTP_201_CREATED,
            )
        except SocialCommerceError as exc:
            return _err_response(exc, request)


class _WhatsAppTemplateCreateSerializer(serializers.Serializer):
    channelId = serializers.UUIDField()
    name = serializers.CharField(max_length=128)
    languageCode = serializers.CharField(max_length=16, required=False, default="tr")
    category = serializers.ChoiceField(choices=SocialWhatsAppTemplate.Category.choices, default=SocialWhatsAppTemplate.Category.UTILITY)


class OpsSocialWhatsAppTemplateListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List registered WhatsApp Business templates with Meta category")
    def get(self, request: Request):
        qs = SocialWhatsAppTemplate.objects.select_related("channel").all()[:100]
        data = [
            {
                "id": str(t.id),
                "channelId": str(t.channel_id),
                "name": t.name,
                "languageCode": t.language_code,
                "category": t.category,
                "status": t.status,
            }
            for t in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Register WhatsApp Business template (always created as PENDING)", request=_WhatsAppTemplateCreateSerializer)
    def post(self, request: Request):
        ser = _WhatsAppTemplateCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ch = get_object_or_404(SocialChannel, id=d["channelId"], platform=SocialPlatform.WHATSAPP)
        tpl, _ = SocialWhatsAppTemplate.objects.update_or_create(
            channel=ch,
            name=d["name"],
            language_code=d["languageCode"],
            defaults={"category": d["category"], "status": SocialWhatsAppTemplate.Status.PENDING},
        )
        return envelope_response(
            {
                "id": str(tpl.id),
                "channelId": str(tpl.channel_id),
                "name": tpl.name,
                "languageCode": tpl.language_code,
                "category": tpl.category,
                "status": tpl.status,
            },
            request=request,
            status=status.HTTP_201_CREATED,
        )


class OpsSocialWhatsAppTemplateApproveView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Audited OPS override to mark verified WhatsApp template APPROVED/REJECTED")
    def post(self, request: Request, template_id: str):
        tpl = get_object_or_404(SocialWhatsAppTemplate, id=template_id)
        next_status = str(request.data.get("status") or SocialWhatsAppTemplate.Status.APPROVED).upper()
        if next_status not in (
            SocialWhatsAppTemplate.Status.APPROVED,
            SocialWhatsAppTemplate.Status.REJECTED,
        ):
            return envelope_response(
                {"error": {"code": "INVALID_STATUS", "message": "status yalnızca APPROVED veya REJECTED olabilir."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        prev = tpl.status
        tpl.status = next_status
        tpl.save(update_fields=["status", "updated_at"])
        from apps.audit.services import record_audit

        record_audit(
            actor=request.user,
            action="social.whatsapp_template.status_updated",
            entity_type="SocialWhatsAppTemplate",
            entity_id=str(tpl.id),
            metadata={"from": prev, "to": next_status, "name": tpl.name},
        )
        return envelope_response(
            {"id": str(tpl.id), "name": tpl.name, "status": tpl.status},
            request=request,
        )


class _CampaignCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    code = serializers.CharField(max_length=48)
    audience = serializers.ChoiceField(choices=["B2C", "B2B"], default="B2C")
    channels = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    budgetTry = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    targetRevenueTry = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    discountPct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), default=Decimal("0.00"))


class OpsSocialCampaignListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List social campaigns")
    def get(self, request: Request):
        qs = SocialCampaign.objects.all()[:100]
        data = [
            {
                "id": str(c.id),
                "name": c.name,
                "code": c.code,
                "audience": c.audience,
                "channels": c.channels,
                "budgetTry": str(c.budget_try),
                "targetRevenueTry": str(c.target_revenue_try),
                "discountPct": str(c.discount_pct),
                "pricingApplied": c.discount_pct > 0,
                "isActive": c.is_active,
            }
            for c in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create social campaign", request=_CampaignCreateSerializer)
    def post(self, request: Request):
        ser = _CampaignCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        c = SocialCampaign.objects.create(
            name=d["name"].strip(),
            code=d["code"].strip().upper(),
            audience=d["audience"],
            channels=d["channels"],
            budget_try=d["budgetTry"],
            target_revenue_try=d["targetRevenueTry"],
            discount_pct=d["discountPct"],
        )
        return envelope_response({"id": str(c.id), "code": c.code}, request=request, status=status.HTTP_201_CREATED)


class _CampaignPatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, required=False)
    isActive = serializers.BooleanField(required=False)
    discountPct = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        required=False,
    )


class OpsSocialCampaignDetailView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Update social campaign", request=_CampaignPatchSerializer)
    def patch(self, request: Request, campaign_id: str):
        c = get_object_or_404(SocialCampaign, id=campaign_id)
        ser = _CampaignPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if "name" in d:
            c.name = d["name"].strip()
        if "isActive" in d:
            c.is_active = d["isActive"]
        if "discountPct" in d:
            c.discount_pct = d["discountPct"]
        c.save()
        from apps.audit.services import record_audit

        record_audit(
            actor=request.user,
            action="social.campaign.updated",
            entity_type="SocialCampaign",
            entity_id=str(c.id),
            metadata={"isActive": c.is_active, "discountPct": str(c.discount_pct)},
        )
        return envelope_response(
            {"id": str(c.id), "code": c.code, "isActive": c.is_active, "discountPct": str(c.discount_pct)},
            request=request,
        )

    @extend_schema(tags=["OPS Social"], summary="Archive (soft-delete) social campaign")
    def delete(self, request: Request, campaign_id: str):
        c = get_object_or_404(SocialCampaign, id=campaign_id)
        c.is_active = False
        c.save(update_fields=["is_active", "updated_at"])
        from apps.audit.services import record_audit

        record_audit(
            actor=request.user,
            action="social.campaign.archived",
            entity_type="SocialCampaign",
            entity_id=str(c.id),
            metadata={"code": c.code},
        )
        return envelope_response({"id": str(c.id), "isActive": False, "archived": True}, request=request)


class _InfluencerCreateSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=160)
    handle = serializers.CharField(max_length=120, required=False, default="", allow_blank=True)
    platform = serializers.ChoiceField(choices=SocialPlatform.choices, default=SocialPlatform.INSTAGRAM)
    followerCount = serializers.IntegerField(min_value=0, default=0)
    defaultCommissionPct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), default=Decimal("5.00"))


class OpsSocialInfluencerListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List influencers")
    def get(self, request: Request):
        qs = SocialInfluencer.objects.all()[:100]
        data = [
            {
                "id": str(i.id),
                "fullName": i.full_name,
                "handle": i.handle,
                "platform": i.platform,
                "followerCount": i.follower_count,
                "defaultCommissionPct": str(i.default_commission_pct),
                "isActive": i.is_active,
            }
            for i in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create influencer", request=_InfluencerCreateSerializer)
    def post(self, request: Request):
        ser = _InfluencerCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        inf = SocialInfluencer.objects.create(
            full_name=d["fullName"].strip(),
            handle=d["handle"],
            platform=d["platform"],
            follower_count=d["followerCount"],
            default_commission_pct=d["defaultCommissionPct"],
        )
        return envelope_response({"id": str(inf.id), "fullName": inf.full_name}, request=request, status=status.HTTP_201_CREATED)


class _AffiliateCodeCreateSerializer(serializers.Serializer):
    influencerId = serializers.UUIDField()
    code = serializers.CharField(max_length=40)
    commissionPct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), required=False)
    discountPct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.00"), max_value=Decimal("100.00"), default=Decimal("0.00"))


class OpsSocialAffiliateCodeListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List affiliate codes")
    def get(self, request: Request):
        qs = AffiliateCode.objects.select_related("influencer")[:100]
        data = [
            {
                "id": str(a.id),
                "code": a.code,
                "influencerId": str(a.influencer_id),
                "influencerName": a.influencer.full_name,
                "commissionPct": str(a.commission_pct),
                "discountPct": str(a.discount_pct),
                "isActive": a.is_active,
            }
            for a in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create affiliate code", request=_AffiliateCodeCreateSerializer)
    def post(self, request: Request):
        ser = _AffiliateCodeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        inf = get_object_or_404(SocialInfluencer, id=d["influencerId"])
        ac = AffiliateCode.objects.create(
            influencer=inf,
            code=d["code"].strip().upper(),
            commission_pct=d.get("commissionPct", inf.default_commission_pct),
            discount_pct=d["discountPct"],
        )
        return envelope_response({"id": str(ac.id), "code": ac.code}, request=request, status=status.HTTP_201_CREATED)


class OpsSocialAffiliateConversionListView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List affiliate conversions (excludes cancelled/refunded from net)")
    def get(self, request: Request):
        qs = AffiliateConversion.objects.select_related("affiliate_code")[:100]
        data = [
            {
                "id": str(c.id),
                "code": c.affiliate_code.code,
                "orderNo": c.order_no,
                "grossAmountTry": str(c.gross_amount_try),
                "netAmountTry": str(c.net_amount_try),
                "commissionAmountTry": str(c.commission_amount_try),
                "status": c.status,
            }
            for c in qs
        ]
        return envelope_response(data, request=request)


class OpsSocialAnalyticsSalesView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Social commerce sales & channel analytics")
    def get(self, request: Request):
        return envelope_response(get_social_analytics_summary(), request=request)


class OpsSocialAutomationDetailView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="Toggle/update social automation rule")
    def patch(self, request: Request, rule_id: str):
        rule = get_object_or_404(SocialAutomationRule, id=rule_id)
        if "isActive" in request.data:
            rule.is_active = bool(request.data["isActive"])
        if "actionConfig" in request.data and isinstance(request.data["actionConfig"], dict):
            rule.action_config = request.data["actionConfig"]
        rule.save()
        return envelope_response({"id": str(rule.id), "isActive": rule.is_active}, request=request)

    @extend_schema(tags=["OPS Social"], summary="Delete social automation rule")
    def delete(self, request: Request, rule_id: str):
        rule = get_object_or_404(SocialAutomationRule, id=rule_id)
        rule.delete()
        return envelope_response({"deleted": True}, request=request)


class OpsSocialAutomationListCreateView(APIView):
    permission_classes = [IsOpsUser]

    @extend_schema(tags=["OPS Social"], summary="List consent-aware automation rules")
    def get(self, request: Request):
        qs = SocialAutomationRule.objects.all()
        data = [
            {
                "id": str(r.id),
                "name": r.name,
                "triggerEvent": r.trigger_event,
                "channel": r.channel,
                "requiresConsent": r.requires_consent,
                "isActive": r.is_active,
            }
            for r in qs
        ]
        return envelope_response(data, request=request)

    @extend_schema(tags=["OPS Social"], summary="Create consent-aware automation rule")
    def post(self, request: Request):
        name = str(request.data.get("name") or "").strip()
        trigger = str(request.data.get("triggerEvent") or "").strip()
        if not name or not trigger:
            return envelope_response(
                {"error": {"code": "VALIDATION_ERROR", "message": "name ve triggerEvent zorunludur."}},
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )
        rule = SocialAutomationRule.objects.create(
            name=name,
            trigger_event=trigger,
            channel=str(request.data.get("channel") or SocialPlatform.WHATSAPP).upper(),
            requires_consent=bool(request.data.get("requiresConsent", True)),
            template_key=str(request.data.get("templateKey") or ""),
        )
        return envelope_response({"id": str(rule.id), "name": rule.name}, request=request, status=status.HTTP_201_CREATED)
