# FinModPro LiteLLM 全面接入与管理台设计

日期：2026-04-25

## 1. 目标

在 FinModPro 当前单机生产约束下，把 `LiteLLM` 从“已部署但语义仍分散”的状态，收敛为：

- `chat`、`embedding` 的默认统一网关；
- 模型接入、默认模型切换、alias / route 管理的唯一管理台主路径；
- 可查询请求级调用摘要、错误分析、延迟分布、成本统计的后台与前端闭环；
- 保持 `LiteLLM` 独立容器部署，不把重依赖重新散回 Django 业务层。

本设计同时覆盖后端数据模型、配置同步、迁移策略、管理台页面信息架构与验收口径。

## 2. 背景与约束

当前仓库与文档已经明确以下现实：

- 当前服务器就是生产环境；
- `LiteLLM` 已经在生产 compose 栈中运行；
- `runtime_service` 已支持 `DeepSeek / DashScope / LiteLLM` provider；
- 项目文档已将 `LiteLLM` 收敛为“统一网关候选”，推荐保持独立容器路线；
- 当前需要补齐的不是再引入更多新框架，而是把统一网关的配置、观测、日志与回退语义补齐。

因此本次设计遵守以下约束：

- 不新增重型状态服务；
- 不把原始 `prompt / response` 留存在后台日志表中；
- 不把模型配置长期维持为多套 provider 语义并行可编辑；
- 不以“先上生产试错”作为 LiteLLM 可行性验证手段。

## 3. 设计范围

### 3.1 In Scope

- 将 `chat`、`embedding` 默认模型接入统一迁到 LiteLLM 配置面；
- 后端新增 LiteLLM 模型调用摘要日志能力；
- 后端新增网关摘要、请求日志、错误分析、成本统计查询接口；
- 管理台新增或重构 LiteLLM 相关页面：
  - Dashboard
  - Models / Routing
  - Logs / Observability
  - Cost / Usage
- 提供从现有有效模型配置迁移到 LiteLLM 的服务层迁移逻辑；
- 保留明确回退语义与同步状态反馈。

### 3.2 Out of Scope

- 当前轮不引入原始请求内容审计；
- 当前轮不自托管 Langfuse；
- 当前轮不新增训练、推理或权重托管类重型服务；
- 当前轮不强制把 `rerank` 一并切换到 LiteLLM，`rerank` 保持兼容路径，后续按收益单独评估。

## 4. 总体方案

整体采用 **“Django 管控制面，LiteLLM 管网关路由，管理台管可见性”** 的方案。

### 4.1 配置面

`backend/llm` 继续以 `ModelConfig` 作为模型管理主表，但管理语义收敛到 LiteLLM：

- `provider=litellm` 成为管理台主路径；
- `capability` 至少覆盖 `chat`、`embedding`；
- `model_name` 表示 LiteLLM alias；
- `endpoint` 统一指向内部 LiteLLM；
- `options` 采用结构化 LiteLLM 路由语义，而不是散落的 provider 私有字段。

建议 `options` 最低包含：

```json
{
  "litellm": {
    "upstream_provider": "openai",
    "upstream_model": "gpt-4o",
    "base_url": "https://api.openai.com/v1",
    "api_key_ref": "env:OPENAI_API_KEY",
    "fallback_aliases": ["chat-backup"],
    "weight": 1,
    "input_price_per_million": 5.0,
    "output_price_per_million": 15.0
  }
}
```

其中：

- `fallback_aliases` 用于管理台 fallback 配置；
- `weight` 用于后续路由策略展示；
- `input_price_per_million` / `output_price_per_million` 作为成本统计的稳定口径。

### 4.2 运行面

`runtime_service` 调整为默认从 LiteLLM 激活配置解析 `chat`、`embedding`：

- 业务层默认不再暴露多套 provider 编辑入口；
- Django 仍通过现有 provider 抽象发请求，但默认落点是 LiteLLM；
- 若 alias 不存在、网关不可达、上游鉴权失败，返回明确失败，不做静默降级；
- 代码中可暂时保留直连 provider 能力作为应急兼容，但不再是管理台常规入口。

### 4.3 日志面

新增 Django 侧 **模型调用摘要日志**，作为管理台主口径：

