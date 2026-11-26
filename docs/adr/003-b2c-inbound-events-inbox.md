# ADR-003: B2C inbound tek Events inbox

**Durum:** Kabul edildi (Faz A)  
**Tarih:** 2026-11-26

## Bağlam

Müşteri, sepet, izin ve sözleşme için ayrı REST yüzeyi çoğaltmak idempotency ve retry yönetimini dağıtır.

## Karar

- Tek birincil endpoint: `POST /api/v1/integrations/b2c/events/`
- Shortcut resource endpoint’leri aynı `IntegrationEvent` inbox + processor’a düşer.
- `event_id` / `idempotency_key` unique; duplicate → 200, yan etki yok.
- Auth: API key scope `integrations:b2c:write`.

## Sonuçlar

+ Tek idempotency ve audit yüzeyi  
+ Schema version ile evrim  
− Processor routing karmaşıklığı
