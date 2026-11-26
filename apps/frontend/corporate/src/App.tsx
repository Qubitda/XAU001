import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@taragold/shared/providers/ThemeProvider';
import { CorporateLayout } from './layouts/CorporateLayout';
import {
  AboutPage,
  ContactPage,
  CorporateHomePage,
  ServicesPage,
} from './pages/CorporatePages';

const storefrontUrl = import.meta.env.VITE_STOREFRONT_URL ?? 'http://localhost:3000/';
const b2bUrl = import.meta.env.VITE_B2B_URL ?? 'http://localhost:3001/b2b/giris';
const opsUrl = import.meta.env.VITE_OPS_URL ?? 'http://localhost:3002/ops/giris';

function PartnerLoginPage() {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight text-foreground">Ortak Portallar</h1>
      <p className="text-sm text-muted-foreground">
        Müşteri vitrini, bayi veya operasyon oturumunuza aşağıdan devam edin.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <a
          href={storefrontUrl}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
        >
          Vitrin (B2C)
        </a>
        <a
          href={b2bUrl}
          className="rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90"
        >
          Bayi Girişi (B2B)
        </a>
        <a
          href={opsUrl}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
        >
          Ops Girişi
        </a>
      </div>
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<CorporateLayout />}>
            <Route path="/" element={<CorporateHomePage />} />
            <Route path="/hakkimizda" element={<AboutPage />} />
            <Route path="/hizmetler" element={<ServicesPage />} />
            <Route path="/iletisim" element={<ContactPage />} />
            <Route path="/giris" element={<PartnerLoginPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