- 记录请求级摘要；
- 支持请求链路聚合；
- 不依赖前端直接读取 LiteLLM 容器日志；
- 与 Langfuse / LiteLLM 自带观测并存，但以后端表为管理台主数据源。

## 5. 后端设计

### 5.1 模型配置与同步

继续复用：

- `llm.models.ModelConfig`
- `llm.services.litellm_config_render_service`
- `llm.services.litellm_alias_service`

并新增一个同步服务层，职责是：

1. 根据当前启用的 LiteLLM `ModelConfig` 生成 route / alias 配置；
2. 渲染到现有 LiteLLM 配置输出位置；
3. 返回同步结果给管理台；
4. 记录最近一次同步状态、错误摘要与更新时间。

建议补一个轻量审计模型：

```python
class LiteLLMSyncEvent(models.Model):
    status = models.CharField(max_length=32)  # success / failed
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    message = models.TextField(blank=True, default="")
    checksum = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

这个模型只负责同步状态审计，不承载请求日志。

### 5.2 模型调用摘要日志

建议新增：

```python
class ModelInvocationLog(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    model_config = models.ForeignKey(ModelConfig, related_name="invocation_logs", on_delete=models.CASCADE)
    capability = models.CharField(max_length=32, choices=ModelConfig.CAPABILITY_CHOICES)
    provider = models.CharField(max_length=32, default="litellm")
    alias = models.CharField(max_length=255)
    upstream_model = models.CharField(max_length=255, blank=True, default="")
    stage = models.CharField(max_length=32, blank=True, default="")  # chat / embedding / rerank / fallback
    status = models.CharField(max_length=32, default=STATUS_SUCCESS)
    latency_ms = models.PositiveIntegerField(default=0)
    request_tokens = models.PositiveIntegerField(default=0)
    response_tokens = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    request_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

设计要点：

- 只记录摘要，不保存原始输入输出；
- `trace_id` 用于“一个请求走了哪些模型”的 trace 视图；
- `stage` 用于标记主路径、fallback、embedding 等阶段；
- 默认由 LiteLLM provider 调用层统一写入。

### 5.3 迁移逻辑

新增迁移服务或管理命令：

1. 读取当前有效的 `chat`、`embedding` 激活配置；
2. 生成对应 LiteLLM alias / upstream mapping；
3. 创建或更新 `provider=litellm` 的 `ModelConfig`；
4. 同步 LiteLLM 配置；
5. 切换默认激活项；
6. 保留旧记录用于兼容与审计，但退出管理台主路径。

迁移失败时必须明确返回：

- 哪个 capability 失败；
- 失败发生在配置转换、LiteLLM 同步还是激活切换；
- 当前默认链路是否已改变。

### 5.4 API 设计

在现有 `/api/ops/` 口径下补齐以下接口：

#### 网关总览

- `GET /api/ops/llm/gateway/summary/`
  - 返回：
    - gateway health
    - recent sync status
    - error rate
    - top models
    - recent errors

#### 模型与路由

- `GET /api/ops/model-configs/`
  - 扩展返回 LiteLLM alias、上游 provider、真实模型、fallback、weight、masked key 信息；
- `POST /api/ops/model-configs/`
  - 新建 LiteLLM 模型路由；
- `PATCH /api/ops/model-configs/{id}/`
  - 更新 alias / upstream / fallback / weight / key；
- `POST /api/ops/model-configs/{id}/activation/`
  - 切换默认模型；
- `POST /api/ops/model-configs/{id}/sync-litellm/`
  - 单模型同步；
- `POST /api/ops/model-configs/migrate-to-litellm/`
  - 执行迁移。

#### 日志与观测

- `GET /api/ops/llm/gateway/logs/`
  - 支持 `model / status / time` 筛选；
- `GET /api/ops/llm/gateway/logs/summary/`
  - 返回请求量、错误率、平均延迟、错误分布；
- `GET /api/ops/llm/gateway/traces/{trace_id}/`
  - 返回一次请求涉及的模型链路摘要；
- `GET /api/ops/llm/gateway/errors/`
  - 返回错误类型聚合与最近错误样本。

#### 成本与使用

- `GET /api/ops/llm/gateway/costs/summary/`
  - 返回 token 使用、成本统计、模型占比；
- `GET /api/ops/llm/gateway/costs/timeseries/`
  - 返回按时间粒度聚合的 usage / cost；
- `GET /api/ops/llm/gateway/costs/models/`
  - 返回按模型聚合的成本与请求占比。

## 6. 前端设计

前端沿用现有 `admin` 布局与 `admin-llm` 导航分组，不新增独立壳层。

### 6.1 页面结构

#### Dashboard

总览页采用精简结构，只放：

- Gateway health
- error rate
- top models
- 最近错误

不在该页承载配置编辑与复杂日志。

#### Models / Routing

专门负责配置治理：

- alias -> model mapping
- 默认模型
- fallback / 权重
- key 管理

页面核心体验是让管理台能直接回答：

- `chat-default` 现在指向哪个模型；
- 有哪些 fallback；
- 当前 key 是否已配置；
- 当前配置是否已同步进 LiteLLM。

#### Logs / Observability

这是重点页，负责：

- `model / status / time` 筛选；
- 请求级表格；
- 错误分析；
- latency 分布；
- trace 入口。

请求级表格建议至少显示：

- 时间
- alias
- upstream model
- capability / stage
- latency
- token
- status
- error
- trace

#### Cost / Usage

独立页面，负责：

- token 使用
- 成本统计
- 模型占比

该页默认回答：

- 哪些模型消耗最高；
- 哪个模型请求占比最高；
- 成本主要来自输入 token 还是输出 token。

### 6.2 视觉与交互方向

延续仓库现有 admin shell 的克制、制度化风格，不做装饰型大盘。

页面视觉原则：

- 使用现有 `AppSectionCard` 作为信息承载单元；
- 通过上方摘要带 + 下方分析区域形成清晰层级；
- 日志页采用高信息密度表格和侧边筛选；
- 成本页优先用可解释的统计模块和占比视图，不做假趋势叙事。

## 7. 错误处理与回退

### 7.1 错误处理

- LiteLLM 不可达：管理台明确提示 gateway unhealthy；
- alias 缺失：请求失败并记录摘要日志；
- 同步失败：写入 `LiteLLMSyncEvent`，并在 Dashboard 暴露最近错误；
- 上游 key 失效：模型配置页显示 key 异常状态，但不回显明文。

日志写入失败属于旁路失败：

- 不阻断主请求完成；
- 必须记录结构化错误；
- Dashboard 或健康摘要中要能看到日志链路异常。

### 7.2 回退

回退路径必须明确：

1. 可以切回迁移前的默认配置；
2. 可以停用新的 LiteLLM 路由并重新激活兼容配置；
3. 任何同步或迁移操作都要返回“当前默认链路是否已改变”。

## 8. 测试与验收

### 8.1 后端

至少覆盖：

- 迁移服务测试；
- LiteLLM 配置同步测试；
- 调用摘要日志写入测试；
- 日志筛选与 trace 查询测试；
- 成本统计聚合测试。

### 8.2 前端

至少覆盖：

- LiteLLM 管理 API client；
- 日志/成本数据 normalizer；
- Models / Routing 页面交互；
- Logs / Observability 页面筛选与表格渲染；
- Cost / Usage 页面统计展示。

### 8.3 最低验收标准

当本轮完成时，必须满足：

- 当前 `chat`、`embedding` 能通过 LiteLLM 统一配置并正常激活；
- 管理台存在 4 个清晰页面：Dashboard / Models & Routing / Logs & Observability / Cost & Usage；
- Logs 页能查看请求级摘要，不包含原始 prompt / response；
- Cost 页能查看 token、cost、模型占比；
- LiteLLM 配置同步与迁移失败都能明确暴露，不制造成功假象；
- 不新增重型状态服务，不偏离独立 LiteLLM 容器路线。

## 9. 与现有文档的关系

- 本文是 LiteLLM 全面接入与管理台闭环的实现设计；
- 它遵守主决策文档中“LiteLLM 作为统一网关候选、保持独立容器”的定位；
- 它遵守生产约束文档中“不新增重型状态服务、必须有明确回退语义”的要求；
- 它把组件边界文档中关于 LiteLLM 的“配置语义清楚、部署依赖清楚、回退语义清楚”具体落实到数据模型、接口和页面结构。
