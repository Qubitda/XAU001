import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import User
from apps.catalog.models import ProductModel, StoneLine
from apps.market.models import RateSnapshot
from apps.market.services import DEFAULT_FX_BASE_RATES, create_rate_snapshot
from apps.organizations.models import Branch, Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.pricing.services import publish_recipe


SEED_PRODUCTS = [
    {
        "parent_sku": "SE009",
        "barcode": "P692105",
        "visual_type": "solitaire_ring",
        "title": "0.60 Karat Pırlanta Tektaş Yüzük",
        "description": "0.60 Karat F Renk VS1 Berraklık 14 Ayar Beyaz Altın Tektaş Yüzük",
        "collection": "Yeni Koleksiyon",
        "category": "Yüzük",
        "sub_category": "Yüzük-Tek Taş",
        "purity_code": "14K",
        "metal_color": "Beyaz",
        "available_colors": ["Beyaz", "Sarı", "Rose"],
        "gross_weight_gram": Decimal("3.1200"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.IN_STOCK,
        "stock_qty": 3,
        "ownership_type": ProductModel.OwnershipType.CONSIGNMENT,
        "supplier_name": "Emre AŞ.",
        "warehouse_location": "MERKEZ-KASA-02",
        "mount_structure": ProductModel.MountStructure.HEAD_BAND,
        "allowed_carat_min": Decimal("0.400"),
        "allowed_carat_max": Decimal("0.750"),
        "head_code": "TAC-6T-050",
        "band_code": "KOL-PAVE-18MM",
        "head_weight_gram": Decimal("0.6800"),
        "band_weight_gram": Decimal("2.3200"),
        "certificate_agency": "GIA",
        "certificate_number": "2141234567",
        "variant_size": 14,
        "available_sizes": [10, 11, 12, 13, 14, 15, 16, 17, 18],
        "seo_slug": "0-60-karat-pirlanta-tektas-yuzuk-14k-beyaz",
        "stones": [
            ("MERKEZ", "Pırlanta", "ct", 1, Decimal("0.5000"), "VS1", "F", "Yuvarlak (Round)"),
            ("PAVE", "Pırlanta", "ct", 10, Decimal("0.0100"), "VS2", "F-G", "Yuvarlak (Round)"),
        ],
        "pricing_mode": "1",
        "costs": [
            ("MADEN", "USD", Decimal("0"), None),
            ("ISCILIK", "EUR", Decimal("15.00"), None),
            ("TAS", "USD", Decimal("400.00"), None),
        ],
        "channels": [
            ("B2B", "%", Decimal("15"), "TRY", Decimal("101.29"), "%", Decimal("1")),
            ("B2C_API", "TRY", Decimal("20000"), "%", Decimal("1"), "%", Decimal("1")),
        ],
    },
    {
        "parent_sku": "SE014",
        "barcode": "P692214",
        "visual_type": "baguette_ring",
        "title": "0.85 Karat Baget Pırlanta Yüzük",
        "description": "0.85 Karat G Renk VS2 Berraklık 14 Ayar Beyaz Altın Baget Pırlanta Yüzük",
        "collection": "İmza Koleksiyonu",
        "category": "Yüzük",
        "sub_category": "Yüzük-Baget",
        "purity_code": "14K",
        "metal_color": "Beyaz",
        "available_colors": ["Beyaz", "Rose"],
        "gross_weight_gram": Decimal("3.6500"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.IN_STOCK,
        "stock_qty": 4,
        "ownership_type": ProductModel.OwnershipType.OWNED,
        "supplier_name": "Tara Gold Atölye",
        "warehouse_location": "MERKEZ-VİTRİN-01",
        "mount_structure": ProductModel.MountStructure.FULL,
        "allowed_carat_min": Decimal("0.300"),
        "allowed_carat_max": Decimal("1.000"),
        "certificate_agency": "HRD",
        "certificate_number": "2300884120",
        "variant_size": 14,
        "available_sizes": [10, 11, 12, 13, 14, 15, 16, 17, 18],
        "seo_slug": "0-85-karat-baget-pirlanta-yuzuk-14k-beyaz",
        "stones": [
            ("MERKEZ", "Pırlanta", "ct", 1, Decimal("0.4500"), "VS2", "G", "Baget"),
            ("YAN", "Pırlanta", "ct", 20, Decimal("0.0200"), "VS2", "G", "Baget"),
        ],
        "pricing_mode": "1",
        "costs": [
            ("MADEN", "USD", Decimal("0"), None),
            ("ISCILIK", "EUR", Decimal("22.00"), None),
            ("TAS", "USD", Decimal("540.00"), None),
        ],
        "channels": [
            ("B2B", "%", Decimal("16"), "%", Decimal("0"), "%", Decimal("1")),
            ("B2C_API", "%", Decimal("48"), "%", Decimal("8"), "%", Decimal("1")),
        ],
    },
    {
        "parent_sku": "KL022",
        "barcode": "P692322",
        "visual_type": "pendant_necklace",
        "title": "0.35 Karat Tektaş Pırlanta Kolye",
        "description": "0.35 Karat E Renk VVS2 Berraklık 18 Ayar Sarı Altın Forse Zincirli Tektaş Kolye",
        "collection": "Yeni Koleksiyon",
        "category": "Kolye",
        "sub_category": "Kolye-Tek Taş",
        "purity_code": "18K",
        "metal_color": "Sarı",
        "available_colors": ["Sarı", "Beyaz", "Rose"],
        "gross_weight_gram": Decimal("2.4800"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.IN_STOCK,
        "stock_qty": 5,
        "ownership_type": ProductModel.OwnershipType.OWNED,
        "supplier_name": "Tara Gold Atölye",
        "warehouse_location": "MERKEZ-KASA-01",
        "mount_structure": ProductModel.MountStructure.FULL,
        "allowed_carat_min": Decimal("0.200"),
        "allowed_carat_max": Decimal("0.750"),
        "certificate_agency": "GIA",
        "certificate_number": "2141889012",
        "variant_size": 45,
        "available_sizes": [40, 42, 45, 50],
        "seo_slug": "0-35-karat-tektas-pirlanta-kolye-18k-sari",
        "stones": [
            ("MERKEZ", "Pırlanta", "ct", 1, Decimal("0.3500"), "VVS2", "E", "Brilliant"),
        ],
        "pricing_mode": "1",
        "costs": [
            ("MADEN", "USD", Decimal("0"), None),
            ("ISCILIK", "EUR", Decimal("14.00"), None),
            ("TAS", "USD", Decimal("295.00"), None),
        ],
        "channels": [
            ("B2B", "%", Decimal("14"), "%", Decimal("0"), "%", Decimal("1")),
            ("B2C_API", "%", Decimal("42"), "%", Decimal("0"), "%", Decimal("1")),
        ],
    },
    {
        "parent_sku": "BL031",
        "barcode": "P692431",
        "visual_type": "tennis_bracelet",
        "title": "2.40 Karat Su Yolu Pırlanta Bileklik",
        "description": "2.40 Karat F Renk VS1 Berraklık 14 Ayar Beyaz Altın Klasik Su Yolu Bileklik",
        "collection": "Haute Joaillerie",
        "category": "Bileklik",
        "sub_category": "Bileklik-Su Yolu",
        "purity_code": "14K",
        "metal_color": "Beyaz",
        "available_colors": ["Beyaz", "Sarı"],
        "gross_weight_gram": Decimal("8.9000"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.IN_STOCK,
        "stock_qty": 2,
        "ownership_type": ProductModel.OwnershipType.CONSIGNMENT,
        "supplier_name": "Emre AŞ.",
        "warehouse_location": "MERKEZ-KASA-02",
        "mount_structure": ProductModel.MountStructure.FULL,
        "allowed_carat_min": Decimal("1.500"),
        "allowed_carat_max": Decimal("5.000"),
        "certificate_agency": "GIA",
        "certificate_number": "2141995401",
        "variant_size": 18,
        "available_sizes": [16, 17, 18, 19, 20],
        "seo_slug": "2-40-karat-su-yolu-pirlanta-bileklik-14k-beyaz",
        "stones": [
            ("MERKEZ", "Pırlanta", "ct", 48, Decimal("0.0500"), "VS1", "F", "Brilliant"),
        ],
        "pricing_mode": "1",
        "costs": [
            ("MADEN", "USD", Decimal("0"), None),
            ("ISCILIK", "EUR", Decimal("68.00"), None),
            ("TAS", "USD", Decimal("1420.00"), None),
        ],
        "channels": [
            ("B2B", "%", Decimal("14"), "%", Decimal("0"), "%", Decimal("1")),
            ("B2C_API", "%", Decimal("40"), "%", Decimal("10"), "%", Decimal("1")),
        ],
    },
    {
        "parent_sku": "KP018",
        "barcode": "P692518",
        "visual_type": "emerald_earring",
        "title": "0.50 Karat Zümrüt & Pırlanta Küpe",
        "description": "Doğal Kolombiya Zümrüt ve Pırlanta Halo Çevrili 18 Ayar Sarı Altın Küpe",
        "collection": "Değerli Taşlar",
        "category": "Küpe",
        "sub_category": "Küpe-Değerli Taş",
        "purity_code": "18K",
        "metal_color": "Sarı",
        "available_colors": ["Sarı", "Beyaz"],
        "gross_weight_gram": Decimal("4.1500"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.IN_STOCK,
        "stock_qty": 2,
        "ownership_type": ProductModel.OwnershipType.CONSIGNMENT,
        "supplier_name": "Emre AŞ.",
        "warehouse_location": "MERKEZ-VİTRİN-02",
        "mount_structure": ProductModel.MountStructure.FULL,
        "allowed_carat_min": Decimal("0.200"),
        "allowed_carat_max": Decimal("1.500"),
        "stone_type": "Zümrüt",
        "certificate_agency": "IGI",
        "certificate_number": "598204118",
        "variant_size": 12,
        "available_sizes": [10, 12],
        "seo_slug": "0-50-karat-zumrut-pirlanta-kupe-18k-sari",
        "stones": [
            ("MERKEZ", "Zümrüt", "ct", 2, Decimal("0.1800"), "VS1", "F", "Oval"),
            ("PAVE", "Pırlanta", "ct", 28, Decimal("0.0050"), "VS1", "F", "Brilliant"),
        ],
        "pricing_mode": "2",
        "costs": [
            ("TEDARIKCI", "USD", Decimal("790.00"), None),
        ],
        "channels": [
            ("B2B", "%", Decimal("15"), "%", Decimal("0"), "%", Decimal("1")),
            ("B2C_API", "%", Decimal("40"), "%", Decimal("5"), "%", Decimal("1")),
        ],
    },
    {
        "parent_sku": "YZ045",
        "barcode": "P692645",
        "visual_type": "eternity_ring",
        "title": "1.10 Karat Tamtur Pırlanta Alyans",
        "description": "1.10 Karat F Renk VS1 Berraklık 14 Ayar Rose Altın Princess Kesim Tamtur Alyans",
        "collection": "Yeni Koleksiyon",
        "category": "Yüzük",
        "sub_category": "Yüzük-Tamtur",
        "purity_code": "14K",
        "metal_color": "Rose",
        "available_colors": ["Rose", "Beyaz", "Sarı"],
        "gross_weight_gram": Decimal("3.4000"),
        "fire_rate_pct": Decimal("2.00"),
        "stock_status": ProductModel.StockStatus.MADE_TO_ORDER,
        "stock_qty": 0,
        "ownership_type": ProductModel.OwnershipType.OWNED,
        "supplier_name": "Tara Gold Atölye",
        "warehouse_location": "ATÖLYE-SİPARİŞ",
        "mount_structure": ProductModel.MountStructure.FULL,
        "allowed_carat_min": Decimal("0.500"),
        "allowed_carat_max": Decimal("2.000"),
        "certificate_agency": "Firma Sertifikalı",
        "certificate_number": "FRM-2026-045",
        "variant_size": 14,
        "available_sizes": [10, 11, 12, 13, 14, 15, 16, 17, 18],
        "seo_slug": "1-10-karat-tamtur-pirlanta-alyans-14k-rose",
        "stones": [
            ("MERKEZ", "Pırlanta", "ct", 22, Decimal("0.0500"), "VS1", "F", "Princess"),
        ],
        "pricing_mode": "1",
        "costs": [
            ("MADEN", "USD", Decimal("0"), None),
            ("ISCILIK", "EUR", Decimal("20.00"), None),
            ("TAS", "USD", Decimal("620.00"), None),
        ],
        "channels": [
            ("B2C_API", "%", Decimal("35"), "%", Decimal("0"), "%", Decimal("1")),
        ],
    },
]


class Command(BaseCommand):
    help = "Idempotently seeds Tara Gold organizations, branches, 13-unit market rates, and full 6-model catalog."

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.definitions.services import seed_definition_tables

        seeded = seed_definition_tables()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tanım tabloları: {seeded['tables']} tablo / {seeded['items']} kalem."
            )
        )
        if not RateSnapshot.objects.filter(is_current=True).exists():
            create_rate_snapshot(fx_base_rates=DEFAULT_FX_BASE_RATES, source_mode="auto")

        hq, _ = Organization.objects.get_or_create(
            code="TG-HQ",
            defaults={
                "name": "Tara Gold Merkez Operasyon A.Ş.",
                "org_type": Organization.OrgType.PLATFORM_OWNER,
                "tax_office_and_no": "Beyoğlu VD · 8240193011",
                "contact_name": "Emre Gönel",
                "city": "İstanbul / Kuyumcukent",
                "credit_limit_usd": Decimal("250000.00"),
                "has_limit_gram": Decimal("1000.0000"),
            },
        )
        br_kk, _ = Branch.objects.get_or_create(
            organization=hq,
            code="TG-KK",
            defaults={"name": "Kuyumcukent Merkez Atölye", "city": "İstanbul", "is_default": True},
        )
        br_no, _ = Branch.objects.get_or_create(
            organization=hq,
            code="TG-NO",
            defaults={"name": "Nuruosmaniye Toptan Showroom", "city": "İstanbul"},
        )

        aydin, _ = Organization.objects.get_or_create(
            code="BY-34018",
            defaults={
                "name": "Aydın Kuyumculuk Mücevherat Ltd. Şti.",
                "org_type": Organization.OrgType.DEALER,
                "tax_office_and_no": "Şişli VD · 1280459120",
                "contact_name": "Murat Aydın",
                "city": "İstanbul / Nişantaşı",
                "credit_limit_usd": Decimal("65000.00"),
                "used_credit_usd": Decimal("14250.00"),
                "has_limit_gram": Decimal("300.0000"),
                "used_has_gram": Decimal("64.5000"),
            },
        )
        br_nis, _ = Branch.objects.get_or_create(
            organization=aydin,
            code="AYD-NIS",
            defaults={"name": "Nişantaşı Mağaza", "city": "İstanbul", "is_default": True},
        )
        br_kpc, _ = Branch.objects.get_or_create(
            organization=aydin,
            code="AYD-KPC",
            defaults={"name": "Kapalıçarşı Şube", "city": "İstanbul"},
        )

        altinbasak, _ = Organization.objects.get_or_create(
            code="BY-06092",
            defaults={
                "name": "Altınbaşak Mücevherat A.Ş.",
                "org_type": Organization.OrgType.DEALER,
                "tax_office_and_no": "Çankaya VD · 3910824419",
                "contact_name": "Hakan Demir",
                "city": "Ankara / Çankaya",
                "credit_limit_usd": Decimal("90000.00"),
                "used_credit_usd": Decimal("21500.00"),
                "has_limit_gram": Decimal("450.0000"),
                "used_has_gram": Decimal("112.2500"),
            },
        )
        br_tun, _ = Branch.objects.get_or_create(
            organization=altinbasak,
            code="ALT-TUN",
            defaults={"name": "Tunalı Hilmi Showroom", "city": "Ankara", "is_default": True},
        )

        seed_password = os.environ.get("SEED_ADMIN_PASSWORD", "").strip()
        user, created = User.objects.get_or_create(
            email="emre.gonel@pigomass.com",
            defaults={"full_name": "Emre Gönel", "is_staff": True, "is_superuser": True},
        )
        if seed_password:
            user.set_password(seed_password)
            user.save(update_fields=["password"])
        elif created:
            self.stdout.write(
                self.style.WARNING(
                    "SEED_ADMIN_PASSWORD boş bırakıldığı için emre.gonel@pigomass.com parolası ayarlanmadı; "
                    "giriş için .env dosyasında SEED_ADMIN_PASSWORD tanımlayıp komutu tekrar çalıştırın."
                )
            )

        OrganizationMembership.objects.get_or_create(
            user=user, organization=None, role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER
        )
        m_aydin, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=aydin,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
            defaults={"default_branch": br_nis},
        )
        m_aydin.branches.set([br_nis, br_kpc])
        m_altin, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=altinbasak,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            defaults={"default_branch": br_tun},
        )
        m_altin.branches.set([br_tun])
        m_hq, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=hq,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            defaults={"default_branch": br_kk},
        )
        m_hq.branches.set([br_kk, br_no])

        from apps.catalog.models import ProductVariant
        from apps.inventory.models import Warehouse
        from apps.inventory.services import set_variant_warehouse_stock

        wh_merkez, _ = Warehouse.objects.get_or_create(
            code="WH-MERKEZ",
            defaults={"name": "Kuyumcukent Merkez Kasa", "branch": br_kk, "is_active": True},
        )
        color_code_map = {"Beyaz": "BYZ", "Sarı": "SRY", "Rose": "RSE"}

        for item in SEED_PRODUCTS:
            stones = item["stones"]
            costs = item["costs"]
            channels = item["channels"]
            pricing_mode = item["pricing_mode"]
            defaults = {
                k: v
                for k, v in item.items()
                if k not in ("parent_sku", "stones", "costs", "channels", "pricing_mode")
            }
            defaults["created_by"] = user
            product, p_created = ProductModel.objects.get_or_create(
                parent_sku=item["parent_sku"],
                defaults=defaults,
            )
            if p_created:
                for role, st_type, unit, cnt, carat, clarity, color, cut in stones:
                    StoneLine.objects.create(
                        product=product,
                        role=role,
                        stone_type=st_type,
                        measure_unit=unit,
                        count=cnt,
                        carat=carat,
                        clarity=clarity,
                        color_grade=color,
                        cut_shape=cut,
                    )
                recipe = PricingRecipe.objects.create(
                    product=product, version=1, pricing_mode=pricing_mode, lc_currency="TRY"
                )
                for lt, cur, price, manual in costs:
                    CostLine.objects.create(
                        recipe=recipe, line_type=lt, fc_currency=cur, fc_price=price, fc_price_manual=manual
                    )
                for ch, p_u, p_v, d_u, d_v, s_u, s_v in channels:
                    ChannelRule.objects.create(
                        recipe=recipe,
                        channel=ch,
                        profit_unit=p_u,
                        profit_value=p_v,
                        discount_unit=d_u,
                        discount_value=d_v,
                        servis_bedeli_unit=s_u,
                        servis_bedeli_value=s_v,
                    )

            # Ensure realistic multi-variant sellable SKUs + WarehouseStock exist for every model
            if not ProductVariant.objects.filter(product=product).exists():
                base_center_carat = next(
                    (carat for role, _, _, _, carat, _, _, _ in stones if role == "MERKEZ"),
                    Decimal("0.000"),
                )
                base_weight = product.gross_weight_gram
                base_qty = product.stock_qty
                variant_specs: list[tuple[str, str, Decimal, int, bool]] = [
                    (product.purity_code, product.metal_color, base_weight, base_qty, True),
                ]
                for extra_color in product.available_colors:
                    if extra_color != product.metal_color:
                        weight_offset = Decimal("0.0800") if extra_color == "Rose" else Decimal("-0.0500")
                        variant_specs.append(
                            (
                                product.purity_code,
                                extra_color,
                                max(Decimal("1.0000"), base_weight + weight_offset),
                                max(0, base_qty - 1) if base_qty > 0 else 0,
                                False,
                            )
                        )
                alt_purity = "18K" if product.purity_code == "14K" else "14K"
                alt_weight = (
                    (base_weight * Decimal("1.12")).quantize(Decimal("0.0001"))
                    if alt_purity == "18K"
                    else (base_weight * Decimal("0.90")).quantize(Decimal("0.0001"))
                )
                variant_specs.append(
                    (alt_purity, product.metal_color, alt_weight, 1 if base_qty > 0 else 0, False)
                )

                for v_purity, v_color, v_weight, v_qty, v_default in variant_specs:
                    c_code = color_code_map.get(v_color, "BYZ")
                    v_sku = f"{product.parent_sku}-{v_purity}-{c_code}-{product.variant_size}"
                    variant = ProductVariant.objects.create(
                        product=product,
                        sku=v_sku,
                        purity_code=v_purity,
                        metal_color=v_color,
                        size=product.variant_size,
                        center_stone_carat=base_center_carat,
                        gross_weight_gram=v_weight,
                        stock_qty=v_qty,
                        is_default=v_default,
                    )
                    set_variant_warehouse_stock(
                        variant=variant,
                        warehouse=wh_merkez,
                        quantity=v_qty,
                        reference_no=f"SEED-{v_sku}",
                        actor=user,
                    )

            if p_created:
                publish_recipe(recipe, actor=user)

        self.stdout.write(
            self.style.SUCCESS(
                "Tara Gold initial seed completed successfully (6 catalog models + multi-variant warehouse stocks)."
            )
        )
