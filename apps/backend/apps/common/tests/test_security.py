from django.test import SimpleTestCase, override_settings

from apps.common.security import (
    assert_safe_sql_identifier,
    refuse_dynamic_code_execution,
    refuse_shell_execution,
    sanitize_permissions,
)


class SanitizePermissionsTests(SimpleTestCase):
    def test_keeps_only_known_codes(self):
        cleaned = sanitize_permissions(
            ["catalog:read", "totally:fake", "  catalog:write  ", "catalog:read", 123]
        )
        self.assertEqual(cleaned, ["catalog:read", "catalog:write"])

    def test_empty_input(self):
        self.assertEqual(sanitize_permissions(None), [])
        self.assertEqual(sanitize_permissions([]), [])


class SqlIdentifierTests(SimpleTestCase):
    def test_accepts_safe_names(self):
        self.assertEqual(assert_safe_sql_identifier("gross_weight_gram"), "gross_weight_gram")

    def test_rejects_injection(self):
        with self.assertRaises(ValueError):
            assert_safe_sql_identifier('x"; DROP TABLE users; --')
        with self.assertRaises(ValueError):
            assert_safe_sql_identifier("a-b")


class AgencyGuardsTests(SimpleTestCase):
    def test_refuse_shell(self):
        with self.assertRaises(RuntimeError):
            refuse_shell_execution("rm", "-rf", "/")

    def test_refuse_eval(self):
        with self.assertRaises(RuntimeError):
            refuse_dynamic_code_execution("__import__('os').system('id')")


class ApiKeyPepperTests(SimpleTestCase):
    @override_settings(SECRET_KEY="test-secret", API_KEY_HASH_PEPPER="dedicated-pepper")
    def test_hash_uses_hmac_pepper(self):
        from apps.api_keys.services import hash_api_key, _legacy_hash_api_key

        raw = "tg_live_abcdef12secret"
        peppered = hash_api_key(raw)
        legacy = _legacy_hash_api_key(raw)
        self.assertNotEqual(peppered, legacy)
        self.assertEqual(len(peppered), 64)
