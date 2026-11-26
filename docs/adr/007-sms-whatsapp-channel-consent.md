# ADR-007: SMS / WhatsApp recovery + kanal bazlı ticari izin

**Durum:** Kabul edildi (Faz D)  
**Tarih:** 2026-11-26

## Bağlam

Abandoned-cart e-posta kapısı (ADR-006) SMS ve WhatsApp için genişletilmelidir. Gerçek Netgsm/Meta API sonraya bırakılabilir; consent gate ve audit şimdi gerekir.

## Karar

- Provider: `console` (varsayılan) veya `webhook` URL.
- Enable: `MESSAGING_SMS_ENABLED` / `MESSAGING_WHATSAPP_ENABLED`.
- B2C T2 → SMS (`COMMERCIAL_SMS` + `SMS` izin + telefon).
- B2C T3 → WhatsApp (`COMMERCIAL_WHATSAPP` + `WHATSAPP` izin + telefon).
- Kanal kapalıysa Attempt yazılmaz (sonradan açılınca denenebilir).
- İzin yok / telefon yok → Attempt `SKIPPED` + reason.
- `ChannelOutboundLog` append-only audit.

## Sonuçlar

+ İYS uyumlu kanal kapısı  
+ Provider değişimi settings ile  
− Gerçek operatör API’si ayrıca bağlanır
