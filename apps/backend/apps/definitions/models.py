from django.db import models

from apps.common.models import TimestampedModel


class DefinitionTable(TimestampedModel):
    """
    Tanım grubu (UI: tanım grubu). Persistence name kept for migrations/API stability.

    parent_table bağlandığında seçenekler üst gruptaki seçeneklere bağlanmalıdır:
    alt_kategori/zincir/kopça→kategori, ayar/renk→metal, yaş→koleksiyon,
    kesim/berraklık/renk/kesim kalitesi/menşei/mıhlama→taş tipi.
    """

    code = models.SlugField("Teknik kod", max_length=64, unique=True, db_index=True)
    name = models.CharField("Tanım adı", max_length=120)
    description = models.TextField("Açıklama", blank=True, default="")
    sort_order = models.PositiveSmallIntegerField("Sıralama", default=100)
    is_active = models.BooleanField("Aktif", default=True)
    is_system = models.BooleanField("Sistem tanımı", default=True)
    parent_table = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_tables",
        verbose_name="Üst tanım grubu",
    )

    class Meta:
        db_table = "definition_table"
        ordering = ["sort_order", "name"]
        verbose_name = "Tanım grubu"
        verbose_name_plural = "Tanım grupları"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class DefinitionItem(TimestampedModel):
    """Tanım seçeneği (UI: seçenek). meta.fineness gibi teknik değerler korunmalıdır."""

    table = models.ForeignKey(
        DefinitionTable,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Tanım grubu",
    )
    code = models.CharField("Teknik kod", max_length=120, db_index=True)
    label = models.CharField("Görünen ad", max_length=240)
    meta = models.JSONField("Gelişmiş meta", default=dict, blank=True)
    sort_order = models.PositiveIntegerField("Sıralama", default=100)
    is_active = models.BooleanField("Aktif", default=True)
    is_system = models.BooleanField("Sistem tanımı", default=False)
    # Related parents (M2M: e.g. 950→Platin+Paladyum, Beyaz→Altın+Gümüş+…).
    parents = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="children",
        verbose_name="Üst tanım seçenekleri",
    )

    class Meta:
        db_table = "definition_item"
        ordering = ["sort_order", "label"]
        verbose_name = "Tanım seçeneği"
        verbose_name_plural = "Tanım seçenekleri"
        constraints = [
            models.UniqueConstraint(fields=["table", "code"], name="uniq_definition_item_code"),
        ]
        indexes = [
            models.Index(fields=["table", "is_active", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.code})"
