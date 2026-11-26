# ADR-006: Abandoned cart ileti yalnızca ticari izin ile

**Durum:** Kabul edildi (Faz A)  
**Tarih:** 2026-11-26

## Bağlam

Terk sepet e-postası ticari elektronik ileti sayılabilir. Sipariş/ödeme transactional mail’den ayrılmalıdır.

## Karar

- B2C recovery **EMAIL** kanalı: gönderimden hemen önce `COMMERCIAL_EMAIL` + `EMAIL` aktif izin zorunlu.
- İzin yoksa Attempt `SKIPPED` / `NO_CONSENT`.
- Withdraw → açık recovery session’lar suppress edilir (`CONSENT_WITHDRAWN`).
- Converted / emptied suppress kuralları korunur.
- IN_APP / OPS_TASK Faz A’da consent gate dışında (transactional / operasyonel); Faz D’de kanal bazlı genişletilir.

## Sonuçlar

+ İYS / ticari ileti uyumu için kapı  
− Consent kaydı olmayan mevcut kullanıcılar e-posta recovery almaz (bilinçli)
