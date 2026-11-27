import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';
import { ExchangeMetalMatrixCard } from '@taragold/shared/components/ExchangeMetalMatrixCard';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { apiFetch, ApiClientError } from '@taragold/shared/lib/api/client';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { FxCurrencyCode, LiveRates } from '@taragold/shared/types/jewelry';
import { TROY_OZ_TO_GRAM } from '@taragold/shared/utils/pricingEngine';

type MatrixVersionRow = {
  id: string;
  version: number;
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  effectiveAt: string | null;
  createdByEmail: string | null;
  note: string;
  liveHasGoldTrySell: string;
  fxBaseRates: Record<string, string>;
  createdAt: string;
  updatedAt?: string;
};

const STATUS_LABELS: Record<MatrixVersionRow['status'], string> = {
  ACTIVE: 'Aktif',
  DRAFT: 'Taslak',
  ARCHIVED: 'Arşivlendi',
};

export function OpsExchangeMatrixPage() {
  const { hasCapability } = useAuth();
  const canEdit = hasCapability('rates:edit');
  const queryClient = useQueryClient();

  const [activeMatrix, setActiveMatrix] = useState<MatrixVersionRow | null>(null);
  const [versions, setVersions] = useState<MatrixVersionRow[]>([]);
  const [draftRates, setDraftRates] = useState<Record<FxCurrencyCode, number> | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [activeRes, versRes] = await Promise.all([
        apiFetch<MatrixVersionRow>('/api/v1/ops/settings/exchange-metal-matrix'),
        apiFetch<MatrixVersionRow[]>('/api/v1/ops/settings/exchange-metal-matrix/versions?pageSize=25'),
      ]);
      const act = activeRes.data;
      setActiveMatrix(act);
      setVersions(Array.isArray(versRes.data) ? versRes.data : []);
      if (act?.fxBaseRates) {
        const parsed: Record<string, number> = {};
        for (const [k, v] of Object.entries(act.fxBaseRates)) {
          parsed[k] = Number(v) || 0;
        }
        setDraftRates(parsed as Record<FxCurrencyCode, number>);
      }
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Matris yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const liveRatesView: LiveRates | null = useMemo(() => {
    if (!draftRates || !activeMatrix) return null;
    const xau = draftRates.XAU ?? 168000;
    return {
      snapshotId: `v${activeMatrix.version} · ${STATUS_LABELS[activeMatrix.status]}`,
      sourceMode: 'manual',
      liveUsdSell: draftRates.USD ?? 42,
      liveEurSell: draftRates.EUR ?? 48.5,
      liveHasGoldTrySell: Number((xau / TROY_OZ_TO_GRAM).toFixed(2)),
      fxBaseRates: draftRates,
      updatedAt: activeMatrix.updatedAt ?? activeMatrix.createdAt,
    } as LiveRates;
  }, [draftRates, activeMatrix]);

  const handleBaseRateChange = (code: FxCurrencyCode, newTryValue: number) => {
    if (!draftRates) return;
    setDraftRates({
      ...draftRates,
      [code]: code === 'TRY' ? 1 : Math.max(0.0001, newTryValue),
    });
  };

  const saveVersion = async (autoPublish: boolean) => {
    if (!draftRates) return;
    setSaving(true);
    try {
      await apiFetch<MatrixVersionRow>('/api/v1/ops/settings/exchange-metal-matrix', {
        method: 'POST',
        body: {
          fxBaseRates: draftRates,
          note: note.trim(),
          autoPublish,
        },
      });
      setNote('');
      toast.success(
        autoPublish
          ? 'Yeni matris versiyonu yayınlandı ve aktif edildi.'
          : 'Taslak matris versiyonu kaydedildi.'
      );
      await load();
      await queryClient.invalidateQueries({ queryKey: ['rates'] });
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Matris kaydedilemedi');
    } finally {
      setSaving(false);
    }
  };

  const publishExisting = async (id: string) => {
    setSaving(true);
    try {
      await apiFetch(`/api/v1/ops/settings/exchange-metal-matrix/${id}/publish`, {
        method: 'POST',
      });
      toast.success('Taslak versiyon yayınlandı.');
      await load();
      await queryClient.invalidateQueries({ queryKey: ['rates'] });
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Yayınlanamadı');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 w-full max-w-full min-w-0 overflow-x-hidden">
      <PortalPageHeader
        eyebrow="Genel Ayarlar · Merkezi Referans"
        title="Çapraz Kur & Değerli Metal Matrisi"
        description="Sistemin merkezi döviz ve değerli metal referans tablosu. Yeni fiyatlamalar aktif versiyonu varsayılan alır; mevcut fiyatlama kayıtları etkilenmez."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void load()} disabled={loading}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Yenile
            </Button>
            {canEdit && (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={saving || !draftRates}
                  onClick={() => void saveVersion(false)}
                >
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                  Taslak Oluştur
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="success"
                  disabled={saving || !draftRates}
                  onClick={() => void saveVersion(true)}
                >
                  <Check className="w-3.5 h-3.5 mr-1.5" />
                  Kaydet ve Yayınla
                </Button>
              </>
            )}
          </div>
        }
      />

      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Versiyon notu (opsiyonel, ör. Gün ortası kur güncellemesi)"
            className="max-w-md text-xs h-9"
          />
        </div>
      )}

      {loading || !liveRatesView ? (
        <PortalDataCard contentClassName="p-6 text-xs text-muted-foreground">
          Matris yükleniyor…
        </PortalDataCard>
      ) : (
        <ExchangeMetalMatrixCard
          rates={liveRatesView}
          onBaseRateChange={handleBaseRateChange}
          defaultExpanded={true}
          readOnly={!canEdit}
        />
      )}

      <PortalDataCard title={`Versiyon Geçmişi (${versions.length})`}>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4">Versiyon</TableHead>
              <TableHead className="px-4">Durum</TableHead>
              <TableHead className="px-4">USD / EUR / Has</TableHead>
              <TableHead className="px-4">Not</TableHead>
              <TableHead className="px-4">Yayın / Tarih</TableHead>
              {canEdit && <TableHead className="px-4 text-right">İşlem</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {versions.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="px-4 font-mono font-semibold">v{v.version}</TableCell>
                <TableCell className="px-4">
                  <Badge variant={v.status === 'ACTIVE' ? 'default' : 'secondary'}>
                    {STATUS_LABELS[v.status]}
                  </Badge>
                </TableCell>
                <TableCell className="px-4 font-mono tabular-nums">
                  {v.fxBaseRates?.USD} / {v.fxBaseRates?.EUR} / {v.liveHasGoldTrySell} TL
                </TableCell>
                <TableCell className="px-4 text-muted-foreground">{v.note || '—'}</TableCell>
                <TableCell className="px-4 text-muted-foreground">
                  {v.effectiveAt
                    ? new Date(v.effectiveAt).toLocaleString('tr-TR')
                    : new Date(v.createdAt).toLocaleString('tr-TR')}
                </TableCell>
                {canEdit && (
                  <TableCell className="px-4 text-right">
                    {v.status === 'DRAFT' ? (
                      <Button size="sm" variant="outline" disabled={saving} onClick={() => void publishExisting(v.id)}>
                        Yayınla
                      </Button>
                    ) : null}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}
