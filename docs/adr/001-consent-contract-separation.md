# ADR-001: Consent ve Contract ayrı bounded context

**Durum:** Kabul edildi (Faz A)  
**Tarih:** 2026-11-26

## Bağlam

KVKK aydınlatma / ticari ileti izinleri ile mesafeli satış / ön bilgilendirme kabul kayıtları farklı yasal amaçlara hizmet eder. Aynı tabloda birleştirmek B2B sözleşme ve kanal genişlemesini zorlaştırır.

## Karar

- `apps.consent` — ConsentLog (append-only izin)
- `apps.contracts` — LegalDocument + ContractAcceptance
- İki domain bağımsız FK’lerle Customer / Order’a bağlanır; birbirine zorunlu bağımlılık yoktur.

## Sonuçlar

+ B2B bayi sözleşmeleri ve farklı satış kanalları aynı Contract çekirdeğini kullanabilir  
+ Ticari ileti kapısı yalnızca Consent domain’ine bakarak çalışır  
− İki app + iki migration seti bakım maliyeti
