from django import forms
from django.contrib import admin

from .crypto import encrypt_secret
from .models import EmailTemplate, MailLog, SmtpSetting


class SmtpSettingAdminForm(forms.ModelForm):
    password_plaintext = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Boş bırakılırsa mevcut şifre korunur. AES-256-GCM ile saklanır.",
    )

    class Meta:
        model = SmtpSetting
        fields = (
            "organization",
            "host",
            "port",
            "encryption",
            "username",
            "password_plaintext",
            "from_name",
            "from_email",
            "is_active",
        )


@admin.register(SmtpSetting)
class SmtpSettingAdmin(admin.ModelAdmin):
    form = SmtpSettingAdminForm
    list_display = (
        "from_email",
        "host",
        "port",
        "encryption",
        "organization",
        "is_active",
        "updated_at",
    )
    list_filter = ("encryption", "is_active")
    search_fields = ("host", "from_email", "username", "organization__code")
    raw_id_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        raw = (form.cleaned_data.get("password_plaintext") or "").strip()
        if raw:
            obj.password_ciphertext = encrypt_secret(raw)
        super().save_model(request, obj, form, change)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_key", "subject", "organization", "is_active", "updated_at")
    list_filter = ("template_key", "is_active")
    search_fields = ("template_key", "subject")
    raw_id_fields = ("organization",)


@admin.register(MailLog)
class MailLogAdmin(admin.ModelAdmin):
    list_display = (
        "template_key",
        "recipient",
        "status",
        "organization",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "template_key")
    search_fields = ("recipient", "template_key", "subject", "error_message")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "context_snapshot",
        "error_message",
        "provider_message_id",
    )
    raw_id_fields = ("organization",)
