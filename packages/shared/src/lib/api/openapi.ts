import { AudienceRole, LiveRates, ProductState } from '../../types/jewelry';
import type {
  B2bDraftSnapshot,
  B2bOrderLine,
  B2bOrderRecord,
  B2cCartItem,
  B2cCartSnapshot,
  B2cOrderRecord,
} from '../../features/commerce/types';
import type {
  components as GeneratedOpenApiComponents,
  operations as GeneratedOpenApiOperations,
  paths as GeneratedOpenApiPaths,
} from './openapi.generated';

export type {
  GeneratedOpenApiComponents,
  GeneratedOpenApiOperations,
  GeneratedOpenApiPaths,
};
export type OpenApiEndpointPath = keyof GeneratedOpenApiPaths;

/**
 * Permission-based RBAC capabilities (Tara Gold Authorization Matrix)
 */
export type PortalCapability =
  | 'catalog:read'
  | 'catalog:write'
  | 'catalog:publish'
  | 'catalog:delete'
  | 'pricing:read'
  | 'pricing:edit'
  | 'rates:edit'
  | 'b2b:order'
  | 'b2c:order'
  | 'orders:manage'
  | 'org:switch'
  | 'users:read'
  | 'users:manage'
  | 'orgs:manage'
  | 'customers:manage'
  | 'carts:view'
  | 'consents:view'
  | 'consents:manage'
  | 'contracts:view'
  | 'legal_docs:manage'
  | 'inventory:manage'
  | 'production:manage'
  | 'finance:manage'
  | 'notifications:manage'
  | 'mail:manage'
  | 'payments:manage'
  | 'audit:read'
  | 'api_keys:read'
  | 'api_keys:manage';

export type PortalRoleKey =
  | 'SUPER_ADMIN'
  | 'ORG_ADMIN'
  | 'OPS'
  | 'B2B_BUYER'
  | 'B2C_CUSTOMER';

export interface BranchDto {
  id: string;
  code: string;
  name: string;
  city: string;
  address: string;
}

export interface OrganizationDto {
  id: string;
  code: string;
  name: string;
  type: 'PLATFORM_OWNER' | 'DEALER';
  taxOfficeAndNo: string;
  contactName: string;
  city: string;
  creditLimitUsd: number;
  usedCreditUsd: number;
  hasLimitGram: number;
  usedHasGram: number;
  defaultConsignmentDays: number;
  branches: BranchDto[];
}

export interface OrganizationMembershipDto {
  id: string;
  organizationId: string | null;
  organizationName: string;
  organizationCode: string;
  organizationType: 'PLATFORM_OWNER' | 'DEALER' | 'INDIVIDUAL';
  roleKey: PortalRoleKey;
  roleLabel: string;
  audience: AudienceRole;
  branchIds: string[];
  defaultBranchId: string | null;
  permissions: PortalCapability[];
}

export interface SessionUserDto {
  authenticated?: boolean;
  id: string;
  email: string;
  fullName: string;
  emailVerified?: boolean;
  role: AudienceRole;
  roleKey: PortalRoleKey;
  capabilities: PortalCapability[];
  activeMembershipId: string;
  activeOrganizationId: string | null;
  activeBranchId: string | null;
  memberships: OrganizationMembershipDto[];
  organizations: OrganizationDto[];
  csrfToken: string;
}

export interface BuyerQuoteDto {
  quoteId: string;
  parentSku: string;
  variantId?: string | null;
  variantSku?: string;
  purityCode?: string;
  metalColor?: string;
  grossWeightGram?: number;
  channel: 'B2B' | 'B2C';
  size?: number;
  lcCurrency: string;
  listPriceTry: number;
  finalPriceLc: number;
  finalPriceTry: number;
  effectiveDiscountPct: number;
  snapshotId: string;
}

