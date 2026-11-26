import { useEffect, useState } from 'react';
import { ArrowLeft, Building2, Plus, Search, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@taragold/shared/components/ui';
import {
  useCreateBranchMutation,
  useCreateOpsOrganizationMutation,
  useOpsOrganizationDossierQuery,
  useOpsOrganizationsQuery,
  useOrgAddressMutation,
  useOrgBankMutation,
  useOrgCreditReviewMutation,
  useOrgDocumentMutation,
  useOrgPriceQuotesQuery,
  usePatchOpsOrganizationMutation,
  useUploadOrgLogoMutation,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import type { OpsOrganization, OpsPartnerRole } from '@taragold/shared/features/ops/types';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import { ApiClientError } from '@taragold/shared/lib/api/client';
import { useCreateOpsMembershipMutation } from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { opsService } from '@taragold/shared/features/ops/services/opsService';

const APPROVAL_LABEL: Record<string, string> = {
  DRAFT: 'Taslak',
  PENDING: 'Onay bekliyor',
  APPROVED: 'Onaylandı',
  REJECTED: 'Reddedildi',
  SUSPENDED: 'Askıya alındı',
  INACTIVE: 'Pasif',
};

const RISK_LABEL: Record<string, string> = {
  LOW: 'Düşük',
  MEDIUM: 'Orta',
  HIGH: 'Yüksek',
  BLOCKED: 'Blokeli',
};

const ROLE_LABEL: Record<string, string> = {
  ORG_ADMIN: 'Firma yöneticisi',
  B2B_BUYER: 'Satın alma / sipariş',
  OPS: 'Operasyon',
  SUPER_ADMIN: 'Süper admin',
  B2C_CUSTOMER: 'B2C müşteri',
};

function money(v?: string | number | null) {
  if (v == null || v === '') return '—';
  return `$${formatTrNumber(Number(v), 0)}`;
}

function PartnerBadges({ org }: { org: OpsOrganization }) {
  const roles = org.partnerRoles?.length
    ? org.partnerRoles
    : ([org.isBuyer ? 'BUYER' : null, org.isSupplier ? 'SUPPLIER' : null].filter(Boolean) as string[]);
  return (
    <div className="flex flex-wrap gap-1">
      {roles.includes('BUYER') && <Badge variant="secondary">Müşteri</Badge>}
      {roles.includes('SUPPLIER') && <Badge variant="outline">Tedarikçi</Badge>}
      {roles.includes('PLATFORM') && <Badge variant="outline">Platform</Badge>}
      {!roles.length && <Badge variant="outline">{org.orgType}</Badge>}
    </div>
  );
}

function OverviewCards({ org }: { org: OpsOrganization }) {
  const o = org.overview;
  const cards = [
    { label: 'Toplam sipariş', value: o ? String(o.totalOrders) : '—' },
    { label: 'Sipariş hacmi', value: o?.totalOrderVolumeUsd != null ? money(o.totalOrderVolumeUsd) : '—' },
    { label: 'Cari bakiye', value: money(o?.cariBalanceUsd ?? org.usedCreditUsd) },
    { label: 'Kredi limiti', value: money(o?.creditLimitUsd ?? org.creditLimitUsd) },
    { label: 'Kullanılabilir kredi', value: money(o?.availableCreditUsd ?? org.remainingCreditUsd) },
    { label: 'Aktif kullanıcı', value: String(o?.activeUserCount ?? org.activeUserCount ?? 0) },
    { label: 'Şube', value: String(o?.branchCount ?? org.branchCount ?? org.branches?.length ?? 0) },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-border bg-card px-3 py-2">
          <div className="text-sm font-semibold tabular-nums">{c.value}</div>
          <div className="text-[10px] text-muted-foreground mt-0.5">{c.label}</div>
        </div>
      ))}
    </div>
  );
}

