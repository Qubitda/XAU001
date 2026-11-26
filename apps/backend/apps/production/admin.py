from django.contrib import admin, messages
from apps.common.admin import NoDeleteAdminMixin
from config.exceptions import DomainError
from .models import WorkOrder
from .services import transition_work_order_status


@admin.register(WorkOrder)
class WorkOrderAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "work_order_no",
        "source_order_no",
        "organization",
        "sku",
        "size",
        "quantity",
        "status",
        "created_at",
    )
    list_filter = ("status", "organization", "created_at")
    search_fields = ("work_order_no", "source_order_no", "sku", "organization__code", "engraving_or_stamp_note")
    autocomplete_fields = ("organization",)
    list_select_related = ("organization",)
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")

    def save_model(self, request, obj: WorkOrder, form, change: bool):
        if change and "status" in form.changed_data:
            desired_status = obj.status
            original = WorkOrder.objects.get(pk=obj.pk)
            obj.status = original.status
            super().save_model(request, obj, form, change)
            try:
                transition_work_order_status(
                    work_order_id_or_no=obj.work_order_no,
                    next_status=desired_status,
                    actor=request.user,
                )
            except DomainError as exc:
                self.message_user(request, str(exc.detail), level=messages.ERROR)
            return
        super().save_model(request, obj, form, change)
