# FinModPro 依赖服务启动说明

本文档面向新机器或本地演示环境，说明 `MySQL / Redis / Milvus / Ollama` 在当前仓库里的真实作用、推荐默认值、启动方式和最小验证。

## 适用范围

当前仓库的默认本地方案是：

- 数据库：SQLite
- 缓存：Django `LocMemCache`
- Celery：内存 broker / result backend
- Chat maintenance：标题、摘要、长期记忆任务默认随请求内联执行
- 向量存储：Milvus Lite（通过 `MILVUS_URI=milvus.db` 文件模式）
- 模型服务：Ollama，可选；只有在你需要真实聊天/embedding 能力时才需要

这意味着：

- 想先把前后端跑起来，不需要先装 `MySQL / Redis`
- 想先验证聊天问答链路，不额外起 Celery worker 也能看到标题/摘要/记忆维护逻辑跑通
- 想演示更完整的依赖链路，再按本文档启用对应服务

## 一、MySQL

### 当前作用

- 仓库通过 `DB_ENGINE=mysql` 切换到 MySQL
- 当前代码读取的变量是：
  - `DB_ENGINE`
  - `DB_NAME`
  - `DB_HOST`
  - `DB_PORT`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_CONN_MAX_AGE`

### 推荐默认值

- 本地最小启动：继续使用 `DB_ENGINE=sqlite`
- 需要演示 MySQL 时：本地 Docker 单机即可

### 启动命令

```bash
docker run -d \
  --name finmodpro-mysql \
  -e MYSQL_ROOT_PASSWORD=change-this-local-root-pw \
  -e MYSQL_DATABASE=finmodpro \
  -e MYSQL_USER=finmodpro \
  -e MYSQL_PASSWORD=finmodpro_dev_pw \
  -p 3306:3306 \
  mysql:8.4
```

### 最小验证

```bash
docker exec -it finmodpro-mysql \
  mysql -ufinmodpro -pfinmodpro_dev_pw -e "SHOW DATABASES;"
```

能看到 `finmodpro` 即可。

### 后端切换示例

```bash
export DB_ENGINE=mysql
export DB_NAME=finmodpro
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=finmodpro
export DB_PASSWORD=finmodpro_dev_pw
python manage.py migrate
```

## 二、Redis

### 当前作用

- 当前仓库只在 `REDIS_ENABLED=true` 时切到 Redis cache
- 代码读取的变量是：
  - `REDIS_ENABLED`
  - `REDIS_HOST`
  - `REDIS_PORT`
  - `REDIS_DB`
  - `REDIS_PASSWORD`

### 推荐默认值

- 本地最小启动：`REDIS_ENABLED=false`
- 需要演示 Redis cache / 更贴近部署环境时再开启

### 启动命令

```bash
docker run -d \
  --name finmodpro-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 最小验证

```bash
docker exec -it finmodpro-redis redis-cli ping
```

预期输出：

```text
PONG
```

### 后端切换示例

```bash
export REDIS_ENABLED=true
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=
```

## 三、Milvus

### 当前作用

- 当前向量能力通过 `MilvusClient(uri=settings.MILVUS_URI)` 连接
- 仓库默认使用的是 **Milvus Lite 文件模式**
- `backend/requirements.txt` 已包含：
  - `pymilvus`
  - `milvus-lite`

### 推荐默认值

- 当前本地/演示环境的推荐默认值就是：

```bash
export MILVUS_URI=milvus.db
export MILVUS_COLLECTION_NAME=knowledgebase_document_chunks
```

这不是远程 Milvus 服务，而是 Milvus Lite 本地文件数据库。对当前仓库来说，这是最符合真实能力、也是最省事的默认方案。

### 启动方式

Milvus Lite 不需要单独起一个后台进程。只要依赖安装完成，并且 `MILVUS_URI` 指向一个本地文件即可。

### 最小验证

```bash
cd /root/finmodpro/backend
./.venv/bin/python - <<'PY'
from pymilvus import MilvusClient
client = MilvusClient("milvus.db")
print(client.list_collections())
PY
```

命令能正常返回列表（空列表也可以）即可。

### 可选增强配置

- 如果你后续想接远程 / Docker 化的 Milvus 服务，可以把 `MILVUS_URI` 改成兼容的服务端 URI，例如：

```bash
export MILVUS_URI=http://127.0.0.1:19530
```

但这一点不是当前仓库的默认演示路径；当前代码和默认文档优先覆盖 `milvus.db` 的 Lite 模式。

## 四、Ollama

### 当前作用

