# ADR-005: IP minimizasyonu

**Durum:** Kabul edildi (Faz A)  
**Tarih:** 2026-11-26

## Bağlam

KVKK veri minimizasyonu: ham IP uzun süre saklanmamalı.

## Karar

- ConsentLog / ContractAcceptance üzerinde `ip_hash` (SHA-256 + server pepper) saklanır.
- Ham IP yalnızca kısa ömürlü request log’larında (varsa); kalıcı legal kayıtlarda hash.
- `user_agent_hash` aynı şekilde.

## Sonuçlar

+ Minimizasyon  
− Adli IP geri çözümü mümkün değil (bilinçli trade-off)
