"""AuditLog record_audit() positive & anonymous-actor regression tests."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.audit.services import record_audit

User = get_user_model()


class AuditRecordTests(TestCase):
    def test_record_audit_persists_authenticated_actor_and_metadata(self) -> None:
        user = User.objects.create_user(email="aud-u@tara.local", password="pw")
        entry = record_audit(
            action="TEST_ACTION",
            entity_type="Order",
            entity_id="ORD-1",
            actor=user,
            metadata={"step": "created"},
        )
        self.assertEqual(entry.actor, user)
        self.assertEqual(entry.metadata, {"step": "created"})
        self.assertEqual(AuditLog.objects.filter(action="TEST_ACTION", entity_id="ORD-1").count(), 1)

    def test_record_audit_stores_none_for_anonymous_actor(self) -> None:
        entry = record_audit(
            action="ANON_ACTION",
            entity_type="System",
            entity_id="SYS-1",
            actor=AnonymousUser(),
        )
        self.assertIsNone(entry.actor)
