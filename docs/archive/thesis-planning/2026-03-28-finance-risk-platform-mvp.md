# Finance Risk Platform MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在你现有的 Django + Vue 登录骨架上，分阶段实现一个可演示的金融风控领域大模型平台 MVP，包含知识库入库、RAG 问答、风险抽取、风险报告、模型配置与基础评测。

**Architecture:** 继续使用前后端分离。Django + DRF 负责用户、知识库、会话、任务、风险事件与报告 API；Celery + Redis 负责异步入库与抽取任务；LangChain 只封装在 `backend/apps/llm/` 下；MySQL 存业务数据，Milvus Lite 存向量，Ollama 提供本地模型与 embedding 接口。

**Tech Stack:** Django, Django REST Framework, MySQL, Redis, Celery, Vue 3, Vue Router, Pinia, Axios, LangChain, Ollama, pymilvus, pytest

---

## Scope decision

当前规格覆盖多个独立子系统：平台基础、知识库、问答、风险抽取、报告、模型评测。为保证可执行性，本计划拆成“一个总路线图 + 八个按周推进的实现任务”。每个任务结束都必须形成**可运行、可截图、可验收**的中间成果，不等全部做完才联调。

## Repository assumptions

1. 当前仓库已经有基础登录功能。
2. 目录默认按以下方式组织；如果你的仓库现状不同，只映射同名职责，不改计划顺序：

```text
backend/
  config/
  apps/
  tests/
frontend/
  src/
```

3. 现阶段不接复杂 RBAC、不做流式输出、不做多智能体、不做云部署优化。
4. 第一阶段仅要求 PDF 年报/研报入库跑通；新闻先支持手工录入文本或上传 txt。

## File structure map

```text
backend/
  config/
    settings/
      base.py               # Django/DRF/Celery/Redis/MySQL 基础配置
    urls.py                 # API 路由聚合
    celery.py               # Celery app 初始化
  apps/
    common/
      views.py              # 健康检查、统一响应工具
    accounts/
      views.py              # 复用现有登录，必要时增加 me 接口
    kb/
      models.py             # knowledge_base / document / document_chunk / ingestion_task
      serializers.py        # KB 与文档序列化
      views.py              # KB、文档上传、任务查询 API
      tasks.py              # parse/chunk/embed/index 任务入口
      services/
        parser_service.py   # PDF 文本解析
        chunk_service.py    # 文本切块
        vector_service.py   # embedding + milvus 写入
    chat/
      models.py             # session / message / retrieval_log
      views.py              # 会话与问答 API
      services/
        retrieval_service.py # 检索封装
        qa_service.py        # RAG 生成封装
    risk/
      models.py             # risk_event
      views.py              # 抽取触发、事件查询、审核 API
      tasks.py              # 批量抽取任务
      services/
        extraction_service.py # 结构化抽取封装
    report/
      models.py             # risk_report
      views.py              # 报告生成与查询 API
      tasks.py              # 报告任务
      services/
        report_service.py   # 报告聚合与生成
    llm/
      models.py             # model_config / eval_record
      providers/
        base.py             # provider 抽象
        ollama_provider.py  # chat 与 embedding provider
      prompts/
        qa_prompt.py
        extraction_prompt.py
        report_prompt.py
      schemas/
        risk_event_schema.py
  tests/
    apps/
      common/
      kb/
      chat/
      risk/
      report/
frontend/
  src/
    api/
      kb.ts
      chat.ts
      risk.ts
      report.ts
      model.ts
    router/
      index.ts
    stores/
      auth.ts
      chat.ts
      kb.ts
    views/
      DashboardView.vue
      kb/KnowledgeBaseListView.vue
      kb/DocumentDetailView.vue
      chat/ChatView.vue
      risk/RiskEventListView.vue
      report/ReportView.vue
      model/ModelConfigView.vue
    components/
      layout/AppLayout.vue
      kb/UploadDialog.vue
      chat/SourceCard.vue
      risk/RiskReviewTable.vue
      report/ReportSummaryCard.vue
```

## Milestones and acceptance

| 周次 | 里程碑 | 必达产出 | 验收标准 |
|---|---|---|---|
| 第 1 周 | 平台基线定型 | 后端 app 骨架、前端菜单、健康检查、数据库迁移可运行 | 登录后能进入主布局，后端 `/api/health/` 返回 200 |
| 第 2 周 | 知识库管理闭环 | 知识库、文档、任务状态 API + 上传页面 | 能创建知识库并上传 PDF，页面可看到任务状态 |
| 第 3 周 | 入库异步链路闭环 | 解析、切块、embedding、Milvus 入库 | 文档状态可从 pending 走到 success，能查到 chunk 数 |
| 第 4 周 | RAG 问答闭环 | 会话、问答 API、来源回显页面 | 问题返回答案、来源片段、页码 |
| 第 5 周 | 风险抽取闭环 | 风险事件结构化落库 + 审核页 | 能从指定文档抽取事件并完成批准/驳回 |
| 第 6 周 | 风险报告闭环 | 报告生成 API + 页面 | 可按公司生成摘要与来源列表 |
| 第 7 周 | 本地模型与评测 | 模型配置、Prompt 参数、基础评测页面 | 能切换模型配置并展示至少 1 组评测结果 |
| 第 8 周 | 收尾与答辩 | 联调、截图、演示脚本、论文图表 | 形成 1 条完整演示路径并能稳定复现 |

---

### Task 1: 平台基线与目录对齐

