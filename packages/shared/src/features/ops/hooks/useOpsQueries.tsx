import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../../providers/AuthProvider';
import { opsService } from '../services/opsService';
import type {
  OpsCustomerCreateInput,
  OpsCustomerPatchInput,
  OpsLedgerCreateInput,
  OpsListParams,
  OpsMembershipCreateInput,
  OpsOrganizationCreateInput,
  OpsStockTransferInput,
  OpsUserCreateInput,
  OpsVariantCreateInput,
  OpsVariantUpdateInput,
} from '../types';

export const opsKeys = {
  all: ['ops'] as const,
  organizations: (f: string) => [...opsKeys.all, 'organizations', f] as const,
  organizationDossier: (id: string) => [...opsKeys.all, 'organization-dossier', id] as const,
  orgPriceQuotes: (orgId: string, f: string) =>
    [...opsKeys.all, 'org-price-quotes', orgId, f] as const,
  warehouses: (f: string) => [...opsKeys.all, 'warehouses', f] as const,
  stocks: (f: string) => [...opsKeys.all, 'stocks', f] as const,
  stockMovements: (f: string) => [...opsKeys.all, 'stock-movements', f] as const,
  variants: (f: string) => [...opsKeys.all, 'variants', f] as const,
  b2cOrders: (f: string) => [...opsKeys.all, 'b2c-orders', f] as const,
  b2bOrders: (f: string) => [...opsKeys.all, 'b2b-orders', f] as const,
  users: (f: string) => [...opsKeys.all, 'users', f] as const,
  roles: () => [...opsKeys.all, 'roles'] as const,
  ledger: (f: string) => [...opsKeys.all, 'ledger', f] as const,
  workOrders: (f: string) => [...opsKeys.all, 'work-orders', f] as const,
  customers: (f: string) => [...opsKeys.all, 'customers', f] as const,
  customer: (id: string) => [...opsKeys.all, 'customer', id] as const,
};

function filtersKey(filters: OpsListParams) {
  return JSON.stringify(filters);
}

export function useOpsOrganizationsQuery(filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.organizations(filtersKey(filters)),
    queryFn: () => opsService.listOrganizations(filters),
    enabled: authenticated && hasCapability('orgs:manage'),
  });
}

export function useOpsOrganizationDossierQuery(orgId: string | null) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.organizationDossier(orgId ?? ''),
    queryFn: () => opsService.getOrganizationDossier(orgId!),
    enabled: Boolean(orgId) && authenticated && hasCapability('orgs:manage'),
  });
}

export function useCreateOpsOrganizationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsOrganizationCreateInput) => opsService.createOrganization(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'organizations'] });
    },
  });
}

export function usePatchOpsOrganizationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      body,
    }: {
      orgId: string;
      body: Parameters<typeof opsService.patchOrganization>[1];
    }) => opsService.patchOrganization(orgId, body),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'organizations'] });
      void qc.invalidateQueries({ queryKey: opsKeys.organizationDossier(vars.orgId) });
    },
  });
}

function invalidateOrg(qc: ReturnType<typeof useQueryClient>, orgId: string) {
  void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'organizations'] });
  void qc.invalidateQueries({ queryKey: opsKeys.organizationDossier(orgId) });
}

export function useUploadOrgLogoMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, file }: { orgId: string; file: File }) =>
      opsService.uploadOrganizationLogo(orgId, file),
    onSuccess: (_d, v) => invalidateOrg(qc, v.orgId),
  });
}

export function useOrgAddressMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      body,
    }: {
      orgId: string;
      body: { title: string; line: string; addressType?: string; city?: string; isDefault?: boolean };
    }) => opsService.createOrganizationAddress(orgId, body),
    onSuccess: (_d, v) => invalidateOrg(qc, v.orgId),
  });
}

export function useOrgBankMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      body,
    }: {
      orgId: string;
      body: { bankName: string; iban: string; currency?: string; accountHolder?: string; isDefault?: boolean };
    }) => opsService.createOrganizationBankAccount(orgId, body),
    onSuccess: (_d, v) => invalidateOrg(qc, v.orgId),
  });
}

export function useOrgDocumentMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      file,
      meta,
    }: {
      orgId: string;
      file: File;
      meta: { name: string; docType?: string };
    }) => opsService.uploadOrganizationDocument(orgId, file, meta),
    onSuccess: (_d, v) => invalidateOrg(qc, v.orgId),
  });
}

