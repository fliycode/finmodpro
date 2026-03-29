# FinModPro 演示脚本

本文档用于答辩或联调时的稳定演示，目标是基于仓库当前真实能力，跑通一条可复现链路：

`登录 -> 上传文档 -> 问答 -> 风险抽取 -> 审核 -> 报告`

## 适用前提

开始前请先完成本地启动：

- [`docs/local-setup.md`](/root/finmodpro/docs/local-setup.md)
- [`backend/docs/dependency-services.md`](/root/finmodpro/backend/docs/dependency-services.md)

本演示脚本假设：

- 后端运行在 `http://127.0.0.1:8000`
- 前端运行在 `http://127.0.0.1:5173`
- 已执行 `python manage.py migrate`
- 已执行 `python manage.py seed_rbac`
- 如果要演示真实问答和风险抽取，Ollama 已启动，且默认模型可用：
  - `llama3.2`
  - `mxbai-embed-large`

为了让“上传后立即可问答/可抽取”更稳定，建议演示时把 Celery 调成 eager 模式，再启动后端：

```bash
cd /root/finmodpro/backend
source .venv/bin/activate
set -a
source .env
export CELERY_TASK_ALWAYS_EAGER=true
export CELERY_TASK_EAGER_PROPAGATES=true
set +a
python manage.py runserver 127.0.0.1:8000
```

这样 `POST /api/knowledgebase/documents/<id>/ingest` 会在当前进程里直接完成摄取，更适合单机演示。

## 当前仓库的演示边界

先说明清楚当前现状，避免演示脚本误导：

- 登录页、工作台、问答页、风险审核/报告页在前端中真实存在
- 后端真实接口已经覆盖文档上传、文档入库、问答、风险抽取、审核、报告
- 但前端 `KnowledgeBase` 组件仍请求旧的 `/api/v1/...` 路径，失败后会回退 mock 数据，所以“上传文档”这一步目前以后端 API 演示最稳
- 模型配置/评测后端能力已存在，但前端请求路径和方法仍有未对齐项，因此本文把它们放到附录，不放进主线

结论：

- 主线推荐采用“前端登录 + 后端 API/浏览器 Network 面板辅助”的方式演示
- 如果你只想做最稳的闭环，整条链路都走 API 也可以

## 一、稳定演示数据准备

当前仓库没有“一键 seed 完整演示数据”的命令。最小可执行方案如下。

### 1. 创建管理员演示账号

普通 `member` 默认只有 `view_document` 和 `ask_financial_qa` 权限，不足以完成上传、抽取、审核和报告生成。建议创建一个 `admin` 组用户：

```bash
cd /root/finmodpro/backend
source .venv/bin/activate
set -a
source .env
set +a
python manage.py shell -c "
from django.contrib.auth.models import Group
from authentication.models import User
from rbac.services.rbac_service import seed_roles_and_permissions

seed_roles_and_permissions()
user, created = User.objects.get_or_create(
    username='demo_admin',
    defaults={'email': 'demo_admin@example.com'}
)
if created:
    user.set_password('secret123')
    user.save()
user.groups.set([Group.objects.get(name='admin')])
print({'username': user.username, 'created': created, 'groups': list(user.groups.values_list('name', flat=True))})
"
```

### 2. 确认默认模型配置已存在

`ModelConfig` 默认记录来自迁移 `backend/llm/migrations/0001_initial.py`，正常 `migrate` 后就会有：

- `default-chat`
- `default-embedding`

可以用下面命令确认：

```bash
cd /root/finmodpro/backend
source .venv/bin/activate
python manage.py shell -c "
from llm.models import ModelConfig
print(list(ModelConfig.objects.values('name', 'capability', 'provider', 'model_name', 'endpoint', 'is_active')))
"
```

### 3. 准备一份稳定测试文档

建议使用纯文本 `.txt`，最省掉 PDF 解析的不确定性，也完全符合当前上传接口支持范围。

在仓库根目录创建一份演示文档：

```bash
cd /root/finmodpro
cat > /tmp/finmodpro-demo-risk.txt <<'EOF'
FinModPro Holdings 2025年第一季度经营纪要

公司在2025年3月出现流动性风险上升迹象，短期债务覆盖倍数下降，管理层已启动现金流监控。
同一时期，公司信用风险也有所抬升，部分核心客户回款周期延长。
管理层表示将继续优化资本结构，并加强回款管理。
EOF
```

