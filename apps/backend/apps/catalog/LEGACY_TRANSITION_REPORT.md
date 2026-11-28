# Catalog Legacy Detail Columns — Dual-Write & Transition Report

## 1. `_DEPRECATED_DETAIL_HELP` ile İşaretli Legacy `ProductModel` Alanları

`apps/catalog/models.py` içinde `[DEPRECATED - use *Detail / ProductVariant]` notuyla işaretlenmiş 24 alan:

| Grup | Legacy Alan | Normalize Hedef Tablo / Alan |
| :--- | :--- | :--- |
| Maden & Ağırlık | `metal_name` | `FinishedDetail.metal_name` / `MountingDetail.metal_name` / `ProductVariant` |
| Maden & Ağırlık | `purity_code` | `FinishedDetail.purity_code` / `MountingDetail.purity_code` / `ProductVariant.purity_code` |
| Maden & Ağırlık | `metal_color` | `FinishedDetail.metal_color` / `MountingDetail.metal_color` / `ProductVariant.metal_color` |
| Maden & Ağırlık | `gross_weight_gram` | `FinishedDetail.base_weight_gr` / `MountingDetail.net_weight_gr` / `ProductVariant.gross_weight_gram` |
| Maden & Ağırlık | `fire_rate_pct` | `FinishedDetail.fire_rate_pct` |
| Montür | `mount_structure` | `MountingDetail.mount_structure` |
| Montür | `allowed_carat_min` | `MountingDetail.min_carat` |
| Montür | `allowed_carat_max` | `MountingDetail.max_carat` |
| Montür | `head_code` | `MountingDetail.head_code` |
| Montür | `band_code` | `MountingDetail.band_code` |
| Montür | `head_weight_gram` | `MountingDetail.head_weight_gram` |
| Montür | `band_weight_gram` | `MountingDetail.band_weight_gram` |
| Taş & Sertifika | `stone_type` | `LooseStoneDetail.stone_category` / `StoneLine.stone_type` |
| Taş & Sertifika | `stone_measure_unit` | `StoneLine.measure_unit` |
| Taş & Sertifika | `stone_clarity` | `LooseStoneDetail.clarity` / `StoneLine.clarity` |
| Taş & Sertifika | `stone_color_grade` | `LooseStoneDetail.color` / `StoneLine.color_grade` |
| Taş & Sertifika | `stone_cut_grade` | `LooseStoneDetail.cut_grade` |
| Taş & Sertifika | `stone_cut_shape` | `LooseStoneDetail.shape` / `StoneLine.cut_shape` |
| Taş & Sertifika | `stone_origin` | (Yalnızca ProductModel header; detail tablosunda yok) |
| Taş & Sertifika | `setting_type` | `MountingDetail.setting_type_code` |
| Taş & Sertifika | `certificate_agency` | `LooseStoneDetail.cert_lab` |
| Taş & Sertifika | `certificate_number` | `LooseStoneDetail.cert_number` |

*(Not: `available_colors` ve `product_type` da legacy/dual-write alanlardır.)*

---

## 2. `dual_write_product_details` ve `mirror_detail_to_legacy` Bağımlılık Haritası

- **`dual_write_product_details(product, overrides)`**:
  - `apps/catalog/api/ops_products.py` → `OpsProductListCreateView.post` (ürün oluşturma)
  - `apps/catalog/api/ops_products.py` → `OpsProductDetailView.patch` (ürün güncelleme)
  - `apps/catalog/admin.py` → `ProductModelAdmin.save_model` (Django Admin kaydı)
  - `apps/catalog/management/commands/backfill_product_details.py` → `Command.handle` (mevcut satırları backfill etme)
- **`mirror_detail_to_legacy(product)`**:
  - `apps/catalog/product_details.py` içinde tanımlı; aktif üretim kod yolunda doğrudan çağrılmamaktadır (geriye dönük yardımcı).

---

## 3. Eksik `*Detail` Satırı Tespit Raporu (`cleanup_legacy_product_columns`)

`python manage.py cleanup_legacy_product_columns` komutu tüm `ProductModel` satırlarını `select_related("finished_detail", "mounting_detail", "loose_stone_detail")` ile tarar; `product_kind` değerine karşılık gelen `*Detail` satırı olmayan kayıtları `<parent_sku>:<detail_attr>` formatında raporlar (`CATALOG_VERIFY_LEGACY_COLUMNS=1` ile `CommandError` fırlatır).

---

## 4. Artık Yalnızca Yazma / Fallback Amaçlı Kalan ("Safe to Drop" Adayı) Alanlar

Okuma call site'ları (`catalog/api/serializers.py`, `catalog/api/common.py`, `catalog/services.py`) `*Detail` tablolarını birincil kaynak yapacak şekilde güncellendikten sonra, `PRICING_READ_FROM_DETAILS=1` ve `CATALOG_DUAL_WRITE_DETAILS=1` ortamlarında aşağıdaki alanlar okuma yolundan tamamen bağımsızdır (yalnızca `pricing` legacy fallback `PRICING_READ_FROM_DETAILS=0` iken `gross_weight_gram` / `fire_rate_pct` / `purity_code` kullanır):

- `head_code`, `band_code`, `head_weight_gram`, `band_weight_gram`, `mount_structure`, `allowed_carat_min`, `allowed_carat_max` (tamamen `MountingDetail` ve `_serialize_mount` üzerinden okunuyor)
- `stone_clarity`, `stone_color_grade`, `stone_cut_grade`, `stone_cut_shape`, `certificate_agency`, `certificate_number` (`LooseStoneDetail` + `StoneLine` üzerinden okunuyor; `FINISHED` ürünlerde header fallback olarak tutulur)

### Uygulanmamış Migration Taslağı (`SeparateDatabaseAndState` — İki Aşamalı Güvenli Drop)

```python
# NOT APPLIED — Run only after PRICING_READ_FROM_DETAILS=1 and cleanup_legacy_product_columns passes in production.
from django.db import migrations

SAFE_TO_DROP_MOUNT_FIELDS = [
    "mount_structure",
    "allowed_carat_min",
    "allowed_carat_max",
    "head_code",
    "band_code",
    "head_weight_gram",
    "band_weight_gram",
]

class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0011_seo_warranty_and_media_roles"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="productmodel", name=f)
                for f in SAFE_TO_DROP_MOUNT_FIELDS
            ],
            database_operations=[],
        ),
    ]
```
*(İkinci aşama deploy'da `DROP COLUMN IF EXISTS ...` çalıştırılır.)*
