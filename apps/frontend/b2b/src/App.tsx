import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryProvider } from '@taragold/shared/providers/QueryProvider';
import { ThemeProvider } from '@taragold/shared/providers/ThemeProvider';
import { AuthProvider } from '@taragold/shared/providers/AuthProvider';
import { PortalSelectionProvider } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { CommerceProvider } from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { PortalRouteGuard } from '@taragold/shared/components/PortalRouteGuard';
import { Toaster } from '@taragold/shared/components/ui';
import { B2bLayout } from './layouts/B2bLayout';
import { B2bLoginPage } from './pages/auth/B2bLoginPage';
import { B2bDashboardPage } from './pages/b2b/B2bDashboardPage';
import { B2bDraftSheetPage } from './pages/b2b/B2bDraftSheetPage';
import { B2bOrdersPage } from './pages/b2b/B2bOrdersPage';
import {
  B2bCompanySettingsPage,
  B2bCompanyUsersPage,
  B2bCurrentAccountPage,
  B2bMailLogsPage,
} from './pages/b2b/B2bAccountPages';
import { StorefrontFeatureView } from '@taragold/shared/features/catalog/components/StorefrontFeatureView';
import { ProductCardFeatureView } from '@taragold/shared/features/catalog/components/ProductCardFeatureView';
import { FavoritesFeatureView } from '@taragold/shared/features/commerce/components/FavoritesFeatureView';
import { B2bDyoPage } from './pages/b2b/B2bDyoPage';

export function App() {
  return (
    <ThemeProvider>
    <QueryProvider>
      <AuthProvider>
        <PortalSelectionProvider>
          <CommerceProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/b2b/giris" element={<B2bLoginPage />} />
                <Route
                  path="/b2b"
                  element={
                    <PortalRouteGuard portal="b2b">
                      <B2bLayout />
                    </PortalRouteGuard>
                  }
                >
                  <Route index element={<Navigate to="/b2b/panel" replace />} />
                  <Route path="panel" element={<B2bDashboardPage />} />
                  <Route path="katalog" element={<StorefrontFeatureView portalMode="b2b" />} />
                  <Route path="urun/:parentSku" element={<ProductCardFeatureView portalMode="b2b" />} />
                  <Route path="tasarla" element={<B2bDyoPage />} />
                  <Route path="tasarla/:mountingSku" element={<B2bDyoPage />} />
                  <Route path="siparis-fisi" element={<B2bDraftSheetPage />} />
                  <Route path="siparisler" element={<B2bOrdersPage />} />
                  <Route path="cari-hesap" element={<B2bCurrentAccountPage />} />
                  <Route path="favoriler" element={<FavoritesFeatureView portalMode="b2b" />} />
                  <Route path="kullanicilar" element={<B2bCompanyUsersPage />} />
                  <Route path="ayarlar" element={<B2bCompanySettingsPage />} />
                  <Route path="mail-loglari" element={<B2bMailLogsPage />} />
                </Route>
                <Route path="/" element={<Navigate to="/b2b/panel" replace />} />
                <Route path="*" element={<Navigate to="/b2b/panel" replace />} />
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