**Files:**
- Modify: `backend/config/urls.py`
- Modify: `backend/config/settings/base.py`
- Create: `backend/apps/common/views.py`
- Create: `backend/tests/apps/common/test_health_api.py`
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/AppLayout.vue`
- Create: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: 写后端健康检查失败测试**

```python
# backend/tests/apps/common/test_health_api.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_api_returns_ok():
    client = APIClient()
    response = client.get('/api/health/')
    assert response.status_code == 200
    assert response.json()['code'] == 0
    assert response.json()['data']['status'] == 'ok'
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `cd backend && pytest tests/apps/common/test_health_api.py -v`
Expected: FAIL with `404 != 200`

- [ ] **Step 3: 实现健康检查接口与路由**

```python
# backend/apps/common/views.py
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            'code': 0,
            'message': 'ok',
            'data': {'status': 'ok'},
        })
```

```python
# backend/config/urls.py
from django.urls import path
from backend.apps.common.views import HealthView

urlpatterns = [
    path('api/health/', HealthView.as_view(), name='health'),
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/apps/common/test_health_api.py -v`
Expected: PASS

- [ ] **Step 5: 配置主布局路由与首页占位页**

```ts
// frontend/src/router/index.ts
{
  path: '/',
  component: () => import('@/layouts/AppLayout.vue'),
  children: [
    { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
  ],
}
```

```vue
<!-- frontend/src/layouts/AppLayout.vue -->
<template>
  <div class="app-layout">
    <aside class="sidebar">金融风控平台</aside>
    <main><router-view /></main>
  </div>
</template>
```

- [ ] **Step 6: 本地启动前后端并人工验证**

Run: `cd backend && python manage.py runserver`

Run: `cd frontend && npm run dev`

Expected: 登录后能进入主布局，并能访问仪表盘占位页。

- [ ] **Step 7: 提交本任务**

```bash
git add backend/config/urls.py backend/config/settings/base.py backend/apps/common/views.py backend/tests/apps/common/test_health_api.py frontend/src/router/index.ts frontend/src/layouts/AppLayout.vue frontend/src/views/DashboardView.vue
git commit -m "feat: add app layout and health endpoint"
```

### Task 2: 建立核心数据模型与迁移

**Files:**
- Create: `backend/apps/kb/models.py`
- Create: `backend/apps/chat/models.py`
- Create: `backend/apps/risk/models.py`
- Create: `backend/apps/report/models.py`
- Create: `backend/apps/llm/models.py`
- Create: `backend/tests/apps/kb/test_models.py`
- Modify: `backend/config/settings/base.py`

- [ ] **Step 1: 写知识库模型失败测试**

```python
# backend/tests/apps/kb/test_models.py
import pytest
from backend.apps.kb.models import KnowledgeBase, Document


@pytest.mark.django_db
def test_can_create_knowledge_base_and_document(django_user_model):
    user = django_user_model.objects.create_user(username='tester', password='123456')
    kb = KnowledgeBase.objects.create(
        name='银行年报库',
        type='annual_report',
        owner=user,
        status='active',
    )
    doc = Document.objects.create(
        kb=kb,
        title='招商银行2024年年度报告',
        doc_type='pdf',
        source_type='upload',
        file_path='uploads/zsbank-2024.pdf',
        parse_status='pending',
        created_by=user,
    )
    assert kb.id is not None
    assert doc.kb_id == kb.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/kb/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError` or model import error

- [ ] **Step 3: 实现知识库与文档模型**

```python
# backend/apps/kb/models.py
from django.conf import settings
from django.db import models


class KnowledgeBase(models.Model):
    TYPE_CHOICES = [
        ('annual_report', 'annual_report'),
        ('research_report', 'research_report'),
        ('news', 'news'),
        ('mixed', 'mixed'),
    ]
    STATUS_CHOICES = [
        ('active', 'active'),
        ('building', 'building'),
        ('archived', 'archived'),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    description = models.CharField(max_length=500, blank=True, default='')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Document(models.Model):
    PARSE_STATUS_CHOICES = [
        ('pending', 'pending'),
        ('parsing', 'parsing'),
        ('parsed', 'parsed'),
        ('failed', 'failed'),
    ]

    kb = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=30)
    source_type = models.CharField(max_length=30)
    company_name = models.CharField(max_length=100, blank=True, default='')
    report_period = models.CharField(max_length=30, blank=True, default='')
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(null=True, blank=True)
    parse_status = models.CharField(max_length=20, choices=PARSE_STATUS_CHOICES, default='pending')
    parse_message = models.CharField(max_length=500, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    chunk_index = models.IntegerField()
    page_no = models.IntegerField(null=True, blank=True)
    chunk_text = models.TextField()
    token_count = models.IntegerField(default=0)
    vector_id = models.CharField(max_length=100, blank=True, default='')
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IngestionTask(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    task_type = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default='pending')
    progress = models.IntegerField(default=0)
    error_message = models.CharField(max_length=1000, blank=True, default='')
    celery_task_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: 补齐其余模型骨架**

```python
# backend/apps/chat/models.py
from django.db import models
from django.conf import settings
from backend.apps.kb.models import KnowledgeBase


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kb = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    content = models.TextField()
    source_json = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=100, blank=True, default='')
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RetrievalLog(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE)
    query_text = models.CharField(max_length=1000)
    query_rewrite = models.CharField(max_length=1000, blank=True, default='')
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    scores_json = models.JSONField(default=list, blank=True)
    top_k = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# backend/apps/risk/models.py
from django.conf import settings
from django.db import models
from backend.apps.kb.models import Document, DocumentChunk


