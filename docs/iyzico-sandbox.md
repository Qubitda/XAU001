# iyzico Checkout Form (B2C) — Sandbox

## Paket

```bash
cd apps/backend
.venv\Scripts\python.exe -m pip install "iyzipay>=1.0.45,<2.0"
```

`requirements.txt` içinde pin’lidir.

## Opsiyonel ticari modül

iyzico sabit değil; satın alan kurulumlarda açılır:

```
ENABLE_IYZICO_PAYMENTS=1          # backend: apps.payments + route’lar
VITE_ENABLE_IYZICO_PAYMENTS=true  # storefront: kredi kartı seçeneği
```

`ENABLE_IYZICO_PAYMENTS=0` → `apps.payments` INSTALLED_APPS’ten çıkar, initialize/callback URL’leri yüklenmez; FE yalnızca havale gösterir.

“İndirilebilir app” modeli: kod monorepoda `apps/payments` olarak durur; müşteri satın alınca deployment’ta iki flag açılır + sandbox/live anahtarlar eklenir. Ayrı PyPI paketi şart değil — ticari modül bayrağı yeterli.

## Ortam değişkenleri

Root `.env` (veya `.env.example`):

```
ENABLE_IYZICO_PAYMENTS=1
VITE_ENABLE_IYZICO_PAYMENTS=true
IYZICO_API_KEY=sandbox-...
IYZICO_SECRET_KEY=sandbox-...
IYZICO_BASE_URL=sandbox-api.iyzipay.com
IYZICO_CALLBACK_BASE_URL=https://<ngrok-host>
FRONTEND_STOREFRONT_URL=http://localhost:3000
```

Canlıya geçiş: merchant panel canlı anahtarları + `IYZICO_BASE_URL=api.iyzipay.com` + production callback HTTPS origin.

`DJANGO_ALLOWED_HOSTS` içine ngrok host’unu ekleyin (ör. `abc123.ngrok-free.app`).

## Akış

1. Storefront sepet → **Kredi Kartı** → `POST /api/v1/storefront/payments/checkout-form/initialize`
2. FE `paymentPageUrl` adresine yönlendirir
3. iyzico `POST /api/v1/payments/iyzico/callback` (`token`)
4. Django `CheckoutForm.retrieve` → sipariş `ODEME_BEKLIYOR` → `ONAYLANDI` / `ATOLYE_URETIMDE` veya `IPTAL_EDILDI`
5. Tarayıcı `/odeme-basarili` veya `/odeme-hatali`

Havale (`BANK_TRANSFER`) hâlâ `POST /api/v1/storefront/orders` kullanır (iyzico yok).

## Lokal callback (ngrok)

```bash
ngrok http 8000
```

`.env`:

```
IYZICO_CALLBACK_BASE_URL=https://YOUR_ID.ngrok-free.app
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,YOUR_ID.ngrok-free.app
```

Django’yu yeniden başlatın. Callback URL initialize sırasında:
`{IYZICO_CALLBACK_BASE_URL}/api/v1/payments/iyzico/callback`

Webhook (opsiyonel, merchant panel):  
`{IYZICO_CALLBACK_BASE_URL}/api/v1/payments/iyzico/webhook`

## Sandbox test kartı

iyzico sandbox panelindeki güncel kart listesini kullanın. Tipik örnek:

| Alan | Değer |
|------|--------|
| Kart no | `5528790000000008` (veya paneldeki başarılı test kartı) |
| SKT | gelecek ay/yıl (ör. `12/30`) |
| CVC | `123` |
| 3DS | sandbox panelinde belirtilen şifre |

Başarısız senaryolar için paneldeki “failure” kart numaralarını kullanın.

## Test

```bash
cd apps/backend
# SQLite (lokal):
set DJANGO_TESTING=1
set DJANGO_DEBUG=1
set DJANGO_SECRET_KEY=dev
# DATABASE_URL / POSTGRES_HOST temiz
.venv\Scripts\python.exe manage.py test apps.payments.tests.test_iyzico_checkout -v2
```
