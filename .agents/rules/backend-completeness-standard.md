---
trigger: always_on
description: Tüm Django uygulamaları için 4 katmanlı (Model, Service, API, Admin) + Frontend/OpenAPI/Test tamlık standardı.
---

# GLOBAL BACKEND COMPLETENESS STANDARD

Bu projede hiçbir backend geliştirmesi yalnızca model veya servis oluşturularak tamamlanmış sayılmaz.

Her yeni özellik için aşağıdaki dört katman birlikte değerlendirilmelidir:

1. **MODEL:** Veri modeli, ilişkiler ve migration'lar.
2. **SERVICE:** İş kuralları, transaction/idempotency ve operasyon mantığı.
3. **API:** Gerekli endpointler, serializerlar, permissionlar, tenant/blind-pool izolasyonu ve standart envelope response yapıları.
4. **ADMIN:** Django Admin yönetim ekranı (`django-admin-standard.md` kurallarına uygun) ve gerekli operasyonel kontroller.

Ek olarak:
- **Frontend entegrasyonu** ve **OpenAPI (`drf-spectacular`) dokümantasyonu** değerlendirilmelidir.
- Her yeni model, servis veya iş akışı geliştirildiğinde:
  - Gerekli endpointlerin mevcut olup olmadığını kontrol et.
  - Gerekli Admin ekranının mevcut olup olmadığını kontrol et.
  - Yetkilendirme ve tenant izolasyonunu doğrula (`B2C` / `B2B` / `OPS`).
  - Frontend'in ihtiyacı olan veri ve işlemleri karşıla.
  - OpenAPI şemasını güncelle (`@extend_schema` / serializer tanımları).
  - İlgili testleri oluştur veya güncelle ve `manage.py check` + testleri çalıştır.

Geliştirme tamamlanırken eksik kalan Admin, API, frontend entegrasyonu ve dokümantasyon maddeleri açıkça raporlanmalıdır. Sadece kodun yazılmış olması, özelliğin tamamlandığı anlamına gelmez.
