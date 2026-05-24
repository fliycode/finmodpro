"""
回填记忆向量命令 — 为缺少 embedding 向量的 MemoryItem 记录补充向量

用于数据迁移或修复场景：当新增 embedding 功能后，已有的 MemoryItem
记录可能没有向量值，此命令为其批量生成并写入。

使用方法: python manage.py backfill_memory_embeddings

SpringBoot 类比: 数据修复批处理任务 / Flyway migration 的回填脚本。
"""

from django.core.management.base import BaseCommand

from chat.models import MemoryItem
from knowledgebase.services.embedding_service import build_dense_embedding


class Command(BaseCommand):
    help = "Backfill embedding vectors for MemoryItem records that have none."

    def handle(self, *args, **options):
        """批量回填记忆向量的主逻辑。

        筛选状态为 ACTIVE 且 embedding 为空的 MemoryItem，
        对每条记录调用 embedding 服务生成向量并写入。
        使用 .iterator() 避免一次性加载大量数据到内存。
        """
        qs = MemoryItem.objects.filter(
            status=MemoryItem.STATUS_ACTIVE,
            embedding=[],  # 只处理没有向量的记录
        )
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("All active memories already have embeddings."))
            return

        self.stdout.write(f"Backfilling embeddings for {total} memories...")
        done = 0
        errors = 0
        for memory in qs.iterator():  # 逐条迭代，节省内存
            if not memory.content:
                continue
            try:
                memory.embedding = build_dense_embedding(memory.content)
                memory.save(update_fields=["embedding"])  # 只更新 embedding 字段
                done += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(f"  Error on memory #{memory.id}: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {done} embeddings written, {errors} errors."
        ))
