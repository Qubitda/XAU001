# İşlemsel E-posta Altyapısı (`apps.mail`)

Merkezi, multi-tenant, event-driven mail katmanı. B2C platform SMTP + B2B org SMTP (fallback platform), şablon DB override + filesystem varsayılan, Celery kuyruk + `mail_logs`.

## Şema

| Tablo | Rol |
|-------|-----|
| `mail_smtp_settings` | `organization` null = platform; password AES-256-GCM |
| `mail_email_templates` | tenant override; `template_key` |
| `mail_mail_logs` | QUEUED / SENT / FAILED |

## Akış

1. Domain TX commit (ör. iyzico `finalize_b2c_order_after_payment`)
2. `emit_payment_success` / `emit_welcome` → `MailLog(QUEUED)` + `transaction.on_commit`
3. Celery `mail.send_transactional_email` (broker yoksa sync fallback)
4. `MailService`: org SMTP → platform SMTP → Django `EMAIL_*`; org template → platform DB → `templates/mail/contents/{key}.html` + `base_layout.html`

## API

- `GET/POST /api/v1/ops/mail/smtp-settings` (`mail:manage`)
- `GET/POST /api/v1/ops/mail/templates`
- `GET /api/v1/ops/mail/logs`

## Env

```
MAIL_ENCRYPTION_KEY=...          # yoksa SECRET_KEY
MAIL_DEFAULT_LOGO_URL=
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend   # lokal
# Prod: SMTP veya SmtpSetting satırı (Gmail App Password / M365 587 TLS / cPanel 465 SSL)
```

## Şablon anahtarları

`welcome`, `payment_success`, `order_created`, `password_reset`, `email_verification`

Değişkenler: `{{ customer_name }}`, `{{ order_no }}`, `{{ amount }}`, `{{ currency }}`, `{{ date }}`, `{{ verify_url }}`, `{{ reset_url }}`, `{{ order_url }}`
