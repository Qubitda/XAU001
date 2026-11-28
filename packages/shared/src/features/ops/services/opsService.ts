import { apiFetch } from '../../../lib/api/client';
import type {
  B2bOrderRecord,
  B2cOrderRecord,
  OpsCustomer,
  OpsCustomerAddress,
  OpsCustomerCreateInput,
  OpsCustomerPatchInput,
  OpsLedgerCreateInput,
  OpsLedgerEntry,
  OpsListParams,
  OpsMembershipCreateInput,
  OpsOrganization,
  OpsOrganizationAddress,
  OpsOrganizationBankAccount,
  OpsOrganizationCreateInput,
  OpsOrganizationDocument,
  OpsOrganizationPatchInput,
  OpsPriceQuote,
  OpsRoleMeta,
  OpsRolesMetadata,
  OpsStockMovement,
  OpsStockTransferInput,
  OpsUserCreateInput,
  OpsUserRow,
  OpsVariant,
  OpsVariantCreateInput,
  OpsVariantUpdateInput,
  OpsWarehouse,
  OpsWarehouseStock,
  OpsWorkOrder,
  PaginatedResult,
} from '../types';

function buildQuery(params?: OpsListParams): string {
  if (!params) return '';
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.page != null) sp.set('page', String(params.page));
  if (params.pageSize != null) sp.set('pageSize', String(params.pageSize));
  if (params.isActive != null) sp.set('isActive', params.isActive ? 'true' : 'false');
  if (params.status) sp.set('status', params.status);
  if (params.warehouseId) sp.set('warehouseId', params.warehouseId);
  if (params.organizationId) sp.set('organizationId', params.organizationId);
  if (params.entryType) sp.set('entryType', params.entryType);
  if (params.parentSku) sp.set('parentSku', params.parentSku);
  if (params.variantId) sp.set('variantId', params.variantId);
  if (params.orgType) sp.set('orgType', params.orgType);
  if (params.partnerRole) sp.set('partnerRole', params.partnerRole);
  if (params.approvalStatus) sp.set('approvalStatus', params.approvalStatus);
  if (params.riskLevel) sp.set('riskLevel', params.riskLevel);
  if (params.city) sp.set('city', params.city);
  if (params.customerType) sp.set('customerType', params.customerType);
  if (params.channel) sp.set('channel', params.channel);
  const raw = sp.toString();
  return raw ? `?${raw}` : '';
}

async function listPaged<T>(path: string, params?: OpsListParams): Promise<PaginatedResult<T[]>> {
  const res = await apiFetch<T[]>(`${path}${buildQuery(params)}`);
  return { items: res.data ?? [], pagination: res.meta.pagination };
}

