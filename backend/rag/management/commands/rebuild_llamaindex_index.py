"""
重建 LlamaIndex 向量索引命令

从数据库中已索引的知识库文档重新构建 Milvus 向量索引。
支持 --clear-only 选项（仅清空索引不重建）。

使用方法:
  python manage.py rebuild_llamaindex_index         # 完全重建
  python manage.py rebuild_llamaindex_index --clear-only  # 仅清空

SpringBoot 类比: 运维工具 / 数据修复脚本。
"""

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from knowledgebase.models import Document
from rag.services.llamaindex_store_service import clear_store, sync_document


class Command(BaseCommand):
    help = "Rebuild the LlamaIndex Milvus vector store from indexed knowledgebase documents."

    def add_arguments(self, parser):
        """添加命令行参数。

        参数:
            parser: argparse ArgumentParser
        """
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Only clear the vector store without rebuilding it.",
        )

    def handle(self, *args, **options):
        """执行索引重建。

        流程:
          1. 输出当前配置的 embedding 维度
          2. 清空 Django 缓存（消除缓存不一致）
          3. 清空 Milvus 向量存储
          4. 如果不是 --clear-only 模式，对所有已索引文档重新同步
        """
        self.stdout.write(f"Embedding dimension: {settings.KB_EMBEDDING_DIMENSION}")
        cache.clear()
        clear_store()

        if options["clear_only"]:
            self.stdout.write(self.style.SUCCESS("Cleared vector store and embedding cache."))
            return

        # 遍历所有已索引状态的文档并同步到 Milvus
        documents = Document.objects.filter(status=Document.STATUS_INDEXED).order_by("id")
        indexed_count = 0
        for document in documents:
            sync_document(document)
            indexed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt vector store for {indexed_count} indexed document(s)."
            )
        )