export function useOrgCreditReviewMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orgId,
      body,
    }: {
      orgId: string;
      body: { riskLevel?: string; riskNote?: string; creditReviewNote?: string; paymentTermDays?: number };
    }) => opsService.creditReviewOrganization(orgId, body),
    onSuccess: (_d, v) => invalidateOrg(qc, v.orgId),
  });
}

export function useCreateBranchMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      organizationId: string;
      code: string;
      name: string;
      city: string;
      address?: string;
      isDefault?: boolean;
    }) => opsService.createBranch(body),
    onSuccess: (_d, v) => invalidateOrg(qc, v.organizationId),
  });
}

export function useOpsWarehousesQuery(filters: OpsListParams = { pageSize: 200 }) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.warehouses(filtersKey(filters)),
    queryFn: () => opsService.listWarehouses(filters),
    enabled: authenticated && hasCapability('inventory:manage'),
  });
}

export function useOpsStocksQuery(filters: OpsListParams = {}, enabled = true) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.stocks(filtersKey(filters)),
    queryFn: () => opsService.listStocks(filters),
    enabled: enabled && authenticated && hasCapability('inventory:manage'),
  });
}

export function useOpsVariantsQuery(filters: OpsListParams = {}, enabled = true) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.variants(filtersKey(filters)),
    queryFn: () => opsService.listVariants(filters),
    enabled: enabled && authenticated && hasCapability('catalog:write'),
  });
}

function invalidateVariantRelated(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'variants'] });
  void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'stocks'] });
  void qc.invalidateQueries({ queryKey: ['catalog'] });
}

export function useCreateOpsVariantMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsVariantCreateInput) => opsService.createVariant(body),
    onSuccess: () => invalidateVariantRelated(qc),
  });
}

export function usePatchOpsVariantMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ variantId, body }: { variantId: string; body: OpsVariantUpdateInput }) =>
      opsService.patchVariant(variantId, body),
    onSuccess: () => invalidateVariantRelated(qc),
  });
}

export function useDeactivateOpsVariantMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (variantId: string) => opsService.deactivateVariant(variantId),
    onSuccess: () => invalidateVariantRelated(qc),
  });
}

export function useOpsStockTransferMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsStockTransferInput) => opsService.transferStock(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'stocks'] });
    },
  });
}

export function useOpsB2cOrdersQuery(filters: OpsListParams = {}, enabled = true) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.b2cOrders(filtersKey(filters)),
    queryFn: () => opsService.listOpsB2cOrders(filters),
    enabled: enabled && authenticated && hasCapability('orders:manage'),
  });
}

export function useOpsB2bOrdersQuery(filters: OpsListParams = {}, enabled = true) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.b2bOrders(filtersKey(filters)),
    queryFn: () => opsService.listOpsB2bOrders(filters),
    enabled: enabled && authenticated && hasCapability('orders:manage'),
  });
}

export function useOpsUsersQuery(filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.users(filtersKey(filters)),
    queryFn: () => opsService.listUsers(filters),
    enabled: authenticated && hasCapability('users:read'),
  });
}

export function useCreateOpsUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsUserCreateInput) => opsService.createUser(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'users'] });
    },
  });
}

export function useOpsRolesQuery() {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.roles(),
    queryFn: () => opsService.getRolesMetadata(),
    enabled: authenticated && hasCapability('users:read'),
  });
}

export function useOpsLedgerQuery(filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.ledger(filtersKey(filters)),
    queryFn: () => opsService.listLedger(filters),
    enabled: authenticated && hasCapability('finance:manage'),
  });
}

export function useCreateOpsLedgerMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsLedgerCreateInput) => opsService.createLedger(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'ledger'] });
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'organizations'] });
    },
  });
}

export function useCreateOpsMembershipMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsMembershipCreateInput) => opsService.createMembership(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'users'] });
    },
  });
}

export function useOpsStockMovementsQuery(filters: OpsListParams = {}, enabled = true) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.stockMovements(filtersKey(filters)),
    queryFn: () => opsService.listStockMovements(filters),
    enabled: enabled && authenticated && hasCapability('inventory:manage'),
  });
}

