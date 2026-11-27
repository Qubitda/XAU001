from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.api_keys.ops_api import OpsApiKeyListCreateView, OpsApiKeyRevokeView
from apps.webhooks.ops_api import OpsWebhookListCreateView, OpsWebhookRevokeView
from apps.common.health import HealthView
from apps.accounts.api import (
    SessionContextSwitchView,
    SessionDetailView,
    SessionLoginView,
    SessionLogoutView,
)
from apps.accounts.auth_api import (
    B2cRegisterView,
    EmailResendVerificationView,
    EmailVerifyView,
    PasswordChangeView,
    PasswordForgotView,
    PasswordResetView,
)
from apps.accounts.ops_api import (
    OpsRolesMetadataView,
    OpsUserDetailView,
    OpsUserListCreateView,
)
from apps.audit.api import OpsAuditLogDetailView, OpsAuditLogListView
from apps.commerce.api import (
    B2bDraftLineDetailView,
    B2bDraftLinesView,
    B2bDraftView,
    B2bOrderReorderView,
    B2bOrdersView,
    OpsB2bOrderStatusView,
    OpsB2cOrderStatusView,
    B2bDraftProformaPdfView,
    B2bOrderProformaPdfView,
    StorefrontCartItemDetailView,
    StorefrontCartItemsView,
    StorefrontCartRefreshLockView,
    StorefrontCartView,
    StorefrontGuestCartRecoveryLeadView,
    StorefrontOrdersView,
)
from apps.commerce.dyo_api import (
    B2bCompatibleStonesView,
    B2bDyoBundleCreateView,
    CompatibleStonesView,
    DyoBundleCreateView,
    DyoBundleDetailView,
    DyoValidateView,
)
from django.conf import settings as django_settings

from apps.mail.ops_api import (
    OpsEmailTemplatesView,
    OpsMailLogRetryView,
    OpsMailLogsView,
    OpsSmtpSettingsView,
    OpsSmtpTestMailView,
    OpsSmtpConnectionTestView,
)
from apps.commerce.ops_api import (
    OpsB2bOrderDetailView,
    OpsB2bOrderListView,
    OpsB2cOrderDetailView,
    OpsB2cOrderListView,
)
from apps.commerce.recovery_api import OpsSalesTaskDetailView, OpsSalesTaskListView
from apps.commerce.cart_ops_api import OpsB2cCartDetailView, OpsB2cCartListView, OpsCustomerCartsView
from apps.common.admin import configure_admin_site
from apps.customers.api import (
    OpsCustomerAddressDetailView,
    OpsCustomerAddressListCreateView,
    OpsCustomerDetailView,
    OpsCustomerListCreateView,
)
from apps.customers.ops_360_api import (
    OpsCustomer360DashboardView,
    OpsCustomer360DetailView,
    OpsCustomerAuditView,
    OpsCustomerConsentsView,
    OpsCustomerContractsView,
    OpsLegalDocumentListCreateView,
)
from apps.customers.storefront_api import (
    StorefrontAddressDetailView,
    StorefrontAddressListCreateView,
    StorefrontProfileView,
)
from apps.integrations.api import (
    B2cIntegrationCartsView,
    B2cIntegrationConsentsView,
    B2cIntegrationContractsView,
    B2cIntegrationCustomersView,
    B2cIntegrationEventsView,
)
from apps.contracts.storefront_api import (
    StorefrontLegalDocumentDetailView,
    StorefrontLegalDocumentListView,
    StorefrontNewsletterSubscribeView,
)
from apps.finance.b2b_api import B2bLedgerListView
from apps.organizations.b2b_api import (
    B2bApplicationCreateView,
    B2bOrganizationPatchView,
    B2bOrganizationUserDetailView,
    B2bOrganizationUsersView,
)
from apps.contracts.ops_api import OpsIysConsentExportView, OpsLegalDocumentDetailView
from apps.messaging.ops_api import OpsMessagingLogListView, OpsMessagingStatusView
from apps.organizations.site_contact_api import OpsSiteContactView, StorefrontSiteContactView
from apps.finance.api import OpsDealerLedgerDetailView, OpsDealerLedgerListCreateView
from apps.market.api import (
    MarketRatesView,
    OpsRateSnapshotDetailView,
    OpsRateSnapshotListCreateView,
    OpsRatesUpdateView,
)
from apps.notifications.api import (
    OpsNotificationDetailView,
    OpsNotificationListCreateView,
)
from apps.notifications.storefront_api import (
    StorefrontNotificationDetailView,
    StorefrontNotificationListView,
    StorefrontNotificationReadAllView,
)
from apps.organizations.api import (
    OpsBranchDetailView,
    OpsBranchListCreateView,
    OpsMembershipDetailView,
    OpsMembershipListCreateView,
    OpsOrganizationDetailView,
    OpsOrganizationListCreateView,
)
from apps.organizations.partner_api import (
    OpsOrganizationAddressDetailView,
    OpsOrganizationAddressListCreateView,
    OpsOrganizationBankDetailView,
    OpsOrganizationBankListCreateView,
    OpsOrganizationCreditReviewView,
    OpsOrganizationDetailRichView,
    OpsOrganizationDocumentDetailView,
    OpsOrganizationDocumentFileView,
    OpsOrganizationDocumentListCreateView,
    OpsOrganizationLogoView,
)
from apps.pricing.api import (
    BuyerQuoteCreateView,
    OpsRecipeEvaluateView,
    OpsRecipePublishView,
)
from apps.pricing.ops_api import (
    OpsChannelRuleDetailView,
    OpsChannelRuleListCreateView,
    OpsCostLineDetailView,
    OpsCostLineListCreateView,
    OpsPriceLockListView,
    OpsPriceQuoteListView,
    OpsPricingRecipeDetailView,
    OpsPricingRecipeListCreateView,
)
from apps.production.api import (
    OpsWorkOrderDetailView,
    OpsWorkOrderListCreateView,
    OpsWorkOrderStatusView,
)