function OrganizationDetail({
  orgId,
  onBack,
}: {
  orgId: string;
  onBack: () => void;
}) {
  const dossier = useOpsOrganizationDossierQuery(orgId);
  const patchMut = usePatchOpsOrganizationMutation();
  const logoMut = useUploadOrgLogoMutation();
  const addrMut = useOrgAddressMutation();
  const bankMut = useOrgBankMutation();
  const docMut = useOrgDocumentMutation();
  const creditMut = useOrgCreditReviewMutation();
  const branchMut = useCreateBranchMutation();
  const membershipMut = useCreateOpsMembershipMutation();
  const quotesQuery = useOrgPriceQuotesQuery(orgId, { pageSize: 50 });

  const org = dossier.data;
  const isSupplier = Boolean(org?.isSupplier || org?.partnerRoles?.includes('SUPPLIER'));
  const isBuyer = Boolean(org?.isBuyer || org?.partnerRoles?.includes('BUYER') || !isSupplier);

  const [corp, setCorp] = useState({
    name: '',
    legalName: '',
    taxOffice: '',
    taxNumber: '',
    contactName: '',
    email: '',
    phone: '',
    website: '',
    city: '',
    description: '',
    companyType: '',
    mersisNo: '',
    tradeRegistryNo: '',
    commercialNotes: '',
    supplierCode: '',
    supplierNotes: '',
    paymentTermDays: '30',
  });
  const [addrForm, setAddrForm] = useState({
    title: '',
    line: '',
    city: '',
    addressType: 'HQ',
  });
  const [bankForm, setBankForm] = useState({ bankName: '', iban: '', accountHolder: '' });
  const [branchForm, setBranchForm] = useState({ code: '', name: '', city: '', address: '' });
  const [memberForm, setMemberForm] = useState({ userId: '', roleKey: 'B2B_BUYER', jobTitle: '' });
  const [users, setUsers] = useState<Array<{ id: string; email: string; fullName: string }>>([]);
  const [riskForm, setRiskForm] = useState({ riskLevel: 'LOW', riskNote: '', creditReviewNote: '', paymentTermDays: '30' });
  const [creditLimits, setCreditLimits] = useState({ creditLimitUsd: '', hasLimitGram: '' });

  useEffect(() => {
    if (!org) return;
    setCorp({
      name: org.name || '',
      legalName: org.legalName || '',
      taxOffice: org.taxOffice || '',
      taxNumber: org.taxNumber || '',
      contactName: org.contactName || '',
      email: org.email || '',
      phone: org.phone || '',
      website: org.website || '',
      city: org.city || '',
      description: org.description || '',
      companyType: org.companyType || '',
      mersisNo: org.mersisNo || '',
      tradeRegistryNo: org.tradeRegistryNo || '',
      commercialNotes: org.commercialNotes || '',
      supplierCode: org.supplierCode || '',
      supplierNotes: org.supplierNotes || '',
      paymentTermDays: String(org.paymentTermDays ?? 30),
    });
    setRiskForm({
      riskLevel: org.riskLevel || 'LOW',
      riskNote: org.riskNote || '',
      creditReviewNote: org.creditReviewNote || '',
      paymentTermDays: String(org.paymentTermDays ?? 30),
    });
    setCreditLimits({
      creditLimitUsd: String(org.creditLimitUsd ?? ''),
      hasLimitGram: String(org.hasLimitGram ?? ''),
    });
  }, [org]);

  useEffect(() => {
    void opsService.listUsers({ pageSize: 100 }).then((r) => {
      setUsers(r.items.map((u) => ({ id: u.id, email: u.email, fullName: u.fullName })));
    });
  }, []);

  if (dossier.isLoading || !org) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
        {dossier.isError ? 'Firma detayı yüklenemedi.' : 'Yükleniyor…'}
      </div>
    );
  }

  const saveCorp = async () => {
    try {
      await patchMut.mutateAsync({
        orgId,
        body: {
          name: corp.name,
          legalName: corp.legalName,
          taxOffice: corp.taxOffice,
          taxNumber: corp.taxNumber,
          contactName: corp.contactName,
          email: corp.email,
          phone: corp.phone,
          website: corp.website,
          city: corp.city,
          description: corp.description,
          companyType: corp.companyType,
          mersisNo: corp.mersisNo,
          tradeRegistryNo: corp.tradeRegistryNo,
          commercialNotes: corp.commercialNotes,
          supplierCode: corp.supplierCode,
          supplierNotes: corp.supplierNotes,
          paymentTermDays: Number(corp.paymentTermDays) || 0,
        },
      });
      toast.success('Kurumsal bilgiler kaydedildi');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Kayıt başarısız');
    }
  };

  const toggleRole = async (role: OpsPartnerRole) => {
    const current = new Set(org.partnerRoles ?? []);
    if (current.has(role)) current.delete(role);
    else current.add(role);
    if (current.size === 0) current.add('BUYER');
    try {
      await patchMut.mutateAsync({ orgId, body: { partnerRoles: [...current] as OpsPartnerRole[] } });
      toast.success('İş ortağı rolleri güncellendi');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Güncellenemedi');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button type="button" variant="outline" size="sm" onClick={onBack}>
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Liste
          </Button>
          <div className="flex items-center gap-3">
            <div className="h-14 w-14 rounded-lg border border-border bg-muted overflow-hidden flex items-center justify-center">
              {org.logoUrl ? (
                <img src={org.logoUrl} alt="" className="h-full w-full object-cover" />
              ) : (
                <Building2 className="w-6 h-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <div className="text-lg font-semibold leading-tight">{org.name}</div>
              <div className="text-xs text-muted-foreground font-mono">{org.code}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                <PartnerBadges org={org} />
                <Badge variant="outline">{APPROVAL_LABEL[org.approvalStatus || ''] || org.approvalStatus}</Badge>
                <Badge variant={org.isActive ? 'secondary' : 'outline'}>
                  {org.isActive ? 'Aktif' : 'Pasif'}
                </Badge>
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex">
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                void logoMut.mutateAsync({ orgId, file: f }).then(
                  () => toast.success('Logo yüklendi'),
                  (err) => toast.error(err instanceof Error ? err.message : 'Logo yüklenemedi')
                );
              }}
            />
            <Button type="button" size="sm" variant="outline" asChild>
              <span>
                <Upload className="w-3.5 h-3.5 mr-1" />
                Logo
              </span>
            </Button>
          </label>
          <Select
            value={org.approvalStatus || 'APPROVED'}
            onValueChange={(v) => {
              void patchMut.mutateAsync({ orgId, body: { approvalStatus: v } }).then(
                () => toast.success('Onay durumu güncellendi'),
                (e) => toast.error(e instanceof Error ? e.message : 'Hata')
              );
            }}
          >
            <SelectTrigger className="h-9 w-44">
              <SelectValue placeholder="Onay" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(APPROVAL_LABEL).map(([k, v]) => (
                <SelectItem key={k} value={k}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
        Yetkili: <span className="text-foreground font-medium">{org.contactName || '—'}</span>
        {' · '}
        {org.email || '—'}
        {' · '}
        {org.phone || '—'}
        {' · '}
        Kayıt: {new Date(org.createdAt).toLocaleDateString('tr-TR')}
      </div>

      <OverviewCards org={org} />

      <Tabs defaultValue="overview">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="overview">Genel Bakış</TabsTrigger>
          <TabsTrigger value="corporate">Kurumsal</TabsTrigger>
          <TabsTrigger value="addresses">Adresler & Şubeler</TabsTrigger>
          <TabsTrigger value="users">Kullanıcılar</TabsTrigger>
          {isBuyer && <TabsTrigger value="finance">Finans</TabsTrigger>}
          <TabsTrigger value="commercial">Ticari</TabsTrigger>
          {isSupplier && <TabsTrigger value="supplier">Tedarikçi</TabsTrigger>}
          <TabsTrigger value="bank">Banka</TabsTrigger>
          <TabsTrigger value="docs">Belgeler</TabsTrigger>
          <TabsTrigger value="activity">Aktivite</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-3 pt-3">
          <PortalDataCard>
            <div className="p-4 space-y-2 text-sm">
              <div>
                <span className="text-muted-foreground">Ticari unvan:</span> {org.legalName || org.name}
              </div>
              <div>
                <span className="text-muted-foreground">Şehir:</span> {org.city || '—'}
              </div>
              <div>
                <span className="text-muted-foreground">Risk:</span>{' '}
                {RISK_LABEL[org.riskLevel || ''] || org.riskLevel || '—'}
              </div>
              <div className="text-muted-foreground text-xs pt-2">{org.description || 'Açıklama girilmemiş.'}</div>
            </div>
          </PortalDataCard>
        </TabsContent>

        <TabsContent value="corporate" className="pt-3 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4">
            {(
              [
                ['name', 'Firma adı'],
                ['legalName', 'Ticari unvan'],
                ['taxOffice', 'Vergi dairesi'],
                ['taxNumber', 'Vergi numarası'],
                ['mersisNo', 'MERSİS'],
                ['tradeRegistryNo', 'Ticaret sicil no'],
                ['companyType', 'Şirket türü'],
                ['contactName', 'Ana yetkili'],
                ['email', 'E-posta'],
                ['phone', 'Telefon'],
                ['website', 'Web sitesi'],
                ['city', 'Şehir'],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="space-y-1">
                <Label className="text-[11px]">{label}</Label>
                <Input
                  value={corp[key]}
                  onChange={(e) => setCorp((p) => ({ ...p, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="md:col-span-2 space-y-1">
              <Label className="text-[11px]">Açıklama</Label>
              <Input
                value={corp.description}
                onChange={(e) => setCorp((p) => ({ ...p, description: e.target.value }))}
              />
            </div>
          </div>
          <Button type="button" size="sm" onClick={() => void saveCorp()} disabled={patchMut.isPending}>
            Kaydet
          </Button>
        </TabsContent>

        <TabsContent value="addresses" className="pt-3 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 space-y-2">
            <div className="text-sm font-medium">Yeni adres</div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <Select
                value={addrForm.addressType}
                onValueChange={(v) => setAddrForm((p) => ({ ...p, addressType: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="HQ">Merkez</SelectItem>
                  <SelectItem value="BILLING">Fatura</SelectItem>
                  <SelectItem value="SHIPPING">Teslimat</SelectItem>
                  <SelectItem value="BRANCH">Şube</SelectItem>
                  <SelectItem value="WAREHOUSE">Depo</SelectItem>
                  <SelectItem value="OTHER">Diğer</SelectItem>
                </SelectContent>
              </Select>
              <Input
                placeholder="Başlık"
                value={addrForm.title}
                onChange={(e) => setAddrForm((p) => ({ ...p, title: e.target.value }))}
              />
              <Input
                placeholder="Şehir"
                value={addrForm.city}
                onChange={(e) => setAddrForm((p) => ({ ...p, city: e.target.value }))}
              />
              <Input
                placeholder="Açık adres"
                value={addrForm.line}
                onChange={(e) => setAddrForm((p) => ({ ...p, line: e.target.value }))}
              />
            </div>
            <Button
              type="button"
              size="sm"
              disabled={addrMut.isPending}
              onClick={() => {
                if (!addrForm.title || !addrForm.line) {
                  toast.error('Başlık ve adres zorunlu');
                  return;
                }
                void addrMut
                  .mutateAsync({ orgId, body: { ...addrForm, isDefault: false } })
                  .then(() => {
                    toast.success('Adres eklendi');
                    setAddrForm({ title: '', line: '', city: '', addressType: 'HQ' });
                  })
                  .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
              }}
            >
              Adres ekle
            </Button>
          </div>
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Başlık</TableHead>
                <TableHead>Tür</TableHead>
                <TableHead>Şehir</TableHead>
                <TableHead>Adres</TableHead>
                <TableHead>Durum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.addresses ?? []).map((a) => (
                <TableRow key={a.id} className={!a.isActive ? 'opacity-50' : undefined}>
                  <TableCell>{a.title}</TableCell>
                  <TableCell>{a.addressType}</TableCell>
                  <TableCell>{a.city || '—'}</TableCell>
                  <TableCell className="max-w-xs truncate">{a.line}</TableCell>
                  <TableCell>{a.isActive ? (a.isDefault ? 'Varsayılan' : 'Aktif') : 'Pasif'}</TableCell>
                </TableRow>
              ))}
              {(org.addresses ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                    Adres yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          <div className="rounded-xl border border-border bg-card p-4 space-y-2">
            <div className="text-sm font-medium">Şube ekle</div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <Input
                placeholder="Kod"
                value={branchForm.code}
                onChange={(e) => setBranchForm((p) => ({ ...p, code: e.target.value }))}
              />
              <Input
                placeholder="Ad"
                value={branchForm.name}
                onChange={(e) => setBranchForm((p) => ({ ...p, name: e.target.value }))}
              />
              <Input
                placeholder="Şehir"
                value={branchForm.city}
                onChange={(e) => setBranchForm((p) => ({ ...p, city: e.target.value }))}
              />
              <Input
                placeholder="Adres"
                value={branchForm.address}
                onChange={(e) => setBranchForm((p) => ({ ...p, address: e.target.value }))}
              />
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                void branchMut
                  .mutateAsync({ organizationId: orgId, ...branchForm })
                  .then(() => {
                    toast.success('Şube eklendi');
                    setBranchForm({ code: '', name: '', city: '', address: '' });
                  })
                  .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
              }}
            >
              Şube kaydet
            </Button>
            <div className="text-xs text-muted-foreground pt-2">
              Mevcut şubeler:{' '}
              {(org.branches ?? []).map((b) => `${b.code} (${b.city})`).join(' · ') || '—'}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="users" className="pt-3 space-y-3">
          <div className="rounded-xl border border-border bg-card p-4 space-y-2">
            <div className="text-sm font-medium">Kullanıcı ata</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <Select
                value={memberForm.userId}
                onValueChange={(v) => setMemberForm((p) => ({ ...p, userId: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Kullanıcı" />
                </SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.fullName || u.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={memberForm.roleKey}
                onValueChange={(v) => setMemberForm((p) => ({ ...p, roleKey: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ORG_ADMIN">Firma yöneticisi</SelectItem>
                  <SelectItem value="B2B_BUYER">Satın alma / sipariş</SelectItem>
                </SelectContent>
              </Select>
              <Input
                placeholder="Pozisyon"
                value={memberForm.jobTitle}
                onChange={(e) => setMemberForm((p) => ({ ...p, jobTitle: e.target.value }))}
              />
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                if (!memberForm.userId) {
                  toast.error('Kullanıcı seçin');
                  return;
                }
                void membershipMut
                  .mutateAsync({
                    userId: memberForm.userId,
                    organizationId: orgId,
                    roleKey: memberForm.roleKey,
                    jobTitle: memberForm.jobTitle,
                    isActive: true,
                  })
                  .then(() => {
                    toast.success('Üyelik eklendi');
                    void dossier.refetch();
                  })
                  .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
              }}
            >
              Ata
            </Button>
          </div>
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Ad</TableHead>
                <TableHead>E-posta</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Pozisyon</TableHead>
                <TableHead>Son giriş</TableHead>
                <TableHead>Durum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.memberships ?? []).map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.userFullName}</TableCell>
                  <TableCell>{m.userEmail}</TableCell>
                  <TableCell>{ROLE_LABEL[m.roleKey] || m.roleKey}</TableCell>
                  <TableCell>{m.jobTitle || '—'}</TableCell>
                  <TableCell>
                    {m.lastLogin ? new Date(m.lastLogin).toLocaleString('tr-TR') : '—'}
                  </TableCell>
                  <TableCell>{m.isActive ? 'Aktif' : 'Pasif'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TabsContent>

        {isBuyer && (
          <TabsContent value="finance" className="pt-3 space-y-3">
            <OverviewCards org={org} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-xl border border-border bg-card p-4 space-y-2">
                <div className="text-sm font-medium">Kredi limitleri (SSOT: Organization)</div>
                <Label className="text-[11px]">USD limit</Label>
                <Input
                  value={creditLimits.creditLimitUsd}
                  onChange={(e) => setCreditLimits((p) => ({ ...p, creditLimitUsd: e.target.value }))}
                />
                <Label className="text-[11px]">Has altın limit (gr)</Label>
                <Input
                  value={creditLimits.hasLimitGram}
                  onChange={(e) => setCreditLimits((p) => ({ ...p, hasLimitGram: e.target.value }))}
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    void patchMut
                      .mutateAsync({
                        orgId,
                        body: {
                          creditLimitUsd: creditLimits.creditLimitUsd,
                          hasLimitGram: creditLimits.hasLimitGram,
                        },
                      })
                      .then(() => toast.success('Limitler güncellendi'))
                      .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
                  }}
                >
                  Limitleri kaydet
                </Button>
                <p className="text-[10px] text-muted-foreground">
                  Kullanılan bakiye cari defterden yönetilir; doğrudan düzenlenemez.
                </p>
              </div>
              <div className="rounded-xl border border-border bg-card p-4 space-y-2">
                <div className="text-sm font-medium">Manuel risk değerlendirmesi</div>
                <Select
                  value={riskForm.riskLevel}
                  onValueChange={(v) => setRiskForm((p) => ({ ...p, riskLevel: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(RISK_LABEL).map(([k, v]) => (
                      <SelectItem key={k} value={k}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Risk notu"
                  value={riskForm.riskNote}
                  onChange={(e) => setRiskForm((p) => ({ ...p, riskNote: e.target.value }))}
                />
                <Input
                  placeholder="Değerlendirme notu"
                  value={riskForm.creditReviewNote}
                  onChange={(e) => setRiskForm((p) => ({ ...p, creditReviewNote: e.target.value }))}
                />
                <Input
                  placeholder="Ödeme vadesi (gün)"
                  value={riskForm.paymentTermDays}
                  onChange={(e) => setRiskForm((p) => ({ ...p, paymentTermDays: e.target.value }))}
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    void creditMut
                      .mutateAsync({
                        orgId,
                        body: {
                          riskLevel: riskForm.riskLevel,
                          riskNote: riskForm.riskNote,
                          creditReviewNote: riskForm.creditReviewNote,
                          paymentTermDays: Number(riskForm.paymentTermDays) || 0,
                        },
                      })
                      .then(() => toast.success('Değerlendirme kaydedildi'))
                      .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
                  }}
                >
                  Değerlendirmeyi kaydet
                </Button>
              </div>
            </div>
            <Table className="text-xs">
              <TableHeader>
                <TableRow>
                  <TableHead>Tarih</TableHead>
                  <TableHead>Tür</TableHead>
                  <TableHead>Referans</TableHead>
                  <TableHead className="text-right">USD</TableHead>
                  <TableHead className="text-right">Has gr</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(org.recentLedger ?? []).map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>{new Date(e.createdAt).toLocaleString('tr-TR')}</TableCell>
                    <TableCell>{e.entryType}</TableCell>
                    <TableCell className="font-mono">{e.referenceNo}</TableCell>
                    <TableCell className="text-right tabular-nums">{e.amountUsd}</TableCell>
                    <TableCell className="text-right tabular-nums">{e.hasGoldGram}</TableCell>
                  </TableRow>
                ))}
                {(org.recentLedger ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                      Cari hareket yok
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TabsContent>
        )}

        <TabsContent value="commercial" className="pt-3 space-y-3">
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="text-sm font-medium">İş ortağı rolleri</div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant={org.partnerRoles?.includes('BUYER') ? 'default' : 'outline'}
                onClick={() => void toggleRole('BUYER')}
              >
                Müşteri
              </Button>
              <Button
                type="button"
                size="sm"
                variant={org.partnerRoles?.includes('SUPPLIER') ? 'default' : 'outline'}
                onClick={() => void toggleRole('SUPPLIER')}
              >
                Tedarikçi
              </Button>
            </div>
            <Label className="text-[11px]">Ticari notlar</Label>
            <Input
              value={corp.commercialNotes}
              onChange={(e) => setCorp((p) => ({ ...p, commercialNotes: e.target.value }))}
            />
            <Label className="text-[11px]">Ödeme vadesi (gün)</Label>
            <Input
              value={corp.paymentTermDays}
              onChange={(e) => setCorp((p) => ({ ...p, paymentTermDays: e.target.value }))}
            />
            <Button type="button" size="sm" onClick={() => void saveCorp()}>
              Kaydet
            </Button>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 space-y-2">
            <div className="text-sm font-medium">Fiyat sözleşmeleri (Pricing)</div>
            <p className="text-[11px] text-muted-foreground">
              Firmaya üretilmiş immutable PriceQuote kayıtları — ikinci ticari SSOT yok.
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Kanal</TableHead>
                  <TableHead>Reçete</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Geçerlilik</TableHead>
                  <TableHead className="text-right">Son fiyat</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(quotesQuery.data?.items ?? []).map((q) => (
                  <TableRow key={q.id}>
                    <TableCell className="font-mono text-xs">{q.parentSku}</TableCell>
                    <TableCell>{q.channel}</TableCell>
                    <TableCell className="text-xs">
                      v{q.recipeVersion}
                      {q.recipeStatus ? ` · ${q.recipeStatus}` : ''}
                    </TableCell>
                    <TableCell>
                      <Badge variant={q.isActive ? 'secondary' : 'outline'}>
                        {q.isActive ? 'Aktif' : 'Pasif'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {q.validFrom
                        ? new Date(q.validFrom).toLocaleString('tr-TR')
                        : new Date(q.createdAt).toLocaleString('tr-TR')}
                      {q.validUntil
                        ? ` → ${new Date(q.validUntil).toLocaleString('tr-TR')}`
                        : ' → açık'}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatTrNumber(Number(q.finalPriceTry), 2)} TRY
                    </TableCell>
                  </TableRow>
                ))}
                {(quotesQuery.data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-6">
                      {quotesQuery.isLoading
                        ? 'Yükleniyor…'
                        : 'Bu firmaya ait fiyat teklifi yok'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {isSupplier && (
          <TabsContent value="supplier" className="pt-3 space-y-3">
            <div className="rounded-xl border border-border bg-card p-4 space-y-2">
              <Label className="text-[11px]">Tedarikçi kodu</Label>
              <Input
                value={corp.supplierCode}
                onChange={(e) => setCorp((p) => ({ ...p, supplierCode: e.target.value }))}
              />
              <Label className="text-[11px]">Tedarikçi notları</Label>
              <Input
                value={corp.supplierNotes}
                onChange={(e) => setCorp((p) => ({ ...p, supplierNotes: e.target.value }))}
              />
              <Button type="button" size="sm" onClick={() => void saveCorp()}>
                Kaydet
              </Button>
              <p className="text-[10px] text-muted-foreground">
                Tedarikçi notları müşteri portalına sızmaz; yalnızca OPS görür.
              </p>
            </div>
          </TabsContent>
        )}

        <TabsContent value="bank" className="pt-3 space-y-3">
          <div className="rounded-xl border border-border bg-card p-4 space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <Input
                placeholder="Banka"
                value={bankForm.bankName}
                onChange={(e) => setBankForm((p) => ({ ...p, bankName: e.target.value }))}
              />
              <Input
                placeholder="IBAN"
                value={bankForm.iban}
                onChange={(e) => setBankForm((p) => ({ ...p, iban: e.target.value }))}
              />
              <Input
                placeholder="Hesap sahibi"
                value={bankForm.accountHolder}
                onChange={(e) => setBankForm((p) => ({ ...p, accountHolder: e.target.value }))}
              />
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                void bankMut
                  .mutateAsync({ orgId, body: bankForm })
                  .then(() => {
                    toast.success('Banka hesabı eklendi');
                    setBankForm({ bankName: '', iban: '', accountHolder: '' });
                  })
                  .catch((e) => toast.error(e instanceof Error ? e.message : 'Hata'));
              }}
            >
              Hesap ekle
            </Button>
          </div>
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Banka</TableHead>
                <TableHead>IBAN</TableHead>
                <TableHead>Para birimi</TableHead>
                <TableHead>Durum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.bankAccounts ?? []).map((b) => (
                <TableRow key={b.id}>
                  <TableCell>{b.bankName}</TableCell>
                  <TableCell className="font-mono">{b.iban}</TableCell>
                  <TableCell>{b.currency}</TableCell>
                  <TableCell>{b.isActive ? 'Aktif' : 'Pasif'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="docs" className="pt-3 space-y-3">
          <label className="inline-flex">
            <input
              type="file"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                void docMut
                  .mutateAsync({ orgId, file: f, meta: { name: f.name, docType: 'OTHER' } })
                  .then(() => toast.success('Belge yüklendi'))
                  .catch((err) => toast.error(err instanceof Error ? err.message : 'Hata'));
              }}
            />
            <Button type="button" size="sm" variant="outline" asChild>
              <span>
                <Upload className="w-3.5 h-3.5 mr-1" />
                Belge yükle
              </span>
            </Button>
          </label>
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Ad</TableHead>
                <TableHead>Tür</TableHead>
                <TableHead>Yükleyen</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.documents ?? []).map((d) => (
                <TableRow key={d.id}>
                  <TableCell>
                    {d.fileUrl ? (
                      <a href={d.fileUrl} target="_blank" rel="noreferrer" className="underline">
                        {d.name}
                      </a>
                    ) : (
                      d.name
                    )}
                  </TableCell>
                  <TableCell>{d.docType}</TableCell>
                  <TableCell>{d.uploadedByEmail || '—'}</TableCell>
                  <TableCell>{new Date(d.createdAt).toLocaleDateString('tr-TR')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="activity" className="pt-3">
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead>Tarih</TableHead>
                <TableHead>İşlem</TableHead>
                <TableHead>Aktör</TableHead>
                <TableHead>Varlık</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.activity ?? []).map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{new Date(a.createdAt).toLocaleString('tr-TR')}</TableCell>
                  <TableCell className="font-mono text-[11px]">{a.action}</TableCell>
                  <TableCell>{a.actorEmail || '—'}</TableCell>
                  <TableCell>
                    {a.entityType}:{a.entityId.slice(0, 8)}
                  </TableCell>
                </TableRow>
              ))}
              {(org.activity ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-6">
                    Aktivite yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export function OpsOrganizationsPage() {
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [page, setPage] = useState(1);
  const [partnerRole, setPartnerRole] = useState<string>('all');
  const [approvalStatus, setApprovalStatus] = useState<string>('all');
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [city, setCity] = useState('');
  const [roles, setRoles] = useState<OpsPartnerRole[]>(['BUYER']);
  const [creditLimitUsd, setCreditLimitUsd] = useState('50000');
  const [hasLimitGram, setHasLimitGram] = useState('500');

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const listQuery = useOpsOrganizationsQuery({
    q: debouncedQ || undefined,
    page,
    pageSize: 25,
    partnerRole: partnerRole === 'all' ? undefined : partnerRole,
    approvalStatus: approvalStatus === 'all' ? undefined : approvalStatus,
  });
  const createMut = useCreateOpsOrganizationMutation();
  const rows = listQuery.data?.items ?? [];
  const pagination = listQuery.data?.pagination;

  const onCreate = async () => {
    try {
      const org = await createMut.mutateAsync({
        code: code.trim(),
        name: name.trim(),
        city: city.trim(),
        orgType: roles.includes('SUPPLIER') && !roles.includes('BUYER') ? 'SUPPLIER' : 'DEALER',
        partnerRoles: roles,
        creditLimitUsd,
        hasLimitGram,
        isActive: true,
        approvalStatus: 'APPROVED',
      });
      toast.success('Firma oluşturuldu');
      setCreateOpen(false);
      setCode('');
      setName('');
      setCity('');
      setSelectedOrgId(org.id);
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Oluşturulamadı');
    }
  };

  if (selectedOrgId) {
    return (
      <div className="space-y-5">
        <PortalPageHeader eyebrow="İş Ortakları" title="Firma Dosyası" />
        <OrganizationDetail orgId={selectedOrgId} onBack={() => setSelectedOrgId(null)} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Business Partner Management"
        title={`Firmalar & İş Ortakları${pagination ? ` (${pagination.total})` : ''}`}
        actions={
          <>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Kod, ad, vergi no..."
                className="h-9 pl-8 w-56 text-xs"
              />
            </div>
            <Select value={partnerRole} onValueChange={setPartnerRole}>
              <SelectTrigger className="h-9 w-36">
                <SelectValue placeholder="Rol" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm roller</SelectItem>
                <SelectItem value="BUYER">Müşteri</SelectItem>
                <SelectItem value="SUPPLIER">Tedarikçi</SelectItem>
              </SelectContent>
            </Select>
            <Select value={approvalStatus} onValueChange={setApprovalStatus}>
              <SelectTrigger className="h-9 w-40">
                <SelectValue placeholder="Onay" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm onaylar</SelectItem>
                {Object.entries(APPROVAL_LABEL).map(([k, v]) => (
                  <SelectItem key={k} value={k}>
                    {v}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" variant="success" onClick={() => setCreateOpen(true)}>
              <Plus className="w-3.5 h-3.5" />
              Yeni Firma
            </Button>
          </>
        }
      />

      <PortalDataCard>
        {listQuery.isError ? (
          <p className="p-4 text-sm text-destructive">Liste alınamadı.</p>
        ) : (
          <Table className="text-xs">
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="px-4">Firma</TableHead>
                <TableHead className="px-4">Tür</TableHead>
                <TableHead className="px-4">Şehir</TableHead>
                <TableHead className="px-4">Yetkili</TableHead>
                <TableHead className="px-4 text-right">Cari / Limit</TableHead>
                <TableHead className="px-4">Onay</TableHead>
                <TableHead className="px-4">Durum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {listQuery.isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                    Yükleniyor...
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                    Kayıt bulunamadı.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((org) => (
                  <TableRow
                    key={org.id}
                    className="cursor-pointer hover:bg-muted/40"
                    onClick={() => setSelectedOrgId(org.id)}
                  >
                    <TableCell className="px-4">
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded border bg-muted overflow-hidden flex items-center justify-center">
                          {org.logoUrl ? (
                            <img src={org.logoUrl} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                          )}
                        </div>
                        <div>
                          <div className="font-medium">{org.name}</div>
                          <div className="font-mono text-[10px] text-muted-foreground">{org.code}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="px-4">
                      <PartnerBadges org={org} />
                    </TableCell>
                    <TableCell className="px-4 text-muted-foreground">{org.city || '—'}</TableCell>
                    <TableCell className="px-4">{org.contactName || '—'}</TableCell>
                    <TableCell className="px-4 text-right font-mono tabular-nums">
                      {money(org.usedCreditUsd)} / {money(org.creditLimitUsd)}
                    </TableCell>
                    <TableCell className="px-4">
                      <Badge variant="outline">
                        {APPROVAL_LABEL[org.approvalStatus || ''] || org.approvalStatus || '—'}
                      </Badge>
                    </TableCell>
                    <TableCell className="px-4">
                      <Badge variant={org.isActive ? 'secondary' : 'outline'}>
                        {org.isActive ? 'Aktif' : 'Pasif'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </PortalDataCard>

      {pagination && pagination.totalPages > 1 && (
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Önceki
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= pagination.totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Sonraki
          </Button>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni iş ortağı</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Firma kodu</Label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} className="font-mono" />
            </div>
            <div className="space-y-1">
              <Label>Firma adı</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Şehir</Label>
              <Input value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant={roles.includes('BUYER') ? 'default' : 'outline'}
                onClick={() =>
                  setRoles((r) =>
                    r.includes('BUYER') ? r.filter((x) => x !== 'BUYER') : [...r, 'BUYER']
                  )
                }
              >
                Müşteri
              </Button>
              <Button
                type="button"
                size="sm"
                variant={roles.includes('SUPPLIER') ? 'default' : 'outline'}
                onClick={() =>
                  setRoles((r) =>
                    r.includes('SUPPLIER') ? r.filter((x) => x !== 'SUPPLIER') : [...r, 'SUPPLIER']
                  )
                }
              >
                Tedarikçi
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label>USD kredi limiti</Label>
                <Input value={creditLimitUsd} onChange={(e) => setCreditLimitUsd(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Has limit (gr)</Label>
                <Input value={hasLimitGram} onChange={(e) => setHasLimitGram(e.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
              İptal
            </Button>
            <Button type="button" onClick={() => void onCreate()} disabled={createMut.isPending}>
              Oluştur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
