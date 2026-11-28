from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.webhooks.services import deliver_webhook_to_endpoint
from apps.webhooks.url_safety import resolve_and_validate_webhook_url, validate_webhook_url
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

    @override_settings(DEBUG=False)
    def test_delivery_pins_validated_ip_against_dns_rebinding(self):
        endpoint = SimpleNamespace(
            id="wh-1",
            url="https://rebind.example.com/hook",
            secret="supersecret",
        )
        # First getaddrinfo returns public IP 93.184.216.34; any subsequent DNS lookup would fail/rebind.
        public_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with (
            patch("apps.webhooks.url_safety.socket.getaddrinfo", return_value=public_addrinfo) as mock_dns,
            patch("apps.webhooks.services.socket.create_connection", side_effect=OSError("stop_after_pin_check")) as mock_conn,
        ):
            deliver_webhook_to_endpoint(endpoint=endpoint, event="order.created", data={"id": "1"})
            _, pinned_ip, host, port = resolve_and_validate_webhook_url("https://rebind.example.com/hook")

        self.assertEqual(mock_dns.call_count, 2)
        mock_conn.assert_called_once()
        target_addr = mock_conn.call_args[0][0]
        self.assertEqual(target_addr, ("93.184.216.34", 443))
        self.assertEqual((pinned_ip, host, port), ("93.184.216.34", "rebind.example.com", 443))
