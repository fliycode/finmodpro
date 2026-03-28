from django.test import Client, TestCase


class HealthApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_returns_unified_response_payload(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["status"], "ok")
        self.assertEqual(payload["data"]["service"], "finmodpro-backend")
        self.assertIn("environment", payload["data"])
        self.assertIn("timestamp", payload["data"])
