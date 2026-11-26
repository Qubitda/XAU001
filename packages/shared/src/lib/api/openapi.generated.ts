/**
 * OpenAPI 3 TypeScript contract file generated from Django drf-spectacular:
 *   GET http://localhost:8000/api/v1/schema/
 *
 * Regenerate via:
 *   npm --prefix frontend run openapi:generate
 */

export interface paths {
  '/api/v1/session': {
    get: operations['session_retrieve'];
  };
  '/api/v1/session/context': {
    patch: operations['session_context_partial_update'];
  };
  '/api/v1/session/login': {
    post: operations['session_login_create'];
  };
  '/api/v1/session/logout': {
    post: operations['session_logout_create'];
  };
  '/api/v1/market/rates': {
    get: operations['market_rates_retrieve'];
  };
  '/api/v1/storefront/products': {
    get: operations['storefront_products_list'];
  };
  '/api/v1/storefront/products/{parent_sku}': {
    get: operations['storefront_products_retrieve'];
  };
  '/api/v1/storefront/favorites': {
    get: operations['storefront_favorites_list'];
  };
  '/api/v1/storefront/favorites/toggle': {
    post: operations['storefront_favorites_toggle_create'];
  };
  '/api/v1/storefront/cart': {
    get: operations['storefront_cart_retrieve'];
    delete: operations['storefront_cart_destroy'];
  };
  '/api/v1/storefront/cart/items': {
    post: operations['storefront_cart_items_create'];
  };
  '/api/v1/storefront/cart/items/{item_id}': {
    patch: operations['storefront_cart_items_partial_update'];
    delete: operations['storefront_cart_items_destroy'];
  };
  '/api/v1/storefront/cart/refresh-lock': {
    post: operations['storefront_cart_refresh_lock_create'];
  };
  '/api/v1/storefront/orders': {
    get: operations['storefront_orders_list'];
    post: operations['storefront_orders_create'];
  };
  '/api/v1/storefront/quotes': {
    post: operations['storefront_quotes_create'];
  };
  '/api/v1/b2b/products': {
    get: operations['b2b_products_list'];
  };
  '/api/v1/b2b/products/{parent_sku}': {
    get: operations['b2b_products_retrieve'];
  };
  '/api/v1/b2b/quotes': {
    post: operations['b2b_quotes_create'];
  };
  '/api/v1/b2b/draft': {
    get: operations['b2b_draft_retrieve'];
    delete: operations['b2b_draft_destroy'];
  };
  '/api/v1/b2b/draft/lines': {
    post: operations['b2b_draft_lines_create'];
  };
  '/api/v1/b2b/draft/lines/{line_id}': {
    patch: operations['b2b_draft_lines_partial_update'];
    delete: operations['b2b_draft_lines_destroy'];
  };
  '/api/v1/b2b/orders': {
    get: operations['b2b_orders_list'];
    post: operations['b2b_orders_create'];
  };
  '/api/v1/b2b/orders/{order_no}/reorder': {
    post: operations['b2b_orders_reorder_create'];
  };
  '/api/v1/ops/users': {
    get: operations['ops_users_list'];
    post: operations['ops_users_create'];
  };
  '/api/v1/ops/users/{user_id}': {
    get: operations['ops_users_retrieve'];
    patch: operations['ops_users_partial_update'];
  };
  '/api/v1/ops/roles': {
    get: operations['ops_roles_retrieve'];
  };
  '/api/v1/ops/organizations': {
    get: operations['ops_organizations_list'];
    post: operations['ops_organizations_create'];
  };
  '/api/v1/ops/organizations/{org_id}': {
    get: operations['ops_organizations_retrieve'];
    patch: operations['ops_organizations_partial_update'];
  };
  '/api/v1/ops/branches': {
    get: operations['ops_branches_list'];
    post: operations['ops_branches_create'];
  };
  '/api/v1/ops/branches/{branch_id}': {
    get: operations['ops_branches_retrieve'];
    patch: operations['ops_branches_partial_update'];
  };
  '/api/v1/ops/memberships': {
    get: operations['ops_memberships_list'];
    post: operations['ops_memberships_create'];
  };
  '/api/v1/ops/memberships/{membership_id}': {
    get: operations['ops_memberships_retrieve'];
    patch: operations['ops_memberships_partial_update'];
    delete: operations['ops_memberships_destroy'];
  };
  '/api/v1/ops/customers': {
    get: operations['ops_customers_list'];
    post: operations['ops_customers_create'];
  };
  '/api/v1/ops/customers/{customer_id}': {
    get: operations['ops_customers_retrieve'];
    patch: operations['ops_customers_partial_update'];
  };
  '/api/v1/ops/products': {
    get: operations['ops_products_list'];
    post: operations['ops_products_create'];
  };
  '/api/v1/ops/products/{parent_sku}': {
    get: operations['ops_products_retrieve'];
    patch: operations['ops_products_partial_update'];
    delete: operations['ops_products_destroy'];
  };
  '/api/v1/ops/variants': {
    get: operations['ops_variants_list'];
    post: operations['ops_variants_create'];
  };
  '/api/v1/ops/variants/{variant_id}': {
    get: operations['ops_variants_retrieve'];
    patch: operations['ops_variants_partial_update'];
    delete: operations['ops_variants_destroy'];
  };
  '/api/v1/ops/stone-lines': {
    get: operations['ops_stone_lines_list'];
    post: operations['ops_stone_lines_create'];
  };
  '/api/v1/ops/stone-lines/{stone_id}': {
    get: operations['ops_stone_lines_retrieve'];
    patch: operations['ops_stone_lines_partial_update'];
    delete: operations['ops_stone_lines_destroy'];
  };
  '/api/v1/ops/media': {
    get: operations['ops_media_list'];
    post: operations['ops_media_create'];
  };
  '/api/v1/ops/media/{media_id}': {
    get: operations['ops_media_retrieve'];
    patch: operations['ops_media_partial_update'];
    delete: operations['ops_media_destroy'];
  };
  '/api/v1/ops/categories': {
    get: operations['ops_categories_retrieve'];
  };
  '/api/v1/ops/pricing/recipes': {
    get: operations['ops_pricing_recipes_list'];
    post: operations['ops_pricing_recipes_create'];
  };
  '/api/v1/ops/pricing/recipes/{recipe_id}': {
    get: operations['ops_pricing_recipes_retrieve'];
    patch: operations['ops_pricing_recipes_partial_update'];
  };
  '/api/v1/ops/pricing/recipes/{recipe_id}/evaluate': {
    post: operations['ops_pricing_recipes_evaluate_create'];
  };
  '/api/v1/ops/pricing/recipes/{recipe_id}/publish': {
    post: operations['ops_pricing_recipes_publish_create'];
  };
  '/api/v1/ops/pricing/recipes/{recipe_id}/cost-lines': {
    get: operations['ops_pricing_recipes_cost_lines_list'];
    post: operations['ops_pricing_recipes_cost_lines_create'];
  };
  '/api/v1/ops/pricing/cost-lines/{cost_line_id}': {
    get: operations['ops_pricing_cost_lines_retrieve'];
    patch: operations['ops_pricing_cost_lines_partial_update'];
    delete: operations['ops_pricing_cost_lines_destroy'];
  };
  '/api/v1/ops/pricing/recipes/{recipe_id}/channel-rules': {
    get: operations['ops_pricing_recipes_channel_rules_list'];
    post: operations['ops_pricing_recipes_channel_rules_create'];
  };
  '/api/v1/ops/pricing/channel-rules/{rule_id}': {
    get: operations['ops_pricing_channel_rules_retrieve'];
    patch: operations['ops_pricing_channel_rules_partial_update'];
    delete: operations['ops_pricing_channel_rules_destroy'];
  };
  '/api/v1/ops/pricing/quotes': {
    get: operations['ops_pricing_quotes_list'];
  };
  '/api/v1/ops/pricing/locks': {
    get: operations['ops_pricing_locks_list'];
  };
  '/api/v1/ops/rates': {
    patch: operations['ops_rates_partial_update'];
  };
  '/api/v1/ops/rates/snapshots': {
    get: operations['ops_rates_snapshots_list'];
    post: operations['ops_rates_snapshots_create'];
  };
  '/api/v1/ops/rates/snapshots/{snapshot_id}': {
    get: operations['ops_rates_snapshots_retrieve'];
  };
  '/api/v1/ops/warehouses': {
    get: operations['ops_warehouses_list'];
    post: operations['ops_warehouses_create'];
  };
  '/api/v1/ops/warehouses/{warehouse_id}': {
    get: operations['ops_warehouses_retrieve'];
    patch: operations['ops_warehouses_partial_update'];
  };
  '/api/v1/ops/stocks': {
    get: operations['ops_stocks_list'];
  };
  '/api/v1/ops/stocks/{stock_id}': {
    get: operations['ops_stocks_retrieve'];
  };
  '/api/v1/ops/stock-movements': {
    get: operations['ops_stock_movements_list'];
    post: operations['ops_stock_movements_create'];
  };
  '/api/v1/ops/stock-transfers': {
    post: operations['ops_stock_transfers_create'];
  };
  '/api/v1/ops/b2c-orders': {
    get: operations['ops_b2c_orders_list'];
  };
  '/api/v1/ops/b2c-orders/{order_no}': {
    get: operations['ops_b2c_orders_retrieve'];
  };
  '/api/v1/ops/b2c-orders/{order_no}/status': {
    patch: operations['ops_b2c_orders_status_partial_update'];
  };
  '/api/v1/ops/b2b-orders': {
    get: operations['ops_b2b_orders_list'];
  };
  '/api/v1/ops/b2b-orders/{order_no}': {
    get: operations['ops_b2b_orders_retrieve'];
  };
  '/api/v1/ops/b2b-orders/{order_no}/status': {
    patch: operations['ops_b2b_orders_status_partial_update'];
  };
  '/api/v1/ops/work-orders': {
    get: operations['ops_work_orders_list'];
    post: operations['ops_work_orders_create'];
  };
  '/api/v1/ops/work-orders/{work_order_id}': {
    get: operations['ops_work_orders_retrieve'];
    patch: operations['ops_work_orders_partial_update'];
  };
  '/api/v1/ops/work-orders/{work_order_id}/status': {
    patch: operations['ops_work_orders_status_partial_update'];
  };
  '/api/v1/ops/ledger': {
    get: operations['ops_ledger_list'];
    post: operations['ops_ledger_create'];
  };
  '/api/v1/ops/ledger/{entry_id}': {
    get: operations['ops_ledger_retrieve'];
  };
  '/api/v1/ops/notifications': {
    get: operations['ops_notifications_list'];
    post: operations['ops_notifications_create'];
  };
  '/api/v1/ops/notifications/{notification_id}': {
    get: operations['ops_notifications_retrieve'];
    patch: operations['ops_notifications_partial_update'];
  };
  '/api/v1/ops/audit-logs': {
    get: operations['ops_audit_logs_list'];
  };
  '/api/v1/ops/audit-logs/{log_id}': {
    get: operations['ops_audit_logs_retrieve'];
  };
}

export interface components {
  schemas: Record<string, unknown>;
}

export type operations = Record<string, unknown>;
