import { Link, Outlet, useLocation } from 'react-router-dom';
import { TaraDiamondLogo } from '@taragold/shared/components/brand/TaraDiamondBrand';
import { ThemeToggle } from '@taragold/shared/components/ui';

const NAV = [
  { to: '/', label: 'Ana Sayfa' },
  { to: '/hakkimizda', label: 'Hakkımızda' },
  { to: '/hizmetler', label: 'Hizmetler' },
  { to: '/iletisim', label: 'İletişim' },
] as const;

const b2bUrl = import.meta.env.VITE_B2B_URL ?? 'http://localhost:3001/b2b/giris';
const opsUrl = import.meta.env.VITE_OPS_URL ?? 'http://localhost:3002/ops/giris';

export function CorporateLayout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground font-sans">
      <header className="border-b border-border bg-background/95 backdrop-blur-sm sticky top-0 z-40">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 flex items-center justify-between gap-6">
          <Link to="/" className="shrink-0">
            <TaraDiamondLogo className="h-8 w-auto text-foreground" />
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={
                  pathname === item.to
                    ? 'text-foreground border-b-2 border-foreground pb-0.5'
                    : 'text-muted-foreground hover:text-foreground transition-colors'
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle compact />
            <PartnerLinks b2bUrl={b2bUrl} opsUrl={opsUrl} />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-border bg-card">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 flex flex-col sm:flex-row gap-4 justify-between text-xs text-muted-foreground">
          <p>© {new Date().getFullYear()} TARA DIAMOND. Tüm hakları saklıdır.</p>
          <PartnerLinks b2bUrl={b2bUrl} opsUrl={opsUrl} compact />
        </div>
      </footer>
    </div>
  );
}

function PartnerLinks({
  b2bUrl,
  opsUrl,
  compact,
}: {
  b2bUrl: string;
  opsUrl: string;
  compact?: boolean;
}) {
  return (
    <div className={`flex items-center gap-2 ${compact ? '' : 'md:gap-3'}`}>
      <a
        href={b2bUrl}
        className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Bayi Girişi
      </a>
      <a
        href={opsUrl}
        className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent transition-colors"
      >
        Ops Girişi
      </a>
    </div>
  );
}
