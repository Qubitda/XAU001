"""
Canonical seed for Tanım_Tablosu from Kuyum_Çalışma.xlsx.

Related tables (child → parent):
  alt_kategori      → kategori
  ayar_kodu         → metal_adi          (Excel M↔N↔O↔P)
  metal_rengi       → metal_adi
  yas_grubu         → koleksiyon
  tas_kesimi        → tas_tipi
  berraklik         → tas_tipi           (pırlanta 4C)
  renk_derecesi     → tas_tipi           (pırlanta 4C)
  kesim_kalitesi    → tas_tipi           (pırlanta 4C)
  tas_mensei        → tas_tipi
  mihlama_tipi      → tas_tipi
  zincir_tipi       → kategori
  kopca_tipi        → kategori

urun_tipi.meta.entersMillesimal = Excel "Milyem Hesabına Girer mi?"
ayar_kodu.meta.{ayarValue,fineness} = Excel O/P sütunları
"""

from __future__ import annotations

# Table: (code, name, description, sort_order, parent_table_code|None)
DEFINITION_TABLES: list[tuple[str, str, str, int, str | None]] = [
    (
        "urun_tipi",
        "Ürün Tipi",
        "PIM ürün formu. Kuyum/Montür/Taş. meta.entersMillesimal milyem hesabını yönetir.",
        10,
        None,
    ),
    (
        "stok_mulkiyet_tipi",
        "Stok Mülkiyet Tipi",
        "PIM ürün formu — öz mal / konsinye seçimi.",
        20,
        None,
    ),
    (
        "stok_durumu",
        "Stok Durumu",
        "PIM ürün formu — stokta / tükendi / siparişe özel.",
        30,
        None,
    ),
    (
        "koleksiyon",
        "Koleksiyon",
        "PIM ürün formu. Yaş grubu seçenekleri koleksiyona bağlıdır.",
        40,
        None,
    ),
    (
        "kategori",
        "Kategori",
        "PIM ürün formu. Alt kategori, zincir ve kopça bu kategoriye bağlıdır.",
        50,
        None,
    ),
    (
        "alt_kategori",
        "Alt Kategori",
        "PIM — kategori seçilince filtrelenir.",
        60,
        "kategori",
    ),
    (
        "metal_rengi",
        "Metal Rengi",
        "PIM / varyant — metal adına göre filtrelenir.",
        70,
        "metal_adi",
    ),
    ("teknik_stil", "Teknik/Stil", "PIM ürün formu stil etiketi.", 80, None),
    ("ozel_gun", "Özel Gün", "PIM ürün formu occasions etiketi.", 90, None),
    (
        "yas_grubu",
        "Yaş Grubu",
        "PIM — seçilen koleksiyona göre filtrelenir.",
        100,
        "koleksiyon",
    ),
    (
        "metal_adi",
        "Metal Adı",
        "PIM / fiyat — ayar kodu ve metal rengi bu metale bağlanır.",
        110,
        None,
    ),
    (
        "ayar_kodu",
        "Ayar Kodu",
        "PIM + fiyat motoru. meta.fineness milyem SSOT; metal adına göre filtrelenir.",
        120,
        "metal_adi",
    ),
    (
        "tas_tipi",
        "Taş Tipi",
        "PIM / taş-montür. Kesim, 4C, menşei ve mıhlama bu tipe bağlıdır.",
        130,
        None,
    ),
    (
        "tas_kesimi",
        "Taş Kesimi",
        "PIM — taş tipine göre kesim şekilleri.",
        140,
        "tas_tipi",
    ),
    (
        "berraklik",
        "Berraklık",
        "PIM — pırlanta 4C berraklık; taş tipine bağlı.",
        150,
        "tas_tipi",
    ),
    (
        "renk_derecesi",
        "Renk Derecesi",
        "PIM — pırlanta 4C renk; taş tipine bağlı.",
        160,
        "tas_tipi",
    ),
    (
        "kesim_kalitesi",
        "Kesim Kalitesi",
        "PIM — pırlanta 4C kesim kalitesi; taş tipine bağlı.",
        170,
        "tas_tipi",
    ),
    (
        "tas_mensei",
        "Taş Menşei",
        "PIM — taş tipine göre menşei.",
        180,
        "tas_tipi",
    ),
    (
        "mihlama_tipi",
        "Mıhlama Tipi",
        "PIM — taş tipine göre mıhlama yöntemi.",
        190,
        "tas_tipi",
    ),
    (
        "zincir_tipi",
        "Zincir Tipleri",
        "PIM — zincir kullanan kategorilere göre seçilir.",
        200,
        "kategori",
    ),
    (
        "kopca_tipi",
        "Kopça Tipi",
        "PIM — kategoriye göre kopça / kilit.",
        210,
        "kategori",
    ),
]

