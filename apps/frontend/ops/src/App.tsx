import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryProvider } from '@taragold/shared/providers/QueryProvider';
import { ThemeProvider } from '@taragold/shared/providers/ThemeProvider';
import { AuthProvider } from '@taragold/shared/providers/AuthProvider';
import { PortalSelectionProvider } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { CommerceProvider } from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { PortalRouteGuard } from '@taragold/shared/components/PortalRouteGuard';
import { Toaster } from '@taragold/shared/components/ui';
import { OpsLayout } from './layouts/OpsLayout';
import { OpsLoginPage } from './pages/auth/OpsLoginPage';
import { OpsDashboardPage } from './pages/ops/OpsDashboardPage';
import {
  OpsRecipesPage,
  OpsStoneMountPage,
  OpsVariantsPage,
} from './pages/ops/OpsDomainPages';
import { OpsFinancePage } from './pages/ops/OpsFinancePage';
import { OpsInventoryPage } from './pages/ops/OpsInventoryPage';
import { OpsOrganizationsPage } from './pages/ops/OpsOrganizationsPage';
import { OpsCustomersPage } from './pages/ops/OpsCustomersPage';
import { OpsProductionPage } from './pages/ops/OpsProductionPage';
import { OpsUsersPermissionsPage } from './pages/ops/OpsUsersPermissionsPage';
import { OpsApiKeysPage } from './pages/ops/OpsApiKeysPage';
import { OpsWebhooksPage } from './pages/ops/OpsWebhooksPage';
import { OpsDefinitionsPage } from './pages/ops/OpsDefinitionsPage';
import { OpsSettingsPage } from './pages/ops/OpsSettingsPage';
import { OpsExchangeMatrixPage } from './pages/ops/OpsExchangeMatrixPage';
import { OpsTransactionsPage } from './pages/ops/OpsTransactionsPage';
import { OpsMailLogsPage } from './pages/ops/OpsMailLogsPage';
import { OpsSalesTasksPage } from './pages/ops/OpsSalesTasksPage';
import {
  OpsConsentsOverviewPage,
  OpsCustomerActivityPage,
} from './pages/ops/OpsCustomer360Placeholders';
import { OpsCartTrackingPage } from './pages/ops/OpsCartTrackingPage';
import { OpsLegalDocumentsPage } from './pages/ops/OpsLegalDocumentsPage';
import { OpsMailTemplatesPage } from './pages/ops/OpsMailTemplatesPage';
import { OpsSiteContactPage } from './pages/ops/OpsSiteContactPage';
import { KatalogPage } from './pages/portal/KatalogPage';
import { FiyatMotoruPage } from './pages/portal/FiyatMotoruPage';
import { OrdersFeatureView } from '@taragold/shared/features/commerce/components/OrdersFeatureView';
import { ProductCardFeatureView } from '@taragold/shared/features/catalog/components/ProductCardFeatureView';

export function App() {
  return (
    <ThemeProvider>
    <QueryProvider>
      <AuthProvider>
        <PortalSelectionProvider>
          <CommerceProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/ops/giris" element={<OpsLoginPage />} />
                <Route
                  path="/ops"
                  element={
                    <PortalRouteGuard portal="ops">
                      <OpsLayout />
                    </PortalRouteGuard>
                  }
                >
                  <Route index element={<Navigate to="/ops/panel" replace />} />
                  <Route path="panel" element={<OpsDashboardPage />} />
                  <Route path="urunler" element={<KatalogPage />} />
                  <Route path="varyantlar" element={<OpsVariantsPage />} />
                  <Route path="tas-montur" element={<OpsStoneMountPage />} />
                  <Route path="fiyat-motoru" element={<FiyatMotoruPage />} />
                  <Route path="receteler" element={<OpsRecipesPage />} />
                  <Route path="siparisler" element={<OrdersFeatureView portalMode="ops" />} />
                  <Route path="satis-gorevleri" element={<OpsSalesTasksPage />} />
                  <Route path="odeme-islemleri" element={<OpsTransactionsPage />} />
                  <Route path="stok-depo" element={<OpsInventoryPage />} />
                  <Route path="uretim" element={<OpsProductionPage />} />
                  <Route path="firmalar" element={<OpsOrganizationsPage />} />
                  <Route path="musteriler" element={<OpsCustomersPage />} />
                  <Route path="sepet-takibi" element={<OpsCartTrackingPage />} />
                  <Route path="izinler" element={<OpsConsentsOverviewPage />} />
                  <Route path="musteri-islem-gecmisi" element={<OpsCustomerActivityPage />} />
                  <Route path="yasal-metinler" element={<OpsLegalDocumentsPage />} />
                  <Route path="eposta-sablonlari" element={<OpsMailTemplatesPage />} />
                  <Route path="iletisim-sablonlari" element={<Navigate to="/ops/eposta-sablonlari" replace />} />
                  <Route path="sirket-iletisim" element={<OpsSiteContactPage />} />
                  <Route path="cari-hesap" element={<OpsFinancePage />} />
                  <Route path="kullanicilar" element={<OpsUsersPermissionsPage />} />
                  <Route path="api-anahtarlari" element={<OpsApiKeysPage />} />
                  <Route path="webhookler" element={<OpsWebhooksPage />} />
                  <Route path="ayarlar" element={<OpsSettingsPage />} />
                  <Route path="ayarlar/kur-matrisi" element={<OpsExchangeMatrixPage />} />
                  <Route path="mail-loglari" element={<OpsMailLogsPage />} />
                  <Route path="tanimlar" element={<OpsDefinitionsPage />} />
                  <Route path="urun/:parentSku" element={<ProductCardFeatureView />} />
                </Route>
                <Route
                  path="/urun/:parentSku"
                  element={
                    <PortalRouteGuard portal="ops">
                      <OpsLayout />
                    </PortalRouteGuard>
                  }
                >
                  <Route index element={<ProductCardFeatureView />} />
                </Route>
                <Route path="/katalog" element={<Navigate to="/ops/urunler" replace />} />
                <Route path="/fiyat-motoru" element={<Navigate to="/ops/fiyat-motoru" replace />} />
                <Route path="/" element={<Navigate to="/ops/panel" replace />} />
                <Route path="*" element={<Navigate to="/ops/panel" replace />} />
              </Routes>
            </BrowserRouter>
            <Toaster position="top-right" richColors closeButton />
          </CommerceProvider>
        </PortalSelectionProvider>
      </AuthProvider>
    </QueryProvider>
    </ThemeProvider>
  );
}

export default App;