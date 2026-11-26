from django.test import TestCase, override_settings

from apps.api_keys.constants import KEY_PREFIX
from apps.api_keys.services import (
    _legacy_hash_api_key,
    create_api_key,
    hash_api_key,
    verify_api_key,
)


@override_settings(SECRET_KEY="test-secret-key-for-api-keys", API_KEY_HASH_PEPPER="pepper-v1")
class ApiKeyAuthenticationTests(TestCase):
    def test_hash_and_verify_roundtrip(self):
        organization = self._make_org()
        user = self._make_user()
        api_key, plaintext = create_api_key(
            organization=organization,
            name="Integration",
            created_by=user,
            scopes=["storefront:read"],
        )
        self.assertTrue(plaintext.startswith(KEY_PREFIX))
        self.assertEqual(api_key.key_hash, hash_api_key(plaintext))
        self.assertEqual(verify_api_key(plaintext).id, api_key.id)
        self.assertIsNone(verify_api_key(plaintext + "x"))

    def test_legacy_unpeppered_hash_upgrades_on_verify(self):
        organization = self._make_org()
        user = self._make_user()
        api_key, plaintext = create_api_key(
            organization=organization,
            name="Legacy",
            created_by=user,
            scopes=["storefront:read"],
        )
        # Simulate pre-pepper storage.
        api_key.key_hash = _legacy_hash_api_key(plaintext)
        api_key.save(update_fields=["key_hash"])

        verified = verify_api_key(plaintext)
        self.assertIsNotNone(verified)
        api_key.refresh_from_db()
        self.assertEqual(api_key.key_hash, hash_api_key(plaintext))

    def _make_org(self):
        from apps.organizations.models import Organization

        return Organization.objects.create(code="TST", name="Test Org")

    def _make_user(self):
        from apps.accounts.models import User

        return User.objects.create_user(email="api@test.local", password="test-pass-1234")