# Shared parent code groups
_FACETED_STONES = ["PIRLANTA", "ZIRKON", "SAFIR", "YAKUT", "ZUMRUT", "AMETIST", "TOPAZ"]
_ALL_STONES = _FACETED_STONES + ["INCI"]
_DIAMOND = ["PIRLANTA"]
_CHAIN_CATS = ["KOLYE", "BILEZIK", "BILEKLIK", "HALHAL", "SET"]
_ALL_CATS = [
    "KOLYE",
    "YUZUK",
    "BILEZIK",
    "KUPE",
    "BILEKLIK",
    "ALYANS",
    "HALHAL",
    "KOL_DUGMESI",
    "CHARM",
    "SET",
    "HEDIYE_CEKI",
]
_GOLD_COLORS = [
    "BEYAZ",
    "SARI",
    "ROSE",
    "IKI_RENK_BEYAZ_SARI",
    "IKI_RENK_BEYAZ_ROSE",
    "UC_RENKLI",
]
_WHITE_METAL_COLORS = ["BEYAZ", "DOGAL"]
_ALT_METAL_COLORS = ["DOGAL", "SIYAH", "BEYAZ"]

# Item: (table_code, code, label, meta, sort, parent_codes[])
DEFINITION_ITEMS: list[tuple[str, str, str, dict, int, list[str]]] = [
    # --- urun_tipi (Excel B↔C milyem) ---
    ("urun_tipi", "KUYUM", "Kuyum (Bitmiş Ürün)", {"entersMillesimal": True}, 10, []),
    ("urun_tipi", "MONTUR", "Montür (Yarı Mamul)", {"entersMillesimal": True}, 20, []),
    ("urun_tipi", "TAS", "Taş (Karat / Adet Bazlı)", {"entersMillesimal": False}, 30, []),
    # --- stok ---
    ("stok_mulkiyet_tipi", "OZ_MAL", "Öz Mal", {}, 10, []),
    ("stok_mulkiyet_tipi", "KONSINYE", "Konsinye (Emanet)", {}, 20, []),
    ("stok_durumu", "STOKTA", "Stokta", {}, 10, []),
    ("stok_durumu", "TUKENDI", "Tükendi", {}, 20, []),
    ("stok_durumu", "SIPARISE_OZEL", "Siparişe Özel", {}, 30, []),
    # --- koleksiyon ---
    ("koleksiyon", "YENI", "Yeni Koleksiyon", {}, 10, []),
    ("koleksiyon", "ERKEK", "Erkek", {}, 20, []),
    ("koleksiyon", "KADIN", "Kadın", {}, 30, []),
    ("koleksiyon", "COCUK", "Çocuk", {}, 40, []),
    # --- kategori ---
    # meta.showOnStorefront → B2C ana sayfa CategoryStrip; storefrontImageUrl OPS'te set edilir.
    ("kategori", "KOLYE", "Kolye", {"showOnStorefront": True}, 10, []),
    ("kategori", "YUZUK", "Yüzük", {"showOnStorefront": True}, 20, []),
    ("kategori", "BILEZIK", "Bilezik", {"showOnStorefront": False}, 30, []),
    ("kategori", "KUPE", "Küpe", {"showOnStorefront": True}, 40, []),
    ("kategori", "BILEKLIK", "Bileklik", {"showOnStorefront": True}, 50, []),
    ("kategori", "ALYANS", "Alyans", {"showOnStorefront": False}, 60, []),
    ("kategori", "HALHAL", "Halhal", {"showOnStorefront": False}, 70, []),
    ("kategori", "KOL_DUGMESI", "Kol Düğmesi", {"showOnStorefront": False}, 80, []),
    ("kategori", "CHARM", "Charm", {"showOnStorefront": False}, 90, []),
    ("kategori", "SET", "Set", {"showOnStorefront": False}, 100, []),
    ("kategori", "HEDIYE_CEKI", "Hediye Çeki", {"showOnStorefront": False}, 110, []),
    # --- alt_kategori → kategori ---
    ("alt_kategori", "KOLYE_INCE_ZINCIR", "Kolye-İnce Zincir", {}, 10, ["KOLYE"]),
    ("alt_kategori", "KOLYE_KOLYE_UCU", "Kolye-Kolye Ucu", {}, 20, ["KOLYE"]),
    ("alt_kategori", "KOLYE_TEK_TAS", "Kolye-Tek Taş Kolye", {}, 30, ["KOLYE"]),
    ("alt_kategori", "KOLYE_ISIMLI", "Kolye-İsimli Kolye", {}, 40, ["KOLYE"]),
    ("alt_kategori", "KOLYE_GERDANLIK", "Kolye-Gerdanlık", {}, 50, ["KOLYE"]),
    ("alt_kategori", "YUZUK_TEK_TAS", "Yüzük-Tek Taş", {}, 60, ["YUZUK"]),
    ("alt_kategori", "YUZUK_PIRLANTA", "Yüzük-Pırlanta", {}, 70, ["YUZUK"]),
    ("alt_kategori", "YUZUK_SOZ_NISAN", "Yüzük-Söz/Nişan Yüzüğü", {}, 80, ["YUZUK"]),
    ("alt_kategori", "YUZUK_BAGUETTE", "Yüzük-Baguette", {}, 90, ["YUZUK"]),
    ("alt_kategori", "YUZUK_RENKLI", "Yüzük-Renkli Taşlı", {}, 100, ["YUZUK"]),
    ("alt_kategori", "BILEZIK_TRABZON", "Bilezik-Trabzon Hasır", {}, 110, ["BILEZIK"]),
    ("alt_kategori", "BILEZIK_BURMA", "Bilezik-Burma", {}, 120, ["BILEZIK"]),
    ("alt_kategori", "BILEZIK_ZINCIR", "Bilezik-Zincir Bilezik", {}, 130, ["BILEZIK"]),
    ("alt_kategori", "BILEZIK_KELEPCE", "Bilezik-Kelepçe", {}, 140, ["BILEZIK"]),
    ("alt_kategori", "BILEZIK_BEBEK", "Bilezik-Bebek Bileziği", {}, 150, ["BILEZIK"]),
    ("alt_kategori", "KUPE_HALKA", "Küpe-Halka", {}, 160, ["KUPE"]),
    ("alt_kategori", "KUPE_SALLANTILI", "Küpe-Sallantılı", {}, 170, ["KUPE"]),
    ("alt_kategori", "KUPE_CIVILI", "Küpe-Çivili", {}, 180, ["KUPE"]),
    ("alt_kategori", "KUPE_TEK_TAS", "Küpe-Tek Taş", {}, 190, ["KUPE"]),
    ("alt_kategori", "KUPE_COCUK", "Küpe-Çocuk Küpesi", {}, 200, ["KUPE"]),
    ("alt_kategori", "BILEKLIK_ZINCIR", "Bileklik-Zincir", {}, 210, ["BILEKLIK"]),
    ("alt_kategori", "BILEKLIK_BONCUKLU", "Bileklik-Boncuklu", {}, 220, ["BILEKLIK"]),
    ("alt_kategori", "BILEKLIK_CHARM", "Bileklik-Charm Bileklik", {}, 230, ["BILEKLIK"]),
    ("alt_kategori", "BILEKLIK_ISIMLI", "Bileklik-İsimli", {}, 240, ["BILEKLIK"]),
    ("alt_kategori", "ALYANS_KLASIK", "Alyans-Klasik", {}, 250, ["ALYANS"]),
    ("alt_kategori", "ALYANS_TASLI", "Alyans-Taşlı", {}, 260, ["ALYANS"]),
    ("alt_kategori", "ALYANS_CIFT", "Alyans-Çift Alyans", {}, 270, ["ALYANS"]),
    ("alt_kategori", "ALYANS_MAT_PARLAK", "Alyans-Mat/Parlak", {}, 280, ["ALYANS"]),
    ("alt_kategori", "HALHAL_ZINCIRLI", "Halhal-Zincirli", {}, 290, ["HALHAL"]),
    ("alt_kategori", "HALHAL_CHARMLI", "Halhal-Charmlı", {}, 300, ["HALHAL"]),
    ("alt_kategori", "HALHAL_TASLI", "Halhal-Taşlı", {}, 310, ["HALHAL"]),
    ("alt_kategori", "KOL_DUGMESI_KLASIK", "Kol Düğmesi-Klasik", {}, 320, ["KOL_DUGMESI"]),
    ("alt_kategori", "KOL_DUGMESI_TASLI", "Kol Düğmesi-Taşlı", {}, 330, ["KOL_DUGMESI"]),
    ("alt_kategori", "KOL_DUGMESI_OZEL", "Kol Düğmesi-Kişiye Özel", {}, 340, ["KOL_DUGMESI"]),
    ("alt_kategori", "CHARM_HARF", "Charm-Harf", {}, 350, ["CHARM"]),
    ("alt_kategori", "CHARM_BURC", "Charm-Burç", {}, 360, ["CHARM"]),
    ("alt_kategori", "CHARM_HAYVAN", "Charm-Hayvan", {}, 370, ["CHARM"]),
    ("alt_kategori", "CHARM_SEMBOL", "Charm-Sembol", {}, 380, ["CHARM"]),
    ("alt_kategori", "SET_KOLYE_KUPE", "Set-Kolye+Küpe", {}, 390, ["SET"]),
    ("alt_kategori", "SET_YUZUK_KUPE", "Set-Yüzük+Küpe", {}, 400, ["SET"]),
    ("alt_kategori", "SET_TAM", "Set-Tam Set", {}, 410, ["SET"]),
    ("alt_kategori", "SET_GELIN", "Set-Gelin Seti", {}, 420, ["SET"]),
    ("alt_kategori", "HEDIYE_CEKI_DIJITAL", "Hediye Çeki-Dijital Çek", {}, 430, ["HEDIYE_CEKI"]),
    ("alt_kategori", "HEDIYE_CEKI_BASILI", "Hediye Çeki-Basılı Çek", {}, 440, ["HEDIYE_CEKI"]),
    # --- metal_adi (parent for renk + ayar) ---
    ("metal_adi", "ALTIN", "Altın", {}, 10, []),
    ("metal_adi", "GUMUS", "Gümüş", {}, 20, []),
    ("metal_adi", "PLATIN", "Platin", {}, 30, []),
    ("metal_adi", "PALADYUM", "Paladyum", {}, 40, []),
    ("metal_adi", "CELIK", "Çelik", {}, 50, []),
    ("metal_adi", "TITANYUM", "Titanyum", {}, 60, []),
    ("metal_adi", "ZIRKONYUM", "Zirkonyum", {}, 70, []),
    ("metal_adi", "TUNGSTEN", "Tungsten", {}, 80, []),
    ("metal_adi", "KOBALT_KROM", "Kobalt Krom", {}, 90, []),
    ("metal_adi", "TANTAL", "Tantal", {}, 100, []),
    # --- metal_rengi → metal_adi ---
    ("metal_rengi", "BEYAZ", "Beyaz", {}, 10, ["ALTIN", "GUMUS", "PLATIN", "PALADYUM", "CELIK"]),
    ("metal_rengi", "SARI", "Sarı", {}, 20, ["ALTIN", "GUMUS"]),
    ("metal_rengi", "ROSE", "Rose (Kırmızı)", {}, 30, ["ALTIN", "GUMUS"]),
    (
        "metal_rengi",
        "IKI_RENK_BEYAZ_SARI",
        "İki Renkli (Beyaz-Sarı)",
        {},
        40,
        ["ALTIN"],
    ),
    (
        "metal_rengi",
        "IKI_RENK_BEYAZ_ROSE",
        "İki Renkli (Beyaz-Rose)",
        {},
        50,
        ["ALTIN"],
    ),
    ("metal_rengi", "UC_RENKLI", "Üç Renkli", {}, 60, ["ALTIN"]),
    (
        "metal_rengi",
        "SIYAH",
        "Siyah (Zirkonyum)",
        {},
        70,
        ["ZIRKONYUM", "CELIK", "TITANYUM", "TUNGSTEN", "KOBALT_KROM", "TANTAL"],
    ),
    (
        "metal_rengi",
        "DOGAL",
        "Doğal Metal Rengi",
        {},
        80,
        [
            "GUMUS",
            "PLATIN",
            "PALADYUM",
            "CELIK",
            "TITANYUM",
            "ZIRKONYUM",
            "TUNGSTEN",
            "KOBALT_KROM",
            "TANTAL",
        ],
    ),
    # --- stil / gün ---
    ("teknik_stil", "TELKARI", "Telkari", {}, 10, []),
    ("teknik_stil", "MINIMAL", "Minimal", {}, 20, []),
    ("teknik_stil", "VINTAGE", "Vintage", {}, 30, []),
    ("teknik_stil", "MODERN", "Modern", {}, 40, []),
    ("teknik_stil", "KLASIK", "Klasik", {}, 50, []),
    ("teknik_stil", "GELENEKSEL", "Geleneksel", {}, 60, []),
    ("teknik_stil", "MAT_PARLAK", "Mat/Parlak", {}, 70, []),
    ("ozel_gun", "NISAN", "Nişan", {}, 10, []),
    ("ozel_gun", "DUGUN", "Düğün", {}, 20, []),
    ("ozel_gun", "HEDIYE", "Hediye", {}, 30, []),
    ("ozel_gun", "DOGUM", "Doğum", {}, 40, []),
    ("ozel_gun", "DOGUM_GUNU", "Doğum Günü", {}, 50, []),
    ("ozel_gun", "ANNELER_GUNU", "Anneler Günü", {}, 60, []),
    ("ozel_gun", "BABALAR_GUNU", "Babalar Günü", {}, 70, []),
    ("ozel_gun", "SEVGILILER_GUNU", "Sevgililer Günü", {}, 80, []),
    ("ozel_gun", "YILDONUMU", "Yıldönümü", {}, 90, []),
    ("ozel_gun", "MEZUNIYET", "Mezuniyet", {}, 100, []),
    ("ozel_gun", "EVLILIK_TEKLIFI", "Evlilik Teklifi", {}, 110, []),
    ("ozel_gun", "BEBEK_HEDIYESI", "Bebek Hediyesi", {}, 120, []),
    ("ozel_gun", "YILBASI", "Yılbaşı", {}, 130, []),
    ("ozel_gun", "YOK", "Yok", {}, 140, []),
    # --- yas_grubu → koleksiyon ---
    ("yas_grubu", "YETISKIN", "Yetişkin", {}, 10, ["YENI", "ERKEK", "KADIN"]),
    ("yas_grubu", "GENC", "Genç", {}, 20, ["YENI", "ERKEK", "KADIN"]),
    ("yas_grubu", "COCUK", "Çocuk (3-12)", {}, 30, ["YENI", "COCUK"]),
    ("yas_grubu", "BEBEK", "Bebek (0-2)", {}, 40, ["YENI", "COCUK"]),
    # --- ayar_kodu → metal_adi (Excel M↔N↔O↔P) ---
    ("ayar_kodu", "8K", "8K", {"ayarValue": 8, "fineness": 0.333}, 10, ["ALTIN"]),
    ("ayar_kodu", "9K", "9K", {"ayarValue": 9, "fineness": 0.375}, 20, ["ALTIN"]),
    ("ayar_kodu", "10K", "10K", {"ayarValue": 10, "fineness": 0.417}, 30, ["ALTIN"]),
    ("ayar_kodu", "14K", "14K", {"ayarValue": 14, "fineness": 0.585}, 40, ["ALTIN"]),
    ("ayar_kodu", "18K", "18K", {"ayarValue": 18, "fineness": 0.75}, 50, ["ALTIN"]),
    ("ayar_kodu", "21K", "21K", {"ayarValue": 21, "fineness": 0.875}, 60, ["ALTIN"]),
    ("ayar_kodu", "22K", "22K", {"ayarValue": 22, "fineness": 0.916}, 70, ["ALTIN"]),
    ("ayar_kodu", "24K_HAS", "24K (Has)", {"ayarValue": 24, "fineness": 0.995}, 80, ["ALTIN"]),
    ("ayar_kodu", "24K_SAF", "24K (Saf)", {"ayarValue": 24, "fineness": 0.999}, 90, ["ALTIN"]),
    ("ayar_kodu", "925", "925", {"ayarValue": 925, "fineness": 0.925}, 100, ["GUMUS"]),
    ("ayar_kodu", "999", "999 (Has)", {"ayarValue": 999, "fineness": 0.999}, 110, ["GUMUS"]),
    ("ayar_kodu", "900", "900", {"ayarValue": 900, "fineness": 0.9}, 120, ["PLATIN"]),
    ("ayar_kodu", "950", "950", {"ayarValue": 950, "fineness": 0.95}, 130, ["PLATIN", "PALADYUM"]),
    (
        "ayar_kodu",
        "AYARSIZ",
        "Ayarsız",
        {"ayarValue": 0, "fineness": 0},
        140,
        ["CELIK", "TITANYUM", "ZIRKONYUM", "TUNGSTEN", "KOBALT_KROM", "TANTAL"],
    ),
    # --- tas_tipi ---
    ("tas_tipi", "TASSIZ", "Taşsız", {}, 10, []),
    ("tas_tipi", "PIRLANTA", "Pırlanta", {}, 20, []),
    ("tas_tipi", "ZIRKON", "Zirkon", {}, 30, []),
    ("tas_tipi", "SAFIR", "Safir", {}, 40, []),
    ("tas_tipi", "YAKUT", "Yakut", {}, 50, []),
    ("tas_tipi", "ZUMRUT", "Zümrüt", {}, 60, []),
    ("tas_tipi", "INCI", "İnci", {}, 70, []),
    ("tas_tipi", "AMETIST", "Ametist", {}, 80, []),
    ("tas_tipi", "TOPAZ", "Topaz", {}, 90, []),
    # --- tas_kesimi → tas_tipi (faceted) ---
    ("tas_kesimi", "BRILLIANT", "Brilliant", {}, 10, list(_FACETED_STONES)),
    ("tas_kesimi", "PRINCESS", "Princess", {}, 20, list(_FACETED_STONES)),
    ("tas_kesimi", "BAGET", "Baget", {}, 30, list(_FACETED_STONES)),
    ("tas_kesimi", "OVAL", "Oval", {}, 40, list(_FACETED_STONES)),
    ("tas_kesimi", "DAMLA", "Damla", {}, 50, list(_FACETED_STONES)),
    ("tas_kesimi", "MARKIZ", "Markiz", {}, 60, list(_FACETED_STONES)),
    ("tas_kesimi", "KALP", "Kalp", {}, 70, list(_FACETED_STONES)),
    ("tas_kesimi", "ZUMRUT_KESIM", "Zümrüt Kesim", {}, 80, list(_FACETED_STONES)),
    # --- pırlanta 4C ---
    ("berraklik", "FL", "FL", {}, 10, list(_DIAMOND)),
    ("berraklik", "IF", "IF", {}, 20, list(_DIAMOND)),
    ("berraklik", "VVS1", "VVS1", {}, 30, list(_DIAMOND)),
    ("berraklik", "VVS2", "VVS2", {}, 40, list(_DIAMOND)),
    ("berraklik", "VS1", "VS1", {}, 50, list(_DIAMOND)),
    ("berraklik", "VS2", "VS2", {}, 60, list(_DIAMOND)),
    ("berraklik", "SI1", "SI1", {}, 70, list(_DIAMOND)),
    ("berraklik", "SI2", "SI2", {}, 80, list(_DIAMOND)),
    ("berraklik", "I1", "I1", {}, 90, list(_DIAMOND)),
    ("renk_derecesi", "D", "D", {}, 10, list(_DIAMOND)),
    ("renk_derecesi", "E", "E", {}, 20, list(_DIAMOND)),
    ("renk_derecesi", "F", "F", {}, 30, list(_DIAMOND)),
    ("renk_derecesi", "G", "G", {}, 40, list(_DIAMOND)),
    ("renk_derecesi", "H", "H", {}, 50, list(_DIAMOND)),
    ("renk_derecesi", "I", "I", {}, 60, list(_DIAMOND)),
    ("renk_derecesi", "J", "J", {}, 70, list(_DIAMOND)),
    ("renk_derecesi", "K", "K", {}, 80, list(_DIAMOND)),
    ("kesim_kalitesi", "EXCELLENT", "Excellent", {}, 10, list(_DIAMOND)),
    ("kesim_kalitesi", "VERY_GOOD", "Very Good", {}, 20, list(_DIAMOND)),
    ("kesim_kalitesi", "GOOD", "Good", {}, 30, list(_DIAMOND)),
    ("kesim_kalitesi", "FAIR", "Fair", {}, 40, list(_DIAMOND)),
    # --- tas_mensei / mihlama → taşlı tipler ---
    ("tas_mensei", "DOGAL", "Doğal", {}, 10, list(_ALL_STONES)),
    ("tas_mensei", "LABORATUVAR", "Laboratuvar", {}, 20, list(_ALL_STONES)),
    ("tas_mensei", "SENTETIK", "Sentetik / Simülant", {}, 30, list(_ALL_STONES)),
    ("mihlama_tipi", "TIRNAK", "Tırnak", {}, 10, list(_ALL_STONES)),
    ("mihlama_tipi", "KANAL", "Kanal", {}, 20, list(_ALL_STONES)),
    ("mihlama_tipi", "BEZEL", "Bezel (Çerçeve)", {}, 30, list(_ALL_STONES)),
    ("mihlama_tipi", "PAVE", "Pave", {}, 40, list(_ALL_STONES)),
    ("mihlama_tipi", "GIZLI", "Gizli", {}, 50, list(_ALL_STONES)),
    # --- zincir_tipi → kategori ---
    ("zincir_tipi", "HALAT", "Halat", {}, 10, list(_CHAIN_CATS)),
    ("zincir_tipi", "FORSE", "Forse", {}, 20, list(_CHAIN_CATS)),
    ("zincir_tipi", "GURMET", "Gurmet", {}, 30, list(_CHAIN_CATS)),
    ("zincir_tipi", "SINGAPUR", "Singapur", {}, 40, list(_CHAIN_CATS)),
    ("zincir_tipi", "VENEDIK", "Venedik", {}, 50, list(_CHAIN_CATS)),
    ("zincir_tipi", "YOK", "Yok", {}, 60, list(_ALL_CATS)),
    # --- kopca_tipi → kategori ---
    ("kopca_tipi", "KISKAC", "Kıskaç", {}, 10, ["KOLYE", "BILEKLIK", "HALHAL", "SET"]),
    (
        "kopca_tipi",
        "BILEZIK_KILIDI",
        "Bilezik Kilidi",
        {},
        20,
        ["BILEZIK", "BILEKLIK", "HALHAL"],
    ),
    ("kopca_tipi", "VIDALI", "Vidalı", {}, 30, ["KOLYE", "BILEKLIK", "HALHAL", "SET"]),
    ("kopca_tipi", "KLIPS", "Klips", {}, 40, ["KUPE"]),
    (
        "kopca_tipi",
        "KOPCASIZ",
        "Kopçasız",
        {},
        50,
        [
            "KOLYE",
            "YUZUK",
            "BILEZIK",
            "KUPE",
            "BILEKLIK",
            "ALYANS",
            "HALHAL",
            "KOL_DUGMESI",
            "CHARM",
            "SET",
            "HEDIYE_CEKI",
        ],
    ),
]

# Unused helpers kept for readability / future seeds
_ = (_GOLD_COLORS, _WHITE_METAL_COLORS, _ALT_METAL_COLORS)

# Backward-compat alias used by older imports
DEFINITION_SEED = DEFINITION_TABLES