export const opsService = {
  listOrganizations(params?: OpsListParams) {
    return listPaged<OpsOrganization>('/api/v1/ops/organizations', params);
  },
  async getOrganization(orgId: string, detail = false): Promise<OpsOrganization> {
    const q = detail ? '?detail=true' : '';
    const res = await apiFetch<OpsOrganization>(`/api/v1/ops/organizations/${orgId}${q}`);
    return res.data;
  },
  async getOrganizationDossier(orgId: string): Promise<OpsOrganization> {
    const res = await apiFetch<OpsOrganization>(`/api/v1/ops/organizations/${orgId}/dossier`);
    return res.data;
  },
  async createOrganization(body: OpsOrganizationCreateInput): Promise<OpsOrganization> {
    const res = await apiFetch<OpsOrganization>('/api/v1/ops/organizations', {
      method: 'POST',
      body,
    });
    return res.data;
  },
  async patchOrganization(orgId: string, body: OpsOrganizationPatchInput): Promise<OpsOrganization> {
    const res = await apiFetch<OpsOrganization>(`/api/v1/ops/organizations/${orgId}`, {
      method: 'PATCH',
      body,
    });
    return res.data;
  },
  async uploadOrganizationLogo(orgId: string, file: File): Promise<OpsOrganization> {
    const fd = new FormData();
    fd.append('logo', file);
    const res = await apiFetch<OpsOrganization>(`/api/v1/ops/organizations/${orgId}/logo`, {
      method: 'POST',
      body: fd,
    });
    return res.data;
  },
  async createOrganizationAddress(
    orgId: string,
    body: Partial<OpsOrganizationAddress> & { title: string; line: string; addressType?: string }
  ): Promise<OpsOrganizationAddress> {
    const res = await apiFetch<OpsOrganizationAddress>(`/api/v1/ops/organizations/${orgId}/addresses`, {
      method: 'POST',
      body,
    });
    return res.data;
  },
  async patchOrganizationAddress(
    orgId: string,
    addressId: string,
    body: Partial<OpsOrganizationAddress>
  ): Promise<OpsOrganizationAddress> {
    const res = await apiFetch<OpsOrganizationAddress>(
      `/api/v1/ops/organizations/${orgId}/addresses/${addressId}`,
      { method: 'PATCH', body }
    );
    return res.data;
  },
  async deactivateOrganizationAddress(orgId: string, addressId: string): Promise<OpsOrganizationAddress> {
    const res = await apiFetch<OpsOrganizationAddress>(
      `/api/v1/ops/organizations/${orgId}/addresses/${addressId}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async createOrganizationBankAccount(
    orgId: string,
    body: { bankName: string; iban: string; currency?: string; accountHolder?: string; isDefault?: boolean }
  ): Promise<OpsOrganizationBankAccount> {
    const res = await apiFetch<OpsOrganizationBankAccount>(
      `/api/v1/ops/organizations/${orgId}/bank-accounts`,
      { method: 'POST', body }
    );
    return res.data;
  },
  async deactivateOrganizationBankAccount(
    orgId: string,
    accountId: string
  ): Promise<OpsOrganizationBankAccount> {
    const res = await apiFetch<OpsOrganizationBankAccount>(
      `/api/v1/ops/organizations/${orgId}/bank-accounts/${accountId}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async uploadOrganizationDocument(
    orgId: string,
    file: File,
    meta: { name: string; docType?: string; notes?: string }
  ): Promise<OpsOrganizationDocument> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', meta.name);
    if (meta.docType) fd.append('docType', meta.docType);
    if (meta.notes) fd.append('notes', meta.notes);
    const res = await apiFetch<OpsOrganizationDocument>(
      `/api/v1/ops/organizations/${orgId}/documents`,
      { method: 'POST', body: fd }
    );
    return res.data;
  },
  async creditReviewOrganization(
    orgId: string,
    body: { riskLevel?: string; riskNote?: string; creditReviewNote?: string; paymentTermDays?: number }
  ): Promise<OpsOrganization> {
    const res = await apiFetch<OpsOrganization>(`/api/v1/ops/organizations/${orgId}/credit-review`, {
      method: 'POST',
      body,
    });
    return res.data;
  },
  async createBranch(body: {
    organizationId: string;
    code: string;
    name: string;
    city: string;
    address?: string;
    isDefault?: boolean;
  }) {
    const res = await apiFetch(`/api/v1/ops/branches`, { method: 'POST', body });
    return res.data;
  },
  listMemberships(params?: OpsListParams) {
    return listPaged('/api/v1/ops/memberships', params);
  },

  listWarehouses(params?: OpsListParams) {
    return listPaged<OpsWarehouse>('/api/v1/ops/warehouses', params);
  },
  listStocks(params?: OpsListParams) {
    return listPaged<OpsWarehouseStock>('/api/v1/ops/stocks', params);
  },

  listVariants(params?: OpsListParams) {
    return listPaged<OpsVariant>('/api/v1/ops/variants', params);
  },
  async createVariant(body: OpsVariantCreateInput): Promise<OpsVariant> {
    const res = await apiFetch<OpsVariant>('/api/v1/ops/variants', { method: 'POST', body });
    return res.data;
  },
  async patchVariant(variantId: string, body: OpsVariantUpdateInput): Promise<OpsVariant> {
    const res = await apiFetch<OpsVariant>(`/api/v1/ops/variants/${encodeURIComponent(variantId)}`, {
      method: 'PATCH',
      body,
    });
    return res.data;
  },
  async deactivateVariant(
    variantId: string
  ): Promise<{ id: string; sku: string; isActive: boolean; deleted?: boolean }> {
    const res = await apiFetch<{ id: string; sku: string; isActive: boolean; deleted?: boolean }>(
      `/api/v1/ops/variants/${encodeURIComponent(variantId)}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async bulkCreateVariants(body: {
    parentSku: string;
    purities: string[];
    colors: string[];
    sizes: number[];
    centerStoneCarat?: string;
    grossWeightGram: string;
    initialStockQty?: number;
  }): Promise<{ createdCount: number; skippedCount: number; items: OpsVariant[] }> {
    const res = await apiFetch<{ createdCount: number; skippedCount: number; items: OpsVariant[] }>(
      '/api/v1/ops/variants/bulk',
      { method: 'POST', body }
    );
    return res.data;
  },
  async createStockMovement(body: {
    variantId?: string;
    variantSku?: string;
    warehouseId?: string;
    warehouseCode?: string;
    movementType: 'INBOUND' | 'SHIP' | 'RESERVE' | 'RELEASE';
    quantity: number;
    referenceNo: string;
  }): Promise<OpsStockMovement> {
    const res = await apiFetch<OpsStockMovement>('/api/v1/ops/stock-movements', {
      method: 'POST',
      body,
    });
    return res.data;
  },
  async transferStock(body: OpsStockTransferInput): Promise<unknown> {
    const res = await apiFetch('/api/v1/ops/stock-transfers', { method: 'POST', body });
    return res.data;
  },

  listOpsB2cOrders(params?: OpsListParams) {
    return listPaged<B2cOrderRecord>('/api/v1/ops/b2c-orders', params);
  },
  listOpsB2bOrders(params?: OpsListParams) {
    return listPaged<B2bOrderRecord>('/api/v1/ops/b2b-orders', params);
  },

  listPriceQuotes(params?: OpsListParams & { channel?: string }) {
    return listPaged<OpsPriceQuote>('/api/v1/ops/pricing/quotes', params);
  },

  listCustomers(params?: OpsListParams & { customerType?: string }) {
    return listPaged<OpsCustomer>('/api/v1/ops/customers', params);
  },
  async getCustomer(customerId: string): Promise<OpsCustomer> {
    const res = await apiFetch<OpsCustomer>(`/api/v1/ops/customers/${customerId}`);
    return res.data;
  },
  async createCustomer(body: OpsCustomerCreateInput): Promise<OpsCustomer> {
    const res = await apiFetch<OpsCustomer>('/api/v1/ops/customers', { method: 'POST', body });
    return res.data;
  },
  async patchCustomer(customerId: string, body: OpsCustomerPatchInput): Promise<OpsCustomer> {
    const res = await apiFetch<OpsCustomer>(`/api/v1/ops/customers/${customerId}`, {
      method: 'PATCH',
      body,
    });
    return res.data;
  },
  async deactivateCustomer(customerId: string): Promise<OpsCustomer | { id: string; deleted: boolean }> {
    const res = await apiFetch<OpsCustomer | { id: string; deleted: boolean }>(
      `/api/v1/ops/customers/${customerId}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async createCustomerAddress(
    customerId: string,
    body: Partial<OpsCustomerAddress> & { title: string; line: string }
  ): Promise<OpsCustomerAddress> {
    const res = await apiFetch<OpsCustomerAddress>(`/api/v1/ops/customers/${customerId}/addresses`, {
      method: 'POST',
      body,
    });
    return res.data;
  },
  async deactivateCustomerAddress(customerId: string, addressId: string): Promise<OpsCustomerAddress> {
    const res = await apiFetch<OpsCustomerAddress>(
      `/api/v1/ops/customers/${customerId}/addresses/${addressId}`,
      { method: 'DELETE' }
    );
    return res.data;
  },

  async getCustomerConsents(customerId: string) {
    const res = await apiFetch<{
      items: import('../types').OpsConsentLog[];
      active: { commercialEmail: boolean; kvkkNotice: boolean };
    }>(`/api/v1/ops/customers/${customerId}/consents`);
    return res.data;
  },
  async getCustomerContracts(customerId: string) {
    const res = await apiFetch<import('../types').OpsContractAcceptance[]>(
      `/api/v1/ops/customers/${customerId}/contracts`
    );
    return res.data;
  },
  async getCustomerAudit(customerId: string) {
    type AuditRow = {
      id: string;
      action: string;
      entityType: string;
      entityId: string;
      createdAt: string;
      actorEmail?: string | null;
    };
    const res = await apiFetch<AuditRow[]>(`/api/v1/ops/customers/${customerId}/audit`);
    return Array.isArray(res.data) ? res.data : [];
  },
  async getCustomer360Dashboard(params?: { from?: string; to?: string; segment?: string }) {
    const qs = new URLSearchParams();
    if (params?.from) qs.set('from', params.from);
    if (params?.to) qs.set('to', params.to);
    if (params?.segment) qs.set('segment', params.segment);
    const q = qs.toString();
    const res = await apiFetch<import('../types').OpsCustomer360Dashboard>(
      `/api/v1/ops/customer-360/dashboard${q ? `?${q}` : ''}`
    );
    return res.data;
  },
  listCarts(params?: OpsListParams & { status?: string; checkoutState?: string; from?: string; to?: string }) {
    return listPaged<import('../types').OpsB2cCart>('/api/v1/ops/carts', params);
  },
  async getCart(cartId: string) {
    const res = await apiFetch<import('../types').OpsB2cCart>(`/api/v1/ops/carts/${cartId}`);
    return res.data;
  },

  async listLegalDocuments(params?: { code?: string; isPublished?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.code) qs.set('code', params.code);
    if (params?.isPublished) qs.set('isPublished', 'true');
    const q = qs.toString();
    const res = await apiFetch<import('../types').OpsLegalDocument[]>(
      `/api/v1/ops/legal-documents${q ? `?${q}` : ''}`
    );
    return res.data;
  },

  listUsers(params?: OpsListParams) {
    return listPaged<OpsUserRow>('/api/v1/ops/users', params);
  },
  async createUser(body: OpsUserCreateInput): Promise<OpsUserRow> {
    const res = await apiFetch<OpsUserRow>('/api/v1/ops/users', { method: 'POST', body });
    return res.data;
  },
  async getRolesMetadata(): Promise<OpsRolesMetadata> {
    const res = await apiFetch<OpsRolesMetadata>('/api/v1/ops/roles');
    return res.data;
  },

  listLedger(params?: OpsListParams) {
    return listPaged<OpsLedgerEntry>('/api/v1/ops/ledger', params);
  },
  async createLedger(body: OpsLedgerCreateInput): Promise<OpsLedgerEntry> {
    const res = await apiFetch<OpsLedgerEntry>('/api/v1/ops/ledger', { method: 'POST', body });
    return res.data;
  },

  async createMembership(body: OpsMembershipCreateInput): Promise<unknown> {
    const res = await apiFetch('/api/v1/ops/memberships', { method: 'POST', body });
    return res.data;
  },

  listStockMovements(params?: OpsListParams) {
    return listPaged<OpsStockMovement>('/api/v1/ops/stock-movements', params);
  },

  listWorkOrders(params?: OpsListParams) {
    return listPaged<OpsWorkOrder>('/api/v1/ops/work-orders', params);
  },
  async updateWorkOrderStatus(workOrderId: string, status: string): Promise<OpsWorkOrder> {
    const res = await apiFetch<OpsWorkOrder>(
      `/api/v1/ops/work-orders/${encodeURIComponent(workOrderId)}/status`,
      { method: 'PATCH', body: { status } }
    );
    return res.data;
  },
};

export type { OpsRoleMeta };