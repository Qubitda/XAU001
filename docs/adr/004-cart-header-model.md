# ADR-004: Cart header modeli (Faz B)

**Durum:** Kabul edildi (tasarım); uygulama Faz B  
**Tarih:** 2026-11-26

## Bağlam

Bugün `B2cCartItem` satır bazlıdır; external cart ID, checkout state ve event stream için header gerekir.

## Karar

- Faz B’de `B2cCart` + `CartEvent` eklenir; mevcut item’lar `cart` FK ile backfill edilir.
- Faz A recovery `B2cCartItem` / `CartRecoverySession` üzerinde çalışmaya devam eder.

## Sonuçlar

+ Kademeli migration riski düşük  
− Faz A’da sepet 360 UI sınırlı kalır
