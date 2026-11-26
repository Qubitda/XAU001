import type { ApiEnvelope } from '../../lib/api/openapi';
import type { B2bOrderRecord, B2cOrderRecord } from '../commerce/types';

export type OpsPagination = NonNullable<ApiEnvelope<unknown>['meta']['pagination']>;

export type PaginatedResult<T> = {
  items: T;
  pagination?: OpsPagination;
};

export type OpsListParams = {
  q?: string;
  page?: number;
  pageSize?: number;
  isActive?: boolean;
  status?: string;
  warehouseId?: string;
  organizationId?: string;
  entryType?: string;
  parentSku?: string;
  variantId?: string;
  orgType?: string;
  partnerRole?: string;
  approvalStatus?: string;
  riskLevel?: string;
  city?: string;
  customerType?: string;
  channel?: string;
};

/** OPS ProductVariant row — satılabilir konfig (stok SSOT değil). */
export type OpsVariant = {
  id: string;
  productId: string;
  parentSku: string;
  productTitle: string;
  sku: string;
  purityCode: string;
  metalColor: string;
  size: number;
  centerStoneCarat: string;
  grossWeightGram: string;
  stockQty: number;
  isDefault: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OpsVariantCreateInput = {
  parentSku: string;
  sku: string;
  purityCode: string;
  metalColor: string;
  size?: number;
  centerStoneCarat?: string | number;
  grossWeightGram: string | number;
  initialStockQty?: number;
  isDefault?: boolean;
  isActive?: boolean;
};

export type OpsVariantUpdateInput = {
  sku?: string;
  purityCode?: string;
  metalColor?: string;
  size?: number;
  centerStoneCarat?: string | number;
  grossWeightGram?: string | number;
  isDefault?: boolean;
  isActive?: boolean;
};

export type OpsPartnerRole = 'BUYER' | 'SUPPLIER' | 'PLATFORM';

export type OpsOrganizationAddress = {
  id: string;
  organizationId: string;
  addressType: string;
  title: string;
  country: string;
  city: string;
  district: string;
  neighborhood: string;
  postalCode: string;
  line: string;
  contactName: string;
  phone: string;
  isDefault: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OpsOrganizationBankAccount = {
  id: string;
  organizationId: string;
  bankName: string;
  iban: string;
  currency: string;
  accountHolder: string;
  isDefault: boolean;
  isActive: boolean;
};

export type OpsOrganizationDocument = {
  id: string;
  organizationId: string;
  name: string;
  docType: string;
  fileUrl: string | null;
  validUntil: string | null;
  uploadedByEmail: string | null;
  isActive: boolean;
  notes: string;
  createdAt: string;
};

export type OpsOrganization = {
  id: string;
  code: string;
  name: string;
  legalName?: string;
  orgType: string;
  partnerRoles?: OpsPartnerRole[];
  isBuyer?: boolean;
  isSupplier?: boolean;
  approvalStatus?: string;
  taxOfficeAndNo: string;
  taxOffice?: string;
  taxNumber?: string;
  mersisNo?: string;
  tradeRegistryNo?: string;
  companyType?: string;
  foundedOn?: string | null;
  contactName: string;
  email?: string;
  phone?: string;
  fax?: string;
  website?: string;
  city: string;
  description?: string;
  logoUrl?: string | null;
  defaultConsignmentDays: number;
  paymentTermDays?: number;
  riskLevel?: string;
  riskNote?: string;
  creditReviewNote?: string;
  creditReviewedAt?: string | null;
  commercialNotes?: string;
  supplierCode?: string;
  supplierLeadTimeDays?: number | null;
  supplierNotes?: string;
  isActive: boolean;
  creditLimitUsd: string;
  usedCreditUsd: string;
  remainingCreditUsd: string;
  hasLimitGram: string;
  usedHasGram: string;
  remainingHasGram: string;
  branchCount?: number;
  activeUserCount?: number;
  branches: Array<{
    id: string;
    code: string;
    name: string;
    city: string;
    address?: string;
    isDefault: boolean;
    isActive: boolean;
  }>;
  overview?: {
    totalOrders: number;
    totalOrderVolumeUsd: string | null;
    cariBalanceUsd: string;
    creditLimitUsd: string;
    availableCreditUsd: string;
    activeUserCount: number;
    branchCount: number;
    addressCount: number;
  };
  addresses?: OpsOrganizationAddress[];
  bankAccounts?: OpsOrganizationBankAccount[];
  documents?: OpsOrganizationDocument[];
  memberships?: Array<{
    id: string;
    userId: string;
    userEmail: string;
    userFullName: string;
    userPhone: string;
    roleKey: string;
    jobTitle: string;
    defaultBranchId: string | null;
    branches: Array<{ id: string; code: string; name: string }>;
    isActive: boolean;
    lastLogin: string | null;
    createdAt: string;
  }>;
  recentLedger?: Array<{
    id: string;
    entryType: string;
    referenceNo: string;
    amountUsd: string;
    hasGoldGram: string;
    note: string;
    createdByEmail: string | null;
    createdAt: string;
  }>;
  activity?: Array<{
    id: string;
    action: string;
    entityType: string;
    entityId: string;
    actorEmail: string | null;
    metadata: Record<string, unknown>;
    createdAt: string;
  }>;
  createdAt: string;
  updatedAt: string;
};

export type OpsOrganizationCreateInput = {
  code: string;
  name: string;
  legalName?: string;
  city?: string;
  orgType?: string;
  partnerRoles?: OpsPartnerRole[];
  approvalStatus?: string;
  taxOfficeAndNo?: string;
  taxOffice?: string;
  taxNumber?: string;
  contactName?: string;
  email?: string;
  phone?: string;
  creditLimitUsd?: string | number;
  hasLimitGram?: string | number;
  isActive?: boolean;
  riskLevel?: string;
  paymentTermDays?: number;
  supplierCode?: string;
};

export type OpsOrganizationPatchInput = Partial<OpsOrganizationCreateInput> & {
  description?: string;
  website?: string;
  fax?: string;
  mersisNo?: string;
  tradeRegistryNo?: string;
  companyType?: string;
  foundedOn?: string | null;
  commercialNotes?: string;
  riskNote?: string;
  creditReviewNote?: string;
  supplierNotes?: string;
  supplierLeadTimeDays?: number | null;
  defaultConsignmentDays?: number;
};

export type OpsWarehouse = {
  id: string;
  code: string;
  name: string;
  branchId: string | null;
  branchCode: string | null;
  branchName: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OpsWarehouseStock = {
  id: string;
  warehouseId: string;
  warehouseCode: string;
  warehouseName: string;
  variantId: string;
  variantSku: string;
  parentSku: string;
  productTitle: string;
  purityCode: string;
  metalColor: string;
  size: number;
  quantity: number;
  reservedQty: number;
  availableQty: number;
  updatedAt: string;
};

export type OpsStockTransferInput = {
  variantSku: string;
  sourceWarehouseId: string;
  targetWarehouseId: string;
  quantity: number;
  referenceNo: string;
};

export type OpsUserRow = {
  id: string;
  email: string;
  fullName: string;
  phone: string;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  lastLogin: string | null;
  createdAt: string;
  updatedAt: string;
  memberships: Array<{
    id: string;
    organizationId: string | null;
    organizationCode: string | null;
    organizationName: string;
    roleKey: string;
    isActive: boolean;
  }>;
};

export type OpsUserCreateInput = {
  email: string;
  fullName: string;
  phone?: string;
  password: string;
  isActive?: boolean;
  isStaff?: boolean;
};

export type OpsRoleMeta = {
  roleKey: string;
  label: string;
  isOps: boolean;
  permissions: string[];
};

export type OpsRolesMetadata = {
  roles: OpsRoleMeta[];
  allPermissions: string[];
  actorRoleKey: string;
};

export type OpsLedgerEntry = {
  id: string;
  organizationId: string;
  organizationCode: string;
  organizationName: string;
  entryType: string;
  referenceNo: string;
  amountUsd: string;
  hasGoldGram: string;
  note: string;
  createdById: string | null;
  createdByEmail: string | null;
  createdAt: string;
};

export type OpsLedgerCreateInput = {
  organizationId: string;
  entryType: 'PAYMENT_CREDIT' | 'HAS_DELIVERY';
  referenceNo: string;
  amountUsd?: string | number;
  hasGoldGram?: string | number;
  note?: string;
};

export type OpsMembershipCreateInput = {
  userId: string;
  organizationId?: string | null;
  roleKey: string;
  jobTitle?: string;
  branchIds?: string[];
  defaultBranchId?: string | null;
  isActive?: boolean;
};

export type OpsStockMovement = {
  id: string;
  productId: string;
  parentSku: string;
  variantId: string | null;
  variantSku: string | null;
  warehouseId: string | null;
  warehouseCode: string | null;
  movementType: string;
  quantityDelta: number;
  referenceNo: string;
  actorId: string | null;
  actorEmail: string | null;
  createdAt: string;
};

export type OpsWorkOrder = {
  id: string;
  workOrderNo: string;
  sourceOrderNo: string;
  organizationId: string | null;
  organizationCode: string | null;
  organizationName: string | null;
  sku: string;
  size: number;
  quantity: number;
  engravingOrStampNote: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsPriceQuote = {
  id: string;
  productId: string;
  parentSku: string;
  variantId: string | null;
  variantSku: string | null;
  recipeId: string;
  recipeVersion: number;
  recipeStatus?: string | null;
  isActive?: boolean;
  snapshotId: string;
  organizationId: string | null;
  organizationCode: string | null;
  channel: string;
  lcCurrency: string;
  listPriceTry: string;
  finalPriceLc: string;
  finalPriceTry: string;
  effectiveDiscountPct: string;
  validFrom?: string;
  validUntil?: string | null;
  createdAt: string;
};

export type OpsCustomerAddress = {
  id: string;
  customerId: string;
  addressType: string;
  title: string;
  city: string;
  district: string;
  postalCode: string;
  line: string;
  contactName: string;
  phone: string;
  isDefault: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OpsCustomer = {
  id: string;
  customerType: string;
  segment?: string;
  externalId?: string | null;
  emailVerified?: boolean;
  userId: string | null;
  userEmail: string | null;
  organizationId: string | null;
  organizationCode: string | null;
  organizationName: string | null;
  fullName: string;
  phone: string;
  email: string;
  identityOrTaxNo: string;
  city: string;
  address: string;
  isActive: boolean;
  notes: string;
  addresses?: OpsCustomerAddress[];
  orders?: Array<{
    orderNo: string;
    status: string;
    grandTotalTry: string;
    paymentMethod: string;
    shippingFullName: string;
    shippingCity: string;
    billingFullName: string;
    createdAt: string;
  }>;
  orderCount?: number;
  createdAt: string;
  updatedAt: string;
};

export type OpsConsentLog = {
  id: string;
  customerId: string | null;
  guestEmail: string | null;
  purpose: string;
  channel: string;
  status: string;
  source: string;
  grantedAt: string | null;
  withdrawnAt: string | null;
  documentVersion: string;
  documentHash: string;
  iysReference: string | null;
  createdAt: string;
};

export type OpsContractAcceptance = {
  id: string;
  customerId: string;
  orderId: string;
  orderNo: string | null;
  documentCode: string;
  documentVersion: string;
  contentHash: string;
  acceptedAt: string;
  source: string;
  createdAt: string;
};

export type OpsLegalDocument = {
  id: string;
  code: string;
  version: string;
  title: string;
  contentHash: string;
  effectiveFrom: string | null;
  isPublished: boolean;
  audience: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsCustomer360Dashboard = {
  totalB2cCustomers: number;
  activeCartSessions: number;
  abandonedCartSessions: number;
  convertedCartSessions: number;
  recoveredCartSessions: number;
  activeRecoverySessions?: number;
  commercialEmailGranted: number;
  commercialEmailWithdrawn: number;
  pendingCommunicationTasks: number;
};

export type OpsB2cCart = {
  id: string;
  externalId: string | null;
  userId: string | null;
  userEmail: string | null;
  customerId: string | null;
  guestEmail: string | null;
  status: string;
  checkoutState: string;
  currency: string;
  subtotalTry: string;
  discountTry: string;
  taxTry: string;
  totalTry: string;
  lineCount: number;
  lastActivityAt: string | null;
  convertedOrderId: string | null;
  convertedOrderNo: string | null;
  createdAt: string;
  updatedAt: string;
  items?: Array<{
    id: string;
    sku: string;
    title: string;
    qty: number;
    unitFinalPriceTry: string;
    metalColor: string;
    size: number;
  }>;
  events?: Array<{
    id: string;
    eventType: string;
    occurredAt: string;
    source: string;
    payload: Record<string, unknown>;
  }>;
};

export type OpsCustomerCreateInput = {
  customerType?: string;
  fullName: string;
  phone?: string;
  email?: string;
  identityOrTaxNo?: string;
  city?: string;
  address?: string;
  notes?: string;
  isActive?: boolean;
  userId?: string | null;
  organizationId?: string | null;
};

export type OpsCustomerPatchInput = Partial<OpsCustomerCreateInput>;

export type { B2bOrderRecord, B2cOrderRecord };