configure_admin_site()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", HealthView.as_view(), name="health"),
    path("api/v1/health", HealthView.as_view(), name="api-health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Session
    path("api/v1/session", SessionDetailView.as_view(), name="session"),
    path("api/v1/session/context", SessionContextSwitchView.as_view(), name="session-context"),
    path("api/v1/session/login", SessionLoginView.as_view(), name="session-login"),
    path("api/v1/session/logout", SessionLogoutView.as_view(), name="session-logout"),
    # Account lifecycle (B2C self-serve + password / email verification)
    path("api/v1/auth/register", B2cRegisterView.as_view(), name="auth-register"),
    path("api/v1/auth/password/change", PasswordChangeView.as_view(), name="auth-password-change"),
    path("api/v1/auth/password/forgot", PasswordForgotView.as_view(), name="auth-password-forgot"),
    path("api/v1/auth/password/reset", PasswordResetView.as_view(), name="auth-password-reset"),
    path("api/v1/auth/email/verify", EmailVerifyView.as_view(), name="auth-email-verify"),
    path("api/v1/auth/email/resend", EmailResendVerificationView.as_view(), name="auth-email-resend"),
    path("api/v1/market/rates", MarketRatesView.as_view(), name="market-rates"),
    # Domain route modules
    path("", include("apps.catalog.urls")),
    path("", include("apps.definitions.urls")),
    path("", include("apps.inventory.urls")),
    # Storefront commerce
    path(
        "api/v1/storefront/legal-documents",
        StorefrontLegalDocumentListView.as_view(),
        name="storefront-legal-documents",
    ),
    path(
        "api/v1/storefront/legal-documents/<str:code>",
        StorefrontLegalDocumentDetailView.as_view(),
        name="storefront-legal-document",
    ),
    path(
        "api/v1/storefront/newsletter",
        StorefrontNewsletterSubscribeView.as_view(),
        name="storefront-newsletter",
    ),
    path(
        "api/v1/storefront/site-contact",
        StorefrontSiteContactView.as_view(),
        name="storefront-site-contact",
    ),
    path("api/v1/storefront/profile", StorefrontProfileView.as_view(), name="storefront-profile"),
    path(
        "api/v1/storefront/addresses",
        StorefrontAddressListCreateView.as_view(),
        name="storefront-addresses",
    ),
    path(
        "api/v1/storefront/addresses/<uuid:address_id>",
        StorefrontAddressDetailView.as_view(),
        name="storefront-address-detail",
    ),
    path("api/v1/storefront/cart", StorefrontCartView.as_view(), name="storefront-cart"),
    path("api/v1/storefront/cart/items", StorefrontCartItemsView.as_view(), name="storefront-cart-items"),
    path(
        "api/v1/storefront/cart/items/<str:item_id>",
        StorefrontCartItemDetailView.as_view(),
        name="storefront-cart-item-detail",
    ),
    path(
        "api/v1/storefront/cart/refresh-lock",
        StorefrontCartRefreshLockView.as_view(),
        name="storefront-cart-refresh-lock",
    ),
    path(
        "api/v1/storefront/cart/recovery-lead",
        StorefrontGuestCartRecoveryLeadView.as_view(),
        name="storefront-cart-recovery-lead",
    ),
    path(
        "api/v1/storefront/notifications",
        StorefrontNotificationListView.as_view(),
        name="storefront-notifications",
    ),
    path(
        "api/v1/storefront/notifications/read-all",
        StorefrontNotificationReadAllView.as_view(),
        name="storefront-notifications-read-all",
    ),
    path(
        "api/v1/storefront/notifications/<uuid:notification_id>",
        StorefrontNotificationDetailView.as_view(),
        name="storefront-notification-detail",
    ),
    path("api/v1/storefront/orders", StorefrontOrdersView.as_view(), name="storefront-orders"),
    path("api/v1/storefront/quotes", BuyerQuoteCreateView.as_view(), name="storefront-quotes"),
    path(
        "api/v1/storefront/dyo/compatible-stones",
        CompatibleStonesView.as_view(),
        name="storefront-dyo-stones",
    ),
    path("api/v1/storefront/dyo/validate", DyoValidateView.as_view(), name="storefront-dyo-validate"),
    path("api/v1/storefront/dyo/bundles", DyoBundleCreateView.as_view(), name="storefront-dyo-bundles"),
    path(
        "api/v1/storefront/dyo/bundles/<uuid:bundle_id>",
        DyoBundleDetailView.as_view(),
        name="storefront-dyo-bundle",
    ),
    # B2B commerce
    path("api/v1/b2b/quotes", BuyerQuoteCreateView.as_view(), name="b2b-quotes"),
    path("api/v1/b2b/dyo/compatible-stones", B2bCompatibleStonesView.as_view(), name="b2b-dyo-stones"),
    path("api/v1/b2b/dyo/validate", DyoValidateView.as_view(), name="b2b-dyo-validate"),
    path("api/v1/b2b/dyo/bundles", B2bDyoBundleCreateView.as_view(), name="b2b-dyo-bundles"),
    path("api/v1/b2b/dyo/bundles/<uuid:bundle_id>", DyoBundleDetailView.as_view(), name="b2b-dyo-bundle"),
    path("api/v1/b2b/draft", B2bDraftView.as_view(), name="b2b-draft"),
    path(
        "api/v1/b2b/draft/proforma.pdf",
        B2bDraftProformaPdfView.as_view(),
        name="b2b-draft-proforma-pdf",
    ),
    path("api/v1/b2b/draft/lines", B2bDraftLinesView.as_view(), name="b2b-draft-lines"),
    path(
        "api/v1/b2b/draft/lines/<str:line_id>",
        B2bDraftLineDetailView.as_view(),
        name="b2b-draft-line-detail",
    ),
    path("api/v1/b2b/orders", B2bOrdersView.as_view(), name="b2b-orders"),
    path(
        "api/v1/b2b/orders/<str:order_no>/proforma.pdf",
        B2bOrderProformaPdfView.as_view(),
        name="b2b-order-proforma-pdf",
    ),
    path(
        "api/v1/b2b/orders/<str:order_no>/reorder",
        B2bOrderReorderView.as_view(),
        name="b2b-order-reorder",
    ),
    path("api/v1/b2b/applications", B2bApplicationCreateView.as_view(), name="b2b-applications"),
    path("api/v1/b2b/ledger", B2bLedgerListView.as_view(), name="b2b-ledger"),
    path("api/v1/b2b/organization", B2bOrganizationPatchView.as_view(), name="b2b-organization"),
    path("api/v1/b2b/organization/users", B2bOrganizationUsersView.as_view(), name="b2b-organization-users"),
    path(
        "api/v1/b2b/organization/users/<uuid:membership_id>",
        B2bOrganizationUserDetailView.as_view(),
        name="b2b-organization-user-detail",
    ),
    # OPS — users / orgs / customers
    path("api/v1/ops/users", OpsUserListCreateView.as_view(), name="ops-users"),
    path("api/v1/ops/users/<uuid:user_id>", OpsUserDetailView.as_view(), name="ops-user-detail"),
    path("api/v1/ops/roles", OpsRolesMetadataView.as_view(), name="ops-roles"),
    path("api/v1/ops/api-keys", OpsApiKeyListCreateView.as_view(), name="ops-api-keys"),
    path(
        "api/v1/ops/api-keys/<uuid:key_id>/revoke",
        OpsApiKeyRevokeView.as_view(),
        name="ops-api-key-revoke",
    ),
    path("api/v1/ops/webhooks", OpsWebhookListCreateView.as_view(), name="ops-webhooks"),
    path(
        "api/v1/ops/webhooks/<uuid:endpoint_id>/revoke",
        OpsWebhookRevokeView.as_view(),
        name="ops-webhook-revoke",
    ),
    path("api/v1/ops/organizations", OpsOrganizationListCreateView.as_view(), name="ops-organizations"),
    path(
        "api/v1/ops/organizations/<uuid:org_id>",
        OpsOrganizationDetailView.as_view(),
        name="ops-organization-detail",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/dossier",
        OpsOrganizationDetailRichView.as_view(),
        name="ops-organization-dossier",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/logo",
        OpsOrganizationLogoView.as_view(),
        name="ops-organization-logo",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/addresses",
        OpsOrganizationAddressListCreateView.as_view(),
        name="ops-organization-addresses",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/addresses/<uuid:address_id>",
        OpsOrganizationAddressDetailView.as_view(),
        name="ops-organization-address-detail",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/bank-accounts",
        OpsOrganizationBankListCreateView.as_view(),
        name="ops-organization-banks",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/bank-accounts/<uuid:account_id>",
        OpsOrganizationBankDetailView.as_view(),
        name="ops-organization-bank-detail",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/documents",
        OpsOrganizationDocumentListCreateView.as_view(),
        name="ops-organization-documents",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/documents/<uuid:document_id>",
        OpsOrganizationDocumentDetailView.as_view(),
        name="ops-organization-document-detail",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/documents/<uuid:document_id>/file",
        OpsOrganizationDocumentFileView.as_view(),
        name="ops-organization-document-file",
    ),
    path(
        "api/v1/ops/organizations/<uuid:org_id>/credit-review",
        OpsOrganizationCreditReviewView.as_view(),
        name="ops-organization-credit-review",
    ),
    path("api/v1/ops/branches", OpsBranchListCreateView.as_view(), name="ops-branches"),
    path("api/v1/ops/branches/<uuid:branch_id>", OpsBranchDetailView.as_view(), name="ops-branch-detail"),
    path("api/v1/ops/memberships", OpsMembershipListCreateView.as_view(), name="ops-memberships"),
    path(
        "api/v1/ops/memberships/<uuid:membership_id>",
        OpsMembershipDetailView.as_view(),
        name="ops-membership-detail",
    ),
    path("api/v1/ops/customers", OpsCustomerListCreateView.as_view(), name="ops-customers"),
    path(
        "api/v1/ops/customer-360/dashboard",
        OpsCustomer360DashboardView.as_view(),
        name="ops-customer-360-dashboard",
    ),
    path(
        "api/v1/ops/legal-documents",
        OpsLegalDocumentListCreateView.as_view(),
        name="ops-legal-documents",
    ),
    path(
        "api/v1/ops/legal-documents/<uuid:document_id>",
        OpsLegalDocumentDetailView.as_view(),
        name="ops-legal-document-detail",
    ),
    path(
        "api/v1/ops/site-contact",
        OpsSiteContactView.as_view(),
        name="ops-site-contact",
    ),
    path(
        "api/v1/ops/consents/iys-export",
        OpsIysConsentExportView.as_view(),
        name="ops-consents-iys-export",
    ),
    path(
        "api/v1/ops/messaging/status",
        OpsMessagingStatusView.as_view(),
        name="ops-messaging-status",
    ),
    path(
        "api/v1/ops/messaging/logs",
        OpsMessagingLogListView.as_view(),
        name="ops-messaging-logs",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>",
        OpsCustomerDetailView.as_view(),
        name="ops-customer-detail",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/360",
        OpsCustomer360DetailView.as_view(),
        name="ops-customer-360",
    ),
    path("api/v1/ops/carts", OpsB2cCartListView.as_view(), name="ops-b2c-carts"),
    path(
        "api/v1/ops/carts/<uuid:cart_id>",
        OpsB2cCartDetailView.as_view(),
        name="ops-b2c-cart-detail",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/carts",
        OpsCustomerCartsView.as_view(),
        name="ops-customer-carts",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/consents",
        OpsCustomerConsentsView.as_view(),
        name="ops-customer-consents",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/contracts",
        OpsCustomerContractsView.as_view(),
        name="ops-customer-contracts",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/audit",
        OpsCustomerAuditView.as_view(),
        name="ops-customer-audit",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/addresses",
        OpsCustomerAddressListCreateView.as_view(),
        name="ops-customer-addresses",
    ),
    path(
        "api/v1/ops/customers/<uuid:customer_id>/addresses/<uuid:address_id>",
        OpsCustomerAddressDetailView.as_view(),
        name="ops-customer-address-detail",
    ),
    # B2C → OPS integrations inbox
    path(
        "api/v1/integrations/b2c/events/",
        B2cIntegrationEventsView.as_view(),
        name="integrations-b2c-events",
    ),
    path(
        "api/v1/integrations/b2c/customers/",
        B2cIntegrationCustomersView.as_view(),
        name="integrations-b2c-customers",
    ),
    path(
        "api/v1/integrations/b2c/consents/",
        B2cIntegrationConsentsView.as_view(),
        name="integrations-b2c-consents",
    ),
    path(
        "api/v1/integrations/b2c/contracts/",
        B2cIntegrationContractsView.as_view(),
        name="integrations-b2c-contracts",
    ),
    path(
        "api/v1/integrations/b2c/carts/",
        B2cIntegrationCartsView.as_view(),
        name="integrations-b2c-carts",
    ),
    # OPS — pricing / market
    path("api/v1/ops/pricing/recipes", OpsPricingRecipeListCreateView.as_view(), name="ops-pricing-recipes"),
    path(
        "api/v1/ops/pricing/recipes/<uuid:recipe_id>",
        OpsPricingRecipeDetailView.as_view(),
        name="ops-pricing-recipe-detail",
    ),
    path(
        "api/v1/ops/pricing/recipes/<str:recipe_id>/evaluate",
        OpsRecipeEvaluateView.as_view(),
        name="ops-recipe-evaluate",
    ),
    path(
        "api/v1/ops/pricing/recipes/<str:recipe_id>/publish",
        OpsRecipePublishView.as_view(),
        name="ops-recipe-publish",
    ),
    path(
        "api/v1/ops/pricing/recipes/<uuid:recipe_id>/cost-lines",
        OpsCostLineListCreateView.as_view(),
        name="ops-recipe-cost-lines",
    ),
    path(
        "api/v1/ops/pricing/cost-lines/<uuid:cost_line_id>",
        OpsCostLineDetailView.as_view(),
        name="ops-cost-line-detail",
    ),
    path(
        "api/v1/ops/pricing/recipes/<uuid:recipe_id>/channel-rules",
        OpsChannelRuleListCreateView.as_view(),
        name="ops-recipe-channel-rules",
    ),
    path(
        "api/v1/ops/pricing/channel-rules/<uuid:rule_id>",
        OpsChannelRuleDetailView.as_view(),
        name="ops-channel-rule-detail",
    ),
    path("api/v1/ops/pricing/quotes", OpsPriceQuoteListView.as_view(), name="ops-pricing-quotes"),
    path("api/v1/ops/pricing/locks", OpsPriceLockListView.as_view(), name="ops-pricing-locks"),
    path("api/v1/ops/rates", OpsRatesUpdateView.as_view(), name="ops-rates"),
    path("api/v1/ops/rates/snapshots", OpsRateSnapshotListCreateView.as_view(), name="ops-rate-snapshots"),
    path(
        "api/v1/ops/rates/snapshots/<str:snapshot_id>",
        OpsRateSnapshotDetailView.as_view(),
        name="ops-rate-snapshot-detail",
    ),
    # OPS — orders / production / finance / notifications / audit
    path("api/v1/ops/b2c-orders", OpsB2cOrderListView.as_view(), name="ops-b2c-orders"),
    path(
        "api/v1/ops/b2c-orders/<str:order_no>",
        OpsB2cOrderDetailView.as_view(),
        name="ops-b2c-order-detail",
    ),
    path(
        "api/v1/ops/b2c-orders/<str:order_no>/status",
        OpsB2cOrderStatusView.as_view(),
        name="ops-b2c-order-status",
    ),
    path("api/v1/ops/b2b-orders", OpsB2bOrderListView.as_view(), name="ops-b2b-orders"),
    path(
        "api/v1/ops/b2b-orders/<str:order_no>",
        OpsB2bOrderDetailView.as_view(),
        name="ops-b2b-order-detail",
    ),
    path(
        "api/v1/ops/b2b-orders/<str:order_no>/status",
        OpsB2bOrderStatusView.as_view(),
        name="ops-b2b-order-status",
    ),
    path("api/v1/ops/work-orders", OpsWorkOrderListCreateView.as_view(), name="ops-work-orders"),
    path(
        "api/v1/ops/work-orders/<str:work_order_id>",
        OpsWorkOrderDetailView.as_view(),
        name="ops-work-order-detail",
    ),
    path(
        "api/v1/ops/work-orders/<str:work_order_id>/status",
        OpsWorkOrderStatusView.as_view(),
        name="ops-work-order-status",
    ),
    path("api/v1/ops/ledger", OpsDealerLedgerListCreateView.as_view(), name="ops-ledger"),
    path("api/v1/ops/ledger/<uuid:entry_id>", OpsDealerLedgerDetailView.as_view(), name="ops-ledger-detail"),
    path("api/v1/ops/notifications", OpsNotificationListCreateView.as_view(), name="ops-notifications"),
    path(
        "api/v1/ops/notifications/<uuid:notification_id>",
        OpsNotificationDetailView.as_view(),
        name="ops-notification-detail",
    ),
    path("api/v1/ops/sales-tasks", OpsSalesTaskListView.as_view(), name="ops-sales-tasks"),
    path(
        "api/v1/ops/sales-tasks/<uuid:task_id>",
        OpsSalesTaskDetailView.as_view(),
        name="ops-sales-task-detail",
    ),
    path("api/v1/ops/audit-logs", OpsAuditLogListView.as_view(), name="ops-audit-logs"),
    path("api/v1/ops/audit-logs/<uuid:log_id>", OpsAuditLogDetailView.as_view(), name="ops-audit-log-detail"),
    path("api/v1/ops/mail/smtp-settings", OpsSmtpSettingsView.as_view(), name="ops-mail-smtp"),
    path("api/v1/ops/mail/smtp-settings/test", OpsSmtpTestMailView.as_view(), name="ops-mail-smtp-test"),
    path("api/v1/ops/mail/smtp-settings/verify", OpsSmtpConnectionTestView.as_view(), name="ops-mail-smtp-verify"),
    path("api/v1/ops/mail/templates", OpsEmailTemplatesView.as_view(), name="ops-mail-templates"),
    path("api/v1/ops/mail/logs", OpsMailLogsView.as_view(), name="ops-mail-logs"),
    path(
        "api/v1/ops/mail/logs/<uuid:log_id>/retry",
        OpsMailLogRetryView.as_view(),
        name="ops-mail-log-retry",
    ),
]

