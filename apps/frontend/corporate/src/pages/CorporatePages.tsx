import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  isB2bPortalEnabled,
  isB2cStorefrontEnabled,
  isOpsPortalEnabled,
} from '@taragold/shared/config/commercialModules';

const storefrontUrl = import.meta.env.VITE_STOREFRONT_URL ?? 'http://localhost:3000/';
const b2bUrl = import.meta.env.VITE_B2B_URL ?? 'http://localhost:3001/b2b/giris';
const opsUrl = import.meta.env.VITE_OPS_URL ?? 'http://localhost:3002/ops/giris';

export function CorporateHomePage() {
  return (
    <>
      <section className="corporate-hero text-primary-foreground px-4 sm:px-6 py-20 sm:py-28">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground mb-4 font-medium">
            TARA GOLD · TARA DIAMOND
          </p>
          <h1 className="font-serif text-4xl sm:text-5xl md:text-6xl font-semibold max-w-3xl leading-tight text-balance">
            Kuyumculuk sektörüne özel ticaret altyapısı.
          </h1>
          <p className="mt-6 max-w-2xl text-sm sm:text-base text-muted-foreground leading-relaxed">
            Zorunlu bir B2C sitesi satmıyoruz. Bayilerinize, operasyon ekiplerinize ve kendi satış
            kanallarınıza bağlanabileceğiniz merkezi ürün, fiyat, stok ve sipariş API’si sunuyoruz.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link
              to="/hizmetler"
              className="rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-foreground hover:bg-[#A88A58]"
            >
              Altyapıyı İnceleyin
            </Link>
            <Link
              to="/iletisim"
              className="rounded-md border border-ring/50 px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-white/5"
            >
              İş Ortaklığı
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 py-16 grid md:grid-cols-3 gap-8">
        {[
          {
            title: 'Merkezi Katalog',
            body: 'Ürün modelleri, varyantlar, taş/montür ve medya tek veri kaynağında yönetilir.',
          },
          {
            title: 'Fiyat & Kur Motoru',
            body: 'Reçete, kanal kuralları ve canlı kur ile B2B/B2C fiyatları tutarlı üretilir.',
          },
          {
            title: 'API Öncelikli Ticaret',
            body: 'Kendi vitrininizi, mobil uygulamanızı veya ERP entegrasyonunuzu API üzerinden bağlayın.',
          },
        ].map((card) => (
          <article key={card.title} className="border-t border-ring/50 pt-5">
            <h2 className="font-serif text-xl text-foreground">{card.title}</h2>
            <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{card.body}</p>
          </article>
        ))}
      </section>

      <section className="bg-white border-y border-border">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 grid lg:grid-cols-2 gap-10 items-start">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground font-medium mb-3">
              Platform
            </p>
            <h2 className="font-serif text-3xl text-foreground text-balance">
              Dört deneyim. Tek iş mantığı.
            </h2>
            <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
              Kurumsal site, bayi portalı, iç operasyon ve isteğe bağlı demo vitrin aynı Django API
              üzerinde çalışır. Ürün, fiyat ve stok kuralları frontend’lerde yeniden yazılmaz.
            </p>
          </div>
          <ul className="space-y-4 text-sm">
            {[
              { label: 'Kurumsal Site', hint: 'Marka, hizmetler, iş ortaklığı', href: '/hakkimizda' },
              { label: 'B2B Portal', hint: 'Bayi katalog, fiyat, sipariş', href: b2bUrl, external: true },
              { label: 'OPS', hint: 'PIM, stok, üretim, yetki', href: opsUrl, external: true },
              { label: 'Demo B2C', hint: 'Opsiyonel referans mağaza', href: storefrontUrl, external: true },
            ].map((item) =>
              item.external ? (
                <li key={item.label}>
                  <a
                    href={item.href}
                    className="flex items-baseline justify-between gap-4 border-b border-border pb-3 hover:text-foreground"
                  >
                    <span className="font-medium text-foreground">{item.label}</span>
                    <span className="text-muted-foreground">{item.hint}</span>
                  </a>
                </li>
              ) : (
                <li key={item.label}>
                  <Link
                    to={item.href}
                    className="flex items-baseline justify-between gap-4 border-b border-border pb-3 hover:text-foreground"
                  >
                    <span className="font-medium text-foreground">{item.label}</span>
                    <span className="text-muted-foreground">{item.hint}</span>
                  </Link>
                </li>
              )
            )}
          </ul>
        </div>
      </section>
    </>
  );
}

