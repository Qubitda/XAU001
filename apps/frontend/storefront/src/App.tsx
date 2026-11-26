import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryProvider } from '@taragold/shared/providers/QueryProvider';
import { ThemeProvider } from '@taragold/shared/providers/ThemeProvider';
import { AuthProvider } from '@taragold/shared/providers/AuthProvider';
import { PortalSelectionProvider } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { CommerceProvider } from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { PortalRouteGuard } from '@taragold/shared/components/PortalRouteGuard';
import { StorefrontLayout } from './layouts/StorefrontLayout';
import {
  B2cLoginPage,
  B2cRegisterPage,
  EmailVerifyPage,
  PasswordResetConfirmPage,
  PasswordResetPage,
} from './pages/auth/B2cAuthPages';
import { B2cHomePage } from './pages/b2c/B2cHomePage';
import {
  B2cAccountOverviewPage,
  B2cAddressesPage,
  B2cOrderDetailPage,
  B2cOrdersListPage,
} from './pages/b2c/B2cAccountPages';
import { StorefrontFeatureView } from '@taragold/shared/features/catalog/components/StorefrontFeatureView';
import { ProductCardFeatureView } from '@taragold/shared/features/catalog/components/ProductCardFeatureView';
import { FavoritesFeatureView } from '@taragold/shared/features/commerce/components/FavoritesFeatureView';
import { B2cDyoPage } from './pages/b2c/B2cDyoPage';
import {
  B2cPaymentFailurePage,
  B2cPaymentSuccessPage,
} from './pages/b2c/B2cPaymentResultPages';

export function App() {
  return (
    <ThemeProvider forcedTheme="light">
    <QueryProvider>
      <AuthProvider>
        <PortalSelectionProvider>
          <CommerceProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<StorefrontLayout />}>
                  <Route path="/" element={<B2cHomePage />} />
                  <Route path="/koleksiyon" element={<StorefrontFeatureView portalMode="b2c" />} />
                  <Route path="/urun/:parentSku" element={<ProductCardFeatureView portalMode="b2c" />} />
                  <Route path="/urun" element={<Navigate to="/koleksiyon" replace />} />
                  <Route path="/tasarla" element={<B2cDyoPage />} />
                  <Route path="/tasarla/:mountingSku" element={<B2cDyoPage />} />
                  <Route path="/favoriler" element={<FavoritesFeatureView portalMode="b2c" />} />
                  <Route path="/odeme-basarili" element={<B2cPaymentSuccessPage />} />
                  <Route path="/odeme-hatali" element={<B2cPaymentFailurePage />} />
                  <Route path="/giris" element={<B2cLoginPage />} />
                  <Route path="/kayit" element={<B2cRegisterPage />} />
                  <Route path="/sifre-yenile" element={<PasswordResetPage />} />
                  <Route path="/sifre-sifirla" element={<PasswordResetConfirmPage />} />
                  <Route path="/e-posta-dogrula" element={<EmailVerifyPage />} />
                  <Route
                    path="/hesabim"
                    element={
                      <PortalRouteGuard portal="b2c-auth">
                        <B2cAccountOverviewPage />
                      </PortalRouteGuard>
                    }
                  />
                  <Route
                    path="/hesabim/adresler"
                    element={
                      <PortalRouteGuard portal="b2c-auth">
                        <B2cAddressesPage />
                      </PortalRouteGuard>
                    }
                  />
                  <Route
                    path="/hesabim/siparisler"
                    element={
                      <PortalRouteGuard portal="b2c-auth">
                        <B2cOrdersListPage />
                      </PortalRouteGuard>
                    }
                  />
                  <Route
                    path="/hesabim/siparisler/:orderNo"
                    element={
                      <PortalRouteGuard portal="b2c-auth">
                        <B2cOrderDetailPage />
                      </PortalRouteGuard>
                    }
                  />
                  <Route path="/siparisler" element={<Navigate to="/hesabim/siparisler" replace />} />
                </Route>
                <Route path="/vitrin" element={<Navigate to="/koleksiyon" replace />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </BrowserRouter>
          </CommerceProvider>
        </PortalSelectionProvider>
      </AuthProvider>
    </QueryProvider>
    </ThemeProvider>
  );
}

export default App;