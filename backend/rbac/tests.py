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
        member_group = Group.objects.create(name="member")
        dashboard_permission = Permission.objects.create(
            codename="view_dashboard",
            name="Can view dashboard",
            content_type=ContentType.objects.get_for_model(User),
        )
        member_group.permissions.add(dashboard_permission)
        self.user.groups.add(member_group)

        response = self.client.get(
            "/api/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.user.id)
        self.assertEqual(response.json()["username"], "alice")
        self.assertEqual(response.json()["email"], "alice@example.com")
        self.assertEqual(response.json()["groups"], ["member"])
        self.assertTrue(
            {"view_dashboard", "view_document", "ask_financial_qa"}.issubset(
                set(response.json()["permissions"])
            )
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class AuthorizationHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="charlie",
            password="secret123",
            email="charlie@example.com",
        )
        self.client = Client()
        self.access_token = generate_access_token(self.user)

    def test_user_has_permission_returns_true_for_group_permission(self):
        manager_group = Group.objects.create(name="admin")
        permission = Permission.objects.create(
            codename="view_dashboard",
            name="Can view dashboard",
            content_type=ContentType.objects.get_for_model(User),
        )
        manager_group.permissions.add(permission)
        self.user.groups.add(manager_group)

        from rbac.services.authz_service import user_has_permission

        self.assertTrue(user_has_permission(self.user, "auth.view_dashboard"))

    def test_user_has_permission_returns_false_without_named_permission(self):
        from rbac.services.authz_service import user_has_permission

        self.assertFalse(user_has_permission(self.user, "auth.view_dashboard"))

    @override_settings(ROOT_URLCONF="rbac.tests")
    def test_permission_required_allows_user_with_named_permission(self):
        manager_group = Group.objects.create(name="admin")
        permission = Permission.objects.create(
            codename="view_dashboard",
            name="Can view dashboard",
            content_type=ContentType.objects.get_for_model(User),
        )
        manager_group.permissions.add(permission)
        self.user.groups.add(manager_group)

        response = self.client.get(
            "/api/rbac/test-protected",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "ok"})

    @override_settings(ROOT_URLCONF="rbac.tests")
    def test_permission_required_rejects_user_without_named_permission(self):
        response = self.client.get(
            "/api/rbac/test-protected",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "无权限。"})


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

        self.assertEqual(users_response.status_code, 403)
        self.assertEqual(groups_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(users_response.json(), {"message": "无权限。"})
        self.assertEqual(groups_response.json(), {"message": "无权限。"})
        self.assertEqual(update_response.json(), {"message": "无权限。"})


class RbacPermissionSeedTests(TestCase):
    def test_seed_roles_and_permissions_adds_knowledgebase_and_rag_permissions(self):
        seed_roles_and_permissions()

        admin_group = Group.objects.get(name=ROLE_ADMIN)
        super_admin_group = Group.objects.get(name=ROLE_SUPER_ADMIN)
        member_group = Group.objects.get(name=ROLE_MEMBER)

        admin_permissions = set(admin_group.permissions.values_list("codename", flat=True))
        super_admin_permissions = set(
            super_admin_group.permissions.values_list("codename", flat=True)
        )
        member_permissions = set(
            member_group.permissions.values_list("codename", flat=True)
        )

        expected_all = {
            "upload_document",
            "view_document",
            "trigger_ingest",
            "ask_financial_qa",
            "view_chat_session",
            "review_risk_event",
            "manage_model_config",
            "view_evaluation",
            "run_evaluation",
            "view_audit_log",
        }

        self.assertTrue(expected_all.issubset(super_admin_permissions))
        self.assertTrue(
            {
                "upload_document",
                "view_document",
                "trigger_ingest",
                "ask_financial_qa",
                "view_chat_session",
                "review_risk_event",
                "manage_model_config",
                "view_evaluation",
                "view_audit_log",
            }.issubset(admin_permissions)
        )
        self.assertEqual(
            member_permissions.intersection(expected_all),
            {"view_document", "ask_financial_qa"},
        )

    def test_seed_roles_and_permissions_adds_delete_document_permission(self):
        groups = seed_roles_and_permissions()

        admin_permissions = set(
            groups[ROLE_ADMIN].permissions.values_list("codename", flat=True)
        )
        member_permissions = set(
            groups[ROLE_MEMBER].permissions.values_list("codename", flat=True)
        )
        super_admin_permissions = set(
            groups[ROLE_SUPER_ADMIN].permissions.values_list("codename", flat=True)
        )

        self.assertIn("delete_document", admin_permissions)
        self.assertIn("delete_document", super_admin_permissions)
        self.assertNotIn("delete_document", member_permissions)
