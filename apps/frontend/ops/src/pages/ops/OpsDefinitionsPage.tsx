import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  BookMarked,
  ChevronRight,
  Filter,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import { PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
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
} from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';
import { getActiveSalesChannels } from '@taragold/shared/constants/salesChannels';

type DefinitionItem = {
  id: string;
  code: string;
  label: string;
  meta: Record<string, unknown>;
  sortOrder: number;
  isActive: boolean;
  isSystem: boolean;
  parentIds?: string[];
  parentCodes?: string[];
  parentLabels?: string[];
};

type DefinitionUsage = {
  businessDomain: string;
  usagePurpose: string;
  usedInApps: string[];
  usedInScreens: string[];
  bindsToEntity?: string | null;
  valueStrategy: string;
  parentFilter: boolean;
  dynamicCapable: boolean;
  criticalMeta: string[];
  integrationStatus: string;
  howToAddOption: string;
};

type DefinitionTable = {
  id: string;
  code: string;
  name: string;
  description: string;
  sortOrder: number;
  isActive: boolean;
  isSystem: boolean;
  parentTableCode?: string | null;
  parentTableName?: string | null;
  childTableCodes?: string[];
  itemCount?: number;
  activeItemCount?: number;
  items?: DefinitionItem[];
  usage?: DefinitionUsage;
};

type DefinitionsPayload = {
  tables: DefinitionTable[];
  salesChannels: { code: string; label: string; isSystem?: boolean }[];
  systemFixed?: Array<{ name: string; codes: string[]; reason: string }>;
};

type ItemFormState = {
  code: string;
  label: string;
  sortOrder: number;
  isActive: boolean;
  parentIds: string[];
  metaJson: string;
};

const emptyForm = (): ItemFormState => ({
  code: '',
  label: '',
  sortOrder: 100,
  isActive: true,
  parentIds: [],
  metaJson: '',
});

function countActive(items: DefinitionItem[] | undefined) {
  return (items ?? []).filter((i) => i.isActive).length;
}

function formatRelation(table: DefinitionTable) {
  if (!table.parentTableName) return null;
  return `${table.name} → ${table.parentTableName}`;
}

function integrationLabel(status?: string) {
  switch (status) {
    case 'wired':
      return 'Ekrana bağlı';
    case 'reference_only':
      return 'Referans';
    case 'system_fixed':
      return 'Sistem sabiti';
    case 'unverified':
      return 'Bağlantı yok';
    default:
      return status || '—';
  }
}