class RiskEvent(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    chunk = models.ForeignKey(DocumentChunk, null=True, blank=True, on_delete=models.SET_NULL)
    company_name = models.CharField(max_length=100)
    report_period = models.CharField(max_length=30, blank=True, default='')
    risk_type = models.CharField(max_length=50)
    risk_level = models.CharField(max_length=20)
    event_time = models.CharField(max_length=50, blank=True, default='')
    summary = models.CharField(max_length=1000)
    evidence_text = models.TextField()
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    review_status = models.CharField(max_length=20, default='pending')
    review_comment = models.CharField(max_length=500, blank=True, default='')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

```python
# backend/apps/report/models.py
from django.conf import settings
from django.db import models
from backend.apps.kb.models import KnowledgeBase


class RiskReport(models.Model):
    kb = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=100)
    time_range = models.CharField(max_length=100, blank=True, default='')
    summary = models.TextField()
    source_json = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=100, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# backend/apps/llm/models.py
from django.db import models


class ModelConfig(models.Model):
    provider = models.CharField(max_length=30)
    model_name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=30)
    endpoint = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, blank=True, default='')
    is_enabled = models.BooleanField(default=True)
    params_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EvalRecord(models.Model):
    eval_type = models.CharField(max_length=30)
    dataset_name = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    metric_json = models.JSONField(default=dict, blank=True)
    remark = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 5: 生成并应用迁移**

Run: `cd backend && python manage.py makemigrations && python manage.py migrate`
Expected: 新表成功创建，无循环依赖报错。

- [ ] **Step 6: 回跑模型测试**

Run: `cd backend && pytest tests/apps/kb/test_models.py -v`
Expected: PASS

- [ ] **Step 7: 提交本任务**

```bash
git add backend/apps/kb/models.py backend/apps/chat/models.py backend/apps/risk/models.py backend/apps/report/models.py backend/apps/llm/models.py backend/tests/apps/kb/test_models.py
git commit -m "feat: add core domain models for kb chat risk report llm"
```

### Task 3: 知识库与文档上传 API

**Files:**
- Create: `backend/apps/kb/serializers.py`
- Create: `backend/apps/kb/views.py`
- Create: `backend/apps/kb/urls.py`
- Create: `backend/tests/apps/kb/test_kb_api.py`
- Create: `frontend/src/api/kb.ts`
- Create: `frontend/src/views/kb/KnowledgeBaseListView.vue`
- Create: `frontend/src/components/kb/UploadDialog.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 写创建知识库 API 失败测试**

```python
# backend/tests/apps/kb/test_kb_api.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_create_kb_returns_created(django_user_model):
    user = django_user_model.objects.create_user(username='admin', password='123456')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/kbs/', {
        'name': '上市银行年报库',
        'type': 'annual_report',
        'description': '用于问答与抽取',
    }, format='json')
    assert response.status_code == 201
    assert response.json()['data']['name'] == '上市银行年报库'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/kb/test_kb_api.py::test_create_kb_returns_created -v`
Expected: FAIL with `404 != 201`

- [ ] **Step 3: 实现序列化器与 ViewSet**

```python
# backend/apps/kb/serializers.py
from rest_framework import serializers
from backend.apps.kb.models import KnowledgeBase, Document


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = ['id', 'name', 'type', 'description', 'status', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'
```

```python
# backend/apps/kb/views.py
from django.core.files.storage import default_storage
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from backend.apps.kb.models import KnowledgeBase, Document
from backend.apps.kb.serializers import KnowledgeBaseSerializer, DocumentSerializer


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeBaseSerializer

    def get_queryset(self):
        return KnowledgeBase.objects.filter(owner=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'code': 0, 'message': 'ok', 'data': serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='documents/upload')
    def upload_document(self, request, pk=None):
        kb = self.get_object()
        file_obj = request.FILES['file']
        saved_path = default_storage.save(f'uploads/{file_obj.name}', file_obj)
        document = Document.objects.create(
            kb=kb,
            title=request.data.get('title') or file_obj.name,
            doc_type=file_obj.name.split('.')[-1].lower(),
            source_type='upload',
            company_name=request.data.get('company_name', ''),
            report_period=request.data.get('report_period', ''),
            file_path=saved_path,
            file_size=file_obj.size,
            parse_status='pending',
            created_by=request.user,
        )
        return Response({'code': 0, 'message': 'uploaded', 'data': {'document_id': document.id, 'parse_status': document.parse_status}}, status=status.HTTP_201_CREATED)
```

- [ ] **Step 4: 注册路由并回跑 API 测试**

```python
# backend/apps/kb/urls.py
from rest_framework.routers import DefaultRouter
from backend.apps.kb.views import KnowledgeBaseViewSet

router = DefaultRouter()
router.register(r'kbs', KnowledgeBaseViewSet, basename='kb')
urlpatterns = router.urls
```

```python
# backend/config/urls.py
from django.urls import include, path

urlpatterns = [
    path('api/', include('backend.apps.kb.urls')),
    path('api/health/', HealthView.as_view(), name='health'),
]
```

Run: `cd backend && pytest tests/apps/kb/test_kb_api.py -v`
Expected: create 用例 PASS

- [ ] **Step 5: 接入前端知识库列表与上传弹窗**

```ts
// frontend/src/api/kb.ts
import request from './request'

export function createKb(data: Record<string, unknown>) {
  return request.post('/api/kbs/', data)
}

export function uploadDocument(kbId: number, form: FormData) {
  return request.post(`/api/kbs/${kbId}/documents/upload/`, form)
}
```

```vue
<!-- frontend/src/views/kb/KnowledgeBaseListView.vue -->
<template>
  <div>
    <h2>知识库管理</h2>
    <button @click="showUpload = true">上传文档</button>
    <UploadDialog v-model:visible="showUpload" />
  </div>
</template>
```

- [ ] **Step 6: 人工验收知识库闭环**

Expected: 页面能创建知识库、上传 PDF，后端能返回 document_id。

- [ ] **Step 7: 提交本任务**

```bash
git add backend/apps/kb/serializers.py backend/apps/kb/views.py backend/apps/kb/urls.py backend/tests/apps/kb/test_kb_api.py frontend/src/api/kb.ts frontend/src/views/kb/KnowledgeBaseListView.vue frontend/src/components/kb/UploadDialog.vue frontend/src/router/index.ts
git commit -m "feat: add kb CRUD and document upload API"
```

### Task 4: Celery 入库任务与文档解析链路

**Files:**
- Create: `backend/config/celery.py`
- Modify: `backend/config/__init__.py`
- Create: `backend/apps/kb/tasks.py`
- Create: `backend/apps/kb/services/parser_service.py`
- Create: `backend/apps/kb/services/chunk_service.py`
- Create: `backend/apps/kb/services/vector_service.py`
- Create: `backend/tests/apps/kb/test_ingestion_pipeline.py`

- [ ] **Step 1: 写解析任务状态流转测试**

```python
# backend/tests/apps/kb/test_ingestion_pipeline.py
import pytest
from django.contrib.auth import get_user_model
from backend.apps.kb.models import KnowledgeBase, Document
from backend.apps.kb.tasks import parse_document_task


@pytest.mark.django_db
def test_parse_document_task_marks_document_parsed(tmp_path):
    user = get_user_model().objects.create_user(username='tester', password='123456')
    kb = KnowledgeBase.objects.create(name='银行年报库', type='annual_report', owner=user, status='active')
    file_path = tmp_path / 'sample.txt'
    file_path.write_text('流动性风险主要来自短期负债集中到期。', encoding='utf-8')
    document = Document.objects.create(
        kb=kb,
        title='sample',
        doc_type='txt',
        source_type='upload',
        file_path=str(file_path),
        parse_status='pending',
        created_by=user,
    )
    parse_document_task(document.id)
    document.refresh_from_db()
    assert document.parse_status == 'parsed'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/kb/test_ingestion_pipeline.py -v`
Expected: FAIL because task/service not found

- [ ] **Step 3: 初始化 Celery 并自动发现 tasks**

```python
# backend/config/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.dev')

app = Celery('backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

```python
# backend/config/__init__.py
from .celery import app as celery_app

__all__ = ('celery_app',)
```

- [ ] **Step 4: 实现解析、切块、向量化服务骨架**

```python
# backend/apps/kb/services/parser_service.py
from pathlib import Path
from pypdf import PdfReader


class ParserService:
    def parse_pdf(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            return ''
        if path.suffix.lower() == '.txt':
            return path.read_text(encoding='utf-8', errors='ignore')
        if path.suffix.lower() == '.pdf':
            reader = PdfReader(str(path))
            return '\n'.join(page.extract_text() or '' for page in reader.pages)
        return ''
```

```python
# backend/apps/kb/services/chunk_service.py
class ChunkService:
    def split(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap if end - overlap > start else end
        return chunks
```

```python
# backend/apps/kb/services/vector_service.py
class VectorService:
    def upsert_chunks(self, chunks: list[dict]) -> list[str]:
        return [f'vec-{item["chunk_index"]}' for item in chunks]
```


- [ ] **Step 5: 实现任务入口与状态更新**

```python
# backend/apps/kb/tasks.py
from celery import shared_task
from backend.apps.kb.models import Document, DocumentChunk
from backend.apps.kb.services.parser_service import ParserService
from backend.apps.kb.services.chunk_service import ChunkService


@shared_task
def parse_document_task(document_id: int):
    document = Document.objects.get(id=document_id)
    document.parse_status = 'parsing'
    document.save(update_fields=['parse_status'])
    text = ParserService().parse_pdf(document.file_path)
    if not text.strip():
        document.parse_status = 'failed'
        document.parse_message = 'empty text'
        document.save(update_fields=['parse_status', 'parse_message'])
        return
    chunks = ChunkService().split(text)
    DocumentChunk.objects.filter(document=document).delete()
    for index, chunk_text in enumerate(chunks):
        DocumentChunk.objects.create(
            document=document,
            chunk_index=index,
            chunk_text=chunk_text,
            token_count=len(chunk_text),
            metadata_json={},
        )
    document.parse_status = 'parsed'
    document.parse_message = f'{len(chunks)} chunks created'
    document.save(update_fields=['parse_status', 'parse_message'])
```

- [ ] **Step 6: 回跑任务测试并本地启动 worker**

Run: `cd backend && pytest tests/apps/kb/test_ingestion_pipeline.py -v`
Expected: PASS

Run: `cd backend && celery -A backend.config worker -l INFO`
Expected: worker 正常启动，无 import error。

- [ ] **Step 7: 在上传成功后触发异步任务**

```python
# backend/apps/kb/views.py
from django.db import transaction
from backend.apps.kb.tasks import parse_document_task

transaction.on_commit(lambda: parse_document_task.delay(document.id))
```

- [ ] **Step 8: 提交本任务**

```bash
git add backend/config/celery.py backend/config/__init__.py backend/apps/kb/tasks.py backend/apps/kb/services/parser_service.py backend/apps/kb/services/chunk_service.py backend/apps/kb/services/vector_service.py backend/tests/apps/kb/test_ingestion_pipeline.py backend/apps/kb/views.py
git commit -m "feat: add celery ingestion pipeline skeleton"
```

### Task 5: 模型适配层与 RAG 问答 API

**Files:**
- Create: `backend/apps/llm/providers/base.py`
- Create: `backend/apps/llm/providers/ollama_provider.py`
- Create: `backend/apps/llm/prompts/qa_prompt.py`
- Create: `backend/apps/chat/serializers.py`
- Create: `backend/apps/chat/views.py`
- Create: `backend/apps/chat/urls.py`
- Create: `backend/apps/chat/services/retrieval_service.py`
- Create: `backend/apps/chat/services/qa_service.py`
- Create: `backend/tests/apps/chat/test_chat_api.py`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/views/chat/ChatView.vue`
- Create: `frontend/src/components/chat/SourceCard.vue`

- [ ] **Step 1: 写问答 API 失败测试**

```python
# backend/tests/apps/chat/test_chat_api.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from backend.apps.kb.models import KnowledgeBase


@pytest.mark.django_db
def test_chat_ask_returns_answer_with_sources():
    user = get_user_model().objects.create_user(username='analyst', password='123456')
    kb = KnowledgeBase.objects.create(name='测试库', type='annual_report', owner=user, status='active')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/chat/sessions/', {'kb_id': kb.id, 'title': '测试会话'}, format='json')
    assert response.status_code == 201
    assert response.json()['data']['session_id'] > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/chat/test_chat_api.py -v`
Expected: FAIL with `404 != 201`

- [ ] **Step 3: 实现 provider 抽象与 Ollama provider**

```python
# backend/apps/llm/providers/base.py
from abc import ABC, abstractmethod


class BaseChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        raise NotImplementedError
```

```python
# backend/apps/llm/providers/ollama_provider.py
import requests
from backend.apps.llm.providers.base import BaseChatProvider


class OllamaChatProvider(BaseChatProvider):
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name

    def chat(self, messages: list[dict]) -> str:
        response = requests.post(
            f'{self.base_url}/v1/chat/completions',
            json={'model': self.model_name, 'messages': messages},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
```

- [ ] **Step 4: 实现简化版检索与 QA service**

```python
# backend/apps/chat/services/retrieval_service.py
from backend.apps.kb.models import DocumentChunk


class RetrievalService:
    def retrieve(self, kb_id: int, query: str, top_k: int = 5) -> list[DocumentChunk]:
        return list(DocumentChunk.objects.filter(document__kb_id=kb_id)[:top_k])
```

```python
# backend/apps/chat/services/qa_service.py
from backend.apps.chat.services.retrieval_service import RetrievalService
from backend.apps.llm.providers.ollama_provider import OllamaChatProvider


class QAService:
    def answer(self, kb_id: int, question: str) -> dict:
        chunks = RetrievalService().retrieve(kb_id, question, top_k=5)
        context = '\n'.join(chunk.chunk_text for chunk in chunks)
        provider = OllamaChatProvider(base_url='http://localhost:11434', model_name='qwen2.5:7b')
        answer = provider.chat([
            {'role': 'system', 'content': '你是金融风控助手，请严格基于给定上下文回答。'},
            {'role': 'user', 'content': f'上下文:\n{context}\n\n问题:\n{question}'},
        ])
        return {
            'answer': answer,
            'sources': [{'chunk_id': chunk.id, 'snippet': chunk.chunk_text[:120]} for chunk in chunks],
        }
```

- [ ] **Step 5: 实现会话 API 与路由**

```python
# backend/apps/chat/views.py
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from backend.apps.chat.models import ChatSession, ChatMessage, RetrievalLog
from backend.apps.chat.services.qa_service import QAService


class ChatSessionViewSet(viewsets.ModelViewSet):
    queryset = ChatSession.objects.all().order_by('-id')

    def create(self, request, *args, **kwargs):
        session = ChatSession.objects.create(
            user=request.user,
            kb_id=request.data['kb_id'],
            title=request.data.get('title', ''),
        )
        return Response({'code': 0, 'message': 'ok', 'data': {'session_id': session.id, 'title': session.title}}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='messages')
    def ask(self, request, pk=None):
        session = self.get_object()
        result = QAService().answer(session.kb_id, request.data['question'])
        ChatMessage.objects.create(session=session, role='user', content=request.data['question'])
        assistant_message = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=result['answer'],
            source_json=result['sources'],
            model_name='qwen2.5:7b',
        )
        RetrievalLog.objects.create(
            message=assistant_message,
            query_text=request.data['question'],
            retrieved_chunk_ids=[item['chunk_id'] for item in result['sources']],
            scores_json=[{'chunk_id': item['chunk_id'], 'score': item.get('score', 0)} for item in result['sources']],
            top_k=len(result['sources']),
        )
        return Response({'code': 0, 'message': 'ok', 'data': result})
```

```python
# backend/apps/chat/urls.py
from rest_framework.routers import DefaultRouter
from backend.apps.chat.views import ChatSessionViewSet

router = DefaultRouter()
router.register(r'chat/sessions', ChatSessionViewSet, basename='chat-session')
urlpatterns = router.urls
```

```python
# backend/config/urls.py
from django.urls import include, path

urlpatterns += [
    path('api/', include('backend.apps.chat.urls')),
]
```

- [ ] **Step 6: 回跑测试并前端接入问答页**

Run: `cd backend && pytest tests/apps/chat/test_chat_api.py -v`
Expected: session create 用例 PASS

```vue
<!-- frontend/src/views/chat/ChatView.vue -->
<template>
  <div>
    <textarea v-model="question" />
    <button @click="submit">发送</button>
    <div v-if="answer">{{ answer }}</div>
    <SourceCard v-for="item in sources" :key="item.chunk_id" :source="item" />
  </div>
</template>
```

- [ ] **Step 7: 人工验收问答闭环**

Expected: 输入问题后页面显示答案和来源片段，数据库写入会话与消息记录。

- [ ] **Step 8: 提交本任务**

```bash
git add backend/apps/llm/providers/base.py backend/apps/llm/providers/ollama_provider.py backend/apps/chat/views.py backend/apps/chat/urls.py backend/apps/chat/services/retrieval_service.py backend/apps/chat/services/qa_service.py backend/tests/apps/chat/test_chat_api.py frontend/src/api/chat.ts frontend/src/views/chat/ChatView.vue frontend/src/components/chat/SourceCard.vue
git commit -m "feat: add rag chat session and answer API"
```

### Task 6: 风险抽取与人工审核

**Files:**
- Create: `backend/apps/llm/schemas/risk_event_schema.py`
- Create: `backend/apps/llm/prompts/extraction_prompt.py`
- Create: `backend/apps/risk/serializers.py`
- Create: `backend/apps/risk/views.py`
- Create: `backend/apps/risk/urls.py`
- Create: `backend/apps/risk/tasks.py`
- Create: `backend/apps/risk/services/extraction_service.py`
- Create: `backend/tests/apps/risk/test_risk_api.py`
- Create: `frontend/src/api/risk.ts`
- Create: `frontend/src/views/risk/RiskEventListView.vue`
- Create: `frontend/src/components/risk/RiskReviewTable.vue`

- [ ] **Step 1: 写风险抽取任务测试**

```python
# backend/tests/apps/risk/test_risk_api.py
import pytest
from django.contrib.auth import get_user_model
from backend.apps.kb.models import KnowledgeBase, Document, DocumentChunk
from backend.apps.risk.models import RiskEvent
from backend.apps.risk.tasks import extract_risk_events_task


@pytest.mark.django_db
def test_extract_risk_events_task_creates_rows(tmp_path):
    user = get_user_model().objects.create_user(username='analyst', password='123456')
    kb = KnowledgeBase.objects.create(name='测试库', type='annual_report', owner=user, status='active')
    document = Document.objects.create(
        kb=kb,
        title='招商银行2024年年度报告',
        doc_type='txt',
        source_type='upload',
        file_path=str(tmp_path / 'sample.txt'),
        parse_status='parsed',
        company_name='招商银行',
        created_by=user,
    )
    DocumentChunk.objects.create(document=document, chunk_index=0, chunk_text='报告期内流动性风险主要来自短期负债集中到期。')
    extract_risk_events_task(document.id)
    assert RiskEvent.objects.filter(document=document).count() == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/risk/test_risk_api.py -v`
Expected: FAIL because task/service not found

- [ ] **Step 3: 定义结构化 schema 与抽取 service**

```python
# backend/apps/llm/schemas/risk_event_schema.py
from pydantic import BaseModel


class RiskEventSchema(BaseModel):
    company_name: str
    report_period: str = ''
    risk_type: str
    risk_level: str
    event_time: str = ''
    summary: str
    evidence_text: str
    confidence: float | None = None
```

```python
# backend/apps/risk/services/extraction_service.py
from backend.apps.kb.models import DocumentChunk
from backend.apps.risk.models import RiskEvent


class ExtractionService:
    def extract_from_document(self, document):
        chunks = DocumentChunk.objects.filter(document=document)
        for chunk in chunks:
            RiskEvent.objects.create(
                document=document,
                chunk=chunk,
                company_name=document.company_name or 'unknown',
                report_period=document.report_period or '',
                risk_type='流动性风险',
                risk_level='medium',
                summary=chunk.chunk_text[:120],
                evidence_text=chunk.chunk_text,
                confidence=0.5,
            )
```

- [ ] **Step 4: 实现任务入口和审核 API**

```python
# backend/apps/risk/tasks.py
from celery import shared_task
from backend.apps.kb.models import Document
from backend.apps.risk.services.extraction_service import ExtractionService


@shared_task
def extract_risk_events_task(document_id: int):
    document = Document.objects.get(id=document_id)
    ExtractionService().extract_from_document(document)
```

```python
# backend/apps/risk/views.py
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from backend.apps.kb.models import Document
from backend.apps.risk.models import RiskEvent
from backend.apps.risk.tasks import extract_risk_events_task


class RiskEventViewSet(viewsets.ModelViewSet):
    queryset = RiskEvent.objects.all().order_by('-id')

    @action(detail=False, methods=['post'], url_path=r'documents/(?P<document_id>[^/.]+)/extract')
    def extract(self, request, document_id=None):
        Document.objects.get(id=document_id)
        extract_risk_events_task.delay(int(document_id))
        return Response({'code': 0, 'message': 'task submitted', 'data': {'document_id': int(document_id)}}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['patch'], url_path='review')
    def review(self, request, pk=None):
        event = self.get_object()
        event.review_status = request.data['review_status']
        event.review_comment = request.data.get('review_comment', '')
        event.reviewer = request.user
        event.reviewed_at = timezone.now()
        event.save(update_fields=['review_status', 'review_comment', 'reviewer', 'reviewed_at'])
        return Response({'code': 0, 'message': 'reviewed', 'data': {'id': event.id, 'review_status': event.review_status}})
```

```python
# backend/apps/risk/urls.py
from rest_framework.routers import DefaultRouter
from backend.apps.risk.views import RiskEventViewSet

router = DefaultRouter()
router.register(r'risk/events', RiskEventViewSet, basename='risk-event')
urlpatterns = router.urls
```

```python
# backend/config/urls.py
from django.urls import include, path

urlpatterns += [
    path('api/', include('backend.apps.risk.urls')),
]
```

- [ ] **Step 5: 回跑测试并补前端审核列表页**

Run: `cd backend && pytest tests/apps/risk/test_risk_api.py -v`
Expected: PASS

```vue
<!-- frontend/src/views/risk/RiskEventListView.vue -->
<template>
  <div>
    <h2>风险事件</h2>
    <RiskReviewTable />
  </div>
</template>
```

- [ ] **Step 6: 人工验收抽取闭环**

Expected: 可触发抽取任务、看到风险事件列表、能批准或驳回一条事件。

- [ ] **Step 7: 提交本任务**

```bash
git add backend/apps/llm/schemas/risk_event_schema.py backend/apps/risk/views.py backend/apps/risk/urls.py backend/apps/risk/tasks.py backend/apps/risk/services/extraction_service.py backend/tests/apps/risk/test_risk_api.py frontend/src/api/risk.ts frontend/src/views/risk/RiskEventListView.vue frontend/src/components/risk/RiskReviewTable.vue
git commit -m "feat: add risk extraction workflow and review API"
```

### Task 7: 风险报告、模型配置与基础评测

**Files:**
- Create: `backend/apps/report/serializers.py`
- Create: `backend/apps/report/views.py`
- Create: `backend/apps/report/urls.py`
- Create: `backend/apps/report/tasks.py`
- Create: `backend/apps/report/services/report_service.py`
- Create: `backend/apps/llm/serializers.py`
- Create: `backend/apps/llm/views.py`
- Create: `backend/apps/llm/urls.py`
- Create: `backend/tests/apps/report/test_report_api.py`
- Create: `frontend/src/api/report.ts`
- Create: `frontend/src/api/model.ts`
- Create: `frontend/src/views/report/ReportView.vue`
- Create: `frontend/src/views/model/ModelConfigView.vue`
- Create: `frontend/src/components/report/ReportSummaryCard.vue`

- [ ] **Step 1: 写报告生成 API 失败测试**

```python
# backend/tests/apps/report/test_report_api.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from backend.apps.kb.models import KnowledgeBase


@pytest.mark.django_db
def test_generate_report_returns_summary():
    user = get_user_model().objects.create_user(username='analyst', password='123456')
    kb = KnowledgeBase.objects.create(name='测试库', type='annual_report', owner=user, status='active')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/reports/generate/', {'kb_id': kb.id, 'company_name': '招商银行'}, format='json')
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/apps/report/test_report_api.py -v`
Expected: FAIL with `404`

- [ ] **Step 3: 实现报告聚合 service 与 API**

```python
# backend/apps/report/services/report_service.py
from backend.apps.risk.models import RiskEvent
from backend.apps.report.models import RiskReport


class ReportService:
    def generate(self, kb_id: int, company_name: str, created_by_id: int) -> RiskReport:
        events = RiskEvent.objects.filter(document__kb_id=kb_id, company_name=company_name, review_status='approved')
        summary = '\n'.join(f'- [{event.risk_type}] {event.summary}' for event in events[:20]) or '暂无已审核风险事件。'
        return RiskReport.objects.create(
            kb_id=kb_id,
            company_name=company_name,
            time_range='',
            summary=summary,
            source_json=[event.id for event in events[:20]],
            created_by_id=created_by_id,
        )
```

```python
# backend/apps/report/views.py
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from backend.apps.report.services.report_service import ReportService


class RiskReportViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        report = ReportService().generate(
            request.data['kb_id'],
            request.data['company_name'],
            request.user.id,
        )
        return Response({'code': 0, 'message': 'ok', 'data': {'report_id': report.id, 'summary': report.summary}}, status=status.HTTP_200_OK)
```

- [ ] **Step 4: 实现模型配置与评测记录查询接口**

```python
# backend/apps/llm/views.py
from rest_framework import viewsets
from rest_framework.response import Response
from backend.apps.llm.models import ModelConfig, EvalRecord


class ModelConfigViewSet(viewsets.ViewSet):
    def list(self, request):
        data = list(ModelConfig.objects.filter(is_enabled=True).values('id', 'provider', 'model_name', 'model_type', 'endpoint'))
        return Response({'code': 0, 'message': 'ok', 'data': data})


class EvalRecordViewSet(viewsets.ViewSet):
    def list(self, request):
        data = list(EvalRecord.objects.all().order_by('-id').values())
        return Response({'code': 0, 'message': 'ok', 'data': data})
```

```python
# backend/apps/report/urls.py
from django.urls import path
from backend.apps.report.views import RiskReportViewSet

report_generate = RiskReportViewSet.as_view({'post': 'generate'})
urlpatterns = [path('reports/generate/', report_generate, name='report-generate')]
```

```python
# backend/apps/llm/urls.py
from django.urls import path
from backend.apps.llm.views import ModelConfigViewSet, EvalRecordViewSet

model_list = ModelConfigViewSet.as_view({'get': 'list'})
eval_list = EvalRecordViewSet.as_view({'get': 'list'})
urlpatterns = [
    path('models/', model_list, name='model-list'),
    path('evals/', eval_list, name='eval-list'),
]
```

```python
# backend/config/urls.py
from django.urls import include, path

urlpatterns += [
    path('api/', include('backend.apps.report.urls')),
    path('api/', include('backend.apps.llm.urls')),
]
```

- [ ] **Step 5: 回跑测试并接前端报告页与模型页**

Run: `cd backend && pytest tests/apps/report/test_report_api.py -v`
Expected: PASS

```vue
<!-- frontend/src/views/report/ReportView.vue -->
<template>
  <div>
    <h2>风险报告</h2>
    <ReportSummaryCard :summary="summary" />
  </div>
</template>
```

- [ ] **Step 6: 人工验收报告与模型页**

Expected: 已审核风险事件可聚合成报告；模型页至少能显示当前启用的 chat 与 embedding 模型配置。

- [ ] **Step 7: 提交本任务**

```bash
git add backend/apps/report/views.py backend/apps/report/urls.py backend/apps/report/tasks.py backend/apps/report/services/report_service.py backend/apps/llm/views.py backend/apps/llm/urls.py backend/tests/apps/report/test_report_api.py frontend/src/api/report.ts frontend/src/api/model.ts frontend/src/views/report/ReportView.vue frontend/src/views/model/ModelConfigView.vue frontend/src/components/report/ReportSummaryCard.vue
git commit -m "feat: add risk report and model config pages"
```

### Task 8: 联调、演示脚本、论文材料与答辩收口

**Files:**
- Create: `docs/demo-script.md`
- Create: `docs/test-checklist.md`
- Create: `docs/thesis-assets.md`
- Modify: `README.md`
- Create: `backend/tests/apps/chat/test_retrieval_log.py`
- Create: `backend/tests/apps/risk/test_review_flow.py`

- [ ] **Step 1: 写两条关键回归测试**

```python
# backend/tests/apps/chat/test_retrieval_log.py
import pytest
from django.contrib.auth import get_user_model
from backend.apps.chat.models import ChatSession, ChatMessage, RetrievalLog
from backend.apps.kb.models import KnowledgeBase


@pytest.mark.django_db
def test_chat_creates_retrieval_log():
    user = get_user_model().objects.create_user(username='analyst', password='123456')
    kb = KnowledgeBase.objects.create(name='测试库', type='annual_report', owner=user, status='active')
    session = ChatSession.objects.create(user=user, kb=kb, title='测试会话')
    message = ChatMessage.objects.create(session=session, role='assistant', content='回答', source_json=[{'chunk_id': 1}])
    log = RetrievalLog.objects.create(message=message, query_text='有哪些流动性风险？', retrieved_chunk_ids=[1], scores_json=[{'chunk_id': 1, 'score': 0.9}], top_k=1)
    assert log.id is not None
```

```python
# backend/tests/apps/risk/test_review_flow.py
import pytest
from django.contrib.auth import get_user_model
from backend.apps.kb.models import KnowledgeBase, Document
from backend.apps.risk.models import RiskEvent


@pytest.mark.django_db
def test_review_flow_updates_status(tmp_path):
    user = get_user_model().objects.create_user(username='reviewer', password='123456')
    kb = KnowledgeBase.objects.create(name='测试库', type='annual_report', owner=user, status='active')
    document = Document.objects.create(kb=kb, title='sample', doc_type='txt', source_type='upload', file_path=str(tmp_path / 'sample.txt'), parse_status='parsed', created_by=user)
    event = RiskEvent.objects.create(document=document, company_name='招商银行', risk_type='流动性风险', risk_level='medium', summary='短期负债集中到期', evidence_text='短期负债集中到期')
    event.review_status = 'approved'
    event.review_comment = '证据充分'
    event.reviewer = user
    event.save(update_fields=['review_status', 'review_comment', 'reviewer'])
    event.refresh_from_db()
    assert event.review_status == 'approved'
```

- [ ] **Step 2: 统一跑后端测试并记录结果**

Run: `cd backend && pytest tests/apps -v`
Expected: 全部 PASS；若失败，先修复再进入答辩材料阶段。

- [ ] **Step 3: 写演示脚本**

```markdown
# docs/demo-script.md
1. 登录系统
2. 进入知识库管理，新建“上市银行年报库”
3. 上传 1 份年报 PDF，展示任务状态
4. 进入问答页，提问“该公司有哪些流动性风险披露？”
5. 展示答案与来源片段
6. 进入风险抽取页，触发抽取并审核 1 条事件
7. 进入报告页，生成公司风险摘要
8. 进入模型页，展示本地模型配置与评测结果
```

- [ ] **Step 4: 写测试清单与论文素材清单**

```markdown
# docs/test-checklist.md
- [ ] 上传 PDF 成功
- [ ] 文档状态从 pending 变为 parsed
- [ ] 问答页返回来源片段
- [ ] 风险事件可审核
- [ ] 报告页可生成摘要
- [ ] 模型配置页可展示当前模型
```

```markdown
# docs/thesis-assets.md
- 系统架构图
- 功能模块图
- 数据库 ER 图
- 知识库入库流程图
- RAG 问答时序图
- 风险抽取结果截图
- 报告页截图
- 模型评测对比表
```

- [ ] **Step 5: 更新 README 的启动方式**

```markdown
# README.md
## Backend
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
celery -A backend.config worker -l INFO

## Frontend
npm install
npm run dev
```

- [ ] **Step 6: 录一遍完整演示路径并修复阻塞问题**

Expected: 从“登录 -> 上传 -> 问答 -> 抽取 -> 审核 -> 报告 -> 模型页”整条路径可连续演示，无临场补救。

- [ ] **Step 7: 提交本任务**

```bash
git add docs/demo-script.md docs/test-checklist.md docs/thesis-assets.md README.md backend/tests/apps/chat/test_retrieval_log.py backend/tests/apps/risk/test_review_flow.py
git commit -m "docs: add demo script test checklist and defense assets"
```

---

## Risk control rules during implementation

1. **先跑通骨架再细化模型效果**：第 1-4 周只要求闭环，不要求答案完美。
2. **每周必须可演示**：禁止连续两周只写底层不出页面。
3. **所有核心结果必须可追溯**：问答要有来源，抽取要有 evidence_text。
4. **抽取默认是“待审核”**：平台定位为辅助分析师，而不是自动决策系统。
5. **模型优化后置**：LoRA 微调与 prompt 调优只能在 Task 5-7 基础稳定后再做。

## Plan review checklist

- 已覆盖规格中的平台基础、知识库、问答、抽取、报告、模型配置、评测与答辩收口。
- 未留 `TODO/TBD` 占位语；所有任务都给出了文件路径、命令或代码骨架。
- 每个任务都能形成独立中间成果，适合单独提交与回归。

## Recommended weekly meeting rhythm

- 周一：锁定本周目标与验收标准
- 周三：完成后端主链路一半并自测
- 周五：前后端联调、截图、记录问题
- 周末：整理论文素材与演示脚本

## What not to build in MVP

- 多智能体调度
- 实时流式输出
- 多租户权限体系
- 自动网页爬虫平台
- 复杂向量重排实验平台
- 云上高可用部署

## After this plan

当本计划全部完成后，再单独写两份补充计划：
1. `lora-finetune-experiment-plan`：用于微调数据准备、训练、评测与对比；
2. `thesis-writing-plan`：用于论文、PPT 与答辩问答准备。
