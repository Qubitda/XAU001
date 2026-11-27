---
trigger: always_on
description: Proje genelindeki tüm Django uygulamaları için kalıcı Django Admin geliştirme ve güvenlik standardı.
---

# DJANGO ADMIN GELİŞTİRME STANDARDI – KALICI KURAL

Bundan sonraki bütün geliştirmelerde şu kurallar proje genelindeki tüm Django uygulamaları için geçerlidir:

1. Yeni Django modeli oluşturulduğunda Admin gereksinimi de değerlendirilmelidir.
2. Yönetilmesi gereken her yeni model için Admin ekranı (`list_display`, `list_filter`, `search_fields`, `readonly_fields`, uygun `OpsRestrictedAdminMixin` / `NoDeleteAdminMixin` / `ImmutableAdminMixin`) aynı geliştirme kapsamında oluşturulmalıdır; çıplak `admin.site.register(model)` kullanılmamalıdır.
3. Yeni `ForeignKey` ve `ManyToMany` ilişkileri için uygun `Inline`, `autocomplete_fields` veya `raw_id_fields` ile `list_select_related` değerlendirilmelidir.
4. Yeni uygulama oluşturulduğunda Admin coverage kontrolü (`UNREGISTERED == []` ve `BARE_MODELADMIN == []`) yapılmalıdır.
5. Admin ekranı olmayan modellerin nedeni dokümante edilmelidir.
6. Her geliştirme sonunda `manage.py check`, Admin kayıtları ve erişim izinleri kontrol edilmelidir.
7. Admin kodu modelin iş kurallarını bypass etmemeli, mevcut servis katmanını kullanmalıdır.
8. Hassas veriler (`password`, `token`, `secret`, `*_encrypted`, `*_ciphertext`), finansal kayıtlar ve B2B/B2C/OPS tenant izolasyonu her zaman korunmalıdır (`exclude`, `readonly_fields`, `get_queryset()`).
