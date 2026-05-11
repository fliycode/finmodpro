import json
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from unittest.mock import patch

from authentication.models import User
from authentication.controllers.auth_controller import (
    forgot_password_view,
    login_view,
    logout_view,
    refresh_view,
    register_view,
    reset_password_view,
)
from authentication.services.refresh_session_service import (
    RefreshSessionError,
    create_refresh_session,
    rotate_refresh_session,
)
from authentication.services.jwt_service import decode_access_token, generate_access_token
from authentication.services.password_reset_service import (
    PasswordResetError,
    create_reset_token,
    reset_password,
    validate_reset_token,
)
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
        self.assertEqual(payload["expires_in"], 3600)
        self.assertEqual(payload["user"]["username"], "alice")

        claims = decode_access_token(payload["access_token"])
        self.assertEqual(claims["sub"], "alice")

    @override_settings(
        JWT_SECRET_KEY="test-jwt-secret",
        JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
        AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS=7 * 24 * 60 * 60,
    )
    def test_login_sets_persistent_refresh_cookie_when_remember_me_enabled(self):
        self.client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "username": "remembered-user",
                    "password": "secret123",
                    "email": "remembered@example.com",
                }
            ),
            content_type="application/json",
        )

        response = self.client.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "username": "remembered-user",
                    "password": "secret123",
                    "remember_me": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["expires_in"], 3600)
        self.assertEqual(
            response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]["max-age"],
            7 * 24 * 60 * 60,
        )

        claims = decode_access_token(payload["access_token"])
        self.assertEqual(claims["sub"], "remembered-user")
        self.assertEqual(claims["exp"] - claims["iat"], 3600)

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


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    JWT_REMEMBER_ME_LIFETIME_SECONDS=7 * 24 * 60 * 60,
)
class JwtLifetimeTests(SimpleTestCase):
    def test_generate_access_token_accepts_custom_lifetime(self):
        claims = decode_access_token(
            generate_access_token(
                type("UserStub", (), {"id": 99, "username": "remembered-user"})(),
                lifetime_seconds=7 * 24 * 60 * 60,
            )
        )

        self.assertEqual(claims["sub"], "remembered-user")
        self.assertEqual(claims["user_id"], 99)
        self.assertEqual(claims["exp"] - claims["iat"], 7 * 24 * 60 * 60)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    AUTH_REFRESH_TOKEN_LIFETIME_SECONDS=24 * 60 * 60,
    AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS=7 * 24 * 60 * 60,
)
class RefreshSessionServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_rotate_refresh_session_returns_new_cookie_value(self):
        cookie_value, _ = create_refresh_session(user_id=7, remember_me=True)

        rotated_cookie_value, session_record = rotate_refresh_session(cookie_value)

        self.assertNotEqual(rotated_cookie_value, cookie_value)
        self.assertEqual(session_record["user_id"], 7)
        self.assertEqual(session_record["remember_me"], True)

    def test_rotate_refresh_session_rejects_previous_secret_reuse(self):
        cookie_value, _ = create_refresh_session(user_id=7, remember_me=False)
        rotated_cookie_value, _ = rotate_refresh_session(cookie_value)

        with self.assertRaises(RefreshSessionError):
            rotate_refresh_session(cookie_value)

        with self.assertRaises(RefreshSessionError):
            rotate_refresh_session(rotated_cookie_value)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=900,
    AUTH_REFRESH_COOKIE_NAME="finmodpro_refresh",
    AUTH_REFRESH_COOKIE_PATH="/api/auth",
    AUTH_REFRESH_COOKIE_SAMESITE="Lax",
    AUTH_REFRESH_COOKIE_SECURE=False,
    AUTH_REFRESH_TOKEN_LIFETIME_SECONDS=24 * 60 * 60,
    AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS=7 * 24 * 60 * 60,
)
class AuthenticationCookieResponseTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("authentication.controllers.auth_controller.build_user_summary")
    @patch("authentication.controllers.auth_controller.create_refresh_session")
    def test_login_sets_session_cookie_without_max_age_by_default(
        self,
        create_refresh_session_mock,
        build_user_summary_mock,
    ):
        request = self.factory.post(
            "/api/auth/login",
            data=json.dumps({"username": "alice", "password": "secret123"}),
            content_type="application/json",
        )
        create_refresh_session_mock.return_value = (
            "refresh-cookie",
            {"remember_me": False},
        )
        build_user_summary_mock.return_value = {
            "id": 1,
            "username": "alice",
            "email": "alice@example.com",
        }

        with patch(
            "authentication.controllers.auth_controller.authenticate_user",
            return_value=SimpleNamespace(id=1, username="alice", email="alice@example.com"),
        ):
            response = login_view(request)

        cookie = response.cookies["finmodpro_refresh"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cookie.value, "refresh-cookie")
        self.assertEqual(cookie["path"], "/api/auth")
        self.assertEqual(cookie["max-age"], "")

    @patch("authentication.controllers.auth_controller.build_user_summary")
    def test_register_does_not_set_refresh_cookie(
        self,
        build_user_summary_mock,
    ):
        request = self.factory.post(
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
        build_user_summary_mock.return_value = {
            "id": 1,
            "username": "alice",
            "email": "alice@example.com",
        }

        with patch(
            "authentication.controllers.auth_controller.username_exists",
            return_value=False,
        ), patch(
            "authentication.controllers.auth_controller.register_user",
            return_value=SimpleNamespace(id=1, username="alice", email="alice@example.com"),
        ):
            response = register_view(request)

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("finmodpro_refresh", response.cookies)

    @patch("authentication.controllers.auth_controller.build_user_summary")
    @patch("authentication.controllers.auth_controller.create_refresh_session")
    def test_login_sets_persistent_cookie_when_remember_me_enabled(
        self,
        create_refresh_session_mock,
        build_user_summary_mock,
    ):
        request = self.factory.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "username": "alice",
                    "password": "secret123",
                    "remember_me": True,
                }
            ),
            content_type="application/json",
        )
        create_refresh_session_mock.return_value = (
            "refresh-cookie",
            {"remember_me": True},
        )
        build_user_summary_mock.return_value = {
            "id": 1,
            "username": "alice",
            "email": "alice@example.com",
        }

        with patch(
            "authentication.controllers.auth_controller.authenticate_user",
            return_value=SimpleNamespace(id=1, username="alice", email="alice@example.com"),
        ):
            response = login_view(request)

        cookie = response.cookies["finmodpro_refresh"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cookie["max-age"], 7 * 24 * 60 * 60)

    @patch("authentication.controllers.auth_controller.get_user_by_id")
    @patch("authentication.controllers.auth_controller.rotate_refresh_session")
    def test_refresh_rotates_cookie_and_returns_new_access_token(
        self,
        rotate_refresh_session_mock,
        get_user_by_id_mock,
    ):
        request = self.factory.post("/api/auth/refresh")
        request.COOKIES["finmodpro_refresh"] = "old-cookie"
        rotate_refresh_session_mock.return_value = (
            "new-cookie",
            {"user_id": 9, "remember_me": True},
        )
        get_user_by_id_mock.return_value = SimpleNamespace(
            id=9,
            username="alice",
            email="alice@example.com",
        )

        response = refresh_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["finmodpro_refresh"].value, "new-cookie")
        self.assertIn("access_token", json.loads(response.content))

    @patch("authentication.controllers.auth_controller.revoke_refresh_session")
    def test_logout_revokes_cookie_and_clears_browser_cookie(self, revoke_refresh_session_mock):
        request = self.factory.post("/api/auth/logout")
        request.COOKIES["finmodpro_refresh"] = "cookie-to-revoke"

        response = logout_view(request)

        revoke_refresh_session_mock.assert_called_once_with("cookie-to-revoke")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["finmodpro_refresh"]["max-age"], 0)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS=1800,
)
class PasswordResetServiceTests(TestCase):
    def test_create_reset_token_raises_for_unknown_username(self):
        with self.assertRaises(PasswordResetError):
            create_reset_token(username="nonexistent")

    def test_create_reset_token_returns_raw_token_and_lifetime(self):
        User.objects.create_user(username="alice", password="secret123")
        raw_token, lifetime = create_reset_token(username="alice")
        self.assertIsInstance(raw_token, str)
        self.assertTrue(len(raw_token) > 20)
        self.assertEqual(lifetime, 1800)

    def test_validate_reset_token_returns_record_for_valid_token(self):
        User.objects.create_user(username="alice", password="secret123")
        raw_token, _ = create_reset_token(username="alice")
        record = validate_reset_token(token=raw_token)
        self.assertEqual(record.user.username, "alice")
        self.assertFalse(record.used)

    def test_validate_reset_token_rejects_invalid_token(self):
        with self.assertRaises(PasswordResetError):
            validate_reset_token(token="invalid-token")

    def test_validate_reset_token_rejects_used_token(self):
        User.objects.create_user(username="alice", password="secret123")
        raw_token, _ = create_reset_token(username="alice")
        reset_password(token=raw_token, new_password="newpass123")
        with self.assertRaises(PasswordResetError):
            validate_reset_token(token=raw_token)

    def test_create_reset_token_invalidates_previous_tokens(self):
        User.objects.create_user(username="alice", password="secret123")
        first_token, _ = create_reset_token(username="alice")
        create_reset_token(username="alice")
        with self.assertRaises(PasswordResetError):
            validate_reset_token(token=first_token)

    def test_reset_password_changes_user_password(self):
        user = User.objects.create_user(username="alice", password="secret123")
        raw_token, _ = create_reset_token(username="alice")
        result_user = reset_password(token=raw_token, new_password="newpass123")
        self.assertEqual(result_user.id, user.id)
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpass123"))

    def test_reset_password_marks_token_as_used(self):
        User.objects.create_user(username="alice", password="secret123")
        raw_token, _ = create_reset_token(username="alice")
        reset_password(token=raw_token, new_password="newpass123")
        from authentication.models import PasswordResetToken
        token_hash = PasswordResetToken.objects.get(user__username="alice")
        self.assertTrue(token_hash.used)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS=1800,
)
class PasswordResetApiTests(TestCase):
    def test_forgot_password_returns_reset_token(self):
        User.objects.create_user(username="alice", password="secret123")
        response = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("reset_token", payload)
        self.assertEqual(payload["expires_in"], 1800)

    def test_forgot_password_rejects_unknown_username(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"username": "nonexistent"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("不存在", response.json()["message"])

    def test_forgot_password_rejects_missing_username(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_password_with_valid_token(self):
        User.objects.create_user(username="alice", password="secret123")
        token_resp = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
        )
        reset_token = token_resp.json()["reset_token"]

        response = self.client.post(
            "/api/auth/reset-password",
            data=json.dumps({"token": reset_token, "new_password": "newpass123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("已重置", response.json()["message"])

        login_resp = self.client.post(
            "/api/auth/login",
            data=json.dumps({"username": "alice", "password": "newpass123"}),
            content_type="application/json",
        )
        self.assertEqual(login_resp.status_code, 200)

    def test_reset_password_rejects_invalid_token(self):
        response = self.client.post(
            "/api/auth/reset-password",
            data=json.dumps({"token": "bad-token", "new_password": "newpass123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_password_rejects_short_password(self):
        User.objects.create_user(username="alice", password="secret123")
        token_resp = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
        )
        reset_token = token_resp.json()["reset_token"]

        response = self.client.post(
            "/api/auth/reset-password",
            data=json.dumps({"token": reset_token, "new_password": "short"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("8位", response.json()["message"])

    def test_reset_password_rejects_used_token(self):
        User.objects.create_user(username="alice", password="secret123")
        token_resp = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
        )
        reset_token = token_resp.json()["reset_token"]

        self.client.post(
            "/api/auth/reset-password",
            data=json.dumps({"token": reset_token, "new_password": "newpass123"}),
            content_type="application/json",
        )

        response = self.client.post(
            "/api/auth/reset-password",
            data=json.dumps({"token": reset_token, "new_password": "another123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_forgot_password_rejects_invalid_json(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_password_rejects_invalid_json(self):
        response = self.client.post(
            "/api/auth/reset-password",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