export interface ApiEnvelope<T> {
  data: T;
  meta: {
    requestId: string;
    timestamp: string;
    organizationId?: string | null;
    branchId?: string | null;
    pagination?: {
      total: number;
      page: number;
      pageSize: number;
      totalPages: number;
    };
  };
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, string[]>;
}

export type ProductDto = ProductState;
export type LiveRatesDto = LiveRates;

export type CreateProductRequest = Omit<ProductState, 'parentSku'> & {
  parentSku: string;
};
export type UpdateProductRequest = Partial<ProductState>;
export type UpdateRatesRequest = Partial<LiveRates>;

/**
 * Separated API namespaces:
 * - /api/v1/storefront/* (B2C buyer scope — blind pool protected)
 * - /api/v1/b2b/*        (B2B organization/branch isolated scope — blind pool protected)
 * - /api/v1/ops/*        (OPS/Admin full catalog, pricing & fulfillment scope)
 */
export interface OpenApiPaths {
  '/api/v1/session': {
    GET: { response: ApiEnvelope<SessionUserDto> };
  };
  '/api/v1/session/context': {
    PATCH: {
      body: { membershipId?: string; branchId?: string; role?: AudienceRole };
      response: ApiEnvelope<SessionUserDto>;
    };
  };
  '/api/v1/market/rates': {
    GET: { response: ApiEnvelope<LiveRatesDto> };
  };
  '/api/v1/storefront/products': {
    GET: { response: ApiEnvelope<ProductDto[]> };
  };
  '/api/v1/storefront/favorites': {
    GET: { response: ApiEnvelope<string[]> };
  };
  '/api/v1/storefront/favorites/toggle': {
    POST: { body: { parentSku: string }; response: ApiEnvelope<string[]> };
  };
  '/api/v1/storefront/cart': {
    GET: { response: ApiEnvelope<B2cCartSnapshot> };
    DELETE: { response: ApiEnvelope<B2cCartSnapshot> };
  };
  '/api/v1/storefront/cart/items': {
    POST: { body: Omit<B2cCartItem, 'id' | 'addedAt'>; response: ApiEnvelope<B2cCartSnapshot> };
  };
  '/api/v1/storefront/orders': {
    GET: { response: ApiEnvelope<B2cOrderRecord[]> };
    POST: {
      body: Omit<B2cOrderRecord, 'orderNo' | 'createdAt' | 'items' | 'status'>;
      response: ApiEnvelope<B2cOrderRecord>;
    };
  };
  '/api/v1/b2b/draft': {
    GET: { response: ApiEnvelope<B2bDraftSnapshot> };
    DELETE: { response: ApiEnvelope<B2bDraftSnapshot> };
  };
  '/api/v1/b2b/draft/lines': {
    POST: {
      body: Omit<B2bOrderLine, 'id' | 'addedAt'> | Array<Omit<B2bOrderLine, 'id' | 'addedAt'>>;
      response: ApiEnvelope<B2bDraftSnapshot>;
    };
  };
  '/api/v1/b2b/orders': {
    GET: { response: ApiEnvelope<B2bOrderRecord[]> };
    POST: {
      body: Omit<B2bOrderRecord, 'orderNo' | 'createdAt' | 'lines' | 'status'>;
      response: ApiEnvelope<B2bOrderRecord>;
    };
  };
  '/api/v1/ops/products': {
    GET: { response: ApiEnvelope<ProductDto[]> };
    POST: { body: CreateProductRequest; response: ApiEnvelope<ProductDto> };
  };
  '/api/v1/ops/products/:parentSku': {
    GET: { response: ApiEnvelope<ProductDto> };
    PATCH: { body: UpdateProductRequest; response: ApiEnvelope<ProductDto> };
    DELETE: { response: ApiEnvelope<{ parentSku: string; deleted: boolean }> };
  };
  '/api/v1/ops/rates': {
    PATCH: { body: UpdateRatesRequest; response: ApiEnvelope<LiveRatesDto> };
  };
}
