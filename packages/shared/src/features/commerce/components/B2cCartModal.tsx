import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  CreditCard,
  Gift,
  Info,
  Landmark,
  Minus,
  PackageCheck,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react';
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../../components/ui';
import { ConfirmDialog } from '../../../components/crud/ConfirmDialog';
import { JewelryIllustration } from '../../../components/JewelryIllustration';
import { resolveProductMedia } from '../../../data/productMedia';
import { useAuth } from '../../../providers/AuthProvider';
import { useActiveProductMetrics } from '../../catalog/hooks/useCatalogQueries';
import type { ProductState } from '../../catalog/types';
import { formatTrNumber } from '../../../utils/pricingEngine';
import { isIyzicoPaymentsEnabled } from '../../../config/commercialModules';
import { apiFetch } from '../../../lib/api/client';
import { b2cCheckoutSchema, b2cDeliveryStepSchema } from '../schemas/commerceSchema';
import {
  useB2cCartQuery,
  useB2cOrdersQuery,
  useClearB2cCartMutation,
  useCommerceUI,
  useInitializeIyzicoCheckoutMutation,
  useRefreshB2cPriceLockMutation,
  useRemoveB2cCartItemMutation,
  useSubmitB2cOrderMutation,
  useUpdateB2cCartItemMutation,
} from '../hooks/useCommerceQueries';
import { useDeleteDyoBundleMutation } from '../../dyo/hooks/useDyoQueries';
import type {
  B2cCartItem,
  B2cOrderRecord,
  B2cPaymentMethod,
  PaymentBankAccountRecord,
} from '../types';

const FREE_SHIPPING_THRESHOLD_TRY = 25000;
const INSURED_SHIPPING_FEE_TRY = 450;
const BANK_TRANSFER_DISCOUNT_PCT = 3;
const CHECKOUT_RESUME_KEY = 'taragold_checkout_resume_v1';

type CheckoutStep = 1 | 2 | 3;

const CHECKOUT_STEPS: { id: CheckoutStep; shortLabel: string; label: string }[] = [
  { id: 1, shortLabel: 'Sepet', label: 'Sepet Kontrolü' },
  { id: 2, shortLabel: 'Teslimat', label: 'Teslimat Bilgileri' },
  { id: 3, shortLabel: 'Ödeme', label: 'Ödeme ve Onay' },
];

function buildStoneSummary(item: B2cCartItem, product?: ProductState): string {
  if (product) {
    if (product.stoneType === 'Taşsız') {
      return product.certificateAgency ? `Taşsız · ${product.certificateAgency}` : 'Taşsız';
    }
    const totalCarat = Number(
      ((product.centerStoneCarat || 0) + (product.sideStoneCarat || 0)).toFixed(2)
    );
    const parts: string[] = [];
    if (totalCarat > 0) {
      parts.push(`${formatTrNumber(totalCarat, 2)} ct ${product.stoneType}`);
    } else {
      parts.push(product.stoneType);
    }
    const grade = [product.stoneColorGrade, product.stoneClarity].filter(Boolean).join('/');
    if (grade) parts.push(grade);
    if (product.certificateAgency) parts.push(product.certificateAgency);
    return parts.join(' · ');
  }
  return item.certificateLabel;
}

