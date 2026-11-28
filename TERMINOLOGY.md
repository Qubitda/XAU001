# TARA DIAMOND — Mücevher & Kuyumculuk Domain Terminolojisi (`TERMINOLOGY.md`)

Bu sözlük, `catalog`, `pricing`, `inventory` ve `commerce` modüllerinde geçen Türkçe kuyumculuk / ERP iş terimlerinin İngilizce kod karşılıklarını ve domain açıklamalarını içerir.

---

## 1. Ürün Tipleri (`product_kinds.py` / `ProductModel.ProductKind`)

| Türkçe Terim | Kod / İngilizce Karşılık | Açıklama |
| :--- | :--- | :--- |
| **Bitmiş Ürün / Kuyum** | `FINISHED` (*Finished Jewelry*) | Doğrudan satışa hazır, maden ve taşı birleştirilmiş nihai mücevher (`FinishedDetail`). |
| **Montür / Yarı Mamul** | `MOUNTING` (*Semi-Mount / Mounting*) | Üzerine sonradan taş mıhlanabilen taşsız veya yarı taşlı metal gövde (`MountingDetail`). |
| **Serbest Taş** | `LOOSE_STONE` (*Loose Gemstone / Diamond*) | Tekil sertifikalı veya karata/adede bağlı çıplak taş (`LooseStoneDetail`); maksimum stok adedi `1` ile sınırlandırılır. |
| **Tek Parça Montür** | `FULL` (*Full Mount*) | Taç ve kolun tek kalıpta birleştiği montür yapısı (`MountStructure.FULL`). |
| **İki Parça Montür** | `HEAD_BAND` (*Head + Band*) | Ayrı taç (`head`) ve kol (`band`) bileşenlerinden oluşan montür yapısı (`MountStructure.HEAD_BAND`). |

---

## 2. Maden, Ayar, Ağırlık ve Üretim Terimleri

| Türkçe Terim | Kod / İngilizce Karşılık | Açıklama |
| :--- | :--- | :--- |
| **Ayar / Ayar Kodu** | `purity_code` (*Purity / Karatage*) | Altın veya kıymetli madenin saflık derecesi (ör. `14K`, `18K`, `22K`, `24K`). |
| **Milyem** | `fineness` (*Millessimal Fineness*) | Ayar kodunun ondalık saflık katsayısı (ör. `14K` → `0.5850`, `18K` → `0.7500`). |
| **Has Altın / Has** | `fine_metal_gram` / `XAU` (*Fine Gold*) | Üründeki saf (24K eşdeğeri) altın miktarı (`net_weight × fineness`). |
| **Brüt Ağırlık** | `gross_weight_gram` (*Gross Weight*) | Ürünün taş dahil toplam ağırlığı (gram). |
| **Net Metal Ağırlığı** | `net_metal_gram` (*Net Metal Weight*) | Taş ağırlığı düşüldükten sonraki saf maden gövde ağırlığı. |
| **Fire / Fire Oranı** | `fire_rate_pct` (*Casting / Polishing Loss*) | Döküm ve cila sırasında oluşan maden kaybı yüzdesi; yalnızca OPS katmanında görünür, alıcılara gizlidir. |
| **İşçilik** | `ISCILIK` / `labor` (*Craftsmanship / Labor Cost*) | Üretim veya mıhlama emeği maliyeti (`PER_GRAM` veya `FIXED`). |
| **Taç** | `head_code` / `head_weight_gram` (*Head / Prong Crown*) | Yüzükte merkez taşı tutan üst bölüm. |
| **Kol** | `band_code` / `band_weight_gram` (*Shank / Band*) | Yüzüğün parmağı saran gövde halkası. |
| **Zincir Tipi** | `chain_type` (*Chain Style*) | Kolye veya bileklik zincir örgü tipi. |
| **Kopça / Kilit Tipi** | `clasp_type` (*Clasp Type*) | Kolye/bileklik bağlantı mekanizması (papağan, halka vb.). |