- 当前聊天和 embedding provider 走 `ollama`
- 默认的 `ModelConfig` 种子记录会指向：
  - endpoint：`http://localhost:11434`
- **注意**：Ollama endpoint / model name 当前不是通过环境变量配置，而是存放在数据库的 `ModelConfig` 记录里

### 推荐默认值

- 如果你只想跑通基础页面和大部分非模型测试，可以先不启动 Ollama
- 如果你要演示真实问答、embedding、风险抽取等链路，建议本机启动 Ollama

### 安装与启动（Linux）

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

另开一个终端拉取当前仓库最接近默认值的模型：

```bash
ollama pull llama3.2
ollama pull mxbai-embed-large
```

### 最小验证

```bash
ollama -v
curl http://127.0.0.1:11434/api/tags
ollama list
```

### 与 FinModPro 的衔接

- 默认聊天模型和 embedding 模型记录由 `llm` app 的 `ModelConfig` 管理
- 如果你修改了实际可用模型名或 endpoint，请同步：
  - 通过 `/api/ops/model-configs`
  - 或直接调整数据库里的 `ModelConfig` 记录

## 五、LiteLLM

### 当前作用

- 第一阶段作为统一 LLM gateway
- Django 通过 `provider=litellm` 配置访问 LiteLLM，再由 LiteLLM 转发到 DeepSeek / Ollama / 未来外部模型

### 推荐默认值

- 本地最小启动：LiteLLM 可选
- 需要演示统一模型入口、为后续 Langfuse 接入做准备时开启

### 关键变量

- `LITELLM_INTERNAL_URL`
- `LITELLM_MASTER_KEY`
- `DEEPSEEK_API_KEY`

### 说明

- 管理台里保存的 LiteLLM endpoint 推荐使用 `http://localhost:4000`
- 生产环境运行时会由后端自动重写到容器内地址 `http://litellm:4000`

## 六、Langfuse

### 当前作用

- 第一阶段作为 Langfuse Cloud 观测后端
- LiteLLM 提供 LLM 调用级日志
- Django 补业务级 trace/span

### 关键变量

- `LANGFUSE_HOST`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

### 推荐默认值

- 本地开发默认可留空
- 接入 Cloud 后再填

## 七、Unstructured Parser Service

### 当前作用

- 为 `pdf/docx` 提供第一阶段结构化解析能力
- backend / celery 通过 `UNSTRUCTURED_API_URL` 访问内部 HTTP 服务
- 解析层与 chunk / embedding / retrieval 主链路解耦

### 推荐默认值

- 本地或容器开发环境：`UNSTRUCTURED_API_URL=http://unstructured-api:8000`
- `pdf` 允许回退到 `pypdf`
- `docx` 不做本地回退，解析失败应直接暴露给上游

### 关键变量

- `UNSTRUCTURED_API_URL`
- `UNSTRUCTURED_API_KEY`
- `UNSTRUCTURED_TIMEOUT_SECONDS`
- `UNSTRUCTURED_PDF_STRATEGY`
- `UNSTRUCTURED_DOCX_STRATEGY`
- `UNSTRUCTURED_PDF_FALLBACK_ENABLED`

### 说明

- 当前仓库只把 Unstructured 作为解析边界，不改变 chunk / embedding / retrieval / API 语义
- 生产部署时应把该服务保留在内部网络，不对公网暴露
- 当 Unstructured 不可用时，只有 `pdf` 会退回到 `pypdf`

## 八、推荐组合

## 八、LLaMA-Factory Runner

### 当前作用

- FinModPro 当前只把训练执行当成外部子系统
- 平台内部负责 `FineTuneRun` 控制面、导出包、callback 验证和候选模型登记
- 实际 GPU 训练仍由外部 `LLaMA-Factory` runner 执行

### 关键变量

- `FINE_TUNE_EXPORT_ROOT`
- `FINE_TUNE_EXPORT_BASE_URL`
- `FINE_TUNE_CALLBACK_SECRET`
- `LITELLM_GENERATED_CONFIG_ROOT`

### 当前边界

- 不在 Django / Celery 里直接执行 `llamafactory-cli`
- 训练成功后应优先回流到 `provider=litellm` 的候选 `ModelConfig`
- callback 只允许更新单个 `FineTuneRun`，不应复用后台管理员登录态
- 外部 runner 应通过 `GET /api/ops/fine-tunes/<id>/runner-spec/` 拉取执行说明，并使用 `X-Fine-Tune-Token` 做鉴权

### Runner 接口契约

当前仓库已经提供给外部执行器的最小契约有两条：

