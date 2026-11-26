# Tara Gold / KuyumPIM Monorepo

Merkezi Django ticaret API’si üzerinde dört bağımsız frontend deneyimi:

| Uygulama | Paket | Port | Rol |
|----------|-------|------|-----|
| Corporate | `@taragold/corporate` | 3003 | Marka / şirket tanıtımı |
| B2B | `@taragold/b2b` | 3001 | Bayi & toptan portal |
| OPS | `@taragold/ops` | 3002 | İç operasyon (PIM / fiyat / stok) |
| Storefront | `@taragold/storefront` | 3000 | Opsiyonel demo B2C |

Tek iş mantığı kaynağı: `apps/backend/` (Django 5 + DRF + PostgreSQL).

## Klasör Yapısı

```text
/
├── apps/
│   ├── frontend/           # Portal frontends + shared Vite helpers
│   │   ├── storefront/     # Demo B2C (:3000)
│   │   ├── b2b/            # Bayi portalı (:3001)
│   │   ├── ops/            # OPS konsolu (:3002)
│   │   ├── corporate/      # Marka sitesi (:3003)
│   │   ├── public/         # Ortak statik varlıklar
│   │   └── vite.shared.ts
│   └── backend/            # Django API
├── packages/
│   └── shared/             # API client, auth, features, shadcn/ui
├── infrastructure/         # Docker Compose
├── scripts/                # smoke_api.py vb.
├── docs/                   # Mimari PDF / Excel dokümanları
├── .env.example
└── README.md
```

> **Neden tek `apps/frontend` değil de altında portal klasörleri?**  
> Dört portal ayrı Vite uygulamalarıdır (farklı port, auth, tema). Clean Architecture diyagramındaki `apps/frontend/` şemsiyesi korunur; portal uygulamaları onun altında kalır. Tek bir SPA’ya birleştirmek çalışan portal izolasyonunu bozar.

## Kurulum

```bash
cp .env.example .env
# DJANGO_SECRET_KEY, POSTGRES_PASSWORD, SEED_ADMIN_PASSWORD,
# VITE_API_BASE_URL=http://localhost:8000 doldurun
# CORS_ALLOWED_ORIGINS / CSRF_TRUSTED_ORIGINS → 3000–3003

npm install
```

### Backend

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
# veya lokal:
# cd apps/backend && .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

- API: http://localhost:8000/api/v1/
- OpenAPI: http://localhost:8000/api/v1/schema/
- Docs: http://localhost:8000/api/v1/docs/

### Frontend

```bash
npm run dev              # storefront :3000
npm run dev:b2b          # :3001
npm run dev:ops          # :3002
npm run dev:corporate    # :3003
npm run build            # tüm uygulamalar
npm run typecheck
npm run openapi:generate # → packages/shared/.../openapi.generated.ts
npm run smoke            # backend ayaktayken API health/schema smoke
```

Vite `envDir` kök `.env` dosyasını okur (`apps/frontend/vite.shared.ts`).  
Çapraz uygulama linkleri: `VITE_STOREFRONT_URL`, `VITE_B2B_URL`, `VITE_OPS_URL`.

## Hesap yaşam döngüsü (API)

| Endpoint | Açıklama |
|----------|----------|
| `POST /api/v1/auth/register` | B2C self-register (`ENABLE_B2C_SELF_REGISTER`) |
| `POST /api/v1/auth/password/change` | Oturum açık parola değiştir |
| `POST /api/v1/auth/password/forgot` | Sıfırlama e-postası |
| `POST /api/v1/auth/password/reset` | Token ile sıfırla |
| `POST /api/v1/auth/email/verify` | E-posta doğrula |
| `POST /api/v1/auth/email/resend` | Doğrulama yeniden gönder |

E-posta: yerel `console` backend; prod’da SMTP / `SENTRY_DSN` opsiyonel.  
Storefront UI: `/kayit`, `/sifre-yenile`, `/sifre-sifirla`, `/e-posta-dogrula`.

```bash
# Backend + Celery (Redis 5+ gerekli; Compose redis servisi = Redis 7)
npm run backend:run
npm run celery:worker
npm run celery:beat
# Docker yoksa / Redis 3.x Windows: aynı işleri senkron çalıştır
npm run jobs:run
# tam stack:
# docker compose -f infrastructure/docker-compose.yml up
```

Celery beat: taş kilidi, fiyat kilidi, kur snapshot (`MARKET_RATES_FEED_URL`), belge KVKK soft-retention.  
Medya: Compose `media_data` volume; S3/MinIO için `AWS_STORAGE_BUCKET_NAME` (+ opsiyonel `--profile minio`).  
Yedek: `scripts/backup_postgres.sh` / `.ps1`. Health: `/health?deep=1`.

## Tasarım

- **Corporate / Storefront:** TARA GOLD / DIAMOND marka kimliği
- **B2B / OPS:** shadcn/ui, zinc grayscale, Geist + Geist Mono (marka altın/bordo yok)

## Mimari ilkeler

- Dört arayüz, tek merkezi ürün / fiyat / stok / sipariş API’si
- Frontend’ler iş kurallarını yeniden yazmaz; `@taragold/shared` üzerinden API kullanır
- Portal: session + CSRF · Harici: `Bearer tg_live_…` (`/ops/api-anahtarlari`)
- Yazmalar: `Idempotency-Key` · Eventler: `/ops/webhookler` (HMAC imza)
# XAU001