export function OpsDefinitionsPage() {
  const [tables, setTables] = useState<DefinitionTable[]>([]);
  const [salesChannels, setSalesChannels] = useState<
    { code: string; label: string; isSystem?: boolean }[]
  >(getActiveSalesChannels().map((c) => ({ ...c, isSystem: true })));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupQuery, setGroupQuery] = useState('');
  const [groupStatus, setGroupStatus] = useState<'all' | 'active' | 'passive'>('all');
  const [showGroupFilters, setShowGroupFilters] = useState(false);

  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [itemQuery, setItemQuery] = useState('');
  const [itemStatus, setItemStatus] = useState<'all' | 'active' | 'passive'>('all');

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editingIsSystem, setEditingIsSystem] = useState(false);
  const [showAdvancedMeta, setShowAdvancedMeta] = useState(false);
  const [form, setForm] = useState<ItemFormState>(emptyForm());
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<DefinitionsPayload>('/api/v1/ops/definitions?includeItems=true');
      const payload = res.data;
      setTables(payload?.tables ?? []);
      if (payload?.salesChannels?.length) setSalesChannels(payload.salesChannels);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Tanımlar yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedTable = useMemo(
    () => tables.find((t) => t.code === selectedCode) ?? null,
    [tables, selectedCode]
  );

  const parentTable = useMemo(() => {
    if (!selectedTable?.parentTableCode) return null;
    return tables.find((t) => t.code === selectedTable.parentTableCode) ?? null;
  }, [tables, selectedTable]);

  const parentOptions = useMemo(
    () => (parentTable?.items ?? []).filter((i) => i.isActive),
    [parentTable]
  );

  const filteredGroups = useMemo(() => {
    const q = groupQuery.trim().toLocaleLowerCase('tr');
    return tables
      .filter((t) => {
        if (groupStatus === 'active' && !t.isActive) return false;
        if (groupStatus === 'passive' && t.isActive) return false;
        if (!q) return true;
        const hay = [t.name, t.description, t.code, t.parentTableName ?? '']
          .join(' ')
          .toLocaleLowerCase('tr');
        return hay.includes(q);
      })
      .sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name, 'tr'));
  }, [tables, groupQuery, groupStatus]);

  const filteredItems = useMemo(() => {
    if (!selectedTable) return [];
    const q = itemQuery.trim().toLocaleLowerCase('tr');
    return [...(selectedTable.items ?? [])]
      .filter((item) => {
        if (itemStatus === 'active' && !item.isActive) return false;
        if (itemStatus === 'passive' && item.isActive) return false;
        if (!q) return true;
        const hay = [item.label, item.code, ...(item.parentLabels ?? [])]
          .join(' ')
          .toLocaleLowerCase('tr');
        return hay.includes(q);
      })
      .sort((a, b) => a.sortOrder - b.sortOrder || a.label.localeCompare(b.label, 'tr'));
  }, [selectedTable, itemQuery, itemStatus]);

  const openCreate = () => {
    if (!selectedTable) return;
    setDialogMode('create');
    setEditingItemId(null);
    setEditingIsSystem(false);
    setShowAdvancedMeta(false);
    setForm(emptyForm());
    setDialogOpen(true);
  };

  const openEdit = (item: DefinitionItem) => {
    setDialogMode('edit');
    setEditingItemId(item.id);
    setEditingIsSystem(item.isSystem);
    const hasMeta = item.meta && Object.keys(item.meta).length > 0;
    setShowAdvancedMeta(Boolean(hasMeta));
    setForm({
      code: item.code,
      label: item.label,
      sortOrder: item.sortOrder,
      isActive: item.isActive,
      parentIds: item.parentIds ?? [],
      metaJson: hasMeta ? JSON.stringify(item.meta, null, 2) : '',
    });
    setDialogOpen(true);
  };

  const toggleParent = (id: string) => {
    setForm((prev) => ({
      ...prev,
      parentIds: prev.parentIds.includes(id)
        ? prev.parentIds.filter((x) => x !== id)
        : [...prev.parentIds, id],
    }));
  };

  const onSeed = async () => {
    try {
      await apiFetch('/api/v1/ops/definitions', {
        method: 'POST',
        body: { resetSystemItems: true },
      });
      await load();
      toast.success('Sistem tanımları yenilendi');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Seed başarısız';
      setError(msg);
      toast.error(msg);
    }
  };

  const parseMeta = (): Record<string, unknown> | undefined => {
    const raw = form.metaJson.trim();
    if (!raw) return undefined;
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Meta bir nesne olmalıdır');
      }
      return parsed as Record<string, unknown>;
    } catch (e) {
      throw new Error(e instanceof Error ? e.message : 'Meta JSON geçersiz');
    }
  };

  const onSave = async () => {
    if (!selectedTable) return;
    if (!form.code.trim() || !form.label.trim()) {
      toast.error('Görünen ad ve teknik kod zorunludur');
      return;
    }
    if (selectedTable.parentTableCode && form.parentIds.length === 0) {
      toast.error(`${selectedTable.parentTableName || 'Üst tanım'} seçimi zorunlu`);
      return;
    }

    let meta: Record<string, unknown> | undefined;
    try {
      if (showAdvancedMeta) meta = parseMeta();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Meta geçersiz');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        label: form.label.trim(),
        sortOrder: form.sortOrder,
        isActive: form.isActive,
        parentIds: form.parentIds,
      };
      if (!(dialogMode === 'edit' && editingIsSystem)) {
        body.code = form.code.trim();
      }
      if (showAdvancedMeta && meta !== undefined) {
        body.meta = meta;
      }

      if (dialogMode === 'create') {
        await apiFetch(`/api/v1/ops/definitions/${selectedTable.code}/items`, {
          method: 'POST',
          body,
        });
        toast.success('Seçenek eklendi');
      } else if (editingItemId) {
        await apiFetch(`/api/v1/ops/definition-items/${editingItemId}`, {
          method: 'PATCH',
          body,
        });
        toast.success('Seçenek güncellendi');
      }
      setDialogOpen(false);
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Kayıt başarısız';
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const onDeactivate = async (itemId: string) => {
    if (!window.confirm('Bu seçenek pasifleştirilsin mi? Silinmez; listeden gizlenebilir.')) return;
    try {
      await apiFetch(`/api/v1/ops/definition-items/${itemId}?soft=1`, { method: 'DELETE' });
      toast.success('Seçenek pasifleştirildi');
      await load();
      setDialogOpen(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Pasifleştirilemedi');
    }
  };

  const onDeleteItem = async (item: DefinitionItem) => {
    const warn = item.isSystem
      ? `"${item.label}" sistem seçeneği kalıcı silinecek. Seed yenileme ile geri gelebilir. Devam?`
      : `"${item.label}" kalıcı silinecek. Bu işlem geri alınamaz. Devam?`;
    if (!window.confirm(warn)) return;
    try {
      await apiFetch(`/api/v1/ops/definition-items/${item.id}`, { method: 'DELETE' });
      toast.success('Seçenek silindi');
      if (editingItemId === item.id) setDialogOpen(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Silinemedi');
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Ayarlar"
        title="Tanım Yönetimi"
        description={
          selectedTable
            ? `${selectedTable.name} seçeneklerini yönetin`
            : 'Ürün, metal, taş ve operasyon tanım gruplarını yönetin'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {selectedTable ? (
              <Button type="button" variant="outline" size="sm" onClick={() => setSelectedCode(null)}>
                <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
                Gruplara dön
              </Button>
            ) : null}
            <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Yenile
            </Button>
            {!selectedTable && (
              <Button type="button" variant="outline" size="sm" onClick={() => void onSeed()}>
                <BookMarked className="w-3.5 h-3.5 mr-1.5" />
                Sistem tanımlarını yenile
              </Button>
            )}
            {selectedTable && (
              <Button type="button" size="sm" variant="success" onClick={openCreate}>
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Seçenek ekle
              </Button>
            )}
          </div>
        }
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 px-3 py-2 text-[11px] text-amber-900 space-y-1">
        <div>
          <strong>Grup</strong> = seçenek listesi (ör. Metal Rengi). <strong>Seçenek eklemek</strong> =
          mevcut listeye değer eklemek. Yeni grup oluşturmak yeni form alanı açmaz; ekranın bu grubu
          okuması gerekir.
        </div>
        <div>
          Satış kanalları sistem sabitidir: {salesChannels.map((c) => c.code).join(' · ')}. Seçenekler
          satırdaki kırmızı sil ile kalıcı silinir; düzenlemede pasifleştirme de vardır.
        </div>
      </div>

      {!selectedTable ? (
        <>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={groupQuery}
                onChange={(e) => setGroupQuery(e.target.value)}
                placeholder="Tanım grubu ara..."
                className="pl-9 h-10"
              />
            </div>
            <Button
              type="button"
              variant={showGroupFilters ? 'secondary' : 'outline'}
              className="h-10"
              onClick={() => setShowGroupFilters((v) => !v)}
            >
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              Filtreler
            </Button>
          </div>

          {showGroupFilters && (
            <div className="rounded-xl border border-border bg-card p-3 max-w-xs">
              <Label className="text-[11px]">Durum</Label>
              <Select
                value={groupStatus}
                onValueChange={(v) => setGroupStatus(v as 'all' | 'active' | 'passive')}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tümü</SelectItem>
                  <SelectItem value="active">Aktif</SelectItem>
                  <SelectItem value="passive">Pasif</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border">
              <div className="text-sm font-medium">
                Tanım grupları
                <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">
                  {filteredGroups.length} grup
                </span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tanım adı</TableHead>
                    <TableHead>İş alanı</TableHead>
                    <TableHead>Kullanım</TableHead>
                    <TableHead className="w-28">Seçenek</TableHead>
                    <TableHead>Üst / Alt</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-xs text-muted-foreground py-10">
                        Yükleniyor…
                      </TableCell>
                    </TableRow>
                  )}
                  {!loading && filteredGroups.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-xs text-muted-foreground py-10">
                        {tables.length === 0
                          ? 'Henüz tanım grubu yok. Sistem tanımlarını yenileyerek başlayın.'
                          : 'Filtrelere uygun grup bulunamadı.'}
                      </TableCell>
                    </TableRow>
                  )}
                  {filteredGroups.map((table) => {
                    const activeCount = table.activeItemCount ?? countActive(table.items);
                    const total = table.itemCount ?? table.items?.length ?? 0;
                    const u = table.usage;
                    return (
                      <TableRow
                        key={table.id}
                        className="cursor-pointer hover:bg-muted/40"
                        onClick={() => {
                          setSelectedCode(table.code);
                          setItemQuery('');
                          setItemStatus('all');
                        }}
                      >
                        <TableCell>
                          <div className="text-sm font-medium">{table.name}</div>
                          <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
                            {table.code}
                          </div>
                        </TableCell>
                        <TableCell className="text-xs">{u?.businessDomain || '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-[220px]">
                          <div className="line-clamp-2">{u?.usagePurpose || table.description || '—'}</div>
                          <Badge variant="outline" className="mt-1 text-[10px]">
                            {integrationLabel(u?.integrationStatus)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs tabular-nums">
                          {activeCount}
                          <span className="text-muted-foreground"> / {total}</span>
                        </TableCell>
                        <TableCell className="text-xs">
                          {table.parentTableName ? (
                            <span>
                              Üst: {table.parentTableName}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">Kök grup</span>
                          )}
                          {(table.childTableCodes?.length ?? 0) > 0 && (
                            <span className="block text-[10px] text-muted-foreground mt-0.5">
                              Alt: {table.childTableCodes!.length} grup
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            <Badge variant={table.isActive ? 'secondary' : 'outline'}>
                              {table.isActive ? 'Aktif' : 'Pasif'}
                            </Badge>
                            {table.isSystem && <Badge variant="outline">Sistem</Badge>}
                          </div>
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          <ChevronRight className="w-4 h-4 inline-block" />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-xl border border-border bg-card px-4 py-3 space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-base font-semibold">{selectedTable.name}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {selectedTable.usage?.usagePurpose ||
                    selectedTable.description ||
                    'Bu grubun seçeneklerini yönetin.'}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge variant={selectedTable.isActive ? 'secondary' : 'outline'}>
                  {selectedTable.isActive ? 'Aktif grup' : 'Pasif grup'}
                </Badge>
                {selectedTable.isSystem && <Badge variant="outline">Sistem grubu</Badge>}
                <Badge variant="outline">
                  {integrationLabel(selectedTable.usage?.integrationStatus)}
                </Badge>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 text-[11px]">
              <div>
                <span className="text-muted-foreground">İş alanı: </span>
                {selectedTable.usage?.businessDomain || '—'}
              </div>
              <div>
                <span className="text-muted-foreground">Kayıt değeri: </span>
                {selectedTable.usage?.valueStrategy === 'code' ? 'Teknik kod' : 'Görünen ad'}
              </div>
              <div className="sm:col-span-2">
                <span className="text-muted-foreground">Ekranlar: </span>
                {(selectedTable.usage?.usedInScreens ?? []).join(' · ') || 'Bağlı ekran doğrulanamadı'}
              </div>
              {selectedTable.parentTableName && (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground">Üst grup: </span>
                  <span className="font-medium">{formatRelation(selectedTable)}</span>
                  {' — '}
                  ürün formunda üst değer seçilince yalnızca bağlı seçenekler gösterilir.
                </div>
              )}
              {(selectedTable.childTableCodes?.length ?? 0) > 0 && (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground">Bu gruba bağlı alt gruplar: </span>
                  {selectedTable.childTableCodes!.join(', ')}
                </div>
              )}
              {(selectedTable.usage?.criticalMeta?.length ?? 0) > 0 && (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground">Kritik meta: </span>
                  {selectedTable.usage!.criticalMeta.join(', ')} (fiyat/milyem bütünlüğü için korunur)
                </div>
              )}
              <div className="sm:col-span-2 rounded-md bg-muted/50 px-2 py-1.5 text-muted-foreground">
                {selectedTable.usage?.howToAddOption ||
                  'Yeni seçenek eklemek otomatik yeni form alanı oluşturmaz; yalnızca bağlı ekranlar bu listeyi okur.'}
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={itemQuery}
                onChange={(e) => setItemQuery(e.target.value)}
                placeholder="Seçenek ara..."
                className="pl-9 h-10"
              />
            </div>
            <Select
              value={itemStatus}
              onValueChange={(v) => setItemStatus(v as 'all' | 'active' | 'passive')}
            >
              <SelectTrigger className="h-10 w-full sm:w-40">
                <SelectValue placeholder="Durum" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm durumlar</SelectItem>
                <SelectItem value="active">Aktif</SelectItem>
                <SelectItem value="passive">Pasif</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border">
              <div className="text-sm font-medium">
                Seçenekler
                <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">
                  {filteredItems.length} kayıt
                </span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Görünen ad</TableHead>
                    <TableHead>Teknik kod</TableHead>
                    <TableHead>Üst tanım</TableHead>
                    <TableHead className="w-16">Sıra</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead className="text-right">İşlem</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-xs text-muted-foreground py-10">
                        Yükleniyor…
                      </TableCell>
                    </TableRow>
                  )}
                  {!loading && filteredItems.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-xs text-muted-foreground py-10">
                        Bu grupta henüz seçenek yok. “Seçenek ekle” ile başlayın.
                      </TableCell>
                    </TableRow>
                  )}
                  {filteredItems.map((item) => (
                    <TableRow key={item.id} className={!item.isActive ? 'opacity-60' : undefined}>
                      <TableCell className="text-sm font-medium">{item.label}</TableCell>
                      <TableCell className="font-mono text-xs">{item.code}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {(item.parentLabels?.length ?? 0) > 0
                          ? (item.parentLabels ?? []).join(', ')
                          : '—'}
                      </TableCell>
                      <TableCell className="text-xs tabular-nums">{item.sortOrder}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          <Badge variant={item.isActive ? 'secondary' : 'outline'}>
                            {item.isActive ? 'Aktif' : 'Pasif'}
                          </Badge>
                          {item.isSystem && <Badge variant="outline">Sistem</Badge>}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="inline-flex items-center gap-0.5">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => openEdit(item)}
                            title="Düzenle"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost-destructive"
                            onClick={() => void onDeleteItem(item)}
                            title="Sil"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {dialogMode === 'create' ? 'Yeni seçenek' : 'Seçeneği düzenle'}
            </DialogTitle>
            <DialogDescription>
              {selectedTable
                ? `${selectedTable.name} grubuna ait seçenek. ${
                    selectedTable.parentTableName
                      ? `Üst tanım: ${selectedTable.parentTableName}.`
                      : ''
                  }`
                : 'Tanım seçeneği'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-1">
            <div className="space-y-1">
              <Label className="text-[11px]">Görünen ad</Label>
              <Input
                value={form.label}
                onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))}
                placeholder="Örn. Altın"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px]">Teknik kod</Label>
                <Input
                  value={form.code}
                  onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                  disabled={dialogMode === 'edit' && editingIsSystem}
                  placeholder="ALTIN"
                  className="font-mono"
                />
                {dialogMode === 'edit' && editingIsSystem && (
                  <p className="text-[10px] text-muted-foreground">
                    Sistem tanımının teknik kodu kilitlidir.
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <Label className="text-[11px]">Sıralama</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.sortOrder}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, sortOrder: Number(e.target.value) || 0 }))
                  }
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-[11px]">Durum</Label>
              <Select
                value={form.isActive ? 'active' : 'passive'}
                onValueChange={(v) => setForm((p) => ({ ...p, isActive: v === 'active' }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Aktif</SelectItem>
                  <SelectItem value="passive">Pasif</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {selectedTable?.parentTableCode ? (
              <div className="space-y-1.5">
                <Label className="text-[11px]">
                  Üst tanım ({selectedTable.parentTableName || selectedTable.parentTableCode}) —
                  zorunlu
                </Label>
                <div className="flex flex-wrap gap-1.5 rounded-md border border-border p-2 max-h-32 overflow-y-auto">
                  {parentOptions.map((p) => {
                    const selected = form.parentIds.includes(p.id);
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => toggleParent(p.id)}
                        className={`rounded px-2 py-1 text-[11px] border transition-colors ${
                          selected
                            ? 'bg-zinc-900 text-white border-zinc-900'
                            : 'bg-white text-zinc-700 border-zinc-200 hover:border-zinc-400'
                        }`}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                  {parentOptions.length === 0 && (
                    <span className="text-[11px] text-muted-foreground">
                      Üst grupta aktif seçenek yok. Önce {selectedTable.parentTableName} ekleyin.
                    </span>
                  )}
                </div>
              </div>
            ) : null}

            <div className="rounded-md border border-border">
              <button
                type="button"
                className="w-full flex items-center justify-between px-3 py-2 text-left text-[11px] font-medium"
                onClick={() => setShowAdvancedMeta((v) => !v)}
              >
                Gelişmiş ayarlar (meta)
                <span className="text-muted-foreground">{showAdvancedMeta ? 'Gizle' : 'Göster'}</span>
              </button>
              {showAdvancedMeta && (
                <div className="px-3 pb-3 space-y-1.5 border-t border-border pt-2">
                  <p className="text-[10px] text-muted-foreground">
                    Yalnızca teknik ihtiyaçlarda kullanın. Sistem tanımlarında{' '}
                    <code className="font-mono">fineness</code> gibi hesaplama alanları korunur.
                  </p>
                  <textarea
                    value={form.metaJson}
                    onChange={(e) => setForm((p) => ({ ...p, metaJson: e.target.value }))}
                    rows={5}
                    placeholder='{"fineness": 0.585}'
                    className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                  />
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            {dialogMode === 'edit' && editingItemId && (
              <div className="mr-auto flex flex-wrap gap-2">
                {form.isActive && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void onDeactivate(editingItemId)}
                  >
                    Pasifleştir
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost-destructive"
                  onClick={() => {
                    const item = selectedTable?.items?.find((i) => i.id === editingItemId);
                    if (item) void onDeleteItem(item);
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                  Sil
                </Button>
              </div>
            )}
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              İptal
            </Button>
            <Button type="button" onClick={() => void onSave()} disabled={saving}>
              {saving ? 'Kaydediliyor…' : 'Kaydet'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