export function B2cCartModal() {
  const navigate = useNavigate();
  const { user, authenticated } = useAuth();
  const { b2cCartOpen, setB2cCartOpen } = useCommerceUI();
  const { products, rates } = useActiveProductMetrics();

  const cartQuery = useB2cCartQuery();
  const ordersQuery = useB2cOrdersQuery();
  const updateItemMutation = useUpdateB2cCartItemMutation();
  const removeItemMutation = useRemoveB2cCartItemMutation();
  const deleteDyoBundleMutation = useDeleteDyoBundleMutation();
  const clearCartMutation = useClearB2cCartMutation();
  const refreshLockMutation = useRefreshB2cPriceLockMutation();
  const submitOrderMutation = useSubmitB2cOrderMutation();
  const iyzicoCheckoutMutation = useInitializeIyzicoCheckoutMutation();

  const removeCartLine = (item: B2cCartItem) => {
    if (item.bundleId) {
      deleteDyoBundleMutation.mutate(item.bundleId);
      return;
    }
    removeItemMutation.mutate(item.id);
  };

  const [activeTab, setActiveTab] = useState<'cart' | 'orders'>('cart');
  const [step, setStep] = useState<CheckoutStep>(1);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [confirmedOrder, setConfirmedOrder] = useState<B2cOrderRecord | null>(null);
  const [copiedIban, setCopiedIban] = useState<string | null>(null);
  const [copiedRef, setCopiedRef] = useState(false);
  const [binInput, setBinInput] = useState('');
  const [installmentOptions, setInstallmentOptions] = useState<
    Array<{ installmentCount: number; monthlyAmount: string | null; totalAmount: string | null }>
  >([]);
  const [cardFamily, setCardFamily] = useState('');
  const [selectedInstallment, setSelectedInstallment] = useState(1);
  const [nowMs, setNowMs] = useState(() => Date.now());

  // Progressive disclosure states
  const [expandedOptions, setExpandedOptions] = useState<Record<string, boolean>>({});
  const [shippingInfoOpen, setShippingInfoOpen] = useState(false);
  const [mobileSummaryOpen, setMobileSummaryOpen] = useState(false);
  const [isTurkishCitizen, setIsTurkishCitizen] = useState(true);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});
  const [guestLeadEmail, setGuestLeadEmail] = useState(() => {
    try {
      return window.localStorage.getItem('tara-guest-recovery-email') || '';
    } catch {
      return '';
    }
  });
  const [guestLeadSaved, setGuestLeadSaved] = useState(() => {
    try {
      return Boolean(window.localStorage.getItem('tara-guest-recovery-email'));
    } catch {
      return false;
    }
  });
  const [guestLeadPending, setGuestLeadPending] = useState(false);
  const [guestLeadError, setGuestLeadError] = useState<string | null>(null);

  // Checkout fields (initialized from authenticated user profile when available; never hardcoded PII)
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [shippingCity, setShippingCity] = useState('');
  const [shippingAddress, setShippingAddress] = useState('');
  const [identityNumber, setIdentityNumber] = useState('');
  const iyzicoEnabled = isIyzicoPaymentsEnabled();
  const [paymentMethod, setPaymentMethod] = useState<B2cPaymentMethod>(
    iyzicoEnabled ? 'CREDIT_CARD' : 'BANK_TRANSFER'
  );
  const [acceptedCustomPolicy, setAcceptedCustomPolicy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const hasPrefilledUserRef = useRef(false);

  useEffect(() => {
    if (!authenticated || hasPrefilledUserRef.current) return;
    hasPrefilledUserRef.current = true;
    if (user.fullName && user.fullName !== 'Misafir') {
      setCustomerName((prev) => prev || user.fullName);
    }
    if (user.email) {
      setCustomerEmail((prev) => prev || user.email);
    }
  }, [authenticated, user.fullName, user.email]);

  useEffect(() => {
    if (!b2cCartOpen) return;
    setNowMs(Date.now());
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [b2cCartOpen]);

  const items = cartQuery.data?.items ?? [];
  const orders = ordersQuery.data ?? [];
  const totalQty = items.reduce((sum, i) => sum + i.qty, 0);

  const handleGoToLoginFromCheckout = () => {
    try {
      window.sessionStorage.setItem(
        CHECKOUT_RESUME_KEY,
        JSON.stringify({
          resumePending: true,
          step,
          customerName,
          customerPhone,
          customerEmail,
          shippingCity,
          shippingAddress,
          isTurkishCitizen,
          identityNumber,
          paymentMethod,
          acceptedCustomPolicy,
        })
      );
    } catch {
      // ignore storage errors
    }
    setB2cCartOpen(false);
    navigate('/giris', {
      state: { from: `${window.location.pathname}${window.location.search}` },
    });
  };

  // Resume checkout step & form fields after returning from login
  useEffect(() => {
    if (!authenticated || cartQuery.isLoading || cartQuery.isFetching) return;
    try {
      const raw = window.sessionStorage.getItem(CHECKOUT_RESUME_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as {
        resumePending?: boolean;
        step?: CheckoutStep;
        customerName?: string;
        customerPhone?: string;
        customerEmail?: string;
        shippingCity?: string;
        shippingAddress?: string;
        isTurkishCitizen?: boolean;
        identityNumber?: string;
        paymentMethod?: B2cPaymentMethod;
        acceptedCustomPolicy?: boolean;
      };
      if (!saved.resumePending) return;
      window.sessionStorage.removeItem(CHECKOUT_RESUME_KEY);
      if (saved.customerName) setCustomerName(saved.customerName);
      if (saved.customerPhone) setCustomerPhone(saved.customerPhone);
      if (saved.customerEmail) setCustomerEmail(saved.customerEmail);
      if (saved.shippingCity) setShippingCity(saved.shippingCity);
      if (saved.shippingAddress) setShippingAddress(saved.shippingAddress);
      if (typeof saved.isTurkishCitizen === 'boolean') setIsTurkishCitizen(saved.isTurkishCitizen);
      if (saved.identityNumber) setIdentityNumber(saved.identityNumber);
      if (saved.paymentMethod) setPaymentMethod(saved.paymentMethod);
      if (typeof saved.acceptedCustomPolicy === 'boolean') {
        setAcceptedCustomPolicy(saved.acceptedCustomPolicy);
      }
      if (items.length > 0 && saved.step) {
        setStep(saved.step);
      }
      setSubmitError(null);
      setActiveTab('cart');
      setB2cCartOpen(true);
    } catch {
      // ignore invalid storage payload
    }
  }, [authenticated, cartQuery.isLoading, cartQuery.isFetching, items.length, setB2cCartOpen]);

  // Reset to step 1 if cart becomes empty (ignore transient loading/fetching states)
  useEffect(() => {
    if (!cartQuery.isLoading && !cartQuery.isFetching && items.length === 0 && step !== 1) {
      setStep(1);
    }
  }, [cartQuery.isLoading, cartQuery.isFetching, items.length, step]);

  const productsByParentSku = useMemo(() => {
    const map = new Map<string, ProductState>();
    for (const p of products) {
      map.set(p.parentSku, p);
    }
    return map;
  }, [products]);

  const remainingSec = useMemo(() => {
    const until = cartQuery.data?.priceLockedUntil
      ? new Date(cartQuery.data.priceLockedUntil).getTime()
      : Date.now() + 15 * 60 * 1000;
    return Math.max(0, Math.floor((until - nowMs) / 1000));
  }, [cartQuery.data?.priceLockedUntil, nowMs]);

  const lockExpired = items.length > 0 && remainingSec === 0;
  const countdownLabel = `${String(Math.floor(remainingSec / 60)).padStart(2, '0')}:${String(
    remainingSec % 60
  ).padStart(2, '0')}`;

  const hasCustomOrEngravedItem = items.some(
    (item) => item.engravingText.trim().length > 0 || item.stockStatus === 'Siparişe Özel'
  );

  const totals = useMemo(() => {
    const subtotalListTry = items.reduce((s, i) => s + i.unitListPriceTry * i.qty, 0);
    const subtotalFinalTry = items.reduce((s, i) => s + i.unitFinalPriceTry * i.qty, 0);
    const campaignDiscountTry = Math.max(0, subtotalListTry - subtotalFinalTry);
    const transferDiscountTry =
      paymentMethod === 'BANK_TRANSFER'
        ? subtotalFinalTry * (BANK_TRANSFER_DISCOUNT_PCT / 100)
        : 0;
    const afterDiscounts = subtotalFinalTry - transferDiscountTry;
    const insuredShippingTry =
      items.length === 0 || afterDiscounts >= FREE_SHIPPING_THRESHOLD_TRY
        ? 0
        : INSURED_SHIPPING_FEE_TRY;
    const grandTotalTry = afterDiscounts + insuredShippingTry;
    const vatIncludedTry = grandTotalTry - grandTotalTry / 1.2;
    return {
      subtotalListTry,
      subtotalFinalTry,
      campaignDiscountTry,
      transferDiscountTry,
      insuredShippingTry,
      vatIncludedTry,
      grandTotalTry,
    };
  }, [items, paymentMethod]);

  const clearFieldError = (key: string) => {
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const validateDeliveryStep = (): boolean => {
    setFieldErrors({});
    setSubmitError(null);
    const parsed = b2cDeliveryStepSchema.safeParse({
      customerName,
      customerPhone,
      customerEmail,
      shippingCity,
      shippingAddress,
      isTurkishCitizen,
      identityNumber: isTurkishCitizen ? identityNumber : identityNumber.trim(),
    });

    if (!parsed.success) {
      const map: Record<string, string> = {};
      parsed.error.issues.forEach((issue) => {
        const key = String(issue.path[0] ?? 'form');
        if (!map[key]) map[key] = issue.message;
      });
      setFieldErrors(map);
      return false;
    }
    return true;
  };

  const handleStepNavigation = (target: CheckoutStep) => {
    if (target === step) return;
    setSubmitError(null);
    if (target < step) {
      setStep(target);
      return;
    }
    if (step === 1 && target === 2) {
      setStep(2);
      return;
    }
    if (target === 3) {
      if (validateDeliveryStep()) {
        setStep(3);
      } else {
        setStep(2);
      }
    }
  };

  const handleProceedFromStep1 = () => {
    setSubmitError(null);
    setStep(2);
  };

  const handleGuestRecoveryLead = async () => {
    const email = guestLeadEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      setGuestLeadError('Geçerli bir e-posta giriniz.');
      return;
    }
    setGuestLeadPending(true);
    setGuestLeadError(null);
    try {
      await apiFetch('/api/v1/storefront/cart/recovery-lead', {
        method: 'POST',
        body: {
          email,
          items: items.map((item) => ({
            sku: item.sku,
            title: item.title,
            qty: item.qty,
            unitFinalPriceTry: item.unitFinalPriceTry,
          })),
        },
      });
      try {
        window.localStorage.setItem('tara-guest-recovery-email', email);
      } catch {
        // ignore
      }
      setGuestLeadSaved(true);
    } catch (err) {
      setGuestLeadError(
        err instanceof Error ? err.message : 'Hatırlatma kaydı oluşturulamadı.'
      );
    } finally {
      setGuestLeadPending(false);
    }
  };

  const handleProceedFromStep2 = () => {
    if (validateDeliveryStep()) {
      setStep(3);
    }
  };

  const handleCheckoutSubmit = async () => {
    setFieldErrors({});
    setSubmitError(null);

    if (lockExpired) {
      setSubmitError('Altın fiyat kilidi süresi doldu. Devam etmek için lütfen kuru güncelleyin.');
      return;
    }

    const parsed = b2cCheckoutSchema.safeParse({
      customerName,
      customerPhone,
      customerEmail,
      shippingCity,
      shippingAddress,
      isTurkishCitizen,
      identityNumber: isTurkishCitizen ? identityNumber : identityNumber.trim(),
      paymentMethod,
      acceptedCustomPolicy,
    });

    if (!parsed.success) {
      const map: Record<string, string> = {};
      parsed.error.issues.forEach((issue) => {
        const key = String(issue.path[0] ?? 'form');
        if (!map[key]) map[key] = issue.message;
      });
      setFieldErrors(map);
      if (
        map.customerName ||
        map.customerPhone ||
        map.customerEmail ||
        map.shippingCity ||
        map.shippingAddress ||
        map.identityNumber
      ) {
        setStep(2);
      }
      return;
    }

    if (hasCustomOrEngravedItem && !acceptedCustomPolicy) {
      setFieldErrors({
        acceptedCustomPolicy:
          'Kişiye özel üretim veya gravürlü ürünler için iade koşulunu onaylamalısınız.',
      });
      return;
    }

    if (!authenticated) {
      setSubmitError(
        'Siparişi tamamlamak için giriş yapmanız veya üye olmanız gerekiyor. Sepetiniz korunacaktır.'
      );
      return;
    }

    const checkoutPayload = {
      snapshotId: rates.snapshotId,
      goldRateTryPerGram: rates.liveHasGoldTrySell,
      customerName: parsed.data.customerName,
      customerPhone: parsed.data.customerPhone,
      customerEmail: parsed.data.customerEmail,
      shippingCity: parsed.data.shippingCity,
      shippingAddress: parsed.data.shippingAddress,
      isTurkishCitizen: parsed.data.isTurkishCitizen,
      identityNumber: parsed.data.identityNumber || undefined,
      paymentMethod: parsed.data.paymentMethod,
      acceptedCustomPolicy: hasCustomOrEngravedItem ? acceptedCustomPolicy : true,
      subtotalListTry: totals.subtotalListTry,
      campaignDiscountTry: totals.campaignDiscountTry,
      transferDiscountTry: totals.transferDiscountTry,
      insuredShippingTry: totals.insuredShippingTry,
      vatIncludedTry: totals.vatIncludedTry,
      grandTotalTry: totals.grandTotalTry,
    };

    try {
      if (parsed.data.paymentMethod === 'CREDIT_CARD') {
        if (!iyzicoEnabled) {
          throw new Error('Kart ödemesi bu kurulumda etkin değil. Havale seçin veya iyzico modülünü açın.');
        }
        const init = await iyzicoCheckoutMutation.mutateAsync(checkoutPayload);
        if (!init.paymentPageUrl) {
          throw new Error('iyzico ödeme sayfası alınamadı.');
        }
        window.location.assign(init.paymentPageUrl);
        return;
      }

      const order = await submitOrderMutation.mutateAsync(checkoutPayload);
      setConfirmedOrder(order);
      setStep(1);
      setMobileSummaryOpen(false);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Sipariş tamamlanamadı.');
    }
  };

  const handlePrimaryAction = () => {
    if (step === 1) {
      handleProceedFromStep1();
    } else if (step === 2) {
      handleProceedFromStep2();
    } else {
      void handleCheckoutSubmit();
    }
  };

  const checkoutPending =
    submitOrderMutation.isPending || iyzicoCheckoutMutation.isPending;

  const primaryCtaLabel =
    step === 1
      ? 'Teslimata Devam Et'
      : step === 2
        ? 'Ödemeye Geç'
        : checkoutPending
          ? paymentMethod === 'CREDIT_CARD'
            ? 'iyzico’ya yönlendiriliyor...'
            : 'Onaylanıyor...'
          : `Siparişi Onayla · ${formatTrNumber(totals.grandTotalTry, 2)} TL`;

  const isCheckoutFlow = activeTab === 'cart' && items.length > 0 && !confirmedOrder;

  const renderSummaryLines = () => (
    <dl className="space-y-2 text-[13px]">
      <div className="flex items-center justify-between gap-3">
        <dt className="text-muted-foreground">Ara Toplam</dt>
        <dd className="font-mono tabular-nums text-foreground">
          {formatTrNumber(totals.subtotalListTry, 2)} TL
        </dd>
      </div>

      {totals.campaignDiscountTry > 0 && (
        <div className="flex items-center justify-between gap-3 text-foreground">
          <dt>Kampanya İndirimi</dt>
          <dd className="font-mono tabular-nums">
            -{formatTrNumber(totals.campaignDiscountTry, 2)} TL
          </dd>
        </div>
      )}

      {totals.transferDiscountTry > 0 && (
        <div className="flex items-center justify-between gap-3 text-success">
          <dt>Havale / EFT (%3)</dt>
          <dd className="font-mono tabular-nums">
            -{formatTrNumber(totals.transferDiscountTry, 2)} TL
          </dd>
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <dt className="text-muted-foreground">Kargo Ücreti</dt>
        <dd className="font-mono tabular-nums text-foreground">
          {totals.insuredShippingTry === 0 ? (
            <span className="font-sans font-medium text-success">Ücretsiz</span>
          ) : (
            `${formatTrNumber(totals.insuredShippingTry, 2)} TL`
          )}
        </dd>
      </div>

      <div className="pt-3 mt-3 border-t border-[#E9DCCB] flex items-baseline justify-between gap-3">
        <div>
          <dt className="font-serif text-base font-medium text-[#252321]">Ödenecek Toplam</dt>
          <p className="text-[11px] text-[#252321]/65 mt-0.5">
            KDV dahil ({formatTrNumber(totals.vatIncludedTry, 2)} TL)
          </p>
        </div>
        <dd className="font-sans text-lg font-semibold text-[#252321] tabular-nums whitespace-nowrap">
          {formatTrNumber(totals.grandTotalTry, 2)} TL
        </dd>
      </div>
    </dl>
  );

  return (
    <>
      <Dialog
        open={b2cCartOpen}
        onOpenChange={(open) => {
          if (!open) {
            setConfirmedOrder(null);
            setMobileSummaryOpen(false);
          }
          setB2cCartOpen(open);
        }}
      >
        <DialogContent
          showGlow={false}
          hideCloseButton
          className="inset-0 left-0 top-0 translate-x-0 translate-y-0 w-full max-w-none h-[100dvh] max-h-[100dvh] rounded-none md:inset-auto md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-[calc(100%-2rem)] md:max-w-[940px] md:h-auto md:max-h-[88vh] md:rounded-[6px]"
          innerClassName="p-0 overflow-hidden h-[100dvh] max-h-[100dvh] md:h-auto md:max-h-[88vh] flex flex-col bg-[#F8F5EF] text-[#252321] border-0 md:border md:border-[#E9DCCB] shadow-2xl"
        >
          {/* Sticky Top Modal Header */}
          <header className="shrink-0 bg-white border-b border-[#E9DCCB] px-4 sm:px-6 py-3.5 flex items-center justify-between gap-2 min-w-0">
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              {isCheckoutFlow && step > 1 && (
                <button
                  type="button"
                  onClick={() => handleStepNavigation((step - 1) as CheckoutStep)}
                  aria-label="Önceki adıma dön"
                  className="md:hidden inline-flex items-center justify-center w-9 h-9 -ml-1.5 rounded-[4px] text-[#252321] hover:bg-[#F8F5EF] transition-colors cursor-pointer shrink-0"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
              )}
              <div className="min-w-0">
                <DialogTitle className="font-serif text-[20px] sm:text-[22px] font-normal text-[#252321] truncate leading-tight">
                  {activeTab === 'orders' ? (
                    'Siparişlerim'
                  ) : confirmedOrder ? (
                    'Sipariş Onayı'
                  ) : (
                    <>
                      <span className="sm:hidden">Sepetim</span>
                      <span className="hidden sm:inline">Alışveriş Sepeti</span>
                    </>
                  )}
                </DialogTitle>
                <DialogDescription className="sr-only">
                  TARA DIAMOND perakende sepeti ve adım adım sipariş tamamlama ekranı.
                </DialogDescription>
              </div>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <div className="inline-flex rounded-[4px] border border-[#E9DCCB] bg-[#F8F5EF] p-0.5 text-[11px] sm:text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setConfirmedOrder(null);
                    setActiveTab('cart');
                  }}
                  className={`px-2.5 sm:px-3 py-1.5 rounded-[3px] font-medium transition-colors whitespace-nowrap cursor-pointer ${
                    activeTab === 'cart'
                      ? 'bg-[#252321] text-white'
                      : 'text-[#252321]/70 hover:text-[#252321]'
                  }`}
                >
                  Sepet ({totalQty})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('orders')}
                  className={`px-2.5 sm:px-3 py-1.5 rounded-[3px] font-medium transition-colors whitespace-nowrap cursor-pointer ${
                    activeTab === 'orders'
                      ? 'bg-[#252321] text-white'
                      : 'text-[#252321]/70 hover:text-[#252321]'
                  }`}
                >
                  <span className="min-[380px]:hidden">Sipariş ({orders.length})</span>
                  <span className="hidden min-[380px]:inline">Siparişler ({orders.length})</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => {
                  setConfirmedOrder(null);
                  setB2cCartOpen(false);
                }}
                aria-label="Sepeti kapat"
                className="inline-flex items-center justify-center w-9 h-9 rounded-[4px] text-[#252321]/70 hover:text-[#252321] hover:bg-[#F8F5EF] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B89A68] cursor-pointer shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </header>

          {/* Stepper + Compact Gold Lock Strip (Checkout Flow Only) */}
          {isCheckoutFlow && (
            <div className="shrink-0 bg-white border-b border-[#E9DCCB]">
              <nav
                aria-label="Sipariş adımları"
                className="px-4 sm:px-6 py-2.5 flex items-center justify-between gap-2"
              >
                <ol className="flex items-center w-full max-w-lg gap-1 sm:gap-2">
                  {CHECKOUT_STEPS.map((item, idx) => {
                    const isActive = step === item.id;
                    const isCompleted = step > item.id;
                    return (
                      <li key={item.id} className="flex items-center flex-1 last:flex-none min-w-0">
                        <button
                          type="button"
                          onClick={() => handleStepNavigation(item.id)}
                          aria-current={isActive ? 'step' : undefined}
                          className={`inline-flex items-center gap-1.5 text-xs font-medium transition-colors whitespace-nowrap cursor-pointer py-1 ${
                            isActive
                              ? 'text-foreground'
                              : isCompleted
                                ? 'text-muted-foreground hover:text-foreground'
                                : 'text-muted-foreground hover:text-muted-foreground'
                          }`}
                        >
                          <span
                            className={`w-5 h-5 rounded-full inline-flex items-center justify-center text-[11px] font-mono shrink-0 ${
                              isActive
                                ? 'bg-[#252321] text-white'
                                : isCompleted
                                  ? 'bg-[#252321] text-white'
                                  : 'bg-[#F8F5EF] border border-[#E9DCCB] text-[#252321]/65'
                            }`}
                          >
                            {isCompleted ? <Check className="w-3 h-3" /> : item.id}
                          </span>
                          <span className="sm:hidden truncate">{item.shortLabel}</span>
                          <span className="hidden sm:inline">{item.label}</span>
                        </button>
                        {idx < CHECKOUT_STEPS.length - 1 && (
                          <div
                            aria-hidden="true"
                            className={`h-px flex-1 mx-2 sm:mx-3 ${
                              step > item.id ? 'bg-[#B89A68]' : 'bg-[#E9DCCB]'
                            }`}
                          />
                        )}
                      </li>
                    );
                  })}
                </ol>

                {/* Subtle price lock indicator on desktop/tablet */}
                {!lockExpired && (
                  <div className="hidden md:flex items-center gap-2 text-[11px] text-muted-foreground whitespace-nowrap shrink-0">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    <span>
                      Fiyat kilidi{' '}
                      <span className="font-mono font-medium text-foreground tabular-nums">
                        {countdownLabel}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => refreshLockMutation.mutate()}
                      disabled={refreshLockMutation.isPending}
                      className="text-muted-foreground hover:text-foreground underline underline-offset-2 cursor-pointer"
                    >
                      Yenile
                    </button>
                  </div>
                )}
              </nav>

              {/* Expired Gold Lock Alert (Pearl White + Anthracite + Subtle Champagne Gold) */}
              {lockExpired && (
                <div className="px-4 sm:px-6 py-2.5 bg-[#F8F5EF] border-t border-[#E9DCCB] flex flex-wrap items-center justify-between gap-2.5 text-xs text-[#252321]">
                  <div className="flex items-center gap-2 min-w-0">
                    <Clock className="w-4 h-4 text-[#B89A68] shrink-0" />
                    <span className="leading-snug">
                      Altın fiyat kilidi süresi doldu. Güncel kurla devam edebilmek için fiyatı yenileyin.
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSubmitError(null);
                      refreshLockMutation.mutate();
                    }}
                    disabled={refreshLockMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[4px] bg-[#252321] text-white text-[11px] font-medium hover:bg-[#252321]/90 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <RefreshCw
                      className={`w-3 h-3 ${refreshLockMutation.isPending ? 'animate-spin' : ''}`}
                    />
                    {refreshLockMutation.isPending ? 'Güncelleniyor...' : 'Kuru Güncelle'}
                  </button>
                </div>
              )}

              {/* Mobile compact active lock bar */}
              {!lockExpired && (
                <div className="md:hidden px-4 py-1.5 border-t border-border/75 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-muted-foreground" />
                    Altın fiyat kilidi:{' '}
                    <strong className="font-mono text-foreground tabular-nums">
                      {countdownLabel}
                    </strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => refreshLockMutation.mutate()}
                    disabled={refreshLockMutation.isPending}
                    className="text-muted-foreground underline underline-offset-2 cursor-pointer"
                  >
                    Yenile
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Single Scrollable Body */}
          <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 sm:px-6 py-4 sm:py-5">
            {/* Confirmed Receipt View */}
            {confirmedOrder && activeTab === 'cart' ? (
              <div className="max-w-xl mx-auto py-3 space-y-5">
                <div className="flex items-start gap-3 pb-4 border-b border-border">
                  <div className="w-9 h-9 rounded-full bg-success/10 border border-success/30 flex items-center justify-center shrink-0">
                    <PackageCheck className="w-5 h-5 text-success" />
                  </div>
                  <div className="space-y-1 min-w-0">
                    <div className="font-serif text-lg font-medium text-foreground">
                      Siparişiniz Alındı · {confirmedOrder.orderNo}
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Fiyatınız{' '}
                      <span className="font-mono font-medium text-foreground">
                        {confirmedOrder.snapshotId}
                      </span>{' '}
                      ({formatTrNumber(confirmedOrder.goldRateTryPerGram, 2)} TL/gr) üzerinden
                      sabitlendi. Orijinal sertifika ve sigortalı kargo poliçesi paketle gönderilir.
                    </p>
                  </div>
                </div>

                <dl className="divide-y divide-border/80 text-xs">
                  <div className="py-3 flex justify-between gap-4">
                    <dt className="text-muted-foreground shrink-0">Alıcı</dt>
                    <dd className="font-medium text-foreground text-right">
                      {confirmedOrder.customerName} · {confirmedOrder.customerPhone}
                    </dd>
                  </div>
                  <div className="py-3 flex justify-between gap-4">
                    <dt className="text-muted-foreground shrink-0">Teslimat Adresi</dt>
                    <dd className="text-foreground text-right">
                      {confirmedOrder.shippingAddress}, {confirmedOrder.shippingCity}
                    </dd>
                  </div>
                  <div className="py-3 flex justify-between gap-4">
                    <dt className="text-muted-foreground shrink-0">Ödeme Yöntemi</dt>
                    <dd className="font-medium text-foreground text-right">
                      {confirmedOrder.paymentMethod === 'BANK_TRANSFER'
                        ? 'Havale / EFT (%3 Nakit İndirimli)'
                        : 'Kredi Kartı (3D Secure)'}
                    </dd>
                  </div>
                  <div className="py-3 flex justify-between items-baseline gap-4">
                    <dt className="text-sm font-semibold text-foreground">
                      {confirmedOrder.paymentMethod === 'BANK_TRANSFER' &&
                      confirmedOrder.status === 'ODEME_BEKLIYOR'
                        ? 'Ödenecek Toplam'
                        : 'Ödenen Toplam'}
                    </dt>
                    <dd className="font-mono text-base font-semibold text-foreground tabular-nums">
                      {formatTrNumber(confirmedOrder.grandTotalTry, 2)} TL
                    </dd>
                  </div>
                </dl>

                {confirmedOrder.paymentMethod === 'BANK_TRANSFER' && (
                  <div className="rounded-[6px] border border-border bg-background p-4 space-y-3">
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <Landmark className="w-4 h-4 text-muted-foreground" />
                      Havale / EFT Bilgileri
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      Lütfen tutarı aşağıdaki hesaba yatırın. Açıklama alanına yalnızca referans
                      kodunu yazın. Dekontu sipariş detayından yükleyebilirsiniz.
                    </p>
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="text-muted-foreground">Referans Kodu</span>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1.5 font-mono font-semibold text-foreground"
                        onClick={() => {
                          const ref =
                            confirmedOrder.transferReference || confirmedOrder.orderNo;
                          void navigator.clipboard?.writeText(ref);
                          setCopiedRef(true);
                          setTimeout(() => setCopiedRef(false), 1500);
                        }}
                      >
                        {confirmedOrder.transferReference || confirmedOrder.orderNo}
                        {copiedRef ? (
                          <Check className="w-3.5 h-3.5 text-success" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                        )}
                      </button>
                    </div>
                    {(confirmedOrder.bankAccounts ?? []).length === 0 ? (
                      <p className="text-xs text-foreground">
                        Aktif banka hesabı henüz tanımlı değil. Lütfen müşteri hizmetleri ile
                        iletişime geçin.
                      </p>
                    ) : (
                      (confirmedOrder.bankAccounts as PaymentBankAccountRecord[]).map((bank) => (
                        <div
                          key={bank.id}
                          className="rounded-[4px] border border-border/80 bg-white p-3 space-y-1.5 text-xs"
                        >
                          <div className="font-medium text-foreground">{bank.bankName}</div>
                          <div className="text-muted-foreground">{bank.accountHolder}</div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-[11px] text-foreground break-all">
                              {bank.iban}
                            </span>
                            <button
                              type="button"
                              className="shrink-0 inline-flex items-center gap-1 text-muted-foreground"
                              onClick={() => {
                                void navigator.clipboard?.writeText(
                                  bank.iban.replace(/\s/g, '')
                                );
                                setCopiedIban(bank.id);
                                setTimeout(() => setCopiedIban(null), 1500);
                              }}
                            >
                              {copiedIban === bank.id ? (
                                <Check className="w-3.5 h-3.5 text-success" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                              <span>Kopyala</span>
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {confirmedOrder.paymentMethod !== 'BANK_TRANSFER' &&
                  confirmedOrder.payment?.installment != null && (
                    <div className="rounded-[6px] border border-border bg-background p-4 space-y-2 text-xs">
                      <div className="font-medium text-foreground">Kart / Taksit Özeti</div>
                      {confirmedOrder.payment.cardFamily ? (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Kart Ailesi</span>
                          <span>{confirmedOrder.payment.cardFamily}</span>
                        </div>
                      ) : null}
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Taksit</span>
                        <span className="font-mono">
                          {confirmedOrder.payment.installment > 1
                            ? `${confirmedOrder.payment.installment} Taksit`
                            : 'Tek Çekim'}
                        </span>
                      </div>
                      {confirmedOrder.payment.lastFourDigits ? (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Kart</span>
                          <span className="font-mono">
                            ****{confirmedOrder.payment.lastFourDigits}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  )}

                <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() => {
                      setConfirmedOrder(null);
                      setActiveTab('orders');
                    }}
                  >
                    Siparişlerime Git
                  </Button>
                  <Button
                    className="w-full sm:w-auto"
                    onClick={() => {
                      setConfirmedOrder(null);
                      setB2cCartOpen(false);
                    }}
                  >
                    Mağazaya Dön
                  </Button>
                </div>
              </div>
            ) : activeTab === 'orders' ? (
              /* Past B2C Orders View */
              <div className="space-y-3">
                {orders.length === 0 ? (
                  <div className="py-12 text-center space-y-2.5">
                    <ShoppingBag className="w-8 h-8 text-muted-foreground mx-auto" />
                    <div className="font-serif text-lg text-foreground">
                      Henüz tamamlanmış siparişiniz yok.
                    </div>
                    <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                      Sepetinize ürün ekleyip teslimat ve ödeme adımlarını tamamladığınızda
                      siparişleriniz burada listelenir.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/80">
                    {orders.map((order) => (
                      <div key={order.orderNo} className="py-4 first:pt-0 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="font-mono font-semibold text-foreground">
                              {order.orderNo}
                            </span>
                            <span className="text-muted-foreground" aria-hidden="true">
                              ·
                            </span>
                            <span className="text-muted-foreground">
                              {new Date(order.createdAt).toLocaleString('tr-TR', {
                                dateStyle: 'short',
                                timeStyle: 'short',
                              })}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs">
                            <span className="font-medium text-success">
                              {order.status === 'ATOLYE_URETIMDE'
                                ? 'Atölye Üretiminde'
                                : 'Sigortalı Kargo Hazırlanıyor'}
                            </span>
                            <span className="font-mono font-semibold text-foreground tabular-nums">
                              {formatTrNumber(order.grandTotalTry, 2)} TL
                            </span>
                          </div>
                        </div>

                        <div className="space-y-1 text-xs">
                          {order.items.map((item) => (
                            <div
                              key={item.id}
                              className="flex flex-wrap items-baseline justify-between gap-2 text-muted-foreground"
                            >
                              <span className="min-w-0">
                                <strong className="text-foreground">{item.qty}×</strong> {item.title}{' '}
                                ({item.purityCode} {item.metalColor} · {item.sizeUnitLabel}{' '}
                                {item.size})
                                {item.engravingText && (
                                  <span className="ml-1.5 text-muted-foreground">
                                    · Yazı: “{item.engravingText}”
                                  </span>
                                )}
                              </span>
                              <span className="font-mono tabular-nums text-foreground shrink-0">
                                {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : items.length === 0 ? (
              /* Empty Cart View */
              <div className="py-12 text-center space-y-3">
                <ShoppingBag className="w-9 h-9 text-muted-foreground mx-auto" />
                <div className="font-serif text-xl text-foreground">Sepetiniz boş</div>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                  Koleksiyondan beğendiğiniz mücevheri seçip ölçüsünü belirleyerek sepetinize
                  ekleyebilirsiniz.
                </p>
                <Button variant="outline" size="sm" onClick={() => setB2cCartOpen(false)}>
                  Koleksiyona Dön
                </Button>
              </div>
            ) : (
              /* Active Multi-Step Checkout Grid */
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-7 items-start">
                {/* Main Step Content Column */}
                <div className="lg:col-span-7 min-w-0">
                  {/* STEP 1: Cart Items & Review */}
                  {step === 1 && (
                    <div className="space-y-4">
                      {!authenticated && items.length > 0 && !guestLeadSaved ? (
                        <div className="rounded-[6px] border border-[#E9DCCB] bg-white px-4 py-3.5 space-y-2.5">
                          <p className="text-xs font-medium text-[#252321]">
                            Sepetinizi e-posta ile hatırlatalım
                          </p>
                          <p className="text-[11px] text-[#252321]/70 leading-relaxed">
                            Çıkmadan önce adresinizi bırakın; sepetiniz kaybolursa nazik bir
                            hatırlatma gönderelim.
                          </p>
                          <div className="flex flex-col sm:flex-row gap-2">
                            <input
                              type="email"
                              value={guestLeadEmail}
                              onChange={(e) => setGuestLeadEmail(e.target.value)}
                              placeholder="E-posta adresiniz"
                              className="flex-1 h-10 px-3 rounded-[4px] border border-[#E9DCCB] bg-[#F8F5EF]/40 text-sm text-[#252321] placeholder:text-[#252321]/45 focus:outline-none focus:border-[#B89A68]"
                            />
                            <button
                              type="button"
                              disabled={guestLeadPending}
                              onClick={() => void handleGuestRecoveryLead()}
                              className="h-10 px-4 rounded-[4px] bg-[#252321] text-white text-xs font-medium hover:bg-[#252321]/90 disabled:opacity-50 transition-colors cursor-pointer"
                            >
                              {guestLeadPending ? 'Kaydediliyor…' : 'Hatırlat'}
                            </button>
                          </div>
                          {guestLeadError ? (
                            <p className="text-[11px] text-[#4A101C]">{guestLeadError}</p>
                          ) : null}
                        </div>
                      ) : null}
                      {!authenticated && guestLeadSaved ? (
                        <p className="text-[11px] text-[#252321]/70">
                          Hatırlatma için e-posta kaydedildi. Sepeti istediğiniz zaman
                          tamamlayabilirsiniz.
                        </p>
                      ) : null}
                      <div className="divide-y divide-[#E9DCCB]/75">
                        {items.map((item) => {
                          const matchedProduct = productsByParentSku.get(item.parentSku);
                          const media = resolveProductMedia(
                            item.parentSku,
                            item.metalColor,
                            matchedProduct?.galleryImages
                          );
                          const imgKey = `${item.id}-${media.mainUrl}`;
                          const imgFailed = failedImages[imgKey];
                          const hasSavings = item.unitListPriceTry > item.unitFinalPriceTry;
                          const stoneSummary = buildStoneSummary(item, matchedProduct);
                          const isExpanded = Boolean(expandedOptions[item.id]);
                          const hasPersonalization =
                            item.engravingText.trim().length > 0 || item.giftWrap;

                          return (
                            <article key={item.id} className="py-4 first:pt-0 space-y-3">
                              <div className="flex gap-3.5 sm:gap-4 items-start">
                                {/* Product Thumbnail */}
                                <div className="w-20 h-20 sm:w-[88px] sm:h-[88px] rounded-[4px] border border-[#E9DCCB]/80 bg-white overflow-hidden shrink-0 flex items-center justify-center">
                                  {media.mainUrl && !imgFailed ? (
                                    <img
                                      src={media.mainUrl}
                                      alt={item.title}
                                      referrerPolicy="no-referrer"
                                      onError={() =>
                                        setFailedImages((prev) => ({ ...prev, [imgKey]: true }))
                                      }
                                      style={
                                        media.toneFilter
                                          ? { filter: media.toneFilter }
                                          : undefined
                                      }
                                      className="w-full h-full object-cover"
                                    />
                                  ) : (
                                    <JewelryIllustration
                                      visualType={matchedProduct?.visualType ?? 'solitaire_ring'}
                                      metalColor={item.metalColor}
                                      stoneType={matchedProduct?.stoneType ?? 'Pırlanta'}
                                      centerStoneCarat={matchedProduct?.centerStoneCarat ?? 0.5}
                                      sideStoneCarat={matchedProduct?.sideStoneCarat ?? 0}
                                      className="w-12 h-12"
                                    />
                                  )}
                                </div>

                                {/* Product Info + Price */}
                                <div className="flex-1 min-w-0 space-y-1">
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <h3 className="font-serif text-[17px] sm:text-[18px] font-medium text-[#252321] leading-snug line-clamp-2">
                                        {item.title}
                                      </h3>
                                      <div className="font-mono text-[11px] text-[#252321]/55 mt-0.5 truncate">
                                        {item.sku}
                                      </div>
                                    </div>

                                    <button
                                      type="button"
                                      onClick={() => removeCartLine(item)}
                                      aria-label={
                                        item.bundleId
                                          ? 'DYO paketini sepetten kaldır'
                                          : `${item.title} ürününü kaldır`
                                      }
                                      data-delete="true"
                                      className="p-1.5 -mr-1.5 -mt-1 text-[#252321]/45 hover:text-[#4A101C] hover:bg-[#4A101C]/5 transition-colors cursor-pointer shrink-0 rounded-md"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </div>

                                  {item.bundleId ? (
                                    <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                                      DYO paket · {item.bundleRole === 'STONE' ? 'Taş' : 'Montür'}
                                    </div>
                                  ) : null}

                                  {/* Essential Jewelry Metadata (Unboxed, clean separators) */}
                                  <div className="text-xs text-muted-foreground leading-relaxed">
                                    <span>
                                      {item.purityCode} {item.metalColor} Altın
                                    </span>
                                    <span className="mx-1.5 text-muted-foreground" aria-hidden="true">
                                      ·
                                    </span>
                                    <span>
                                      {item.sizeUnitLabel}{' '}
                                      <strong className="font-medium text-foreground">
                                        {item.size}
                                      </strong>
                                    </span>
                                    <span className="mx-1.5 text-muted-foreground" aria-hidden="true">
                                      ·
                                    </span>
                                    <span className="tabular-nums">
                                      {formatTrNumber(item.grossWeightGram, 2)} gr
                                    </span>
                                  </div>

                                  {stoneSummary && (
                                    <div className="text-xs text-muted-foreground truncate">
                                      {stoneSummary}
                                    </div>
                                  )}

                                  {/* Bottom Row: Quantity Stepper + Price */}
                                  <div className="pt-2 flex flex-wrap items-center justify-between gap-2">
                                    {item.bundleId ? (
                                      <div className="inline-flex items-center h-8 px-2.5 rounded-[4px] border border-border bg-card text-[11px] text-muted-foreground">
                                        Paket adedi sabit (1)
                                      </div>
                                    ) : (
                                    <div className="inline-flex items-center border border-input rounded-[4px] bg-card overflow-hidden">
                                      <button
                                        type="button"
                                        aria-label="Adet azalt"
                                        onClick={() =>
                                          item.qty <= 1
                                            ? removeCartLine(item)
                                            : updateItemMutation.mutate({
                                                id: item.id,
                                                patch: { qty: item.qty - 1 },
                                              })
                                        }
                                        className="w-8 h-8 inline-flex items-center justify-center hover:bg-muted text-foreground transition-colors cursor-pointer"
                                      >
                                        <Minus className="w-3.5 h-3.5" />
                                      </button>
                                      <span className="w-8 text-center text-xs font-mono font-medium text-foreground tabular-nums">
                                        {item.qty}
                                      </span>
                                      <button
                                        type="button"
                                        aria-label="Adet artır"
                                        onClick={() =>
                                          updateItemMutation.mutate({
                                            id: item.id,
                                            patch: { qty: item.qty + 1 },
                                          })
                                        }
                                        className="w-8 h-8 inline-flex items-center justify-center hover:bg-muted text-foreground transition-colors cursor-pointer"
                                      >
                                        <Plus className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                    )}

                                    <div className="text-right">
                                      {hasSavings && (
                                        <div className="font-mono text-[11px] text-muted-foreground line-through tabular-nums">
                                          {formatTrNumber(item.unitListPriceTry * item.qty, 2)} TL
                                        </div>
                                      )}
                                      <div className="font-mono text-sm font-semibold text-foreground tabular-nums">
                                        {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>

                              {/* Optional Personalization & Gift Accordion (Collapsed by default) */}
                              {!item.bundleId && (
                              <div className="pl-0 sm:pl-[92px]">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedOptions((prev) => ({
                                      ...prev,
                                      [item.id]: !prev[item.id],
                                    }))
                                  }
                                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer py-1"
                                >
                                  <SlidersHorizontal className="w-3.5 h-3.5 text-muted-foreground" />
                                  <span className="font-medium">
                                    Kişiselleştirme & Hediye Paketi
                                  </span>
                                  {hasPersonalization && !isExpanded && (
                                    <span className="text-[11px] text-muted-foreground">
                                      ·{' '}
                                      {[
                                        item.engravingText.trim()
                                          ? `“${item.engravingText.trim()}”`
                                          : null,
                                        item.giftWrap ? 'Hediye paketi' : null,
                                      ]
                                        .filter(Boolean)
                                        .join(', ')}
                                    </span>
                                  )}
                                  {isExpanded ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                                  ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                                  )}
                                </button>

                                {isExpanded && (
                                  <div className="mt-2 pt-3 border-t border-border/75 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                                    <div className="space-y-1">
                                      <label className="text-[11px] font-medium text-muted-foreground block">
                                        Lazer İç Yazı (Ücretsiz · Maks. 20 karakter)
                                      </label>
                                      <input
                                        type="text"
                                        maxLength={20}
                                        value={item.engravingText}
                                        onChange={(e) =>
                                          updateItemMutation.mutate({
                                            id: item.id,
                                            patch: { engravingText: e.target.value },
                                          })
                                        }
                                        placeholder="Örn: S & K · 24.11.2026"
                                        className="w-full h-9 px-2.5 rounded-[4px] border border-input bg-white text-xs text-foreground focus:outline-none focus:border-ring"
                                      />
                                    </div>

                                    <div className="space-y-1.5">
                                      <label className="inline-flex items-center gap-2 text-[11px] font-medium text-foreground cursor-pointer pt-0.5">
                                        <input
                                          type="checkbox"
                                          checked={item.giftWrap}
                                          onChange={(e) =>
                                            updateItemMutation.mutate({
                                              id: item.id,
                                              patch: { giftWrap: e.target.checked },
                                            })
                                          }
                                          className="rounded border-input accent-foreground"
                                        />
                                        <Gift className="w-3.5 h-3.5 text-muted-foreground" />
                                        Kadife Hediye Kutusu & Kart
                                      </label>
                                      {item.giftWrap && (
                                        <input
                                          type="text"
                                          maxLength={140}
                                          value={item.giftNote}
                                          onChange={(e) =>
                                            updateItemMutation.mutate({
                                              id: item.id,
                                              patch: { giftNote: e.target.value },
                                            })
                                          }
                                          placeholder="Hediye kartı notunuz..."
                                          className="w-full h-9 px-2.5 rounded-[4px] border border-input bg-white text-xs text-foreground focus:outline-none focus:border-ring"
                                        />
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                              )}
                            </article>
                          );
                        })}
                      </div>

                      {/* Single Compact Trust & Expandable Shipping Strip */}
                      <div className="pt-3 border-t border-border space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                          <div className="flex items-center gap-2 min-w-0">
                            <ShieldCheck className="w-4 h-4 text-muted-foreground shrink-0" />
                            <span>
                              %100 Sigortalı Kargo · Orijinal Sertifika · Ömür Boyu Bakım
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setShippingInfoOpen((prev) => !prev)}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground cursor-pointer whitespace-nowrap"
                          >
                            <Info className="w-3.5 h-3.5" />
                            Teslimat bilgisi
                            {shippingInfoOpen ? (
                              <ChevronUp className="w-3 h-3" />
                            ) : (
                              <ChevronDown className="w-3 h-3" />
                            )}
                          </button>
                        </div>

                        {shippingInfoOpen && (
                          <div className="rounded-[4px] bg-card border border-border p-3 text-xs text-muted-foreground space-y-1 leading-relaxed">
                            <p>
                              Brinks / Loomis sigortalı değerli kurye ile teslim imzasına kadar
                              ürün bedelinin %100’ü sigortalıdır.
                            </p>
                            <p>
                              {formatTrNumber(FREE_SHIPPING_THRESHOLD_TRY, 0)} TL üzeri
                              siparişlerde kargo ücretsizdir. Tahmini teslimat:{' '}
                              <span className="text-foreground font-medium">
                                {items[0]?.leadTimeText}
                              </span>
                              .
                            </p>
                          </div>
                        )}

                        <div className="flex items-center justify-between pt-1">
                          <button
                            type="button"
                            onClick={() => setB2cCartOpen(false)}
                            className="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                          >
                            Alışverişe devam et
                          </button>
                          <button
                            type="button"
                            onClick={() => setClearConfirmOpen(true)}
                            className="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                          >
                            Sepeti boşalt
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* STEP 2: Delivery & Contact Details */}
                  {step === 2 && (
                    <div className="space-y-4">
                      <div>
                        <h3 className="font-serif text-lg font-normal text-foreground">
                          Teslimat ve İletişim Bilgileri
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Sigortalı kurye teslimatı yalnızca alıcının kendisine imza karşılığı
                          yapılır.
                        </p>
                      </div>

                      <div className="space-y-3.5 text-xs">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <label
                              htmlFor="b2c-customer-name"
                              className="font-medium text-foreground block"
                            >
                              Ad Soyad *
                            </label>
                            <input
                              id="b2c-customer-name"
                              type="text"
                              autoComplete="name"
                              value={customerName}
                              onChange={(e) => {
                                setCustomerName(e.target.value);
                                clearFieldError('customerName');
                              }}
                              placeholder="Teslim alacak kişi"
                              className="w-full h-10 px-3 rounded-[4px] border border-input bg-white text-sm sm:text-xs text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                            />
                            {fieldErrors.customerName && (
                              <p className="text-[11px] text-foreground">
                                {fieldErrors.customerName}
                              </p>
                            )}
                          </div>

                          <div className="space-y-1">
                            <label
                              htmlFor="b2c-customer-phone"
                              className="font-medium text-foreground block"
                            >
                              Telefon *
                            </label>
                            <input
                              id="b2c-customer-phone"
                              type="tel"
                              inputMode="tel"
                              autoComplete="tel"
                              value={customerPhone}
                              onChange={(e) => {
                                setCustomerPhone(e.target.value);
                                clearFieldError('customerPhone');
                              }}
                              placeholder="05XX XXX XX XX"
                              className="w-full h-10 px-3 rounded-[4px] border border-input bg-white text-sm sm:text-xs text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                            />
                            {fieldErrors.customerPhone && (
                              <p className="text-[11px] text-foreground">
                                {fieldErrors.customerPhone}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <label
                              htmlFor="b2c-customer-email"
                              className="font-medium text-foreground block"
                            >
                              E-posta *
                            </label>
                            <input
                              id="b2c-customer-email"
                              type="email"
                              inputMode="email"
                              autoComplete="email"
                              value={customerEmail}
                              onChange={(e) => {
                                setCustomerEmail(e.target.value);
                                clearFieldError('customerEmail');
                              }}
                              placeholder="ornek@eposta.com"
                              className="w-full h-10 px-3 rounded-[4px] border border-input bg-white text-sm sm:text-xs text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                            />
                            {fieldErrors.customerEmail && (
                              <p className="text-[11px] text-foreground">
                                {fieldErrors.customerEmail}
                              </p>
                            )}
                          </div>

                          <div className="space-y-1">
                            <label
                              htmlFor="b2c-shipping-city"
                              className="font-medium text-foreground block"
                            >
                              İl *
                            </label>
                            <input
                              id="b2c-shipping-city"
                              type="text"
                              autoComplete="address-level1"
                              value={shippingCity}
                              onChange={(e) => {
                                setShippingCity(e.target.value);
                                clearFieldError('shippingCity');
                              }}
                              placeholder="Örn: İstanbul"
                              className="w-full h-10 px-3 rounded-[4px] border border-input bg-white text-sm sm:text-xs text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                            />
                            {fieldErrors.shippingCity && (
                              <p className="text-[11px] text-foreground">
                                {fieldErrors.shippingCity}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="space-y-1">
                          <label
                            htmlFor="b2c-shipping-address"
                            className="font-medium text-foreground block"
                          >
                            Açık Teslimat Adresi *
                          </label>
                          <textarea
                            id="b2c-shipping-address"
                            rows={2}
                            autoComplete="street-address"
                            value={shippingAddress}
                            onChange={(e) => {
                              setShippingAddress(e.target.value);
                              clearFieldError('shippingAddress');
                            }}
                            placeholder="Mahalle, cadde/sokak, bina ve daire no"
                            className="w-full px-3 py-2 rounded-[4px] border border-input bg-white text-sm sm:text-xs text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25 resize-none"
                          />
                          {fieldErrors.shippingAddress && (
                            <p className="text-[11px] text-foreground">
                              {fieldErrors.shippingAddress}
                            </p>
                          )}
                        </div>

                        {/* TC Kimlik No — required for Turkish citizens */}
                        <div className="pt-2 border-t border-border/75 space-y-2">
                          {isTurkishCitizen ? (
                            <div className="max-w-xs space-y-1">
                              <label
                                htmlFor="b2c-identity-number"
                                className="font-medium text-foreground block"
                              >
                                TC Kimlik No *
                              </label>
                              <input
                                id="b2c-identity-number"
                                type="text"
                                inputMode="numeric"
                                autoComplete="off"
                                maxLength={11}
                                value={identityNumber}
                                onChange={(e) => {
                                  setIdentityNumber(e.target.value.replace(/\D/g, '').slice(0, 11));
                                  clearFieldError('identityNumber');
                                }}
                                placeholder="11 haneli TC Kimlik No"
                                aria-required="true"
                                className="w-full h-10 px-3 rounded-[4px] border border-input bg-white text-sm sm:text-xs font-mono text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                              />
                              {fieldErrors.identityNumber && (
                                <p className="text-[11px] text-foreground">
                                  {fieldErrors.identityNumber}
                                </p>
                              )}
                              <p className="text-[11px] text-muted-foreground">
                                Fatura ve sigortalı teslimat için zorunludur.
                              </p>
                            </div>
                          ) : null}

                          <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                            <input
                              type="checkbox"
                              checked={!isTurkishCitizen}
                              onChange={(e) => {
                                const foreign = e.target.checked;
                                setIsTurkishCitizen(!foreign);
                                if (foreign) {
                                  setIdentityNumber('');
                                  clearFieldError('identityNumber');
                                }
                              }}
                              className="rounded border-input accent-foreground"
                            />
                            Türk vatandaşı değilim
                          </label>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* STEP 3: Payment Method & Final Confirmation */}
                  {step === 3 && (
                    <div className="space-y-5">
                      {/* Compact Delivery Review Bar */}
                      <div className="flex items-start justify-between gap-3 pb-3.5 border-b border-border text-xs">
                        <div className="space-y-0.5 min-w-0">
                          <div className="text-[11px] text-muted-foreground">Teslimat Bilgileri</div>
                          <div className="font-medium text-foreground">
                            {customerName} · {customerPhone}
                          </div>
                          <div className="text-muted-foreground truncate">
                            {shippingAddress}, {shippingCity}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setStep(2)}
                          className="text-xs font-medium text-muted-foreground hover:text-foreground underline underline-offset-2 shrink-0 cursor-pointer"
                        >
                          Düzenle
                        </button>
                      </div>

                      {/* Payment Method Selection */}
                      <div className="space-y-2.5">
                        <h3 className="font-serif text-lg font-normal text-foreground">
                          Ödeme Yöntemi
                        </h3>
                        <div
                          className={`grid grid-cols-1 ${iyzicoEnabled ? 'sm:grid-cols-2' : ''} gap-3 text-xs`}
                        >
                          {iyzicoEnabled && (
                            <button
                              type="button"
                              onClick={() => setPaymentMethod('CREDIT_CARD')}
                              className={`min-h-11 p-3.5 rounded-[6px] border text-left transition-colors cursor-pointer ${
                                paymentMethod === 'CREDIT_CARD'
                                  ? 'border-foreground bg-card ring-1 ring-ring/40'
                                  : 'border-border bg-white hover:border-ring'
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-2 font-semibold text-foreground">
                                  <CreditCard className="w-4 h-4 text-muted-foreground" />
                                  Kredi Kartı (iyzico)
                                </span>
                                <span
                                  className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                    paymentMethod === 'CREDIT_CARD'
                                      ? 'border-foreground bg-primary text-primary-foreground'
                                      : 'border-input'
                                  }`}
                                >
                                  {paymentMethod === 'CREDIT_CARD' && (
                                    <Check className="w-2.5 h-2.5" />
                                  )}
                                </span>
                              </div>
                              <p className="text-[11px] text-muted-foreground mt-1.5">
                                iyzico Checkout Form · 3D Secure
                              </p>
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => setPaymentMethod('BANK_TRANSFER')}
                            className={`min-h-11 p-3.5 rounded-[6px] border text-left transition-colors cursor-pointer ${
                              paymentMethod === 'BANK_TRANSFER'
                                ? 'border-foreground bg-card ring-1 ring-ring/40'
                                : 'border-border bg-white hover:border-ring'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="inline-flex items-center gap-2 font-semibold text-foreground">
                                <Landmark className="w-4 h-4 text-muted-foreground" />
                                Havale / EFT
                              </span>
                              <span
                                className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                  paymentMethod === 'BANK_TRANSFER'
                                    ? 'border-foreground bg-primary text-primary-foreground'
                                    : 'border-input'
                                }`}
                              >
                                {paymentMethod === 'BANK_TRANSFER' && (
                                  <Check className="w-2.5 h-2.5" />
                                )}
                              </span>
                            </div>
                            <p className="text-[11px] text-success font-medium mt-1.5">
                              Ek %{BANK_TRANSFER_DISCOUNT_PCT} nakit indirimi uygulanır
                            </p>
                          </button>
                        </div>
                      </div>

                      {paymentMethod === 'CREDIT_CARD' && iyzicoEnabled && (
                        <div className="rounded-[6px] border border-border bg-card p-3.5 space-y-3 text-xs">
                          <div className="font-medium text-foreground">Taksit Sorgula (BIN)</div>
                          <p className="text-[11px] text-muted-foreground">
                            Kartınızın ilk 6–8 hanesini girin; iyzico kart ailesi ve taksit
                            seçeneklerini gösterir. Asıl taksit seçimi 3D Secure sayfasında
                            tamamlanır.
                          </p>
                          <div className="flex flex-wrap gap-2 items-end">
                            <div className="space-y-1 flex-1 min-w-[140px]">
                              <label className="text-[11px] text-muted-foreground">Kart BIN</label>
                              <input
                                className="w-full h-9 rounded-[4px] border border-border bg-white px-2.5 font-mono text-sm"
                                inputMode="numeric"
                                maxLength={8}
                                value={binInput}
                                onChange={(e) =>
                                  setBinInput(e.target.value.replace(/\D/g, '').slice(0, 8))
                                }
                                placeholder="454360"
                              />
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              className="h-9"
                              onClick={() => {
                                void (async () => {
                                  try {
                                    const res = await apiFetch<{
                                      cardFamily?: string;
                                      options?: Array<{
                                        installmentCount: number;
                                        monthlyAmount: string | null;
                                        totalAmount: string | null;
                                      }>;
                                    }>('/api/v1/storefront/payments/installments', {
                                      method: 'POST',
                                      body: {
                                        binNumber: binInput,
                                        price: totals.grandTotalTry,
                                      },
                                    });
                                    setCardFamily(res.data?.cardFamily || '');
                                    setInstallmentOptions(res.data?.options ?? []);
                                    setSelectedInstallment(1);
                                  } catch (err) {
                                    setSubmitError(
                                      err instanceof Error
                                        ? err.message
                                        : 'Taksit bilgisi alınamadı'
                                    );
                                  }
                                })();
                              }}
                              disabled={binInput.length < 6}
                            >
                              Sorgula
                            </Button>
                          </div>
                          {cardFamily ? (
                            <div className="text-[11px] text-muted-foreground">
                              Kart ailesi: <strong className="text-foreground">{cardFamily}</strong>
                            </div>
                          ) : null}
                          {installmentOptions.length > 0 && (
                            <div className="space-y-1.5">
                              {installmentOptions.map((opt) => (
                                <label
                                  key={opt.installmentCount}
                                  className={`min-h-11 flex items-center justify-between gap-2 rounded-[4px] border px-2.5 py-2.5 cursor-pointer ${
                                    selectedInstallment === opt.installmentCount
                                      ? 'border-foreground bg-white'
                                      : 'border-border bg-white/60'
                                  }`}
                                >
                                  <span className="inline-flex items-center gap-2">
                                    <input
                                      type="radio"
                                      name="installment"
                                      checked={selectedInstallment === opt.installmentCount}
                                      onChange={() =>
                                        setSelectedInstallment(opt.installmentCount)
                                      }
                                    />
                                    {opt.installmentCount === 1
                                      ? 'Tek Çekim'
                                      : `${opt.installmentCount} Taksit`}
                                  </span>
                                  <span className="font-mono tabular-nums text-foreground">
                                    {opt.monthlyAmount
                                      ? `${opt.installmentCount}× ${opt.monthlyAmount} TL`
                                      : ''}
                                    {opt.totalAmount
                                      ? ` · Top. ${opt.totalAmount} TL`
                                      : ''}
                                  </span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Required Legal Consent for Custom/Engraved Items (Step 3 Only) */}
                      {hasCustomOrEngravedItem && (
                        <div className="rounded-md border border-border bg-muted p-3.5 space-y-2.5 text-xs text-foreground">
                          <div className="flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                            <p className="leading-relaxed">
                              Sepetinizde kişiye özel üretim veya lazer yazılı ürün bulunuyor.
                              Mesafeli Satışlar Yönetmeliği m.15/b gereği kişiye özel ürünlerde
                              cayma hakkı geçerli değildir.
                            </p>
                          </div>
                          <label className="flex items-start gap-2.5 font-medium cursor-pointer text-foreground">
                            <input
                              type="checkbox"
                              checked={acceptedCustomPolicy}
                              onChange={(e) => {
                                setAcceptedCustomPolicy(e.target.checked);
                                clearFieldError('acceptedCustomPolicy');
                              }}
                              className="mt-0.5 rounded border-ring accent-foreground"
                            />
                            <span>Kişiye özel üretim ve gravür iade koşulunu onaylıyorum.</span>
                          </label>
                          {fieldErrors.acceptedCustomPolicy && (
                            <p className="text-[11px] text-foreground font-medium">
                              {fieldErrors.acceptedCustomPolicy}
                            </p>
                          )}
                        </div>
                      )}

                      {!authenticated && (
                        <div className="rounded-md border border-[#E9DCCB] bg-[#F8F5EF] p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div className="space-y-0.5">
                            <p className="text-xs font-semibold text-[#252321]">
                              Siparişi tamamlamak için üye girişi gerekiyor
                            </p>
                            <p className="text-[11px] text-[#252321]/75 leading-relaxed">
                              Sepetinizdeki ürünler korunur; giriş yaptıktan sonra ödeme adımına devam edebilirsiniz.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={handleGoToLoginFromCheckout}
                            className="shrink-0 h-9 px-4 rounded-[6px] bg-[#242321] text-white text-xs font-medium hover:bg-[#393530] transition-colors cursor-pointer whitespace-nowrap"
                          >
                            Giriş Yap / Üye Ol
                          </button>
                        </div>
                      )}

                      {submitError && (
                        <div className="rounded-[4px] border border-foreground bg-primary/[0.06] px-3 py-2.5 text-xs text-foreground font-medium flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <span>{submitError}</span>
                          {!authenticated && (
                            <button
                              type="button"
                              onClick={handleGoToLoginFromCheckout}
                              className="shrink-0 h-8 px-3 rounded-[6px] bg-[#242321] text-white text-[11px] font-medium hover:bg-[#393530] transition-colors cursor-pointer whitespace-nowrap"
                            >
                              Giriş Sayfasına Git
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Desktop & Tablet Order Summary Panel (Hidden on Mobile — Mobile uses Sticky Bottom Bar) */}
                <aside className="hidden md:block lg:col-span-5 lg:sticky lg:top-0 rounded-[6px] border border-[#E9DCCB] bg-white p-5 sm:p-6 space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E9DCCB]/70 pb-3">
                    <h3 className="font-serif text-xl font-normal text-[#252321]">Sipariş Özeti</h3>
                    <span className="text-xs text-[#252321]/65">{totalQty} ürün</span>
                  </div>

                  {/* Mini item preview on Steps 2 & 3 */}
                  {step > 1 && (
                    <div className="pb-3 border-b border-[#E9DCCB]/70 space-y-1.5 text-xs">
                      {items.map((item) => (
                        <div key={item.id} className="flex items-baseline justify-between gap-2">
                          <span className="text-[#252321]/75 truncate">
                            {item.qty}× {item.title}
                          </span>
                          <span className="font-sans font-medium tabular-nums text-[#252321] shrink-0">
                            {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {renderSummaryLines()}

                  <div className="space-y-2 pt-1">
                    <Button
                      type="button"
                      className="w-full h-11 text-sm font-medium rounded-[4px] bg-[#252321] text-white hover:bg-[#252321]/90"
                      disabled={checkoutPending || (step === 3 && lockExpired)}
                      onClick={handlePrimaryAction}
                    >
                      <span>{primaryCtaLabel}</span>
                      {step < 3 && <ArrowRight className="w-4 h-4 ml-1.5" />}
                    </Button>

                    {step > 1 && (
                      <button
                        type="button"
                        onClick={() => handleStepNavigation((step - 1) as CheckoutStep)}
                        className="w-full h-9 inline-flex items-center justify-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        {step === 2 ? 'Sepete Dön' : 'Teslimat Bilgilerine Dön'}
                      </button>
                    )}
                  </div>
                </aside>
              </div>
            )}
          </div>

          {/* Mobile Sticky Bottom Checkout Bar (< 768px Only) */}
          {isCheckoutFlow && (
            <div className="md:hidden shrink-0 border-t border-[#E9DCCB] bg-white px-3 min-[360px]:px-4 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))] space-y-2.5">
              {/* Collapsible Order Summary Accordion */}
              {mobileSummaryOpen && (
                <div className="pb-2.5 border-b border-[#E9DCCB]">{renderSummaryLines()}</div>
              )}

              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setMobileSummaryOpen((prev) => !prev)}
                  className="inline-flex items-center gap-1 text-left cursor-pointer py-0.5 min-w-0"
                >
                  <div className="min-w-0">
                    <div className="text-[11px] text-muted-foreground flex items-center gap-1 whitespace-nowrap">
                      <span>Ödenecek Toplam</span>
                      {mobileSummaryOpen ? (
                        <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      ) : (
                        <ChevronUp className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      )}
                    </div>
                    <div className="font-mono text-sm min-[360px]:text-base font-semibold text-foreground tabular-nums whitespace-nowrap">
                      {formatTrNumber(totals.grandTotalTry, 2)} TL
                    </div>
                  </div>
                </button>

                <Button
                  type="button"
                  className="min-h-[44px] px-3 min-[360px]:px-4 text-xs min-[360px]:text-sm font-medium rounded-[4px] bg-[#252321] text-white hover:bg-[#252321]/90 shrink-0"
                  disabled={checkoutPending || (step === 3 && lockExpired)}
                  onClick={handlePrimaryAction}
                >
                  <span className="whitespace-nowrap">
                    {step === 1
                      ? 'Teslimata Geç'
                      : step === 2
                        ? 'Ödemeye Geç'
                        : checkoutPending
                          ? paymentMethod === 'CREDIT_CARD'
                            ? 'Yönlendiriliyor...'
                            : 'Onaylanıyor...'
                          : 'Siparişi Onayla'}
                  </span>
                  {step < 3 && <ArrowRight className="w-4 h-4 ml-1 shrink-0" />}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={clearConfirmOpen}
        onOpenChange={setClearConfirmOpen}
        variant="destructive"
        isLoading={clearCartMutation.isPending}
        title="Sepeti boşalt"
        description="Sepetinizdeki tüm ürünler, gravür yazıları ve hediye notları silinecek."
        confirmLabel="Sepeti Boşalt"
        cancelLabel="Vazgeç"
        onConfirm={async () => {
          await clearCartMutation.mutateAsync();
          setClearConfirmOpen(false);
          setStep(1);
        }}
      />
    </>
  );
}
