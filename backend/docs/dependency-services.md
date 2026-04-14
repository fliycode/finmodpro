# FinModPro 依赖服务启动说明

本文档面向新机器或本地演示环境，说明 `MySQL / Redis / Milvus / Ollama` 在当前仓库里的真实作用、推荐默认值、启动方式和最小验证。

## 适用范围

当前仓库的默认本地方案是：

- 数据库：SQLite
- 缓存：Django `LocMemCache`
- Celery：内存 broker / result backend
- 向量存储：Milvus Lite（通过 `MILVUS_URI=milvus.db` 文件模式）
- 模型服务：Ollama，可选；只有在你需要真实聊天/embedding 能力时才需要

这意味着：

- 想先把前后端跑起来，不需要先装 `MySQL / Redis`
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

## 七、推荐组合

### 最小本地启动

适合先把前后端跑起来：

- SQLite
- LocMemCache
- Celery memory backend
- Milvus Lite（`milvus.db`）
- Ollama 可不启

### 更完整本地演示

适合演示更贴近部署环境的依赖：

- MySQL Docker
- Redis Docker
- Milvus Lite（当前仓库默认推荐）或你自己的远程 Milvus URI
- Ollama 本机启动

## 八、常用联调命令

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

## 七、当前边界说明

- 本文档只覆盖当前仓库代码已经真实读取或依赖到的服务与配置
- 当前 **不** 提供 Docker Compose 一键编排
- 当前 **不** 把 Ollama endpoint / model name 写进 `.env`，因为仓库实际是通过 `ModelConfig` 管理它们
- 当前 Milvus 的默认路径是 Lite 模式，不应把“远程 Milvus 集群部署”描述成仓库默认能力