export function useOpsWorkOrdersQuery(filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.workOrders(filtersKey(filters)),
    queryFn: () => opsService.listWorkOrders(filters),
    enabled: authenticated && hasCapability('production:manage'),
  });
}

export function useUpdateOpsWorkOrderStatusMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workOrderId, status }: { workOrderId: string; status: string }) =>
      opsService.updateWorkOrderStatus(workOrderId, status),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'work-orders'] });
    },
  });
}

export function useOrgPriceQuotesQuery(orgId: string | null, filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.orgPriceQuotes(orgId ?? '', filtersKey(filters)),
    queryFn: () =>
      opsService.listPriceQuotes({
        ...filters,
        organizationId: orgId!,
        pageSize: filters.pageSize ?? 50,
      }),
    enabled: Boolean(orgId) && authenticated && hasCapability('pricing:read'),
  });
}

export function useOpsCustomersQuery(filters: OpsListParams = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.customers(filtersKey(filters)),
    queryFn: () => opsService.listCustomers(filters),
    enabled: authenticated && hasCapability('customers:manage'),
  });
}

export function useOpsCustomerQuery(customerId: string | null) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: opsKeys.customer(customerId ?? ''),
    queryFn: () => opsService.getCustomer(customerId!),
    enabled: Boolean(customerId) && authenticated && hasCapability('customers:manage'),
  });
}

export function useCreateOpsCustomerMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsCustomerCreateInput) => opsService.createCustomer(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'customers'] });
    },
  });
}

export function usePatchOpsCustomerMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ customerId, body }: { customerId: string; body: OpsCustomerPatchInput }) =>
      opsService.patchCustomer(customerId, body),
    onSuccess: (_d, v) => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'customers'] });
      void qc.invalidateQueries({ queryKey: opsKeys.customer(v.customerId) });
    },
  });
}

export function useDeactivateOpsCustomerMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (customerId: string) => opsService.deactivateCustomer(customerId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'customers'] });
    },
  });
}

export function useCreateCustomerAddressMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      customerId,
      body,
    }: {
      customerId: string;
      body: { title: string; line: string; addressType?: string; city?: string; isDefault?: boolean };
    }) => opsService.createCustomerAddress(customerId, body),
    onSuccess: (_d, v) => {
      void qc.invalidateQueries({ queryKey: opsKeys.customer(v.customerId) });
    },
  });
}

export function useCustomerConsentsQuery(customerId: string | null) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'customer-consents', customerId],
    queryFn: () => opsService.getCustomerConsents(customerId!),
    enabled:
      Boolean(customerId) &&
      authenticated &&
      (hasCapability('consents:view') || hasCapability('customers:manage')),
  });
}

export function useCustomerContractsQuery(customerId: string | null) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'customer-contracts', customerId],
    queryFn: () => opsService.getCustomerContracts(customerId!),
    enabled:
      Boolean(customerId) &&
      authenticated &&
      (hasCapability('contracts:view') || hasCapability('customers:manage')),
  });
}

export function useCustomerAuditQuery(customerId: string | null) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'customer-audit', customerId],
    queryFn: () => opsService.getCustomerAudit(customerId!),
    enabled: Boolean(customerId) && authenticated && hasCapability('audit:read'),
  });
}

export function useCustomer360DashboardQuery(filters: { from?: string; to?: string; segment?: string } = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'customer-360-dashboard', JSON.stringify(filters)],
    queryFn: () => opsService.getCustomer360Dashboard(filters),
    enabled: authenticated && hasCapability('customers:manage'),
  });
}

export function useOpsCartsQuery(filters: OpsListParams & { status?: string } = {}) {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'carts', filtersKey(filters)],
    queryFn: () => opsService.listCarts({ ...filters, pageSize: filters.pageSize ?? 50 }),
    enabled:
      authenticated &&
      (hasCapability('carts:view') || hasCapability('customers:manage')),
  });
}

export function useLegalDocumentsQuery() {
  const { authenticated, hasCapability } = useAuth();
  return useQuery({
    queryKey: [...opsKeys.all, 'legal-documents'],
    queryFn: () => opsService.listLegalDocuments(),
    enabled:
      authenticated &&
      (hasCapability('contracts:view') ||
        hasCapability('legal_docs:manage') ||
        hasCapability('customers:manage')),
  });
}