from django.contrib import admin

from apps.common.admin import (
    ImmutableAdminMixin,
    NoDeleteAdminMixin,
    OpsRestrictedAdminMixin,
    ReadOnlyInlineMixin,
)

from .models import (
    AffiliateCode,
    AffiliateConversion,
    SocialAttribution,
    SocialAutomationRule,
    SocialCampaign,
    SocialCampaignProduct,
    SocialCatalog,
    SocialChannel,
    SocialConnection,
    SocialInboxConversation,
    SocialInboxMessage,
    SocialInfluencer,
    SocialMediaAsset,
    SocialPost,
    SocialPostChannel,
    SocialProductMapping,
    SocialWhatsAppTemplate,
)

_ENCRYPTED_TOKEN_FIELDS = (
    "access_token_encrypted",
    "refresh_token_encrypted",
    "webhook_secret_encrypted",
)


class SocialConnectionInline(ReadOnlyInlineMixin, admin.StackedInline):
    model = SocialConnection
    exclude = _ENCRYPTED_TOKEN_FIELDS
    readonly_fields = ("status", "token_expires_at", "scopes", "last_synced_at", "last_error")


class SocialPostChannelInline(admin.TabularInline):
    model = SocialPostChannel
    extra = 0
    fields = ("channel", "publish_status", "scheduled_at", "published_at", "external_post_id")
    readonly_fields = ("published_at", "external_post_id")


class SocialInboxMessageInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = SocialInboxMessage
    fields = ("direction", "external_message_id", "body", "delivery_status", "created_at")
    readonly_fields = fields


class SocialCampaignProductInline(admin.TabularInline):
    model = SocialCampaignProduct
    extra = 0
    autocomplete_fields = ("product",)


class AffiliateCodeInline(admin.TabularInline):
    model = AffiliateCode
    extra = 0
    fields = ("code", "campaign", "commission_pct", "discount_pct", "is_active")


@admin.register(SocialChannel)
class SocialChannelAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "platform", "organization", "account_handle", "country_code", "is_active")
    list_filter = ("platform", "is_active", "country_code")
    search_fields = ("name", "account_handle", "external_account_id", "organization__code")
    list_select_related = ("organization",)
    inlines = (SocialConnectionInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialConnection)
class SocialConnectionAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("channel", "status", "token_expires_at", "last_synced_at", "updated_at")
    list_filter = ("status", "channel__platform")
    search_fields = ("channel__name", "channel__external_account_id")
    list_select_related = ("channel",)
    exclude = _ENCRYPTED_TOKEN_FIELDS
    readonly_fields = ("id", "channel", "status", "token_expires_at", "scopes", "last_synced_at", "last_error", "created_at", "updated_at")


@admin.register(SocialCatalog)
class SocialCatalogAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "channel", "audience", "sync_status", "last_synced_at", "is_active")
    list_filter = ("audience", "sync_status", "is_active")
    search_fields = ("name", "external_catalog_id", "channel__name")
    list_select_related = ("channel",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialProductMapping)
class SocialProductMappingAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("catalog", "product", "sync_status", "last_synced_price_try", "last_synced_stock_qty", "last_synced_at")
    list_filter = ("sync_status", "catalog__audience")
    search_fields = ("product__parent_sku", "external_product_id", "catalog__name")
    list_select_related = ("catalog", "product")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialMediaAsset)
class SocialMediaAssetAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "format_kind", "is_approved", "created_at")
    list_filter = ("format_kind", "is_approved")
    search_fields = ("product__parent_sku", "source_url")
    list_select_related = ("product",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialPost)
class SocialPostAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "post_type", "product", "created_by", "created_at")
    list_filter = ("post_type", "created_at")
    search_fields = ("title", "caption", "product__parent_sku")
    list_select_related = ("product", "created_by")
    inlines = (SocialPostChannelInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialPostChannel)
class SocialPostChannelAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("post", "channel", "publish_status", "scheduled_at", "published_at")
    list_filter = ("publish_status", "channel__platform")
    search_fields = ("post__title", "channel__name", "external_post_id")
    list_select_related = ("post", "channel")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialInboxConversation)
class SocialInboxConversationAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("platform", "sender_display_name", "sender_phone", "customer", "status", "last_message_at")
    list_filter = ("platform", "status")
    search_fields = ("sender_display_name", "sender_phone", "external_thread_id", "customer__full_name")
    list_select_related = ("channel", "customer", "product", "assigned_to")
    inlines = (SocialInboxMessageInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialInboxMessage)
class SocialInboxMessageAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("conversation", "direction", "external_message_id", "delivery_status", "created_at")
    list_filter = ("direction", "delivery_status")
    search_fields = ("body", "external_message_id", "conversation__external_thread_id")
    list_select_related = ("conversation", "attached_product", "sent_by")
    readonly_fields = tuple(f.name for f in SocialInboxMessage._meta.fields)


@admin.register(SocialWhatsAppTemplate)
class SocialWhatsAppTemplateAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "channel", "language_code", "category", "status", "updated_at")
    list_filter = ("category", "status", "language_code")
    search_fields = ("name",)
    list_select_related = ("channel",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialCampaign)
class SocialCampaignAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "audience", "organization", "discount_pct", "is_active", "starts_at", "ends_at")
    list_filter = ("audience", "is_active")
    search_fields = ("code", "name", "organization__code")
    list_select_related = ("organization",)
    inlines = (SocialCampaignProductInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialCampaignProduct)
class SocialCampaignProductAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("campaign", "product", "created_at")
    search_fields = ("campaign__code", "product__parent_sku")
    list_select_related = ("campaign", "product")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SocialInfluencer)
class SocialInfluencerAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("full_name", "handle", "platform", "follower_count", "default_commission_pct", "is_active")
    list_filter = ("platform", "is_active")
    search_fields = ("full_name", "handle")
    inlines = (AffiliateCodeInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AffiliateCode)
class AffiliateCodeAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("code", "influencer", "campaign", "commission_pct", "discount_pct", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "influencer__full_name", "campaign__code")
    list_select_related = ("influencer", "campaign")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AffiliateConversion)
class AffiliateConversionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("order_no", "affiliate_code", "audience", "gross_amount_try", "net_amount_try", "commission_amount_try", "status", "created_at")
    list_filter = ("status", "audience")
    search_fields = ("order_no", "affiliate_code__code")
    list_select_related = ("affiliate_code",)
    date_hierarchy = "created_at"
    readonly_fields = tuple(f.name for f in AffiliateConversion._meta.fields)


@admin.register(SocialAttribution)
class SocialAttributionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("platform", "event_type", "touch_role", "order_no", "revenue_try", "audience", "created_at")
    list_filter = ("platform", "event_type", "touch_role", "audience")
    search_fields = ("order_no", "utm_campaign", "session_key")
    list_select_related = ("product", "campaign", "customer")
    date_hierarchy = "created_at"
    readonly_fields = tuple(f.name for f in SocialAttribution._meta.fields)


@admin.register(SocialAutomationRule)
class SocialAutomationRuleAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "trigger_event", "channel", "requires_consent", "is_active", "updated_at")
    list_filter = ("channel", "requires_consent", "is_active")
    search_fields = ("name", "trigger_event")
    readonly_fields = ("id", "created_at", "updated_at")