- `GET /api/ops/fine-tunes/<id>/runner-spec/`
  - 使用 `X-Fine-Tune-Token`
  - 返回训练框架、基础模型、训练参数摘要、export bundle 文件列表、callback URL
- `POST /api/ops/fine-tunes/<id>/callback/`
  - 使用同一个 `X-Fine-Tune-Token`
  - 回写 `status`、`metrics`、`artifact_manifest`、`deployment_endpoint`、`deployment_model_name`

`FINE_TUNE_EXPORT_BASE_URL` 的作用是给 `runner-spec` 里的导出文件生成可下载 URL。
如果这个变量为空，runner 仍然能拿到本地 `export_path` 和文件清单，但默认假设执行器与导出目录之间已经有共享挂载或别的文件分发手段。

`LITELLM_GENERATED_CONFIG_ROOT` 的作用是保存训练成功后自动生成的 LiteLLM alias 配置片段。
当前实现会在成功 callback 且带 `deployment_endpoint + deployment_model_name` 时生成 `<run_key>.yaml`，供后续部署或人工合并到主 `config.yaml`。

如果你想把这些片段渲染成一份可直接挂载给 LiteLLM 的配置文件，可以执行：

```bash
python3 scripts/render_litellm_config.py
```

默认会读取：

- `deploy/litellm/config.yaml`
- `deploy/litellm/generated/*.yaml`

并输出：

- `deploy/litellm/rendered.config.yaml`

当前 `docker-compose.prod.yml` 中的 `litellm` 服务默认挂载的也是这份 `rendered.config.yaml`，`scripts/deploy.sh` 会在 `docker compose up` 前先执行一次渲染。

### 最小 runner 命令

仓库当前自带一个最小 runner 客户端：

```bash
python3 scripts/llamafactory_runner.py \
  --api-base-url http://127.0.0.1:8000 \
  --run-id 1 \
  --token ftcb_xxx \
  --work-dir /tmp/finmodpro-runner \
  --deployment-endpoint http://127.0.0.1:9000/v1 \
  --deployment-model-name finmodpro-ft-chat \
  --dry-run
```

它会：

- 拉取 `runner-spec`
- 优先复用本地 `export_path`，否则按 `runner-spec` 里的文件 URL 下载 bundle
- 组装 `llamafactory-cli train ...` 命令
- 非 `--dry-run` 模式下回写 `running -> succeeded/failed`
- 如果提供部署参数，则在成功回写后自动生成 LiteLLM alias 配置片段

## 九、推荐组合

### 最小本地启动

适合先把前后端跑起来：

- SQLite
- LocMemCache
- Celery memory backend
- `CHAT_CONTEXT_RECENT_MESSAGES=8`
- `CHAT_MEMORY_RESULT_LIMIT=5`
- `CHAT_SUMMARY_TRIGGER_MESSAGES=6`
- Milvus Lite（`milvus.db`）
- Ollama 可不启

说明：

- 在这个默认组合下，聊天维护任务会因为 `CELERY_BROKER_URL=memory://` 而由 Django 进程直接执行，不依赖额外 worker
- 如果你把 `CHAT_*` 变量配成非法非整数值，Django 会在加载 `settings.py` 时启动失败
- 如果你把它们配成合法整数但值为 `0` 或负数，运行时会至少按 `1` 条处理

### 更完整本地演示

适合演示更贴近部署环境的依赖：

- MySQL Docker
- Redis Docker
- Redis 作为 Celery broker / backend（或其他真实 broker）
- Milvus Lite（当前仓库默认推荐）或你自己的远程 Milvus URI
- Ollama 本机启动

补充：

- 切到真实 broker 且未开启 `CELERY_TASK_ALWAYS_EAGER` 后，聊天标题、滚动摘要、长期记忆提取会改为异步入队
- 这种模式下需要额外启动 Celery worker；否则问答接口仍会返回，但后台维护结果不会更新

## 十、常用联调命令

```bash
cd /root/finmodpro/backend
cp .env.example .env
set -a
source .env
set +a
python manage.py migrate
python manage.py seed_rbac
python manage.py runserver 127.0.0.1:8000
```

如果你启用了 MySQL / Redis，请在 `source .env` 之前先把对应变量改好。

## 十一、当前边界说明

- 本文档只覆盖当前仓库代码已经真实读取或依赖到的服务与配置
- 当前 **不** 提供 Docker Compose 一键编排
- 当前 **不** 把 Ollama endpoint / model name 写进 `.env`，因为仓库实际是通过 `ModelConfig` 管理它们
- 当前 Milvus 的默认路径是 Lite 模式，不应把“远程 Milvus 集群部署”描述成仓库默认能力
