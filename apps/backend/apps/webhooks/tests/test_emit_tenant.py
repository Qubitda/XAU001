from unittest.mock import patch

from django.test import TestCase

from apps.organizations.models import Organization
from apps.webhooks.models import WebhookEndpoint
from apps.webhooks.services import emit_webhook_event


class EmitWebhookTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="AAA", name="Org A")
        self.org_b = Organization.objects.create(code="BBB", name="Org B")
        self.ep_a = WebhookEndpoint.objects.create(
            organization=self.org_a,
            is_platform=False,
            url="https://example.com/a",
            secret="a" * 64,
            events=["b2b.order.created", "b2c.order.created"],
            is_active=True,
        )
        self.ep_b = WebhookEndpoint.objects.create(
            organization=self.org_b,
            is_platform=False,
            url="https://example.com/b",
            secret="b" * 64,
            events=["b2c.order.created", "b2b.order.created"],
            is_active=True,
        )
        self.ep_platform = WebhookEndpoint.objects.create(
            organization=None,
            is_platform=True,
            url="https://example.com/platform",
            secret="c" * 64,
            events=["b2c.order.created"],
            is_active=True,
        )

    @patch("apps.webhooks.services.schedule_webhook_delivery")
    def test_b2c_only_hits_platform_endpoints(self, schedule):
        emit_webhook_event(
            "b2c.order.created",
            {"orderNo": "B2C-1"},
            platform=True,
        )
        scheduled_ids = {call.args[0] for call in schedule.call_args_list}
        self.assertEqual(scheduled_ids, {str(self.ep_platform.id)})

    @patch("apps.webhooks.services.schedule_webhook_delivery")
    def test_b2b_only_hits_that_organization(self, schedule):
        emit_webhook_event(
            "b2b.order.created",
            {"orderNo": "B2B-1"},
            organization_id=self.org_a.id,
        )
        scheduled_ids = {call.args[0] for call in schedule.call_args_list}
        self.assertEqual(scheduled_ids, {str(self.ep_a.id)})

    @patch("apps.webhooks.services.schedule_webhook_delivery")
    def test_missing_org_refuses_fanout(self, schedule):
        emit_webhook_event("b2b.order.created", {"orderNo": "X"})
        schedule.assert_not_called()
