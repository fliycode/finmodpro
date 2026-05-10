import json

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.test import Client, TestCase, override_settings
from django.urls import path

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from rbac.services.authz_service import permission_required
from rbac.services.rbac_service import (
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_SUPER_ADMIN,
    seed_roles_and_permissions,
)


@permission_required("auth.view_dashboard")
def protected_dashboard_view(request):
    return JsonResponse({"message": "ok"})


urlpatterns = [
    path("api/rbac/test-protected", protected_dashboard_view),
]


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RbacApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice",
            password="secret123",
            email="alice@example.com",
        )
        self.access_token = generate_access_token(self.user)

    def test_get_me_returns_rbac_profile_for_authenticated_user(self):
        seed_roles_and_permissions()
        member_group = Group.objects.get(name=ROLE_MEMBER)
        self.user.groups.add(member_group)

        response = self.client.get(
            "/api/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.user.id)
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["email"], "alice@example.com")
        self.assertEqual(data["groups"], ["member"])
        self.assertTrue(
            {"view_dashboard", "view_document", "ask_financial_qa"}.issubset(
                set(data["permissions"])
            )
        )
        self.assertIn("date_joined", data)
        self.assertIn("stats", data)
        self.assertIn("question_count", data["stats"])
        self.assertIn("question_count_today", data["stats"])
        self.assertIn("document_count", data["stats"])
        self.assertIn("usage_days", data["stats"])

    def test_patch_me_updates_username_and_email(self):
        seed_roles_and_permissions()
        self.user.groups.add(Group.objects.get(name=ROLE_MEMBER))

        response = self.client.patch(
            "/api/auth/me",
            data=json.dumps({"username": "alice-updated", "email": "new@example.com"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], "alice-updated")
        self.assertEqual(data["email"], "new@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "alice-updated")
        self.assertEqual(self.user.email, "new@example.com")

    def test_patch_me_rejects_duplicate_username(self):
        seed_roles_and_permissions()
        User.objects.create_user(username="taken", password="secret123", email="taken@example.com")

        response = self.client.patch(
            "/api/auth/me",
            data=json.dumps({"username": "taken", "email": "alice@example.com"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("用户名", response.json()["message"])

    def test_change_password_with_valid_old_password(self):
        response = self.client.post(
            "/api/auth/me/password",
            data=json.dumps({"old_password": "secret123", "new_password": "newpass456"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "密码已修改。")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))

    def test_change_password_rejects_wrong_old_password(self):
        response = self.client.post(
            "/api/auth/me/password",
            data=json.dumps({"old_password": "wrong", "new_password": "newpass456"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("旧密码", response.json()["message"])


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class AdminManagementApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="admin-user",
            password="secret123",
            email="admin@example.com",
            is_staff=True,
        )
        self.super_admin_user = User.objects.create_user(
            username="root-user",
            password="secret123",
            email="root@example.com",
            is_staff=True,
            is_superuser=True,
        )
        self.member_user = User.objects.create_user(
            username="member-user",
            password="secret123",
            email="member@example.com",
        )
        self.target_user = User.objects.create_user(
            username="target-user",
            password="secret123",
            email="target@example.com",
        )

        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.super_admin_user.groups.add(Group.objects.get(name=ROLE_SUPER_ADMIN))
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.target_user.groups.add(Group.objects.get(name=ROLE_MEMBER))

        self.admin_access_token = generate_access_token(self.admin_user)
        self.super_admin_access_token = generate_access_token(self.super_admin_user)
        self.member_access_token = generate_access_token(self.member_user)

    def test_get_admin_users_requires_view_user_and_returns_rbac_aware_rows(self):
        response = self.client.get(
            "/api/admin/users",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 4)
        self.assertEqual(
            response.json()[0],
            {
                "id": self.admin_user.id,
                "username": "admin-user",
                "email": "admin@example.com",
                "groups": [ROLE_ADMIN],
                "permissions": [
                    "add_user",
                    "ask_financial_qa",
                    "change_user",
                    "delete_document",
                    "manage_model_config",
                    "review_risk_event",
                    "trigger_ingest",
                    "upload_document",
                    "view_audit_log",
                    "view_chat_session",
                    "view_dashboard",
                    "view_document",
                    "view_evaluation",
                    "view_role",
                    "view_user",
                ],
                "is_superuser": False,
                "is_staff": True,
                "date_joined": self.admin_user.date_joined.isoformat(),
            },
        )

    def test_get_admin_groups_requires_view_role_and_returns_available_groups(self):
        response = self.client.get(
            "/api/admin/groups",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"id": Group.objects.get(name=ROLE_ADMIN).id, "name": ROLE_ADMIN},
                {"id": Group.objects.get(name=ROLE_MEMBER).id, "name": ROLE_MEMBER},
                {
                    "id": Group.objects.get(name=ROLE_SUPER_ADMIN).id,
                    "name": ROLE_SUPER_ADMIN,
                },
            ],
        )

    def test_put_admin_user_groups_requires_assign_role_and_replaces_group_set(self):
        response = self.client.put(
            f"/api/admin/users/{self.target_user.id}/groups",
            data=json.dumps({"groups": [ROLE_ADMIN, ROLE_MEMBER]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertEqual(
            sorted(self.target_user.groups.values_list("name", flat=True)),
            [ROLE_ADMIN, ROLE_MEMBER],
        )
        self.assertEqual(
            response.json(),
            {
                "id": self.target_user.id,
                "username": "target-user",
                "email": "target@example.com",
                "groups": [ROLE_ADMIN, ROLE_MEMBER],
                "permissions": [
                    "add_user",
                    "ask_financial_qa",
                    "change_user",
                    "delete_document",
                    "manage_model_config",
                    "review_risk_event",
                    "trigger_ingest",
                    "upload_document",
                    "view_audit_log",
                    "view_chat_session",
                    "view_dashboard",
                    "view_document",
                    "view_evaluation",
                    "view_role",
                    "view_user",
                ],
                "is_superuser": False,
                "is_staff": False,
                "date_joined": self.target_user.date_joined.isoformat(),
            },
        )

    def test_post_admin_users_creates_user_and_assigns_groups(self):
        response = self.client.post(
            "/api/admin/users",
            data=json.dumps(
                {
                    "username": "new-analyst",
                    "email": "new-analyst@example.com",
                    "password": "secret123",
                    "groups": [ROLE_MEMBER],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 201)
        created_user = User.objects.get(username="new-analyst")
        self.assertEqual(created_user.email, "new-analyst@example.com")
        self.assertEqual(
            list(created_user.groups.values_list("name", flat=True)),
            [ROLE_MEMBER],
        )
        self.assertEqual(response.json()["username"], "new-analyst")

    def test_patch_admin_user_detail_updates_profile_fields_and_groups(self):
        response = self.client.patch(
            f"/api/admin/users/{self.target_user.id}",
            data=json.dumps(
                {
                    "username": "target-user-updated",
                    "email": "target-updated@example.com",
                    "password": "",
                    "groups": [ROLE_ADMIN],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.username, "target-user-updated")
        self.assertEqual(self.target_user.email, "target-updated@example.com")
        self.assertEqual(
            list(self.target_user.groups.values_list("name", flat=True)),
            [ROLE_ADMIN],
        )

    def test_delete_admin_user_detail_removes_target_user(self):
        response = self.client.delete(
            f"/api/admin/users/{self.target_user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())
        self.assertEqual(response.json(), {"message": "用户已删除。"})

    def test_delete_admin_user_detail_rejects_current_user(self):
        response = self.client.delete(
            f"/api/admin/users/{self.super_admin_user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "不能删除当前登录用户。"})

    def test_member_receives_403_on_admin_apis(self):
        users_response = self.client.get(
            "/api/admin/users",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )
        groups_response = self.client.get(
            "/api/admin/groups",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )
        update_response = self.client.put(
            f"/api/admin/users/{self.target_user.id}/groups",
            data=json.dumps({"groups": [ROLE_MEMBER]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )
        create_response = self.client.post(
            "/api/admin/users",
            data=json.dumps(
                {
                    "username": "forbidden-user",
                    "email": "forbidden@example.com",
                    "password": "secret123",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )
        delete_response = self.client.delete(
            f"/api/admin/users/{self.target_user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(users_response.status_code, 403)
        self.assertEqual(groups_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertEqual(users_response.json(), {"message": "无权限。"})
        self.assertEqual(groups_response.json(), {"message": "无权限。"})
        self.assertEqual(update_response.json(), {"message": "无权限。"})
        self.assertEqual(create_response.json(), {"message": "无权限。"})
        self.assertEqual(delete_response.json(), {"message": "无权限。"})