export function AboutPage() {
  return (
    <PageShell title="Hakkımızda">
      <p>
        TARA GOLD / TARA DIAMOND; kuyumculuk ve mücevher operasyonları için merkezi ticaret
        altyapısı geliştirir. Amacımız perakende sitesi satmak değil; ürün, katalog, fiyatlandırma,
        stok ve sipariş süreçlerini güvenilir bir API katmanında birleştirmektir.
      </p>
      <p>
        Atölye disiplini ile yazılım mühendisliğini aynı standartta tutuyoruz: ölçülebilir fiyat,
        izlenebilir stok, rol bazlı yetki ve kanal bağımsız entegrasyon.
      </p>
      <h2 className="font-serif text-2xl text-foreground !mt-10">Vizyon</h2>
      <p>
        Sektördeki her markanın kendi vitrinini ve satış kanalını özgürce kurabildiği; ancak arka
        planda tutarlı, denetlenebilir ve ölçeklenebilir bir ticaret omurgasına bağlandığı bir
        ekosistem.
      </p>
    </PageShell>
  );
}

export function ServicesPage() {
  return (
    <PageShell title="Hizmetler & Teknoloji">
      <ul className="space-y-5 list-none pl-0">
        {[
          {
            t: 'Ürün & Varyant PIM',
            d: 'Model, SKU matrisi, taş/montür satırları ve medya yönetimi.',
          },
          {
            t: 'Fiyat Motoru',
            d: 'Maliyet reçeteleri, kanal marjları, kur snapshot’ları ve teklif kilidi.',
          },
          {
            t: 'B2B Ticaret',
            d: 'Bayiye özel katalog, sipariş fişi, sipariş geçmişi ve cari görünüm.',
          },
          {
            t: 'OPS Operasyon',
            d: 'Stok/depo, üretim kuyruğu, firma/yetki ve sipariş yönetimi.',
          },
          {
            t: 'Storefront API',
            d: 'Harici B2C sistemler için `/api/v1/storefront` sözleşmesi (demo vitrin opsiyonel).',
          },
        ].map((item) => (
          <li key={item.t} className="border-b border-border pb-4">
            <div className="font-medium text-foreground">{item.t}</div>
            <p className="mt-1 text-muted-foreground">{item.d}</p>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}

export function ContactPage() {
  return (
    <PageShell title="İletişim & İş Ortaklığı">
      <p>
        Kurumsal iş birliği, API entegrasyonu ve bayi ağı için{' '}
        <a href="mailto:info@taradiamond.com" className="text-foreground underline decoration-ring">
          info@taradiamond.com
        </a>
      </p>
      <div className="mt-8 grid sm:grid-cols-2 gap-3">
        {isB2bPortalEnabled() ? (
          <a
            href={b2bUrl}
            className="rounded-md bg-primary text-primary-foreground px-4 py-3 text-sm font-semibold text-center hover:bg-primary"
          >
            Bayi Portalı Girişi
          </a>
        ) : null}
        {isOpsPortalEnabled() ? (
          <a
            href={opsUrl}
            className="rounded-md border border-border bg-white px-4 py-3 text-sm font-semibold text-foreground text-center hover:border-ring"
          >
            OPS Girişi
          </a>
        ) : null}
      </div>
      {isB2cStorefrontEnabled() ? (
        <p className="mt-6 text-sm text-muted-foreground">
          Demo vitrin: <a href={storefrontUrl} className="underline">{storefrontUrl}</a>
        </p>
      ) : null}
    </PageShell>
  );
}

function PageShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-16">
      <h1 className="font-serif text-3xl sm:text-4xl text-foreground mb-6">{title}</h1>
      <div className="text-sm sm:text-base text-muted-foreground leading-relaxed space-y-4">{children}</div>
    </div>
  );
}
