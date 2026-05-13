from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils.timezone import now
from django_celery_beat.models import PeriodicTask

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from ops.models import AlertEvent, AlertRule, SystemMetric
from ops.services import evaluate_alert_rules
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class OpsMonitoringApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.admin_user = User.objects.create_user(
            username="ops-admin",
            password="secret123",
            email="ops-admin@example.com",
            is_staff=True,
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.admin_user)

    def auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.access_token}"}

    def test_seed_default_rules_endpoint_is_idempotent(self):
        first_response = self.client.post(
            "/api/monitoring/alerts/rules/seed-defaults/",
            **self.auth_headers(),
        )

        self.assertEqual(first_response.status_code, 201)
        first_payload = first_response.json()["data"]
        self.assertEqual(first_payload["created"], 4)
        self.assertEqual(first_payload["skipped"], 0)
        self.assertEqual(AlertRule.objects.count(), 4)
        self.assertTrue(
            all(
                rule.notification_channels == ["in_app"]
                for rule in AlertRule.objects.order_by("id")
            )
        )

        second_response = self.client.post(
            "/api/monitoring/alerts/rules/seed-defaults/",
            **self.auth_headers(),
        )

        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()["data"]
        self.assertEqual(second_payload["created"], 0)
        self.assertEqual(second_payload["skipped"], 4)
        self.assertEqual(AlertRule.objects.count(), 4)

    def test_seed_periodic_tasks_command_also_seeds_default_rules(self):
        call_command("seed_periodic_tasks")

        self.assertTrue(PeriodicTask.objects.filter(name="ops-collect-metrics").exists())
        self.assertTrue(PeriodicTask.objects.filter(name="ops-evaluate-alerts").exists())
        self.assertTrue(PeriodicTask.objects.filter(name="risk-expire-stale-extractions").exists())
        self.assertEqual(AlertRule.objects.count(), 4)

    def test_alert_event_api_handles_acknowledge_and_resolve_lifecycle(self):
        rule = AlertRule.objects.create(
            name="CPU Hot",
            metric_name="cpu_percent",
            condition=AlertRule.CONDITION_GTE,
            threshold=80.0,
            severity=AlertRule.SEVERITY_CRITICAL,
            enabled=True,
            notification_channels=["in_app"],
            created_by=self.admin_user,
        )

        def create_metric(value, offset_minutes):
            return SystemMetric.objects.create(
                metric_name="cpu_percent",
                value=value,
                unit="%",
                tags={},
                collected_at=now() + timedelta(minutes=offset_minutes),
            )

        create_metric(92.0, 0)
        evaluate_alert_rules()

        list_response = self.client.get(
            "/api/monitoring/alerts/events/",
            **self.auth_headers(),
        )
        self.assertEqual(list_response.status_code, 200)
        first_event = list_response.json()["data"][0]
        self.assertEqual(first_event["rule_id"], rule.id)
        self.assertEqual(first_event["status"], AlertEvent.STATUS_FIRING)
        self.assertEqual(first_event["notification_channels"], ["in_app"])

        acknowledge_response = self.client.post(
            f"/api/monitoring/alerts/events/{first_event['id']}/acknowledge/",
            **self.auth_headers(),
        )
        self.assertEqual(acknowledge_response.status_code, 200)
        self.assertEqual(
            acknowledge_response.json()["data"]["status"],
            AlertEvent.STATUS_ACKNOWLEDGED,
        )

        create_metric(95.0, 1)
        evaluate_alert_rules()

        self.assertEqual(AlertEvent.objects.count(), 1)
        event = AlertEvent.objects.get(id=first_event["id"])
        self.assertEqual(event.status, AlertEvent.STATUS_ACKNOWLEDGED)
        self.assertEqual(event.triggered_value, 95.0)

        create_metric(30.0, 2)
        evaluate_alert_rules()

        event.refresh_from_db()
        self.assertEqual(event.status, AlertEvent.STATUS_RESOLVED)
        self.assertIsNotNone(event.resolved_at)

        create_metric(91.0, 3)
        evaluate_alert_rules()

        self.assertEqual(AlertEvent.objects.count(), 2)
        latest_event = AlertEvent.objects.order_by("-id").first()
        self.assertIsNotNone(latest_event)
        self.assertEqual(latest_event.status, AlertEvent.STATUS_FIRING)

        firing_response = self.client.get(
            "/api/monitoring/alerts/events/?status=firing",
            **self.auth_headers(),
        )
        self.assertEqual(firing_response.status_code, 200)
        firing_payload = firing_response.json()["data"]
        self.assertEqual(len(firing_payload), 1)
        self.assertEqual(firing_payload[0]["id"], latest_event.id)