### 4. 获取 access token

```bash
curl -sS -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_admin","password":"secret123"}'
```

预期返回：

- `access_token`
- `user`
- `expires_in`

后续命令都要把这个 token 带上。下面用 shell 变量 `TOKEN` 表示：

```bash
TOKEN='<把上一步 access_token 粘进来>'
```

## 二、主线演示脚本

## 1. 登录

### 页面动作

打开 `http://127.0.0.1:5173`，使用：

- 用户名：`demo_admin`
- 密码：`secret123`

登录成功后，首页会进入工作台，可看到：

- `金融问答`
- `知识库管理`
- `历史会话`
- `风险与摘要`
- `工作台大盘`
- `模型配置`
- `评测结果`

### API 兜底验证

```bash
curl -sS http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

预期可看到：

- `groups` 含 `admin`
- `permissions` 至少包含：
  - `upload_document`
  - `view_document`
  - `trigger_ingest`
  - `ask_financial_qa`
  - `review_risk_event`

## 2. 上传文档

### 稳定演示方式

当前前端“知识库管理”页的上传仍走旧接口，失败后会退回 mock，因此主线建议直接调用真实后端接口：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/knowledgebase/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=FinModPro Q1 风险纪要" \
  -F "source_date=2025-03-31" \
  -F "file=@/tmp/finmodpro-demo-risk.txt;type=text/plain"
```

预期响应里会有：

- `document.id`
- `document.title`
- `document.status=uploaded`
- `document.doc_type=txt`

把返回的文档 ID 记成：

```bash
DOC_ID=<上传返回的 document.id>
```

## 3. 触发入库

上传后要显式触发摄取：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/knowledgebase/documents/$DOC_ID/ingest \
  -H "Authorization: Bearer $TOKEN"
```

如果你已经按本文开头把 `CELERY_TASK_ALWAYS_EAGER=true` 打开，这一步通常会直接把文档处理到可检索状态。最稳的判断标准仍然是再次查看文档详情。

继续查询详情：

```bash
curl -sS http://127.0.0.1:8000/api/knowledgebase/documents/$DOC_ID \
  -H "Authorization: Bearer $TOKEN"
```

预期至少看到：

- `document.chunk_count >= 1`
- `document.status` 最好为 `indexed`

如果这里仍停留在 `uploaded` 或 `failed`，先不要继续问答和抽取，优先检查：

- Ollama 是否已启动
- 当前激活的 embedding 模型是否可用
- `backend/.env` 中 `MILVUS_URI` 是否可写

## 4. 问答

### 页面动作

进入前端 `金融问答` 页，输入：

```text
这份纪要里提到了哪些风险？
```

预期页面现象：

- 新建一条会话
- 返回一条回答
- 底部出现“参考来源”标签
- 来源标签里能看到当前文档标题和片段摘要

### API 兜底验证

```bash
curl -sS -X POST http://127.0.0.1:8000/api/chat/ask \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"这份纪要里提到了哪些风险？","top_k":3}'
```

预期响应里会有：

- `answer`
- `citations`
- `duration_ms`

稳定演示时重点看两点：

- `citations` 非空
- `citations[0].document_title` 是刚上传的文档标题

## 5. 风险抽取

对刚刚入库的文档触发风险抽取：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/risk/documents/$DOC_ID/extract \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'
```

预期响应：

- `code=0`
- `message=风险抽取完成。`
- `data.created_count >= 1`
- `data.risk_events` 为数组

根据当前后端 schema，单条风险事件至少会包含：

- `company_name`
- `risk_type`
- `risk_level`
- `event_time`
- `summary`
- `evidence_text`
- `confidence_score`
- `review_status`
- `document_id`
- `chunk_id`

## 6. 审核

### 先查询待审核事件

```bash
curl -sS "http://127.0.0.1:8000/api/risk/events?document_id=$DOC_ID&review_status=pending" \
  -H "Authorization: Bearer $TOKEN"
```

预期响应里会有：

- `data.total`
- `data.risk_events`

取第一条事件 ID：

```bash
EVENT_ID=<第一条风险事件 id>
```

### 执行审核

通过：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/risk/events/$EVENT_ID/review \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"review_status":"approved"}'
```

或者忽略：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/risk/events/$EVENT_ID/review \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"review_status":"rejected"}'
```

建议主线演示至少通过 1 条事件，因为后续生成报告只会统计 `approved` 的事件。

