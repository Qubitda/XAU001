import { CATALOG_PRODUCTS, INITIAL_RATES } from '../../data/jewelryData';
import { AudienceRole, LiveRates, ProductState } from '../../types/jewelry';
import type {
  B2bDraftSnapshot,
  B2bOrderLine,
  B2bOrderRecord,
  B2cCartItem,
  B2cCartSnapshot,
  B2cOrderRecord,
  DealerAccountProfile,
} from '../../features/commerce/types';
import type {
  ApiEnvelope,
  OrganizationDto,
  OrganizationMembershipDto,
  PortalCapability,
  SessionUserDto,
} from './openapi';
import { ApiClientError, type ApiFetchOptions } from './client';

const ROLE_CAPABILITIES: Record<AudienceRole, PortalCapability[]> = {
  erp: [
    'catalog:read',
    'catalog:write',
    'catalog:delete',
    'pricing:read',
    'pricing:edit',
    'rates:edit',
    'b2b:order',
    'b2c:order',
    'orders:manage',
    'org:switch',
    'api_keys:read',
    'api_keys:manage',
    'orgs:manage',
    'users:read',
    'users:manage',
    'finance:manage',
    'inventory:manage',
    'production:manage',
    'audit:read',
  ],
  b2b: ['catalog:read', 'pricing:read', 'b2b:order', 'org:switch'],
  b2c: ['catalog:read', 'pricing:read', 'b2c:order', 'org:switch'],
};

const CSRF_STORAGE_KEY = 'taragold_csrf_token';
const PERSIST_STORAGE_KEY = 'taragold_store_v3';
const B2C_LOCK_MS = 15 * 60 * 1000;

const DEFAULT_ORGANIZATIONS: OrganizationDto[] = [
  {
    id: 'org_taragold_hq',
    code: 'TG-HQ',
    name: 'Tara Gold Merkez Operasyon A.Ş.',
    type: 'PLATFORM_OWNER',
    taxOfficeAndNo: 'Beyoğlu VD · 8240193011',
    contactName: 'Emre Gönel',
    city: 'İstanbul / Kuyumcukent',
    creditLimitUsd: 250000,
    usedCreditUsd: 0,
    hasLimitGram: 1000,
    usedHasGram: 0,
    defaultConsignmentDays: 60,
    branches: [
      {
        id: 'br_hq_kuyumcukent',
        code: 'TG-KK',
        name: 'Kuyumcukent Merkez Atölye',
        city: 'İstanbul',
        address: 'Yenibosna Kuyumcukent Atölye Bloğu No:42 Bahçelievler / İstanbul',
      },
      {
        id: 'br_hq_nuruosmaniye',
        code: 'TG-NO',
        name: 'Nuruosmaniye Toptan Showroom',
        city: 'İstanbul',
        address: 'Nuruosmaniye Cad. No:68 Fatih / İstanbul',
      },
    ],
  },
  {
    id: 'org_aydin_kuyum',
    code: 'BY-34018',
    name: 'Aydın Kuyumculuk Mücevherat Ltd. Şti.',
    type: 'DEALER',
    taxOfficeAndNo: 'Şişli VD · 1280459120',
    contactName: 'Murat Aydın',
    city: 'İstanbul / Nişantaşı',
    creditLimitUsd: 65000,
    usedCreditUsd: 14250,
    hasLimitGram: 300,
    usedHasGram: 64.5,
    defaultConsignmentDays: 45,
    branches: [
      {
        id: 'br_aydin_nisantasi',
        code: 'AYD-NIS',
        name: 'Nişantaşı Mağaza',
        city: 'İstanbul',
        address: 'Abdi İpekçi Cad. No:24 Şişli / İstanbul',
      },
      {
        id: 'br_aydin_kapalicarsi',
        code: 'AYD-KPC',
        name: 'Kapalıçarşı Şube',
        city: 'İstanbul',
        address: 'Kalpakçılar Cad. No:118 Fatih / İstanbul',
      },
    ],
  },
  {
    id: 'org_altinbasak',
    code: 'BY-06092',
    name: 'Altınbaşak Mücevherat A.Ş.',
    type: 'DEALER',
    taxOfficeAndNo: 'Çankaya VD · 3910824419',
    contactName: 'Hakan Demir',
    city: 'Ankara / Çankaya',
    creditLimitUsd: 90000,
    usedCreditUsd: 21500,
    hasLimitGram: 450,
    usedHasGram: 112.25,
    defaultConsignmentDays: 30,
    branches: [
      {
        id: 'br_altinbasak_tunali',
        code: 'ALT-TUN',
        name: 'Tunalı Hilmi Showroom',
        city: 'Ankara',
        address: 'Tunalı Hilmi Cad. No:84 Çankaya / Ankara',
      },
    ],
  },
];

const DEFAULT_MEMBERSHIPS: OrganizationMembershipDto[] = [
  {
    id: 'mem_b2c_retail',
    organizationId: null,
    organizationName: 'Bireysel Mağaza Hesabı',
    organizationCode: 'B2C',
    organizationType: 'INDIVIDUAL',
    roleKey: 'B2C_CUSTOMER',
    roleLabel: 'Perakende Müşteri',
    audience: 'b2c',
    branchIds: [],
    defaultBranchId: null,
    permissions: ROLE_CAPABILITIES.b2c,
  },
  {
    id: 'mem_aydin_b2b',
    organizationId: 'org_aydin_kuyum',
    organizationName: 'Aydın Kuyumculuk Mücevherat Ltd. Şti.',
    organizationCode: 'BY-34018',
    organizationType: 'DEALER',
    roleKey: 'ORG_ADMIN',
    roleLabel: 'Firma Yöneticisi (Bayi)',
    audience: 'b2b',
    branchIds: ['br_aydin_nisantasi', 'br_aydin_kapalicarsi'],
    defaultBranchId: 'br_aydin_nisantasi',
    permissions: ROLE_CAPABILITIES.b2b,
  },
  {
    id: 'mem_altinbasak_b2b',
    organizationId: 'org_altinbasak',
    organizationName: 'Altınbaşak Mücevherat A.Ş.',
    organizationCode: 'BY-06092',
    organizationType: 'DEALER',
    roleKey: 'B2B_BUYER',
    roleLabel: 'Satın Alma Yetkilisi (Bayi)',
    audience: 'b2b',
    branchIds: ['br_altinbasak_tunali'],
    defaultBranchId: 'br_altinbasak_tunali',
    permissions: ROLE_CAPABILITIES.b2b,
  },
  {
    id: 'mem_taragold_ops',
    organizationId: 'org_taragold_hq',
    organizationName: 'Tara Gold Merkez Operasyon A.Ş.',
    organizationCode: 'TG-HQ',
    organizationType: 'PLATFORM_OWNER',
    roleKey: 'SUPER_ADMIN',
    roleLabel: 'Süper Admin / OPS',
    audience: 'erp',
    branchIds: ['br_hq_kuyumcukent', 'br_hq_nuruosmaniye'],
    defaultBranchId: 'br_hq_kuyumcukent',
    permissions: ROLE_CAPABILITIES.erp,
  },
];

