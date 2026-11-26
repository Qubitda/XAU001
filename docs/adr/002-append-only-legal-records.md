# ADR-002: Append-only ConsentLog / ContractAcceptance

**Durum:** Kabul edildi (Faz A)  
**Tarih:** 2026-11-26

## Bağlam

İzin geri çekme ve sözleşme versiyon değişikliklerinde geçmiş kanıt korunmalıdır. Update/overwrite denetim ve İYS uyumunu zayıflatır.

## Karar

- ConsentLog ve ContractAcceptance soft-delete ve in-place update yok.
- Geri çekme = yeni `WITHDRAWN` satırı (veya `withdrawn_at` ile yeni kayıt).
- ContractAcceptance sipariş anında snapshot (version + content_hash) alır; document güncellense eski kabul değişmez.

## Sonuçlar

+ Denetlenebilir geçmiş  
+ Versiyon değişiminde kanıt bütünlüğü  
− Tablo büyür; aktif izin “son durum” sorgusu ile hesaplanır