### 页面动作

前端进入 `风险与摘要 -> 风险事件审核`：

- 可按公司名、风险类型、风险等级、审核状态筛选
- 对 `pending` 事件点击：
  - `确认`
  - `忽略`

备注：

- 页面表格当前会优先展示真实接口结果
- `confidence_score` 在当前前端里不会完整显示成百分比标签，这是页面展示对齐问题，不影响主流程

## 7. 报告

### 公司维度报告

```bash
curl -sS -X POST http://127.0.0.1:8000/api/risk/reports/company \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"company_name":"FinModPro Holdings"}'
```

预期响应里会有：

- `data.report.title`
- `data.report.summary`
- `data.report.content`
- `data.report.source_metadata.event_count`
- `data.report.source_metadata.risk_type_counts`

### 页面动作

前端进入 `风险与摘要 -> 风险报告生成`：

1. 选择 `按公司维度`
2. 公司名称填 `FinModPro Holdings`
3. 开始/结束日期先留空
4. 点击 `生成报告`

预期页面能展示：

- 报告标题
- 高管摘要
- 风险等级分布
- 风险类型分布
- 报告详情

备注：

- 公司维度报告的日期字段在后端里是可选的。为了避免抽取结果里 `event_time` 缺失导致筛空，主线演示建议先不要填日期
- 当前前端会把报告时间字段按 `generated_at` 读取，而后端真实字段是 `created_at`
- 所以页面上的“生成时间”可能显示 `N/A`
- 这不影响演示主链路，汇报时可以直接说明是一个前端字段映射遗留项

## 三、推荐答辩口径

如果你要边点边讲，建议压缩成下面这段：

1. 先用管理员账号登录，证明当前系统有权限分层
2. 上传一份文本纪要并触发入库，把文档转成可检索切块
3. 在问答页提问，系统基于检索结果回答，并返回来源片段
4. 对同一文档执行风险抽取，把自然语言内容转成结构化风险事件
5. 在审核页人工确认有效事件
6. 基于已审核事件生成风险报告，而不是直接对整篇原文做长摘要

## 四、常见失败点

## 1. 登录成功，但上传/抽取/审核报 403

说明你登录的不是 `admin` 或 `super_admin`。

最小检查：

```bash
curl -sS http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## 2. 问答返回“未检索到相关资料”

优先检查：

- 文档是否已经 `indexed`
- `citations` 是否为空
- embedding 模型是否可用

如果文档没有成功入库，问答就只会返回“当前知识库中未检索到相关资料”。

## 3. 风险抽取返回 502 或上游错误

风险抽取依赖聊天模型输出合法 JSON。优先检查：

- `ollama serve` 是否已启动
- `llama3.2` 是否存在
- 当前激活 chat 模型是否仍指向 `http://localhost:11434`

## 4. 报告生成返回“未找到已审核通过的风险事件”

说明当前只有 `pending` 或 `rejected` 事件，还没有 `approved` 事件。

先执行审核通过，再生成报告。

## 5. 前端知识库页面看起来有数据，但后端查不到

这是当前仓库已知现状：`KnowledgeBase` 组件仍保留旧 `/api/v1/...` 调用，失败后会回退 mock。答辩时不要把该页当成“上传成功”的唯一依据，主线以真实后端接口响应为准。

## 附录 A：可选演示项

## A1. 模型配置

后端真实接口：

- `GET /api/ops/model-configs/`
- `PATCH /api/ops/model-configs/<id>/activation/`

当前仓库在迁移时会自动创建两条默认配置：

- `default-chat`
- `default-embedding`

适合演示的方式：

- 用后端 API 或 Django shell 展示当前激活模型
- 说明模型切换已经有后端能力，但前端页面仍有接口路径/方法待对齐

## A2. 基础评测

后端真实接口：

- `GET /api/ops/evaluations`
- `POST /api/ops/evaluations`

当前评测服务 `backend/llm/services/evaluation_service.py` 跑的是 smoke 级基线，不依赖真实问答入库数据集；它会产出：

- `qa_accuracy`
- `extraction_accuracy`
- `average_latency_ms`

最小演示命令：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/ops/evaluations \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"task_type":"qa","version":"demo-v1"}'
```

注意：

- 触发评测要求 `run_evaluation` 权限
- `admin` 默认只有 `view_evaluation`，没有 `run_evaluation`
- 如果你要演示这个附录，建议改用 `super_admin` 账号