# Optional commercial module: iyzico Checkout Form (ENABLE_IYZICO_PAYMENTS=1).
# Provider settings / transaction ops stay available so Super Admin can configure keys
# even before flipping the runtime flag for storefront checkout.
from apps.payments.ops_api import (
    OpsBankAccountDetailView,
    OpsBankAccountsView,
    OpsBankTransferApproveView,
    OpsBankTransferRejectView,
    OpsManualBankRefundView,
    OpsPaymentCancelView,
    OpsPaymentProviderSettingsView,
    OpsPaymentProviderTestView,
    OpsPaymentReceiptFileView,
    OpsPaymentRefundView,
    OpsPaymentTransactionDetailView,
    OpsPaymentTransactionsView,
    OpsRefundRequestActionView,
    OpsRefundRequestsView,
)
from apps.payments.storefront_api import (
    StorefrontBankAccountsView,
    StorefrontInstallmentInfoView,
    StorefrontOrderPaymentsView,
    StorefrontReceiptFileView,
    StorefrontReceiptUploadView,
    StorefrontRefundRequestCreateView,
)

urlpatterns += [
    path(
        "api/v1/ops/payments/provider-settings",
        OpsPaymentProviderSettingsView.as_view(),
        name="ops-payment-provider-settings",
    ),
    path(
        "api/v1/ops/payments/provider-settings/test",
        OpsPaymentProviderTestView.as_view(),
        name="ops-payment-provider-settings-test",
    ),
    path(
        "api/v1/ops/payments/bank-accounts",
        OpsBankAccountsView.as_view(),
        name="ops-payment-bank-accounts",
    ),
    path(
        "api/v1/ops/payments/bank-accounts/<uuid:account_id>",
        OpsBankAccountDetailView.as_view(),
        name="ops-payment-bank-account-detail",
    ),
    path(
        "api/v1/ops/payments/transactions",
        OpsPaymentTransactionsView.as_view(),
        name="ops-payment-transactions",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>",
        OpsPaymentTransactionDetailView.as_view(),
        name="ops-payment-transaction-detail",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/cancel",
        OpsPaymentCancelView.as_view(),
        name="ops-payment-cancel",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/refund",
        OpsPaymentRefundView.as_view(),
        name="ops-payment-refund",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/approve-transfer",
        OpsBankTransferApproveView.as_view(),
        name="ops-payment-approve-transfer",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/reject-transfer",
        OpsBankTransferRejectView.as_view(),
        name="ops-payment-reject-transfer",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/manual-refund",
        OpsManualBankRefundView.as_view(),
        name="ops-payment-manual-refund",
    ),
    path(
        "api/v1/ops/payments/transactions/<uuid:payment_id>/receipt",
        OpsPaymentReceiptFileView.as_view(),
        name="ops-payment-receipt",
    ),
    path(
        "api/v1/ops/payments/refund-requests",
        OpsRefundRequestsView.as_view(),
        name="ops-payment-refund-requests",
    ),
    path(
        "api/v1/ops/payments/refund-requests/<uuid:request_id>/action",
        OpsRefundRequestActionView.as_view(),
        name="ops-payment-refund-request-action",
    ),
    path(
        "api/v1/storefront/payments/bank-accounts",
        StorefrontBankAccountsView.as_view(),
        name="storefront-bank-accounts",
    ),
    path(
        "api/v1/storefront/payments/installments",
        StorefrontInstallmentInfoView.as_view(),
        name="storefront-installments",
    ),
    path(
        "api/v1/storefront/orders/<str:order_no>/payments",
        StorefrontOrderPaymentsView.as_view(),
        name="storefront-order-payments",
    ),
    path(
        "api/v1/storefront/orders/<str:order_no>/receipt",
        StorefrontReceiptUploadView.as_view(),
        name="storefront-receipt-upload",
    ),
    path(
        "api/v1/storefront/orders/<str:order_no>/receipt-file",
        StorefrontReceiptFileView.as_view(),
        name="storefront-receipt-file",
    ),
    path(
        "api/v1/storefront/orders/<str:order_no>/refund-requests",
        StorefrontRefundRequestCreateView.as_view(),
        name="storefront-refund-requests",
    ),
]

if getattr(django_settings, "ENABLE_IYZICO_PAYMENTS", False):
    from apps.payments.api import (
        IyzicoCallbackView,
        IyzicoWebhookView,
        StorefrontCheckoutFormInitializeView,
    )

    urlpatterns += [
        path(
            "api/v1/storefront/payments/checkout-form/initialize",
            StorefrontCheckoutFormInitializeView.as_view(),
            name="storefront-checkout-form-initialize",
        ),
        path(
            "api/v1/payments/iyzico/callback",
            IyzicoCallbackView.as_view(),
            name="iyzico-callback",
        ),
        path(
            "api/v1/payments/iyzico/webhook",
            IyzicoWebhookView.as_view(),
            name="iyzico-webhook",
        ),
        path(
            "api/webhooks/iyzico",
            IyzicoWebhookView.as_view(),
            name="iyzico-webhook-alias",
        ),
    ]

# Partner logos/documents are served only via authenticated OPS API endpoints.
# Do not mount public /media/ static serving — that exposes uploaded files by URL.
