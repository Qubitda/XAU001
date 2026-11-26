import { useEffect, useState } from 'react';
import { ArrowLeft, Plus, Search, UserRound } from 'lucide-react';
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
  useCreateCustomerAddressMutation,
  useCreateOpsCustomerMutation,
  useCustomerAuditQuery,
  useCustomerConsentsQuery,
  useCustomerContractsQuery,
  useDeactivateOpsCustomerMutation,
  useOpsCustomerQuery,
  useOpsCustomersQuery,
  usePatchOpsCustomerMutation,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { ApiClientError } from '@taragold/shared/lib/api/client';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

function errMsg(e: unknown) {
  return e instanceof ApiClientError ? e.message : 'İşlem başarısız';
}

function CustomerDetail({ customerId, onBack }: { customerId: string; onBack: () => void }) {
  const detail = useOpsCustomerQuery(customerId);
  const consentsQ = useCustomerConsentsQuery(customerId);
  const contractsQ = useCustomerContractsQuery(customerId);
  const auditQ = useCustomerAuditQuery(customerId);
  const patchMut = usePatchOpsCustomerMutation();
  const deactivateMut = useDeactivateOpsCustomerMutation();
  const addrMut = useCreateCustomerAddressMutation();
  const c = detail.data;

  const [form, setForm] = useState({
    fullName: '',
    phone: '',
    email: '',
    identityOrTaxNo: '',
    city: '',
    address: '',
    notes: '',
  });
  const [addrForm, setAddrForm] = useState({
    title: '',
    line: '',
    city: '',
    addressType: 'SHIPPING',
  });

  useEffect(() => {
    if (!detail.data) return;
    const row = detail.data;
    setForm({
      fullName: row.fullName,
      phone: row.phone || '',
      email: row.email || '',
      identityOrTaxNo: row.identityOrTaxNo || '',
      city: row.city || '',
      address: row.address || '',
      notes: row.notes || '',
    });
  }, [detail.data?.id]);

  async function saveProfile() {
    try {
      await patchMut.mutateAsync({ customerId, body: form });
      toast.success('Müşteri güncellendi');
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function toggleActive() {
    try {
      if (c?.isActive) {
        await deactivateMut.mutateAsync(customerId);
        toast.success('Müşteri pasifleştirildi');
      } else {
        await patchMut.mutateAsync({ customerId, body: { isActive: true } });
        toast.success('Müşteri aktifleştirildi');
      }
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function addAddress() {
    if (!addrForm.title.trim() || !addrForm.line.trim()) {
      toast.error('Başlık ve adres satırı gerekli');
      return;
    }
    try {
      await addrMut.mutateAsync({
        customerId,
        body: {
          title: addrForm.title,
          line: addrForm.line,
          city: addrForm.city,
          addressType: addrForm.addressType,
        },
      });
      setAddrForm({ title: '', line: '', city: '', addressType: 'SHIPPING' });
      toast.success('Adres eklendi');
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  if (detail.isLoading || !c) {
    return (
      <div className="space-y-3">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Geri
        </Button>
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Geri
        </Button>
        <div className="flex items-center gap-2">
          <Badge variant={c.isActive ? 'secondary' : 'outline'}>{c.isActive ? 'Aktif' : 'Pasif'}</Badge>
          <Button type="button" size="sm" variant="outline" onClick={() => void toggleActive()}>
            {c.isActive ? 'Pasifleştir' : 'Aktifleştir'}
          </Button>
        </div>
      </div>

      <PortalPageHeader
        title={c.fullName}
        description={`${c.segment || c.customerType} · ${c.city || 'Şehir yok'} · ${c.orderCount ?? 0} sipariş${c.externalId ? ` · ext:${c.externalId}` : ''}`}
      />

      <Tabs defaultValue="profile">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="profile">Genel Bilgiler</TabsTrigger>
          <TabsTrigger value="orders">Sepetler ve Siparişler</TabsTrigger>
          <TabsTrigger value="consents">İzinler ve Sözleşmeler</TabsTrigger>
          <TabsTrigger value="addresses">Adresler</TabsTrigger>
          <TabsTrigger value="audit">Denetim Kayıtları</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="pt-3 space-y-3">
          <div className="rounded-xl border border-border bg-card p-4 grid gap-3 md:grid-cols-2">
            <div>
              <Label className="text-[11px]">Ad soyad</Label>
              <Input
                value={form.fullName}
                onChange={(e) => setForm((p) => ({ ...p, fullName: e.target.value }))}
              />
            </div>
            <div>
              <Label className="text-[11px]">Telefon</Label>
              <Input
                value={form.phone}
                onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value }))}
              />
            </div>
            <div>
              <Label className="text-[11px]">E-posta</Label>
              <Input
                value={form.email}
                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              />
            </div>
            <div>
              <Label className="text-[11px]">TCKN / Vergi no</Label>
              <Input
                value={form.identityOrTaxNo}
                onChange={(e) => setForm((p) => ({ ...p, identityOrTaxNo: e.target.value }))}
              />
            </div>
            <div>
              <Label className="text-[11px]">Şehir</Label>
              <Input
                value={form.city}
                onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
              />
            </div>
            <div>
              <Label className="text-[11px]">Varsayılan adres</Label>
              <Input
                value={form.address}
                onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
              />
            </div>
            <div className="md:col-span-2">
              <Label className="text-[11px]">Notlar</Label>
              <Input
                value={form.notes}
                onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
              />
            </div>
            <div className="md:col-span-2 text-[11px] text-muted-foreground">
              Hesap: {c.userEmail || 'Portal hesabı bağlı değil'}
              {c.organizationCode ? ` · Org: ${c.organizationCode}` : ''}
            </div>
            <div>
              <Button type="button" size="sm" onClick={() => void saveProfile()}>
                Kaydet
              </Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="addresses" className="pt-3 space-y-3">
          <div className="rounded-xl border border-border bg-card p-4 grid gap-2 md:grid-cols-4">
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
            <Select
              value={addrForm.addressType}
              onValueChange={(v) => setAddrForm((p) => ({ ...p, addressType: v }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="SHIPPING">Teslimat</SelectItem>
                <SelectItem value="BILLING">Fatura</SelectItem>
                <SelectItem value="OTHER">Diğer</SelectItem>
              </SelectContent>
            </Select>
            <Button type="button" size="sm" variant="success" onClick={() => void addAddress()}>
              Ekle
            </Button>
            <Input
              className="md:col-span-4"
              placeholder="Adres satırı"
              value={addrForm.line}
              onChange={(e) => setAddrForm((p) => ({ ...p, line: e.target.value }))}
            />
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Başlık</TableHead>
                <TableHead>Tip</TableHead>
                <TableHead>Şehir</TableHead>
                <TableHead>Adres</TableHead>
                <TableHead>Durum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(c.addresses ?? []).map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{a.title}</TableCell>
                  <TableCell>{a.addressType}</TableCell>
                  <TableCell>{a.city || '—'}</TableCell>
                  <TableCell className="max-w-[240px] truncate text-xs">{a.line}</TableCell>
                  <TableCell>
                    <Badge variant={a.isActive ? 'secondary' : 'outline'}>
                      {a.isDefault ? 'Varsayılan · ' : ''}
                      {a.isActive ? 'Aktif' : 'Pasif'}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {(c.addresses ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                    Adres yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="orders" className="pt-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sipariş</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Teslimat</TableHead>
                <TableHead className="text-right">Tutar</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(c.orders ?? []).map((o) => (
                <TableRow key={o.orderNo}>
                  <TableCell className="font-mono text-xs">{o.orderNo}</TableCell>
                  <TableCell>{o.status}</TableCell>
                  <TableCell className="text-xs">
                    {o.shippingFullName}
                    {o.shippingCity ? ` · ${o.shippingCity}` : ''}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatTrNumber(Number(o.grandTotalTry), 2)} TRY
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(o.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
              {(c.orders ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                    Sipariş yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="consents" className="pt-3 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 text-sm space-y-1">
            <div>
              Ticari e-posta izni:{' '}
              <Badge variant={consentsQ.data?.active?.commercialEmail ? 'secondary' : 'outline'}>
                {consentsQ.data?.active?.commercialEmail ? 'Var' : 'Yok'}
              </Badge>
            </div>
            <div>
              KVKK aydınlatma:{' '}
              <Badge variant={consentsQ.data?.active?.kvkkNotice ? 'secondary' : 'outline'}>
                {consentsQ.data?.active?.kvkkNotice ? 'Var' : 'Yok'}
              </Badge>
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Amaç</TableHead>
                <TableHead>Kanal</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Kaynak</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(consentsQ.data?.items ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-mono text-xs">{row.purpose}</TableCell>
                  <TableCell>{row.channel}</TableCell>
                  <TableCell>{row.status}</TableCell>
                  <TableCell>{row.source}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(row.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
              {(consentsQ.data?.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                    İzin kaydı yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sözleşme</TableHead>
                <TableHead>Versiyon</TableHead>
                <TableHead>Sipariş</TableHead>
                <TableHead>Kabul</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(contractsQ.data ?? []).map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-mono text-xs">{row.documentCode}</TableCell>
                  <TableCell>{row.documentVersion}</TableCell>
                  <TableCell className="font-mono text-xs">{row.orderNo || row.orderId}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(row.acceptedAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
              {(contractsQ.data ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-6">
                    Sözleşme kabulü yok
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        <TabsContent value="audit" className="pt-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Aksiyon</TableHead>
                <TableHead>Varlık</TableHead>
                <TableHead>Aktör</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(Array.isArray(auditQ.data) ? auditQ.data : []).map((row: {
                id: string;
                action: string;
                entityType: string;
                entityId: string;
                createdAt: string;
                actorEmail?: string | null;
              }) => (
                <TableRow key={row.id}>
                  <TableCell className="font-mono text-xs">{row.action}</TableCell>
                  <TableCell className="text-xs">
                    {row.entityType}:{row.entityId}
                  </TableCell>
                  <TableCell className="text-xs">{row.actorEmail || '—'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(row.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
              {(!auditQ.data || (Array.isArray(auditQ.data) && auditQ.data.length === 0)) && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-6">
                    {auditQ.isError ? 'Denetim yetkisi yok veya hata' : 'Kayıt yok'}
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

export function OpsCustomersPage() {
  const [q, setQ] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    fullName: '',
    phone: '',
    email: '',
    city: '',
    identityOrTaxNo: '',
    customerType: 'INDIVIDUAL',
  });

  const list = useOpsCustomersQuery({ q: q.trim() || undefined, pageSize: 100 });
  const createMut = useCreateOpsCustomerMutation();

  if (selectedId) {
    return <CustomerDetail customerId={selectedId} onBack={() => setSelectedId(null)} />;
  }

  async function createCustomer() {
    if (!createForm.fullName.trim()) {
      toast.error('Ad soyad gerekli');
      return;
    }
    try {
      const created = await createMut.mutateAsync(createForm);
      setCreateOpen(false);
      setCreateForm({
        fullName: '',
        phone: '',
        email: '',
        city: '',
        identityOrTaxNo: '',
        customerType: 'INDIVIDUAL',
      });
      toast.success('Müşteri oluşturuldu');
      setSelectedId(created.id);
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title={`B2C Müşteriler${list.data?.pagination ? ` (${list.data.pagination.total})` : ''}`}
        description="Bireysel müşteri profilleri — Organization iş ortağı modelinden ayrı tutulur."
        actions={
          <Button type="button" size="sm" variant="success" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-1" /> Yeni müşteri
          </Button>
        }
      />

      <div className="flex gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Ad, telefon, e-posta…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <PortalDataCard>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Müşteri</TableHead>
              <TableHead>İletişim</TableHead>
              <TableHead>Şehir</TableHead>
              <TableHead>Tip</TableHead>
              <TableHead>Durum</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(list.data?.items ?? []).map((row) => (
              <TableRow
                key={row.id}
                className="cursor-pointer"
                onClick={() => setSelectedId(row.id)}
              >
                <TableCell>
                  <div className="flex items-center gap-2">
                    <UserRound className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{row.fullName}</div>
                      <div className="text-[11px] text-muted-foreground">{row.identityOrTaxNo || '—'}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-xs">
                  <div>{row.phone || '—'}</div>
                  <div className="text-muted-foreground">{row.email || ''}</div>
                </TableCell>
                <TableCell>{row.city || '—'}</TableCell>
                <TableCell>{row.customerType}</TableCell>
                <TableCell>
                  <Badge variant={row.isActive ? 'secondary' : 'outline'}>
                    {row.isActive ? 'Aktif' : 'Pasif'}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {(list.data?.items ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  {list.isLoading ? 'Yükleniyor…' : 'Müşteri bulunamadı'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni B2C müşteri</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label>Ad soyad</Label>
              <Input
                value={createForm.fullName}
                onChange={(e) => setCreateForm((p) => ({ ...p, fullName: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Telefon</Label>
                <Input
                  value={createForm.phone}
                  onChange={(e) => setCreateForm((p) => ({ ...p, phone: e.target.value }))}
                />
              </div>
              <div>
                <Label>Şehir</Label>
                <Input
                  value={createForm.city}
                  onChange={(e) => setCreateForm((p) => ({ ...p, city: e.target.value }))}
                />
              </div>
            </div>
            <div>
              <Label>E-posta</Label>
              <Input
                value={createForm.email}
                onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))}
              />
            </div>
            <div>
              <Label>TCKN / VKN</Label>
              <Input
                value={createForm.identityOrTaxNo}
                onChange={(e) => setCreateForm((p) => ({ ...p, identityOrTaxNo: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
              İptal
            </Button>
            <Button type="button" onClick={() => void createCustomer()}>
              Oluştur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
