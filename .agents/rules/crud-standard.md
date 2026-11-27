---
trigger: always_on
description: Tüm Django uygulamaları için kalıcı CRUD bütünlüğü, güvenlik, silme politikası ve frontend/OpenAPI uyumluluk standardı.
---

# GLOBAL DJANGO CRUD STANDARDI – KALICI KURAL

Bundan sonraki bütün Django geliştirmelerinde şu kurallar proje genelinde geçerlidir:

1. **Model → CRUD Değerlendirmesi:** Her yeni model oluşturulduğunda Create / Read (List & Detail) / Update / Delete ihtiyacı iş kurallarına göre değerlendirilmelidir. Gereksiz CRUD işlemi eklenmez; `NOT_REQUIRED` olan işlemlerin nedeni belgelenir.
2. **CREATE Standardı:** Organizasyon ve şube bilgisi istemciden körü körüne alınmaz, yetkili kullanıcı kapsamından doğrulanır. Finansal tutarlar backend'de hesaplanır; kritik işlemler `transaction.atomic()` ve gerektiğinde idempotency ile korunur.
3. **READ Standardı:** B2B / B2C / OPS izolasyonu ve blind-pool kuralları korunur. `select_related`/`prefetch_related` ile N+1 önlenir; büyük listelerde pagination, filtreleme ve arama sağlanır.
4. **UPDATE Standardı:** Yalnızca izin verilen alanlar DRF serializer ile doğrulanır; `id`, `organization`, `created_at` gibi sistem alanları korunur ve durum geçişleri servis katmanından geçer.
5. **DELETE Standardı:** Sipariş, ödeme, iade, stok hareketi, fiyat geçmişi, audit kaydı, kampanya/affiliate geçmişi ve gönderim geçmişi gibi finansal/operasyonel modellerde **hard delete yapılmaz**; arşivleme (`is_active=False`) veya iptal durum geçişi kullanılır.
6. **Yetki & Audit:** Her CRUD işlemi mevcut RBAC (`HasPortalPermission`, `IsOpsUser`, `IsB2bOrganizationMember`, `HasApiScope*`) ile korunur ve kritik değişiklikler `record_audit` ile loglanır.
7. **Tamlık Kontrolü:** Her geliştirme sonunda CRUD coverage, Django Admin (`django-admin-standard.md`), OpenAPI şeması ve `manage.py check` + testler birlikte doğrulanır.
