import { Link } from 'react-router-dom';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import { Button } from '@taragold/shared/components/ui';
import { useCustomer360DashboardQuery } from '@taragold/shared/features/ops/hooks/useOpsQueries';

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PortalDataCard title={label}>
      <div className="px-4 py-5 text-2xl font-semibold tabular-nums text-foreground">{value}</div>
    </PortalDataCard>
  );
}

export function OpsConsentsOverviewPage() {
  const dash = useCustomer360DashboardQuery();
  const d = dash.data;
  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="İzin ve Onay Yönetimi"
        description="Ticari ileti ve KVKK izin özeti. Müşteri detayından kayıt bazlı inceleme yapılır."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi label="Ticari e-posta izni" value={String(d?.commercialEmailGranted ?? '—')} />
        <Kpi label="İzin geri çekilmiş" value={String(d?.commercialEmailWithdrawn ?? '—')} />
        <Kpi label="Toplam B2C müşteri" value={String(d?.totalB2cCustomers ?? '—')} />
      </div>
      <Button variant="outline" size="sm" asChild>
        <Link to="/ops/musteriler">Müşteri listesine git</Link>
      </Button>
    </div>
  );
}

export function OpsCustomerActivityPage() {
  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="Müşteri İşlem Geçmişi"
        description="Denetim kayıtları müşteri detayındaki Denetim sekmesinden filtrelenir."
      />
      <Button variant="outline" size="sm" asChild>
        <Link to="/ops/musteriler">Müşteri seç</Link>
      </Button>
    </div>
  );
}
