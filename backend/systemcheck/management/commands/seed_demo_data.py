"""
播种演示数据命令 — 为开发/演示环境创建预置示例数据

使用方法: python manage.py seed_demo_data

SpringBoot 类比: CommandLineRunner 实现，在应用启动后执行一次数据初始化。
"""

from django.core.management.base import BaseCommand

from systemcheck.services.demo_data_service import seed_demo_data


class Command(BaseCommand):
    help = "Seed repeatable demo data for the FinModPro demo flow."

    def handle(self, *args, **options):
        """执行演示数据播种并输出结果摘要。

        调用 seed_demo_data() 创建演示用户、文档、聊天和风险数据，
        然后打印创建的各实体数量和默认密码。
        """
        summary = seed_demo_data()
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo data. "
                f"Users: {', '.join(summary['users'])}. "
                f"Documents: {len(summary['documents'])}. "
                f"Chat session: {summary['chat_session_id']}. "
                f"Risk events: {len(summary['risk_event_ids'])}. "
                f"Risk report: {summary['risk_report_id']}. "
                f"Default password: {summary['default_password']}"
            )
        )