function getOrCreateCsrfToken(): string {
  try {
    const existing = window.sessionStorage.getItem(CSRF_STORAGE_KEY);
    if (existing) return existing;
    const token = `csrf_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
    window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
    return token;
  } catch {
    return 'csrf_session_token';
  }
}

interface PersistedLocalState {
  products: ProductState[];
  rates: LiveRates;
  activeMembershipId: string;
  activeBranchId: string | null;
  organizations: OrganizationDto[];
  favorites: string[];
  b2cCartItems: B2cCartItem[];
  b2cPriceLockedUntil: string;
  b2cOrders: B2cOrderRecord[];
  b2bDraftsByOrg: Record<string, B2bOrderLine[]>;
  b2bOrders: B2bOrderRecord[];
}

function createDefaultState(): PersistedLocalState {
  return {
    products: CATALOG_PRODUCTS.map((p) => ({
      ...p,
      ledger: {
        ...p.ledger,
        channelRules: p.ledger.channelRules.map((r) => ({
          ...r,
          profit: { ...r.profit },
          discount: { ...r.discount },
          platformFee: { ...r.platformFee },
        })),
      },
    })),
    rates: {
      ...INITIAL_RATES,
      fxBaseRates: { ...INITIAL_RATES.fxBaseRates },
    },
    activeMembershipId: 'mem_b2c_retail',
    activeBranchId: null,
    organizations: DEFAULT_ORGANIZATIONS.map((org) => ({
      ...org,
      branches: org.branches.map((b) => ({ ...b })),
    })),
    favorites: ['SE009', 'BL031'],
    b2cCartItems: [],
    b2cPriceLockedUntil: new Date(Date.now() + B2C_LOCK_MS).toISOString(),
    b2cOrders: [
      {
        orderNo: 'TG-B2C-2026-1038',
        createdAt: '2026-11-21T11:15:00.000Z',
        snapshotId: 'SNP-20261121-1110',
        goldRateTryPerGram: 5401.32,
        customerName: 'Selin Karahan',
        customerPhone: '0532 418 29 10',
        customerEmail: 'selin.karahan@ornek.com',
        shippingCity: 'İstanbul',
        shippingAddress: 'Teşvikiye Mah. Vali Konağı Cad. No:48 D:6 Şişli / İstanbul',
        paymentMethod: 'CREDIT_CARD',
        acceptedCustomPolicy: true,
        items: [
          {
            id: 'seed_b2c_1',
            sku: 'KL022-14K-SRY-045',
            parentSku: 'KL022',
            title: '0.45 Karat Damla Pırlanta Kolye',
            category: 'Kolye',
            metalColor: 'Sarı',
            purityCode: '14K',
            size: 45,
            sizeUnitLabel: 'Zincir Boyu',
            qty: 1,
            engravingText: '',
            giftWrap: true,
            giftNote: 'Nice mutlu yıllara.',
            certificateLabel: 'HRD · HRD-26018492',
            stockStatus: 'Stokta',
            leadTimeText: '1–2 iş günü sigortalı kurye teslimatı',
            grossWeightGram: 2.85,
            unitListPriceTry: 34200,
            unitFinalPriceTry: 31464,
            snapshotId: 'SNP-20261121-1110',
            addedAt: '2026-11-21T11:12:00.000Z',
          },
        ],
        subtotalListTry: 34200,
        campaignDiscountTry: 2736,
        transferDiscountTry: 0,
        insuredShippingTry: 0,
        vatIncludedTry: 5244,
        grandTotalTry: 31464,
        status: 'SIGORTALI_KARGODA',
      },
    ],
    b2bDraftsByOrg: {
      org_aydin_kuyum: [],
      org_altinbasak: [],
      org_taragold_hq: [],
    },
    b2bOrders: [
      {
        orderNo: 'TG-B2B-2026-0142',
        createdAt: '2026-11-23T14:22:00.000Z',
        snapshotId: 'SNP-20261123-1415',
        usdTryRate: 42.0,
        goldRateTryPerGram: 5401.32,
        organizationId: 'org_aydin_kuyum',
        branchId: 'br_aydin_nisantasi',
        branchName: 'Nişantaşı Mağaza',
        createdByUserId: 'usr_taragold_01',
        createdByUserName: 'Emre Gönel',
        dealerCode: 'BY-34018',
        dealerName: 'Aydın Kuyumculuk Mücevherat Ltd. Şti.',
        taxOfficeAndNo: 'Şişli VD · 1280459120',
        contactPerson: 'Murat Aydın',
        settlementMethod: 'HAS_PLUS_CURRENCY',
        rateLockMode: 'LOCK_ON_ORDER',
        deliveryMethod: 'KAPALICARSI_HANDOVER',
        orderNote: 'İç kol lazer 585 + Aydın marka damgası uygulanacak.',
        acceptedWeightTolerance: true,
        lines: [
          {
            id: 'seed_line_1',
            sku: 'SE009-14K-BYZ-060',
            parentSku: 'SE009',
            title: '0.60 Karat Pırlanta Tektaş Yüzük',
            category: 'Yüzük',
            metalColor: 'Beyaz',
            purityCode: '14K',
            size: 14,
            sizeUnitLabel: 'Yüzük Ölçüsü',
            qty: 3,
            supplyType: 'STOCK',
            dealerStampNote: 'Aydın 585 damga',
            unitGrossGram: 3.12,
            unitNetMetalGram: 3.0,
            unitFireIncludedFineGram: 1.7901,
            unitLaborAndStoneUsd: 492.4,
            unitWholesaleUsd: 785.5,
            unitWholesaleTry: 32991,
            pricingCurrency: 'USD',
            snapshotId: 'SNP-20261123-1415',
            addedAt: '2026-11-23T14:18:00.000Z',
          },
        ],
        totalPieces: 3,
        totalGrossGram: 9.36,
        totalHasGoldGram: 5.3703,
        totalLaborAndStoneUsd: 1477.2,
        totalWholesaleUsd: 2356.5,
        totalWholesaleTry: 98973,
        status: 'SEVK_HAZIR',
      },
      {
        orderNo: 'TG-B2B-2026-0145',
        createdAt: '2026-11-24T09:40:00.000Z',
        snapshotId: 'SNP-20261124-0930',
        usdTryRate: 42.0,
        goldRateTryPerGram: 5401.32,
        organizationId: 'org_altinbasak',
        branchId: 'br_altinbasak_tunali',
        branchName: 'Tunalı Hilmi Showroom',
        createdByUserId: 'usr_taragold_01',
        createdByUserName: 'Emre Gönel',
        dealerCode: 'BY-06092',
        dealerName: 'Altınbaşak Mücevherat A.Ş.',
        taxOfficeAndNo: 'Çankaya VD · 3910824419',
        contactPerson: 'Hakan Demir',
        settlementMethod: 'CONSIGNMENT',
        rateLockMode: 'LOCK_ON_ORDER',
        consignmentDays: 30,
        deliveryMethod: 'BRINKS_INSURED',
        orderNote: 'Tunalı vitrin açılış konsinye teslimatı.',
        acceptedWeightTolerance: true,
        lines: [
          {
            id: 'seed_line_2',
            sku: 'BL031-14K-BYZ-240',
            parentSku: 'BL031',
            title: '2.40 Karat Su Yolu Pırlanta Bileklik',
            category: 'Bileklik',
            metalColor: 'Beyaz',
            purityCode: '14K',
            size: 18,
            sizeUnitLabel: 'Bileklik Boyu',
            qty: 2,
            supplyType: 'STOCK',
            dealerStampNote: 'Altınbaşak 585',
            unitGrossGram: 8.6,
            unitNetMetalGram: 8.12,
            unitFireIncludedFineGram: 4.8452,
            unitLaborAndStoneUsd: 1620,
            unitWholesaleUsd: 2243.1,
            unitWholesaleTry: 94210.2,
            pricingCurrency: 'USD',
            snapshotId: 'SNP-20261124-0930',
            addedAt: '2026-11-24T09:35:00.000Z',
          },
        ],
        totalPieces: 2,
        totalGrossGram: 17.2,
        totalHasGoldGram: 9.6904,
        totalLaborAndStoneUsd: 3240,
        totalWholesaleUsd: 4486.2,
        totalWholesaleTry: 188420.4,
        status: 'PROFORMA_ONAYLANDI',
      },
    ],
  };
}

function loadState(): PersistedLocalState {
  const defaults = createDefaultState();
  try {
    const raw = window.localStorage.getItem(PERSIST_STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<PersistedLocalState>;
    const validMembership = DEFAULT_MEMBERSHIPS.some((m) => m.id === parsed.activeMembershipId);
    return {
      products:
        Array.isArray(parsed.products) && parsed.products.length > 0
          ? parsed.products
          : defaults.products,
      rates: parsed.rates?.fxBaseRates ? parsed.rates : defaults.rates,
      activeMembershipId: validMembership
        ? (parsed.activeMembershipId as string)
        : defaults.activeMembershipId,
      activeBranchId: parsed.activeBranchId ?? defaults.activeBranchId,
      organizations:
        Array.isArray(parsed.organizations) && parsed.organizations.length > 0
          ? parsed.organizations
          : defaults.organizations,
      favorites: Array.isArray(parsed.favorites) ? parsed.favorites : defaults.favorites,
      b2cCartItems: Array.isArray(parsed.b2cCartItems) ? parsed.b2cCartItems : defaults.b2cCartItems,
      b2cPriceLockedUntil: parsed.b2cPriceLockedUntil ?? defaults.b2cPriceLockedUntil,
      b2cOrders: Array.isArray(parsed.b2cOrders) ? parsed.b2cOrders : defaults.b2cOrders,
      b2bDraftsByOrg: parsed.b2bDraftsByOrg ?? defaults.b2bDraftsByOrg,
      b2bOrders: Array.isArray(parsed.b2bOrders) ? parsed.b2bOrders : defaults.b2bOrders,
    };
  } catch {
    return defaults;
  }
}

let store: PersistedLocalState = loadState();

function persistStore() {
  try {
    window.localStorage.setItem(PERSIST_STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Ignore storage quota restrictions
  }
}

function getActiveMembership(): OrganizationMembershipDto {
  return (
    DEFAULT_MEMBERSHIPS.find((m) => m.id === store.activeMembershipId) ?? DEFAULT_MEMBERSHIPS[0]
  );
}

function resolveActiveDealerOrg(): OrganizationDto {
  const mem = getActiveMembership();
  const targetOrgId = mem.organizationId ?? 'org_aydin_kuyum';
  return (
    store.organizations.find((o) => o.id === targetOrgId) ??
    store.organizations.find((o) => o.type === 'DEALER') ??
    store.organizations[0]
  );
}

function buildDealerProfile(org: OrganizationDto): DealerAccountProfile {
  const branch =
    org.branches.find((b) => b.id === store.activeBranchId) ?? org.branches[0];
  return {
    organizationId: org.id,
    dealerCode: org.code,
    companyName: org.name,
    taxOfficeAndNo: org.taxOfficeAndNo,
    contactName: org.contactName,
    city: branch ? `${branch.city} / ${branch.name}` : org.city,
    branchId: branch?.id ?? '',
    branchName: branch?.name ?? 'Merkez',
    creditLimitUsd: org.creditLimitUsd,
    usedCreditUsd: org.usedCreditUsd,
    hasLimitGram: org.hasLimitGram,
    usedHasGram: org.usedHasGram,
    defaultConsignmentDays: org.defaultConsignmentDays,
  };
}

function buildSessionDto(csrfToken: string): SessionUserDto {
  const mem = getActiveMembership();
  const org = mem.organizationId
    ? store.organizations.find((o) => o.id === mem.organizationId) ?? null
    : null;
  const resolvedBranchId = org
    ? org.branches.some((b) => b.id === store.activeBranchId)
      ? store.activeBranchId
      : mem.defaultBranchId ?? org.branches[0]?.id ?? null
    : null;

  return {
    id: 'usr_taragold_01',
    email: 'emre.gonel@pigomass.com',
    fullName: 'Emre Gönel',
    emailVerified: true,
    role: mem.audience,
    roleKey: mem.roleKey,
    capabilities: mem.permissions,
    activeMembershipId: mem.id,
    activeOrganizationId: mem.organizationId,
    activeBranchId: resolvedBranchId,
    memberships: DEFAULT_MEMBERSHIPS,
    organizations: store.organizations.map((o) => ({
      ...o,
      branches: o.branches.map((b) => ({ ...b })),
    })),
    csrfToken,
  };
}

function buildEnvelope<T>(data: T): ApiEnvelope<T> {
  const mem = getActiveMembership();
  return {
    data,
    meta: {
      requestId: `req_${Math.random().toString(36).slice(2, 10)}`,
      timestamp: new Date().toISOString(),
      organizationId: mem.organizationId,
      branchId: store.activeBranchId,
    },
  };
}

type DemoLedgerRow = {
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

type DemoStockMovementRow = {
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

let demoLedgerEntries: DemoLedgerRow[] = [
  {
    id: 'led_seed_1',
    organizationId: 'org_aydin_kuyum',
    organizationCode: 'BY-34018',
    organizationName: 'Aydın Kuyumculuk Mücevherat Ltd. Şti.',
    entryType: 'PAYMENT_CREDIT',
    referenceNo: 'TAH-2026-0041',
    amountUsd: '5000.00',
    hasGoldGram: '0.0000',
    note: 'Havale tahsilatı',
    createdById: 'usr_taragold_01',
    createdByEmail: 'emre.gonel@pigomass.com',
    createdAt: '2026-11-20T10:00:00.000Z',
  },
];

let demoStockMovements: DemoStockMovementRow[] = [];

const DEMO_WAREHOUSES = [
  {
    id: 'wh_kk_main',
    code: 'TG-KK-ANA',
    name: 'Kuyumcukent Ana Depo',
    branchId: 'br_hq_kuyumcukent',
    branchCode: 'TG-KK',
    branchName: 'Kuyumcukent Merkez Atölye',
    isActive: true,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
  },
  {
    id: 'wh_nisantasi',
    code: 'AYD-NIS-DEPO',
    name: 'Nişantaşı Mağaza Deposu',
    branchId: 'br_aydin_nisantasi',
    branchCode: 'AYD-NIS',
    branchName: 'Nişantaşı Mağaza',
    isActive: true,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
  },
];

function parseListPath(fullPath: string): { basePath: string; page: number; pageSize: number } {
  const qIdx = fullPath.indexOf('?');
  const basePath = qIdx >= 0 ? fullPath.slice(0, qIdx) : fullPath;
  const search = qIdx >= 0 ? fullPath.slice(qIdx + 1) : '';
  const sp = new URLSearchParams(search);
  const page = Math.max(1, Number(sp.get('page') || '1') || 1);
  const pageSize = Math.min(200, Math.max(1, Number(sp.get('pageSize') || sp.get('page_size') || '25') || 25));
  return { basePath, page, pageSize };
}

function buildPaginatedEnvelope<T>(fullPath: string, items: T[]): ApiEnvelope<T[]> {
  const { page, pageSize } = parseListPath(fullPath);
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize;
  const pageItems = items.slice(start, start + pageSize);
  const mem = getActiveMembership();
  return {
    data: pageItems,
    meta: {
      requestId: `req_${Math.random().toString(36).slice(2, 10)}`,
      timestamp: new Date().toISOString(),
      organizationId: mem.organizationId,
      branchId: store.activeBranchId,
      pagination: { total, page, pageSize, totalPages },
    },
  };
}

function mapStoreOrgToOps(org: OrganizationDto) {
  const credit = Number(org.creditLimitUsd);
  const usedCredit = Number(org.usedCreditUsd);
  const hasLimit = Number(org.hasLimitGram);
  const usedHas = Number(org.usedHasGram);
  return {
    id: org.id,
    code: org.code,
    name: org.name,
    orgType: org.type,
    taxOfficeAndNo: org.taxOfficeAndNo,
    contactName: org.contactName,
    city: org.city,
    defaultConsignmentDays: org.defaultConsignmentDays,
    isActive: true,
    creditLimitUsd: credit.toFixed(2),
    usedCreditUsd: usedCredit.toFixed(2),
    remainingCreditUsd: Math.max(0, credit - usedCredit).toFixed(2),
    hasLimitGram: hasLimit.toFixed(4),
    usedHasGram: usedHas.toFixed(4),
    remainingHasGram: Math.max(0, hasLimit - usedHas).toFixed(4),
    branches: org.branches.map((b) => ({
      id: b.id,
      code: b.code,
      name: b.name,
      city: b.city,
      isDefault: false,
      isActive: true,
    })),
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: new Date().toISOString(),
  };
}

function demoOpsUsersList() {
  const membershipRows = DEFAULT_MEMBERSHIPS.filter((m) => m.audience !== 'b2c').map((m) => ({
    id: m.id,
    organizationId: m.organizationId,
    organizationCode: m.organizationCode,
    organizationName: m.organizationName,
    roleKey: m.roleKey,
    isActive: true,
  }));
  return [
    {
      id: 'usr_taragold_01',
      email: 'emre.gonel@pigomass.com',
      fullName: 'Emre Gönel',
      phone: '',
      isActive: true,
      isStaff: true,
      isSuperuser: false,
      lastLogin: new Date().toISOString(),
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: new Date().toISOString(),
      memberships: membershipRows,
    },
  ];
}

function requireCapability(capability: PortalCapability) {
  const mem = getActiveMembership();
  if (!mem.permissions.includes(capability)) {
    throw new ApiClientError(403, {
      code: 'FORBIDDEN',
      message: 'Bu işlem için aktif firma/rol yetkiniz bulunmuyor.',
    });
  }
}

/**
 * Standalone browser demo mock handler.
 * Lazily imported ONLY when VITE_API_BASE_URL is unset and demo mode is permitted.
 */
export async function demoApiFetch<T>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<ApiEnvelope<T>> {
  const method = options.method ?? 'GET';

  const csrfToken = getOrCreateCsrfToken();
  const activeMem = getActiveMembership();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    ...(method !== 'GET' ? { 'X-CSRF-Token': csrfToken } : {}),
    ...(activeMem.organizationId ? { 'X-Organization-Id': activeMem.organizationId } : {}),
    ...(store.activeBranchId ? { 'X-Branch-Id': store.activeBranchId } : {}),
    ...options.headers,
  };

  if (method !== 'GET') {
    if (!headers['X-CSRF-Token']) {
      throw new ApiClientError(403, {
        code: 'CSRF_MISSING',
        message: 'CSRF doğrulama anahtarı eksik.',
      });
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }

  // ── Session & Tenant Context ─────────────────────────────────────────
  if (path === '/api/v1/session' && method === 'GET') {
    return buildEnvelope({ ...buildSessionDto(csrfToken), authenticated: true } as unknown as T);
  }

  if (path === '/api/v1/session/login' && method === 'POST') {
    const body = (options.body ?? {}) as { email?: string; password?: string };
    if (!body.email || !body.password) {
      throw new ApiClientError(400, {
        code: 'INVALID_CREDENTIALS',
        message: 'E-posta ve parola zorunludur.',
      });
    }
    return buildEnvelope({
      ...buildSessionDto(csrfToken),
      authenticated: true,
      emailVerified: true,
    } as unknown as T);
  }

  if (path === '/api/v1/auth/register' && method === 'POST') {
    const body = (options.body ?? {}) as {
      email?: string;
      password?: string;
      fullName?: string;
    };
    if (!body.email || !body.password || !body.fullName) {
      throw new ApiClientError(400, {
        code: 'VALIDATION_ERROR',
        message: 'E-posta, parola ve ad soyad zorunludur.',
      });
    }
    return buildEnvelope({
      ...buildSessionDto(csrfToken),
      authenticated: true,
      email: body.email,
      fullName: body.fullName,
      emailVerified: false,
      emailVerificationSent: true,
    } as unknown as T);
  }

  if (path === '/api/v1/auth/password/forgot' && method === 'POST') {
    return buildEnvelope({ accepted: true } as unknown as T);
  }

  if (path === '/api/v1/auth/password/reset' && method === 'POST') {
    return buildEnvelope({ passwordReset: true } as unknown as T);
  }

  if (path === '/api/v1/auth/email/verify' && method === 'POST') {
    return buildEnvelope({
      emailVerified: true,
      emailVerifiedAt: new Date().toISOString(),
    } as unknown as T);
  }

  if (path === '/api/v1/auth/email/resend' && method === 'POST') {
    return buildEnvelope({ emailVerificationSent: true } as unknown as T);
  }

  if (path === '/api/v1/session/logout' && method === 'POST') {
    return buildEnvelope({ loggedOut: true } as unknown as T);
  }

  if ((path === '/api/v1/session/context' || path === '/api/v1/session/role') && method === 'PATCH') {
    const body = (options.body ?? {}) as {
      membershipId?: string;
      branchId?: string | null;
      role?: AudienceRole;
    };

    let nextMembership = getActiveMembership();
    if (body.membershipId) {
      const found = DEFAULT_MEMBERSHIPS.find((m) => m.id === body.membershipId);
      if (found) nextMembership = found;
    } else if (body.role) {
      const found = DEFAULT_MEMBERSHIPS.find((m) => m.audience === body.role);
      if (found) nextMembership = found;
    }

    let nextBranchId = store.activeBranchId;
    if (body.membershipId || body.role) {
      nextBranchId = nextMembership.defaultBranchId;
    }
    if (body.branchId !== undefined) {
      if (body.branchId === null || nextMembership.branchIds.includes(body.branchId)) {
        nextBranchId = body.branchId;
      }
    }

    store = {
      ...store,
      activeMembershipId: nextMembership.id,
      activeBranchId: nextBranchId,
    };
    persistStore();
    return buildEnvelope({ ...buildSessionDto(csrfToken), authenticated: true } as unknown as T);
  }

  // ── Catalog & Products (/storefront/products, /b2b/products, /ops/products) ──
  if (
    (path === '/api/v1/storefront/products' ||
      path === '/api/v1/b2b/products' ||
      path === '/api/v1/ops/products' ||
      path === '/api/v1/products') &&
    method === 'GET'
  ) {
    return buildEnvelope([...store.products] as unknown as T);
  }

  if ((path === '/api/v1/storefront/quotes' || path === '/api/v1/b2b/quotes') && method === 'POST') {
    const body = (options.body ?? {}) as { parentSku: string; channel: 'B2B' | 'B2C'; size?: number };
    const product = store.products.find((p) => p.parentSku === body.parentSku);
    if (!product) {
      throw new ApiClientError(404, {
        code: 'PRODUCT_NOT_FOUND',
        message: `Ürün bulunamadı: ${body.parentSku}`,
      });
    }
    return buildEnvelope({
      quoteId: `q_${Date.now().toString(36)}`,
      parentSku: product.parentSku,
      channel: body.channel,
      size: body.size ?? product.variantSize,
      lcCurrency: product.ledger.lcCurrency,
      listPriceTry: 0,
      finalPriceLc: 0,
      finalPriceTry: 0,
      effectiveDiscountPct: product.discountRatePct,
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  if ((path === '/api/v1/ops/products' || path === '/api/v1/products') && method === 'POST') {
    requireCapability('catalog:write');
    const incoming = options.body as ProductState;
    const normalizedSku = incoming.parentSku.trim().toUpperCase();
    if (store.products.some((p) => p.parentSku.toUpperCase() === normalizedSku)) {
      throw new ApiClientError(409, {
        code: 'DUPLICATE_SKU',
        message: `${normalizedSku} model kodu zaten katalogda mevcut.`,
      });
    }
    const created: ProductState = { ...incoming, parentSku: normalizedSku };
    store = { ...store, products: [created, ...store.products] };
    persistStore();
    return buildEnvelope(created as unknown as T);
  }

  const productMatch = path.match(/^\/api\/v1\/(?:(?:storefront|b2b|ops)\/)?products\/([^/]+)$/);
  if (productMatch) {
    const sku = decodeURIComponent(productMatch[1]);
    const idx = store.products.findIndex((p) => p.parentSku === sku);

    if (method === 'GET') {
      if (idx === -1) {
        throw new ApiClientError(404, {
          code: 'PRODUCT_NOT_FOUND',
          message: `Ürün bulunamadı: ${sku}`,
        });
      }
      return buildEnvelope(store.products[idx] as unknown as T);
    }

    if (method === 'PATCH') {
      if (idx === -1) {
        throw new ApiClientError(404, {
          code: 'PRODUCT_NOT_FOUND',
          message: `Güncellenecek ürün bulunamadı: ${sku}`,
        });
      }
      const patch = options.body as Partial<ProductState>;
      const updated: ProductState = { ...store.products[idx], ...patch };
      store = {
        ...store,
        products: store.products.map((item, i) => (i === idx ? updated : item)),
      };
      persistStore();
      return buildEnvelope(updated as unknown as T);
    }

    if (method === 'DELETE') {
      requireCapability('catalog:delete');
      if (idx === -1) {
        throw new ApiClientError(404, {
          code: 'PRODUCT_NOT_FOUND',
          message: `Silinecek ürün bulunamadı: ${sku}`,
        });
      }
      if (store.products.length <= 1) {
        throw new ApiClientError(400, {
          code: 'LAST_PRODUCT_PROTECTED',
          message: 'Katalogda en az bir aktif ürün kalmalıdır.',
        });
      }
      store = {
        ...store,
        products: store.products.filter((_, i) => i !== idx),
        favorites: store.favorites.filter((fav) => fav !== sku),
      };
      persistStore();
      return buildEnvelope({ parentSku: sku, deleted: true } as unknown as T);
    }
  }

  // ── OPS API Keys (demo stubs) ───────────────────────────────────────
  if (path === '/api/v1/ops/api-keys' && method === 'GET') {
    requireCapability('api_keys:read');
    return buildEnvelope([] as unknown as T);
  }
  if (path === '/api/v1/ops/api-keys' && method === 'POST') {
    requireCapability('api_keys:manage');
    const body = (options.body ?? {}) as {
      name?: string;
      organizationId?: string;
      scopes?: string[];
    };
    const plaintext = `tg_live_demo_${Math.random().toString(36).slice(2, 10)}${Math.random()
      .toString(36)
      .slice(2, 18)}`;
    return buildEnvelope({
      id: `apk_${Date.now()}`,
      name: body.name ?? 'Demo Key',
      prefix: plaintext.replace('tg_live_', '').slice(0, 8),
      organizationId: body.organizationId ?? 'org_taragold_hq',
      organizationName: 'Tara Gold HQ',
      scopes: body.scopes ?? ['storefront:read', 'storefront:write', 'market:read'],
      isActive: true,
      lastUsedAt: null,
      createdAt: new Date().toISOString(),
      key: plaintext,
      meta: { plaintextShownOnce: true, note: 'Demo anahtar — production değil.' },
    } as unknown as T);
  }
  if (/^\/api\/v1\/ops\/api-keys\/[^/]+\/revoke$/.test(path) && (method === 'POST' || method === 'DELETE')) {
    requireCapability('api_keys:manage');
    return buildEnvelope({ id: path.split('/')[5], isActive: false } as unknown as T);
  }

  if (path === '/api/v1/ops/webhooks' && method === 'GET') {
    requireCapability('orgs:manage');
    return buildEnvelope([] as unknown as T);
  }
  if (path === '/api/v1/ops/webhooks' && method === 'POST') {
    requireCapability('orgs:manage');
    const body = (options.body ?? {}) as {
      organizationId?: string;
      url?: string;
      events?: string[];
    };
    return buildEnvelope({
      id: `wh_${Date.now()}`,
      organizationId: body.organizationId ?? 'org_taragold_hq',
      organizationName: 'Tara Gold HQ',
      url: body.url ?? 'https://example.com/webhook',
      events: body.events ?? ['b2b.order.created'],
      isActive: true,
      createdAt: new Date().toISOString(),
      secret: `whsec_demo_${Math.random().toString(36).slice(2, 18)}`,
      meta: { secretShownOnce: true, note: 'Demo secret — production değil.' },
    } as unknown as T);
  }
  if (/^\/api\/v1\/ops\/webhooks\/[^/]+\/revoke$/.test(path) && (method === 'POST' || method === 'DELETE')) {
    requireCapability('orgs:manage');
    return buildEnvelope({ id: path.split('/')[5], isActive: false } as unknown as T);
  }

  // ── OPS Admin stubs (organizations, inventory, users, finance, orders) ─
  const { basePath: opsBasePath } = parseListPath(path);

  if (opsBasePath === '/api/v1/ops/organizations' && method === 'GET') {
    requireCapability('orgs:manage');
    const orgs = store.organizations.map(mapStoreOrgToOps);
    return buildPaginatedEnvelope(path, orgs) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/organizations' && method === 'POST') {
    requireCapability('orgs:manage');
    const body = (options.body ?? {}) as {
      code?: string;
      name?: string;
      city?: string;
      creditLimitUsd?: number | string;
      hasLimitGram?: number | string;
    };
    const id = `org_${Date.now().toString(36)}`;
    const newOrg: OrganizationDto = {
      id,
      code: body.code ?? 'NEW',
      name: body.name ?? 'Yeni Firma',
      type: 'DEALER',
      taxOfficeAndNo: '',
      contactName: '',
      city: body.city ?? '',
      creditLimitUsd: Number(body.creditLimitUsd ?? 0),
      usedCreditUsd: 0,
      hasLimitGram: Number(body.hasLimitGram ?? 0),
      usedHasGram: 0,
      defaultConsignmentDays: 45,
      branches: [],
    };
    store = { ...store, organizations: [newOrg, ...store.organizations] };
    persistStore();
    return buildEnvelope(mapStoreOrgToOps(newOrg) as unknown as T);
  }
  const opsOrgPatch = path.match(/^\/api\/v1\/ops\/organizations\/([^/?]+)$/);
  if (opsOrgPatch && method === 'PATCH') {
    requireCapability('orgs:manage');
    const orgId = decodeURIComponent(opsOrgPatch[1]);
    const patch = (options.body ?? {}) as {
      creditLimitUsd?: number | string;
      hasLimitGram?: number | string;
      isActive?: boolean;
      name?: string;
      city?: string;
    };
    store = {
      ...store,
      organizations: store.organizations.map((org) => {
        if (org.id !== orgId) return org;
        return {
          ...org,
          name: patch.name ?? org.name,
          city: patch.city ?? org.city,
          creditLimitUsd:
            patch.creditLimitUsd !== undefined ? Number(patch.creditLimitUsd) : org.creditLimitUsd,
          hasLimitGram:
            patch.hasLimitGram !== undefined ? Number(patch.hasLimitGram) : org.hasLimitGram,
        };
      }),
    };
    persistStore();
    const updated = store.organizations.find((o) => o.id === orgId);
    if (!updated) {
      throw new ApiClientError(404, { code: 'ORG_NOT_FOUND', message: 'Firma bulunamadı.' });
    }
    return buildEnvelope(mapStoreOrgToOps(updated) as unknown as T);
  }

  if (opsBasePath === '/api/v1/ops/warehouses' && method === 'GET') {
    requireCapability('inventory:manage');
    return buildPaginatedEnvelope(path, [...DEMO_WAREHOUSES]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/stocks' && method === 'GET') {
    requireCapability('inventory:manage');
    return buildPaginatedEnvelope(path, [] as unknown[]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/stock-movements' && method === 'GET') {
    requireCapability('inventory:manage');
    return buildPaginatedEnvelope(path, [...demoStockMovements]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/stock-transfers' && method === 'POST') {
    requireCapability('inventory:manage');
    const body = (options.body ?? {}) as {
      variantSku?: string;
      referenceNo?: string;
      quantity?: number;
    };
    demoStockMovements = [
      {
        id: `smv_${Date.now()}`,
        productId: 'prod_demo',
        parentSku: body.variantSku?.split('-')[0] ?? 'SE009',
        variantId: null,
        variantSku: body.variantSku ?? null,
        warehouseId: 'wh_kk_main',
        warehouseCode: 'TG-KK-ANA',
        movementType: 'SHIP',
        quantityDelta: -(body.quantity ?? 1),
        referenceNo: body.referenceNo ?? 'TRF',
        actorId: 'usr_taragold_01',
        actorEmail: 'emre.gonel@pigomass.com',
        createdAt: new Date().toISOString(),
      },
      ...demoStockMovements,
    ];
    return buildEnvelope({ ok: true } as unknown as T);
  }

  if (opsBasePath === '/api/v1/ops/users' && method === 'GET') {
    requireCapability('users:read');
    return buildPaginatedEnvelope(path, demoOpsUsersList()) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/users' && method === 'POST') {
    requireCapability('users:manage');
    const body = (options.body ?? {}) as { email?: string; fullName?: string };
    return buildEnvelope({
      id: `usr_${Date.now()}`,
      email: body.email ?? 'user@demo.local',
      fullName: body.fullName ?? 'Demo Kullanıcı',
      phone: '',
      isActive: true,
      isStaff: true,
      isSuperuser: false,
      lastLogin: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      memberships: [],
    } as unknown as T);
  }
  if (opsBasePath === '/api/v1/ops/roles' && method === 'GET') {
    requireCapability('users:read');
    const mem = getActiveMembership();
    const roles = DEFAULT_MEMBERSHIPS.map((m) => ({
      roleKey: m.roleKey,
      label: m.roleLabel,
      isOps: m.audience === 'erp',
      permissions: [...m.permissions],
    }));
    const unique = Array.from(new Map(roles.map((r) => [r.roleKey, r])).values());
    return buildEnvelope({
      roles: unique,
      allPermissions: ROLE_CAPABILITIES.erp,
      actorRoleKey: mem.roleKey,
    } as unknown as T);
  }

  if (opsBasePath === '/api/v1/ops/memberships' && method === 'POST') {
    requireCapability('users:manage');
    const body = (options.body ?? {}) as {
      userId?: string;
      organizationId?: string | null;
      roleKey?: string;
    };
    return buildEnvelope({
      id: `mem_${Date.now()}`,
      userId: body.userId,
      organizationId: body.organizationId ?? null,
      roleKey: body.roleKey ?? 'B2B_BUYER',
      isActive: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    } as unknown as T);
  }

  if (opsBasePath === '/api/v1/ops/ledger' && method === 'GET') {
    requireCapability('finance:manage');
    return buildPaginatedEnvelope(path, [...demoLedgerEntries]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/ledger' && method === 'POST') {
    requireCapability('finance:manage');
    const body = (options.body ?? {}) as {
      organizationId?: string;
      entryType?: string;
      referenceNo?: string;
      amountUsd?: number | string;
      hasGoldGram?: number | string;
      note?: string;
    };
    const org = store.organizations.find((o) => o.id === body.organizationId);
    if (!org) {
      throw new ApiClientError(404, { code: 'ORG_NOT_FOUND', message: 'Bayi bulunamadı.' });
    }
    const amountUsd = Number(body.amountUsd ?? 0);
    const hasGold = Number(body.hasGoldGram ?? 0);
    const entry: DemoLedgerRow = {
      id: `led_${Date.now()}`,
      organizationId: org.id,
      organizationCode: org.code,
      organizationName: org.name,
      entryType: body.entryType ?? 'PAYMENT_CREDIT',
      referenceNo: body.referenceNo ?? 'REF',
      amountUsd: amountUsd.toFixed(2),
      hasGoldGram: hasGold.toFixed(4),
      note: body.note ?? '',
      createdById: 'usr_taragold_01',
      createdByEmail: 'emre.gonel@pigomass.com',
      createdAt: new Date().toISOString(),
    };
    demoLedgerEntries = [entry, ...demoLedgerEntries];
    if (body.entryType === 'PAYMENT_CREDIT') {
      store = {
        ...store,
        organizations: store.organizations.map((o) =>
          o.id === org.id
            ? { ...o, usedCreditUsd: Math.max(0, o.usedCreditUsd - amountUsd) }
            : o
        ),
      };
      persistStore();
    }
    if (body.entryType === 'HAS_DELIVERY') {
      store = {
        ...store,
        organizations: store.organizations.map((o) =>
          o.id === org.id ? { ...o, usedHasGram: Math.max(0, o.usedHasGram - hasGold) } : o
        ),
      };
      persistStore();
    }
    return buildEnvelope(entry as unknown as T);
  }

  if (opsBasePath === '/api/v1/ops/work-orders' && method === 'GET') {
    requireCapability('production:manage');
    return buildPaginatedEnvelope(path, [] as unknown[]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/b2b-orders' && method === 'GET') {
    requireCapability('orders:manage');
    return buildPaginatedEnvelope(path, [...store.b2bOrders]) as ApiEnvelope<T>;
  }
  if (opsBasePath === '/api/v1/ops/b2c-orders' && method === 'GET') {
    requireCapability('orders:manage');
    return buildPaginatedEnvelope(path, [...store.b2cOrders]) as ApiEnvelope<T>;
  }

  // ── Market Rates (/api/v1/market/rates & /api/v1/ops/rates) ──────────
  if ((path === '/api/v1/market/rates' || path === '/api/v1/rates') && method === 'GET') {
    return buildEnvelope({
      ...store.rates,
      fxBaseRates: { ...store.rates.fxBaseRates },
    } as unknown as T);
  }

  if ((path === '/api/v1/ops/rates' || path === '/api/v1/rates') && method === 'PATCH') {
    const patch = options.body as Partial<LiveRates>;
    store = {
      ...store,
      rates: {
        ...store.rates,
        ...patch,
        fxBaseRates: patch.fxBaseRates
          ? { ...store.rates.fxBaseRates, ...patch.fxBaseRates }
          : { ...store.rates.fxBaseRates },
      },
    };
    persistStore();
    return buildEnvelope({
      ...store.rates,
      fxBaseRates: { ...store.rates.fxBaseRates },
    } as unknown as T);
  }

  // ── Storefront Favorites ─────────────────────────────────────────────
  if (
    (path === '/api/v1/storefront/favorites' || path === '/api/v1/favorites') &&
    method === 'GET'
  ) {
    return buildEnvelope([...store.favorites] as unknown as T);
  }

  if (
    (path === '/api/v1/storefront/favorites/toggle' || path === '/api/v1/favorites/toggle') &&
    method === 'POST'
  ) {
    const { parentSku } = (options.body ?? {}) as { parentSku: string };
    const exists = store.favorites.includes(parentSku);
    store = {
      ...store,
      favorites: exists
        ? store.favorites.filter((id) => id !== parentSku)
        : [parentSku, ...store.favorites],
    };
    persistStore();
    return buildEnvelope([...store.favorites] as unknown as T);
  }

  // ── B2C Storefront Cart & Orders (/api/v1/storefront/*) ──────────────
  if (
    (path === '/api/v1/storefront/cart' || path === '/api/v1/commerce/b2c-cart') &&
    method === 'GET'
  ) {
    const snap: B2cCartSnapshot = {
      items: store.b2cCartItems.map((item) => ({ ...item })),
      priceLockedUntil: store.b2cPriceLockedUntil,
      snapshotId: store.rates.snapshotId,
    };
    return buildEnvelope(snap as unknown as T);
  }

  if (
    (path === '/api/v1/storefront/cart/items' || path === '/api/v1/commerce/b2c-cart/items') &&
    method === 'POST'
  ) {
    const incoming = options.body as Omit<B2cCartItem, 'id' | 'addedAt'>;
    const normEngraving = incoming.engravingText.trim();
    const existingIdx = store.b2cCartItems.findIndex(
      (i) =>
        i.sku === incoming.sku &&
        i.size === incoming.size &&
        i.engravingText.trim().toLowerCase() === normEngraving.toLowerCase() &&
        i.giftWrap === incoming.giftWrap
    );
    const nextItems =
      existingIdx >= 0
        ? store.b2cCartItems.map((item, idx) =>
            idx === existingIdx
              ? {
                  ...item,
                  qty: Math.min(10, item.qty + incoming.qty),
                  unitFinalPriceTry: incoming.unitFinalPriceTry,
                  unitListPriceTry: incoming.unitListPriceTry,
                  snapshotId: incoming.snapshotId,
                }
              : item
          )
        : [
            {
              ...incoming,
              id: `b2c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
              engravingText: normEngraving,
              addedAt: new Date().toISOString(),
            },
            ...store.b2cCartItems,
          ];

    store = {
      ...store,
      b2cCartItems: nextItems,
      b2cPriceLockedUntil: new Date(Date.now() + B2C_LOCK_MS).toISOString(),
    };
    persistStore();
    return buildEnvelope({
      items: store.b2cCartItems.map((i) => ({ ...i })),
      priceLockedUntil: store.b2cPriceLockedUntil,
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  const b2cItemMatch = path.match(
    /^\/api\/v1\/(?:storefront\/cart|commerce\/b2c-cart)\/items\/([^/]+)$/
  );
  if (b2cItemMatch) {
    const itemId = decodeURIComponent(b2cItemMatch[1]);
    if (method === 'PATCH') {
      const patch = options.body as Partial<B2cCartItem>;
      store = {
        ...store,
        b2cCartItems: store.b2cCartItems.map((item) =>
          item.id === itemId
            ? {
                ...item,
                ...patch,
                qty: patch.qty !== undefined ? Math.max(1, Math.min(10, patch.qty)) : item.qty,
              }
            : item
        ),
      };
      persistStore();
      return buildEnvelope({
        items: store.b2cCartItems.map((i) => ({ ...i })),
        priceLockedUntil: store.b2cPriceLockedUntil,
        snapshotId: store.rates.snapshotId,
      } as unknown as T);
    }
    if (method === 'DELETE') {
      store = {
        ...store,
        b2cCartItems: store.b2cCartItems.filter((item) => item.id !== itemId),
      };
      persistStore();
      return buildEnvelope({
        items: store.b2cCartItems.map((i) => ({ ...i })),
        priceLockedUntil: store.b2cPriceLockedUntil,
        snapshotId: store.rates.snapshotId,
      } as unknown as T);
    }
  }

  if (
    (path === '/api/v1/storefront/cart' || path === '/api/v1/commerce/b2c-cart') &&
    method === 'DELETE'
  ) {
    store = {
      ...store,
      b2cCartItems: [],
      b2cPriceLockedUntil: new Date(Date.now() + B2C_LOCK_MS).toISOString(),
    };
    persistStore();
    return buildEnvelope({
      items: [],
      priceLockedUntil: store.b2cPriceLockedUntil,
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  if (
    (path === '/api/v1/storefront/cart/refresh-lock' ||
      path === '/api/v1/commerce/b2c-cart/refresh-lock') &&
    method === 'POST'
  ) {
    store = {
      ...store,
      b2cPriceLockedUntil: new Date(Date.now() + B2C_LOCK_MS).toISOString(),
    };
    persistStore();
    return buildEnvelope({
      items: store.b2cCartItems.map((i) => ({ ...i })),
      priceLockedUntil: store.b2cPriceLockedUntil,
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  if (
    (path === '/api/v1/storefront/orders' || path === '/api/v1/commerce/b2c-orders') &&
    method === 'GET'
  ) {
    return buildEnvelope([...store.b2cOrders] as unknown as T);
  }

  if (
    (path === '/api/v1/storefront/orders' || path === '/api/v1/commerce/b2c-orders') &&
    method === 'POST'
  ) {
    if (store.b2cCartItems.length === 0) {
      throw new ApiClientError(400, {
        code: 'EMPTY_CART',
        message: 'Sipariş oluşturmak için sepette en az bir ürün bulunmalıdır.',
      });
    }
    const payload = options.body as Omit<
      B2cOrderRecord,
      'orderNo' | 'createdAt' | 'items' | 'status'
    >;
    const hasMadeToOrder = store.b2cCartItems.some(
      (item) => item.stockStatus === 'Siparişe Özel' || item.engravingText.trim().length > 0
    );
    const orderNo = `TG-B2C-2026-${String(1041 + store.b2cOrders.length).padStart(4, '0')}`;
    const record: B2cOrderRecord = {
      ...payload,
      orderNo,
      createdAt: new Date().toISOString(),
      items: store.b2cCartItems.map((item) => ({ ...item })),
      status: hasMadeToOrder ? 'ATOLYE_URETIMDE' : 'ONAYLANDI',
    };
    store = {
      ...store,
      b2cOrders: [record, ...store.b2cOrders],
      b2cCartItems: [],
    };
    persistStore();
    return buildEnvelope(record as unknown as T);
  }

  const b2cStatusMatch = path.match(
    /^\/api\/v1\/(?:ops\/b2c-orders|commerce\/b2c-orders)\/([^/]+)\/status$/
  );
  if (b2cStatusMatch && method === 'PATCH') {
    requireCapability('orders:manage');
    const orderNo = decodeURIComponent(b2cStatusMatch[1]);
    const { status } = options.body as { status: B2cOrderRecord['status'] };
    store = {
      ...store,
      b2cOrders: store.b2cOrders.map((o) => (o.orderNo === orderNo ? { ...o, status } : o)),
    };
    persistStore();
    return buildEnvelope([...store.b2cOrders] as unknown as T);
  }

  // ── B2B Tenant-Isolated Dealer Draft & Orders (/api/v1/b2b/*) ────────
  const currentDealerOrg = resolveActiveDealerOrg();
  const currentOrgId = currentDealerOrg.id;
  const currentOrgDraft = store.b2bDraftsByOrg[currentOrgId] ?? [];

  if ((path === '/api/v1/b2b/draft' || path === '/api/v1/commerce/b2b-draft') && method === 'GET') {
    const snap: B2bDraftSnapshot = {
      lines: currentOrgDraft.map((line) => ({ ...line })),
      dealer: buildDealerProfile(currentDealerOrg),
      snapshotId: store.rates.snapshotId,
    };
    return buildEnvelope(snap as unknown as T);
  }

  if (
    (path === '/api/v1/b2b/draft/lines' || path === '/api/v1/commerce/b2b-draft/lines') &&
    method === 'POST'
  ) {
    const raw = options.body as
      | Omit<B2bOrderLine, 'id' | 'addedAt'>
      | Array<Omit<B2bOrderLine, 'id' | 'addedAt'>>;
    const incomingList = Array.isArray(raw) ? raw : [raw];
    let nextLines = [...currentOrgDraft];

    incomingList.forEach((incoming) => {
      const existingIdx = nextLines.findIndex(
        (l) =>
          l.sku === incoming.sku &&
          l.size === incoming.size &&
          l.supplyType === incoming.supplyType &&
          l.dealerStampNote.trim().toLowerCase() === incoming.dealerStampNote.trim().toLowerCase()
      );
      if (existingIdx >= 0) {
        nextLines = nextLines.map((line, idx) =>
          idx === existingIdx
            ? {
                ...line,
                qty: Math.min(500, line.qty + incoming.qty),
                unitWholesaleUsd: incoming.unitWholesaleUsd,
                unitWholesaleTry: incoming.unitWholesaleTry,
                unitFireIncludedFineGram: incoming.unitFireIncludedFineGram,
                unitLaborAndStoneUsd: incoming.unitLaborAndStoneUsd,
                snapshotId: incoming.snapshotId,
              }
            : line
        );
      } else {
        nextLines = [
          {
            ...incoming,
            id: `b2b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
            addedAt: new Date().toISOString(),
          },
          ...nextLines,
        ];
      }
    });

    store = {
      ...store,
      b2bDraftsByOrg: {
        ...store.b2bDraftsByOrg,
        [currentOrgId]: nextLines,
      },
    };
    persistStore();
    return buildEnvelope({
      lines: nextLines.map((l) => ({ ...l })),
      dealer: buildDealerProfile(currentDealerOrg),
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  const b2bLineMatch = path.match(/^\/api\/v1\/(?:b2b\/draft|commerce\/b2b-draft)\/lines\/([^/]+)$/);
  if (b2bLineMatch) {
    const lineId = decodeURIComponent(b2bLineMatch[1]);
    if (method === 'PATCH') {
      const patch = options.body as Partial<B2bOrderLine>;
      const nextLines = currentOrgDraft.map((line) =>
        line.id === lineId
          ? {
              ...line,
              ...patch,
              qty: patch.qty !== undefined ? Math.max(1, Math.min(500, patch.qty)) : line.qty,
            }
          : line
      );
      store = {
        ...store,
        b2bDraftsByOrg: { ...store.b2bDraftsByOrg, [currentOrgId]: nextLines },
      };
      persistStore();
      return buildEnvelope({
        lines: nextLines.map((l) => ({ ...l })),
        dealer: buildDealerProfile(currentDealerOrg),
        snapshotId: store.rates.snapshotId,
      } as unknown as T);
    }
    if (method === 'DELETE') {
      const nextLines = currentOrgDraft.filter((line) => line.id !== lineId);
      store = {
        ...store,
        b2bDraftsByOrg: { ...store.b2bDraftsByOrg, [currentOrgId]: nextLines },
      };
      persistStore();
      return buildEnvelope({
        lines: nextLines.map((l) => ({ ...l })),
        dealer: buildDealerProfile(currentDealerOrg),
        snapshotId: store.rates.snapshotId,
      } as unknown as T);
    }
  }

  if ((path === '/api/v1/b2b/draft' || path === '/api/v1/commerce/b2b-draft') && method === 'DELETE') {
    store = {
      ...store,
      b2bDraftsByOrg: { ...store.b2bDraftsByOrg, [currentOrgId]: [] },
    };
    persistStore();
    return buildEnvelope({
      lines: [],
      dealer: buildDealerProfile(currentDealerOrg),
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  if ((path === '/api/v1/b2b/orders' || path === '/api/v1/commerce/b2b-orders') && method === 'GET') {
    // Strict tenant isolation: OPS/Super Admin sees all organizations; B2B sees ONLY active organization
    const scopedOrders =
      activeMem.audience === 'erp'
        ? store.b2bOrders
        : store.b2bOrders.filter((o) => o.organizationId === currentOrgId);
    return buildEnvelope([...scopedOrders] as unknown as T);
  }

  if ((path === '/api/v1/b2b/orders' || path === '/api/v1/commerce/b2b-orders') && method === 'POST') {
    if (currentOrgDraft.length === 0) {
      throw new ApiClientError(400, {
        code: 'EMPTY_B2B_ORDER',
        message: 'Sipariş fişi onaylamak için en az bir kalem eklemelisiniz.',
      });
    }
    const payload = options.body as Omit<
      B2bOrderRecord,
      'orderNo' | 'createdAt' | 'lines' | 'status'
    >;
    const dealerProfile = buildDealerProfile(currentDealerOrg);
    const hasProduction = currentOrgDraft.some((line) => line.supplyType === 'PRODUCTION');
    const orderNo = `TG-B2B-2026-${String(146 + store.b2bOrders.length).padStart(4, '0')}`;
    const record: B2bOrderRecord = {
      ...payload,
      organizationId: currentOrgId,
      branchId: payload.branchId || dealerProfile.branchId,
      branchName: payload.branchName || dealerProfile.branchName,
      createdByUserId: 'usr_taragold_01',
      createdByUserName: 'Emre Gönel',
      orderNo,
      createdAt: new Date().toISOString(),
      lines: currentOrgDraft.map((line) => ({ ...line })),
      status: hasProduction ? 'ATOLYE_PLANLANDI' : 'PROFORMA_ONAYLANDI',
    };

    const updatedOrgs = store.organizations.map((org) => {
      if (org.id !== currentOrgId) return org;
      if (record.settlementMethod === 'HAS_PLUS_CURRENCY') {
        return {
          ...org,
          usedHasGram: Number((org.usedHasGram + (record.totalHasGoldGram ?? 0)).toFixed(4)),
          usedCreditUsd: Number((org.usedCreditUsd + (record.totalLaborAndStoneUsd ?? 0)).toFixed(2)),
        };
      }
      if (record.settlementMethod === 'OPEN_ACCOUNT' || record.settlementMethod === 'CONSIGNMENT') {
        return {
          ...org,
          usedCreditUsd: Number((org.usedCreditUsd + record.totalWholesaleUsd).toFixed(2)),
        };
      }
      return org;
    });

    store = {
      ...store,
      organizations: updatedOrgs,
      b2bOrders: [record, ...store.b2bOrders],
      b2bDraftsByOrg: { ...store.b2bDraftsByOrg, [currentOrgId]: [] },
    };
    persistStore();
    return buildEnvelope(record as unknown as T);
  }

  const b2bStatusMatch = path.match(
    /^\/api\/v1\/(?:ops\/b2b-orders|commerce\/b2b-orders)\/([^/]+)\/status$/
  );
  if (b2bStatusMatch && method === 'PATCH') {
    requireCapability('orders:manage');
    const orderNo = decodeURIComponent(b2bStatusMatch[1]);
    const { status } = options.body as { status: B2bOrderRecord['status'] };
    store = {
      ...store,
      b2bOrders: store.b2bOrders.map((o) => (o.orderNo === orderNo ? { ...o, status } : o)),
    };
    persistStore();
    return buildEnvelope([...store.b2bOrders] as unknown as T);
  }

  const b2bReorderMatch = path.match(
    /^\/api\/v1\/(?:b2b\/orders|commerce\/b2b-orders)\/([^/]+)\/reorder$/
  );
  if (b2bReorderMatch && method === 'POST') {
    const orderNo = decodeURIComponent(b2bReorderMatch[1]);
    const sourceOrder = store.b2bOrders.find((o) => o.orderNo === orderNo);
    if (!sourceOrder) {
      throw new ApiClientError(404, {
        code: 'ORDER_NOT_FOUND',
        message: `Sipariş bulunamadı: ${orderNo}`,
      });
    }
    if (activeMem.audience !== 'erp' && sourceOrder.organizationId !== currentOrgId) {
      throw new ApiClientError(403, {
        code: 'TENANT_ISOLATION_VIOLATION',
        message: 'Başka firmaya ait sipariş kaydına erişilemez.',
      });
    }
    const clonedLines: B2bOrderLine[] = sourceOrder.lines.map((line) => ({
      ...line,
      id: `b2b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
      snapshotId: store.rates.snapshotId,
      addedAt: new Date().toISOString(),
    }));
    const nextLines = [...clonedLines, ...currentOrgDraft];
    store = {
      ...store,
      b2bDraftsByOrg: { ...store.b2bDraftsByOrg, [currentOrgId]: nextLines },
    };
    persistStore();
    return buildEnvelope({
      lines: nextLines.map((l) => ({ ...l })),
      dealer: buildDealerProfile(currentDealerOrg),
      snapshotId: store.rates.snapshotId,
    } as unknown as T);
  }

  throw new ApiClientError(404, {
    code: 'ROUTE_NOT_FOUND',
    message: `Bilinmeyen API uç noktası: ${method} ${path}`,
  });
}
