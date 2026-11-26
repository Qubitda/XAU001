from django.contrib import admin

from apps.definitions.models import DefinitionItem, DefinitionTable


class DefinitionItemInline(admin.TabularInline):
    model = DefinitionItem
    extra = 0
    fields = ("code", "label", "sort_order", "is_active", "is_system", "meta")
    verbose_name = "Tanım seçeneği"
    verbose_name_plural = "Tanım seçenekleri"
    show_change_link = True


@admin.register(DefinitionTable)
class DefinitionTableAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent_table", "sort_order", "is_active", "is_system")
    list_filter = ("is_active", "is_system")
    search_fields = ("code", "name", "description")
    readonly_fields = ("code", "is_system")
    autocomplete_fields = ("parent_table",)
    inlines = [DefinitionItemInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DefinitionItem)
class DefinitionItemAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "table", "sort_order", "is_active", "is_system")
    list_filter = ("table", "is_active", "is_system")
    search_fields = ("code", "label", "table__code", "table__name")
    autocomplete_fields = ("table",)
    filter_horizontal = ("parents",)
    readonly_fields = ("is_system",)

    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_system and "code" not in base:
            base.append("code")
        return base

    def has_delete_permission(self, request, obj=None):
        return False
