"""
manage.py — Django 项目管理命令行入口

所有 Django 管理命令都通过此文件执行。它设置 DJANGO_SETTINGS_MODULE 环境变量，
然后转发命令行参数给 Django 的管理命令执行器。

常用命令:
  python manage.py runserver     — 启动开发服务器
  python manage.py migrate       — 执行数据库迁移
  python manage.py test          — 运行测试
  python manage.py shell         — 打开 Django 交互式 shell
  python manage.py seed_rbac     — 初始化 RBAC 角色和权限

SpringBoot 类比: ./mvnw spring-boot:run 或 ./gradlew bootRun —
单一入口执行所有管理和运行命令。
"""

#!/usr/bin/env python3
import os
import sys


def main():
    """Django 管理命令主入口。

    设置默认配置模块 → 调用 Django 命令执行器 → 转发命令行参数。
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
