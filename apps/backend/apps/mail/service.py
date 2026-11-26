"""Central multi-tenant transactional MailService."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from email.utils import formataddr
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import Context, Engine, Template
from django.template.loader import render_to_string
from django.utils import timezone

from apps.organizations.models import Organization

from .constants import DEFAULT_SUBJECTS, FILESYSTEM_TEMPLATE_KEYS
from .crypto import decrypt_secret
from .models import EmailTemplate, MailLog, SmtpSetting

logger = logging.getLogger(__name__)

# Isolated engine so filesystem + string templates share Django syntax without project TEMPLATES coupling.
_STRING_ENGINE = Engine(debug=getattr(settings, "DEBUG", False))


@dataclass(frozen=True)
class ResolvedSmtp:
    host: str
    port: int
    encryption: str
    username: str
    password: str
    from_name: str
    from_email: str
    source: str  # "org" | "platform" | "django_settings"


@dataclass(frozen=True)
class ResolvedTemplate:
    template_key: str
    subject: str
    body_html: str
    primary_color: str
    logo_url: str
    source: str  # "org_db" | "platform_db" | "filesystem"


class MailService:
    def resolve_smtp(self, *, organization: Organization | None = None) -> ResolvedSmtp:
        if organization is not None:
            row = (
                SmtpSetting.objects.filter(organization=organization, is_active=True)
                .order_by("-updated_at")
                .first()
            )
            if row is not None:
                return self._smtp_from_row(row, source="org")

        platform = (
            SmtpSetting.objects.filter(organization__isnull=True, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if platform is not None:
            return self._smtp_from_row(platform, source="platform")

        # Fallback: Django EMAIL_* / console backend settings
        return ResolvedSmtp(
            host=getattr(settings, "EMAIL_HOST", "localhost") or "localhost",
            port=int(getattr(settings, "EMAIL_PORT", 587) or 587),
            encryption="TLS"
            if getattr(settings, "EMAIL_USE_TLS", True)
            else ("SSL" if getattr(settings, "EMAIL_USE_SSL", False) else "NONE"),
            username=getattr(settings, "EMAIL_HOST_USER", "") or "",
            password=getattr(settings, "EMAIL_HOST_PASSWORD", "") or "",
            from_name="Tara Gold",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@taragold.local"),
            source="django_settings",
        )

    def _smtp_from_row(self, row: SmtpSetting, *, source: str) -> ResolvedSmtp:
        password = ""
        if row.password_ciphertext:
            try:
                password = decrypt_secret(row.password_ciphertext)
            except Exception:
                logger.exception("Failed to decrypt SMTP password for %s", row.id)
                raise
        return ResolvedSmtp(
            host=row.host,
            port=row.port,
            encryption=row.encryption,
            username=row.username or "",
            password=password,
            from_name=row.from_name or "Tara Gold",
            from_email=row.from_email,
            source=source,
        )

    def resolve_template(
        self,
        *,
        template_key: str,
        organization: Organization | None = None,
        context: dict[str, Any] | None = None,
    ) -> ResolvedTemplate:
        ctx = context or {}
        if organization is not None:
            org_tpl = (
                EmailTemplate.objects.filter(
                    organization=organization, template_key=template_key, is_active=True
                )
                .order_by("-updated_at")
                .first()
            )
            if org_tpl is not None:
                return ResolvedTemplate(
                    template_key=template_key,
                    subject=org_tpl.subject,
                    body_html=org_tpl.body_html,
                    primary_color=org_tpl.primary_color or "#4A101C",
                    logo_url=org_tpl.logo_url or "",
                    source="org_db",
                )

        platform_tpl = (
            EmailTemplate.objects.filter(
                organization__isnull=True, template_key=template_key, is_active=True
            )
            .order_by("-updated_at")
            .first()
        )
        if platform_tpl is not None:
            return ResolvedTemplate(
                template_key=template_key,
                subject=platform_tpl.subject,
                body_html=platform_tpl.body_html,
                primary_color=platform_tpl.primary_color or "#4A101C",
                logo_url=platform_tpl.logo_url or "",
                source="platform_db",
            )

        if template_key not in FILESYSTEM_TEMPLATE_KEYS:
            raise ValueError(f"Unknown template_key: {template_key}")

        # Filesystem: render content partial, then wrap in base layout.
        inner = render_to_string(f"mail/contents/{template_key}.html", ctx)
        subject_tpl = DEFAULT_SUBJECTS.get(template_key, template_key)
        return ResolvedTemplate(
            template_key=template_key,
            subject=subject_tpl,
            body_html=inner,
            primary_color="#4A101C",
            logo_url=ctx.get("logo_url") or getattr(settings, "MAIL_DEFAULT_LOGO_URL", "") or "",
            source="filesystem",
        )

    def render_subject(self, subject_template: str, context: dict[str, Any]) -> str:
        return Template(subject_template, engine=_STRING_ENGINE).render(Context(context)).strip()

    def render_html(
        self,
        *,
        resolved: ResolvedTemplate,
        context: dict[str, Any],
    ) -> str:
        ctx = {
            **context,
            "primary_color": resolved.primary_color or context.get("primary_color") or "#4A101C",
            "logo_url": resolved.logo_url or context.get("logo_url") or "",
            "company_name": context.get("company_name") or "Tara Gold",
            "company_address": context.get("company_address")
            or "Kuyumcukent, İstanbul",
            "support_email": context.get("support_email")
            or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@taragold.local"),
            "year": timezone.now().year,
        }
        # Render DB/filesystem inner content with variables first.
        inner = Template(resolved.body_html, engine=_STRING_ENGINE).render(Context(ctx))
        ctx["content_html"] = inner
        return render_to_string("mail/base_layout.html", ctx)

    def send(
        self,
        *,
        template_key: str,
        recipient: str,
        context: dict[str, Any] | None = None,
        organization_id: str | None = None,
        mail_log_id: str | None = None,
    ) -> MailLog:
        organization = None
        if organization_id:
            organization = Organization.objects.filter(id=organization_id).first()

        ctx = dict(context or {})
        # Alias camelCase / snake_case for template authors.
        if "customer_name" not in ctx and ctx.get("customerName"):
            ctx["customer_name"] = ctx["customerName"]
        if "order_no" not in ctx and ctx.get("orderNo"):
            ctx["order_no"] = ctx["orderNo"]

        log = None
        if mail_log_id:
            log = MailLog.objects.filter(id=mail_log_id).first()
        if log is None:
            log = MailLog.objects.create(
                organization=organization,
                recipient=recipient,
                template_key=template_key,
                status=MailLog.Status.QUEUED,
                context_snapshot=ctx,
            )

        try:
            resolved_tpl = self.resolve_template(
                template_key=template_key, organization=organization, context=ctx
            )
            subject = self.render_subject(resolved_tpl.subject, ctx)
            html_body = self.render_html(resolved=resolved_tpl, context=ctx)
            smtp = self.resolve_smtp(organization=organization)

            use_tls = smtp.encryption == SmtpSetting.Encryption.TLS
            use_ssl = smtp.encryption == SmtpSetting.Encryption.SSL
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=smtp.host,
                port=smtp.port,
                username=smtp.username or None,
                password=smtp.password or None,
                use_tls=use_tls,
                use_ssl=use_ssl,
                timeout=30,
                fail_silently=False,
            )
            # Console backend override for local/dev without real SMTP host.
            backend_path = getattr(settings, "EMAIL_BACKEND", "")
            if "console" in backend_path or "locmem" in backend_path or "filebased" in backend_path:
                connection = get_connection(backend=backend_path, fail_silently=False)

            from_email = formataddr((smtp.from_name, smtp.from_email))
            message = EmailMultiAlternatives(
                subject=subject,
                body=_html_to_text(html_body),
                from_email=from_email,
                to=[recipient],
                connection=connection,
            )
            message.attach_alternative(html_body, "text/html")
            message.send(fail_silently=False)

            log.subject = subject
            log.status = MailLog.Status.SENT
            log.sent_at = timezone.now()
            log.error_message = ""
            log.save(
                update_fields=["subject", "status", "sent_at", "error_message", "updated_at"]
            )
            return log
        except Exception as exc:
            logger.exception(
                "Transactional mail failed key=%s to=%s", template_key, recipient
            )
            log.status = MailLog.Status.FAILED
            log.error_message = str(exc)[:2000]
            log.save(update_fields=["status", "error_message", "updated_at"])
            return log


def _html_to_text(html: str) -> str:
    # Lightweight strip for multipart/alternative text part.
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p>", "\n\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
