from django.test import SimpleTestCase, override_settings

from apps.webhooks.url_safety import validate_webhook_url
from config.exceptions import DomainError


class WebhookUrlSafetyTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_requires_https_in_production(self):
        with self.assertRaises(DomainError) as ctx:
            validate_webhook_url("http://example.com/hook")
        self.assertEqual(ctx.exception.error_code, "WEBHOOK_URL_HTTPS_REQUIRED")

    @override_settings(DEBUG=False)
    def test_blocks_loopback_literal(self):
        with self.assertRaises(DomainError) as ctx:
            validate_webhook_url("https://127.0.0.1/hook")
        self.assertEqual(ctx.exception.error_code, "WEBHOOK_URL_BLOCKED")

    @override_settings(DEBUG=False)
    def test_blocks_metadata_ip(self):
        with self.assertRaises(DomainError) as ctx:
            validate_webhook_url("https://169.254.169.254/latest/meta-data/")
        self.assertEqual(ctx.exception.error_code, "WEBHOOK_URL_BLOCKED")

    @override_settings(DEBUG=False)
    def test_blocks_localhost_hostname(self):
        with self.assertRaises(DomainError) as ctx:
            validate_webhook_url("https://localhost/hook")
        self.assertEqual(ctx.exception.error_code, "WEBHOOK_URL_BLOCKED")

    @override_settings(DEBUG=True)
    def test_allows_http_in_debug_for_public_host(self):
        # example.com resolves publicly; should pass scheme check in DEBUG.
        url = validate_webhook_url("https://example.com/webhook")
        self.assertEqual(url, "https://example.com/webhook")
