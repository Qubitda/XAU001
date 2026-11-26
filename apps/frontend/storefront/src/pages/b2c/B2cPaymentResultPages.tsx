import type { ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, XCircle } from 'lucide-react';

function ResultShell({
  tone,
  title,
  children,
}: {
  tone: 'success' | 'error';
  title: string;
  children: ReactNode;
}) {
  const Icon = tone === 'success' ? CheckCircle2 : XCircle;
  const iconClass =
    tone === 'success' ? 'text-[#2F6B4F] bg-[#E8F3EC]' : 'text-foreground bg-primary';

  return (
    <div className="max-w-lg mx-auto px-4 py-16 sm:py-20">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-5 text-center">
        <div
          className={`mx-auto w-12 h-12 rounded-full flex items-center justify-center border border-border ${iconClass}`}
        >
          <Icon className="w-6 h-6" aria-hidden />
        </div>
        <h1 className="font-display text-2xl text-foreground tracking-tight">{title}</h1>
        {children}
      </div>
    </div>
  );
}

export function B2cPaymentSuccessPage() {
  const [params] = useSearchParams();
  const orderNo = params.get('orderNo') || '';

  return (
    <ResultShell tone="success" title="Ödeme başarılı">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Kart ödemeniz iyzico üzerinden alındı.
        {orderNo ? (
          <>
            {' '}
            Sipariş numaranız:{' '}
            <span className="font-mono text-foreground font-medium">{orderNo}</span>
          </>
        ) : null}
      </p>
      <div className="flex flex-col sm:flex-row gap-2 justify-center pt-2">
        {orderNo ? (
          <Link
            to={`/hesabim/siparisler/${encodeURIComponent(orderNo)}`}
            className="inline-flex items-center justify-center min-h-[42px] px-4 rounded-[4px] bg-primary text-white text-sm font-medium hover:bg-[#3a0c16] transition-colors"
          >
            Sipariş Detayı
          </Link>
        ) : (
          <Link
            to="/hesabim/siparisler"
            className="inline-flex items-center justify-center min-h-[42px] px-4 rounded-[4px] bg-primary text-white text-sm font-medium hover:bg-[#3a0c16] transition-colors"
          >
            Siparişlerim
          </Link>
        )}
        <Link
          to="/koleksiyon"
          className="inline-flex items-center justify-center min-h-[42px] px-4 rounded-[4px] border border-border text-foreground text-sm font-medium hover:border-ring transition-colors"
        >
          Alışverişe Devam
        </Link>
      </div>
    </ResultShell>
  );
}

export function B2cPaymentFailurePage() {
  const [params] = useSearchParams();
  const orderNo = params.get('orderNo') || '';
  const reason = params.get('reason') || '';

  return (
    <ResultShell tone="error" title="Ödeme tamamlanamadı">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Kart ödemesi onaylanmadı veya iptal edildi.
        {orderNo ? (
          <>
            {' '}
            Referans: <span className="font-mono text-foreground">{orderNo}</span>
          </>
        ) : null}
        {reason ? (
          <span className="block mt-2 text-xs text-muted-foreground">Kod: {reason}</span>
        ) : null}
      </p>
      <div className="flex flex-col sm:flex-row gap-2 justify-center pt-2">
        <Link
          to="/koleksiyon"
          className="inline-flex items-center justify-center min-h-[42px] px-4 rounded-[4px] bg-primary text-white text-sm font-medium hover:bg-[#3a0c16] transition-colors"
        >
          Sepete Dön / Tekrar Dene
        </Link>
        <Link
          to="/"
          className="inline-flex items-center justify-center min-h-[42px] px-4 rounded-[4px] border border-border text-foreground text-sm font-medium hover:border-ring transition-colors"
        >
          Ana Sayfa
        </Link>
      </div>
    </ResultShell>
  );
}