---

## 3. Taş ve Sertifika Terimleri (`StoneLine` / `LooseStoneDetail`)

| Türkçe Terim | Kod / İngilizce Karşılık | Açıklama |
| :--- | :--- | :--- |
| **Pırlanta / Değerli Taş** | `stone_type` (*Diamond / Gemstone*) | Üründe kullanılan taş türü (Pırlanta, Yakut, Zümrüt, Safir, Baget vb.). |
| **Merkez Taş** | `MERKEZ` (*Center Stone*) | Mücevherin ana odak taşı (`StoneLine.Role.MERKEZ`). |
| **Yan Taş** | `YAN` (*Side Stone*) | Merkez taşı çevreleyen yardımcı taşlar (`StoneLine.Role.YAN`). |
| **Pavé** | `PAVE` (*Pavé Setting Stones*) | Gövdeye yan yana döşenen küçük taş dizisi (`StoneLine.Role.PAVE`). |
| **Aksan Taş** | `AKSAN` (*Accent Stone*) | Tasarımı tamamlayan ikincil vurgu taşları (`StoneLine.Role.AKSAN`). |
| **Karat** | `carat` / `ct` (*Carat Weight*) | Taş ağırlık birimi (`1 ct = 0.20 gr`). |
| **Berraklık** | `clarity` (*Clarity Grade*) | Taşın iç/dış kusur derecesi (FL, IF, VVS1, VS1, SI1 vb.). |
| **Renk Derecesi** | `color_grade` (*Color Grade*) | Pırlanta renk skalası (D–Z). |
| **Kesim Kalitesi / Şekli** | `cut_grade` / `cut_shape` (*Cut Grade / Shape*) | Taşın oran kalitesi (Excellent, Very Good) ve geometrisi (Yuvarlak, Baget, Prenses, Damla vb.). |
| **Mıhlama Tipi** | `setting_type` (*Setting Style*) | Taşın montüre sabitlenme tekniği (Tırnak/Prong, Kanal, Gömme, Pavé). |
| **Sertifika Kurumu** | `certificate_agency` / `cert_lab` | Taş/ürün sertifikasyon laboratuvarı (`GIA`, `HRD`, `IGI`, `EGL`). |

---

## 4. Stok, Mülkiyet ve Ticari Model (`ProductModel` / `WarehouseStock` / `SupplierOffer`)

| Türkçe Terim | Kod / İngilizce Karşılık | Açıklama |
| :--- | :--- | :--- |
| **Öz Mal** | `OWNED` / `Öz Mal` (*Company-Owned Stock*) | Mülkiyeti tamamen şirkete ait fiziksel stok. |
| **Konsinye** | `CONSIGNMENT` / `Konsinye` (*Consignment*) | Tedarikçiden satıldıkça ödenmek üzere alınan stok. |
| **Emanet / Saklama** | `CUSTODY` (*Custody*) | Üçüncü taraf mülkiyetinde olup geçici olarak depoda tutulan stok. |
| **Siparişe Özel** | `MADE_TO_ORDER` / `Siparişe Özel` (*Made to Order*) | Stokta tutulmayıp sipariş üzerine üretilen ürün durumu. |
| **Kör Havuz** | *Blind-Pool* | B2B/B2C alıcılarına tedarikçi kimliği, maliyet, fire ve kesin depo miktarını gizleyen anonim tedarik mimarisi (`offer_ref` UUID üzerinden). |
| **Fiyat Reçetesi** | `PricingRecipe` (*Cost & Margin Recipe*) | Ürünün maden, işçilik, taş, montür ve kanal kâr/indirim kurallarını tutan versiyonlu fiyat tanımı. |
| **Varyant** | `ProductVariant` (*Sellable Variant*) | Ayar, metal rengi, ölçü ve merkez karat eksenlerinde satılabilir somut ürün konfigürasyonu. |
