import json

from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from unittest.mock import patch

from authentication.models import User
from authentication.services.jwt_service import decode_access_token
from rbac.services.rbac_service import seed_roles_and_permissions


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_creates_user_and_returns_access_token(self):
        response = self.client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "username": "alice",
                    "password": "secret123",
                    "email": "alice@example.com",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["message"], "注册成功。")
        self.assertEqual(payload["access_token_type"], "Bearer")
        self.assertIn("access_token", payload)
        self.assertEqual(payload["user"]["username"], "alice")
        self.assertEqual(payload["user"]["email"], "alice@example.com")

        claims = decode_access_token(payload["access_token"])
        self.assertEqual(claims["sub"], "alice")
        self.assertEqual(claims["user_id"], payload["user"]["id"])

    def test_register_adds_new_user_to_member_group(self):
        Group.objects.create(name="member")

        response = self.client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "username": "bob",
                    "password": "secret123",
                    "email": "bob@example.com",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], "bob")
        self.assertEqual(
            Group.objects.get(name="member").user_set.filter(username="bob").count(),
            1,
        )

    def test_login_returns_access_token_for_valid_credentials(self):
        self.client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "username": "alice",
                    "password": "secret123",
                    "email": "alice@example.com",
                }
            ),
            content_type="application/json",
        )

        response = self.client.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "username": "alice",
                    "password": "secret123",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["message"], "登录成功。")
        self.assertEqual(payload["access_token_type"], "Bearer")
        self.assertIn("access_token", payload)
        self.assertEqual(payload["user"]["username"], "alice")

        claims = decode_access_token(payload["access_token"])
        self.assertEqual(claims["sub"], "alice")

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "username": "alice",
                    "password": "wrong-password",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "用户名或密码错误。")

    def test_login_bootstraps_staff_user_rbac_for_permission_gated_modules(self):
        seed_roles_and_permissions()
        staff_user = User.objects.create_user(
            username="ops-admin",
            password="secret123",
            email="ops-admin@example.com",
            is_staff=True,
        )

        login_response = self.client.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "username": "ops-admin",
                    "password": "secret123",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(login_response.status_code, 200)
        access_token = login_response.json()["access_token"]

        staff_user.refresh_from_db()
        self.assertEqual(
            sorted(staff_user.groups.values_list("name", flat=True)),
            ["admin"],
        )

        profile_response = self.client.get(
            "/api/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.json()["groups"], ["admin"])
        self.assertTrue(
            {
                "view_dashboard",
                "view_document",
                "ask_financial_qa",
                "manage_model_config",
                "view_evaluation",
            }.issubset(set(profile_response.json()["permissions"]))
        )

        for path in (
            "/api/dashboard/stats",
            "/api/knowledgebase/documents",
            "/api/ops/model-configs",
            "/api/ops/evaluations",
            "/api/risk/events",
        ):
            with self.subTest(path=path):
                response = self.client.get(
                    path,
                    HTTP_AUTHORIZATION=f"Bearer {access_token}",
                )
                self.assertNotIn(response.status_code, {401, 403})

    def test_login_binds_existing_role_group_without_reseeding_rbac_permissions(self):
        Group.objects.bulk_create(
            [
                Group(name="member"),
                Group(name="admin"),
                Group(name="super_admin"),
            ],
            ignore_conflicts=True,
        )
        staff_user = User.objects.create_user(
            username="ops-admin-lite",
            password="secret123",
            email="ops-admin-lite@example.com",
            is_staff=True,
        )

        with patch(
            "rbac.services.rbac_service.seed_roles_and_permissions",
            side_effect=AssertionError("login should not reseed RBAC permissions"),
        ):
            login_response = self.client.post(
                "/api/auth/login",
                data=json.dumps(
                    {
                        "username": "ops-admin-lite",
                        "password": "secret123",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(login_response.status_code, 200)
        staff_user.refresh_from_db()
        self.assertEqual(
            sorted(staff_user.groups.values_list("name", flat=True)),
            ["admin"],
        )
