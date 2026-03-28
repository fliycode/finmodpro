from django.test import Client, TestCase


class HealthApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_returns_service_status_environment_and_timestamp(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "finmodpro-backend")
        self.assertIn("environment", payload)
        self.assertIn("timestamp", payload)
