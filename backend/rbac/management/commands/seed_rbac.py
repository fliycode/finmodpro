"""
RBAC 数据初始化命令 — 种子填充系统角色与权限。

作用：通过 Django Management Command 机制，在部署/迁移时一键初始化
      三大系统角色（super_admin/admin/member）及其对应的权限集合。

类比 Spring Boot：
  - 本模块相当于一个实现了 `CommandLineRunner` 或 `ApplicationRunner` 的 Bean，
    在应用启动时执行数据初始化（类似 Flyway/Liquibase 的种子脚本）。
  - `--reset-system-role-permissions` 参数类似 "force reset" 开关，
    对应 Spring Boot 配置中的 `spring.sql.init.mode=always`。
"""

from django.core.management.base import BaseCommand

from rbac.services.rbac_service import ROLE_PERMISSION_MAP, seed_roles_and_permissions


class Command(BaseCommand):
    """
    Django 管理命令：seed_rbac。

    用法:
        python manage.py seed_rbac [--reset-system-role-permissions]

    选项:
        --reset-system-role-permissions: 强制重置系统角色的权限为 ROLE_PERMISSION_MAP 定义的默认值。

    类比 Spring Boot:
        相当于 `SeedRbacCommandRunner implements CommandLineRunner`，
        `run()` 方法中调用 `rbacService.seedRolesAndPermissions()`。
    """
    help = "Seed default RBAC groups and permissions."

    def add_arguments(self, parser):
        """
        声明命令行参数。

        参数:
            parser: Django 管理命令的 ArgumentParser 实例。

        类比 Spring Boot: 类似在 CommandLineRunner 中读取 `ApplicationArguments`，
            或通过 `@Option` 注解声明命令行选项。
        """
        parser.add_argument(
            "--reset-system-role-permissions",
            action="store_true",
            help="Reset built-in role permissions back to ROLE_PERMISSION_MAP defaults.",
        )

    def handle(self, *args, **options):
        """
        执行 RBAC 种子填充的主入口。

        调用 seed_roles_and_permissions 创建/更新系统角色组及其权限，
        并将结果（角色名称列表和权限总数）打印到标准输出。

        参数:
            *args:    命令行位置参数（未使用）。
            **options: 命令行选项字典，包含 --reset-system-role-permissions 布尔值。

        类比 Spring Boot: `CommandLineRunner.run(String... args)` 的实现，
            在 `ApplicationContext` 完全初始化后执行一次性数据初始化。
        """
        groups = seed_roles_and_permissions(
            reset_system_role_permissions=options["reset_system_role_permissions"]
        )
        permission_names = set()
        for values in ROLE_PERMISSION_MAP.values():
            permission_names.update(values)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded RBAC roles: {', '.join(sorted(groups.keys()))}. "
                f"Permission map count: {len(permission_names)}."
            )
        )
