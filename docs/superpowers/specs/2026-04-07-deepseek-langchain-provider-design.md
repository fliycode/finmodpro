# FinModPro DeepSeek + LangChain 可配置对话模型设计

## 目标
在现有 `llm` 配置体系上扩展一个可配置的 `DeepSeek` 对话提供方，并通过 `LangChain` 完成调用适配。管理员可以在后台配置和切换平台级对话模型，智能问答页继续复用 `/api/chat/ask`，不感知底层模型来源。

本次设计解决三个问题：
- 现有聊天链路仅支持既有 provider，无法接入 `DeepSeek`
- 智能问答缺少统一的、可切换的运行时模型配置
- 管理员缺少一个可维护 API Key、模型名和启用状态的配置入口

## 设计原则
- 保留现有 `llm` 作为模型注册中心，不新建平行配置体系
- 运行时入口继续使用 `get_chat_provider()`，避免聊天、风险抽取等链路分叉
- 管理员配置平台级模型，不开放普通用户自定义 key
- `api_key` 不以明文回显给前端，接口仅返回掩码状态
- DeepSeek 接入先覆盖 `chat` 能力，不扩展到 embedding、rerank、fallback 和流式输出

## 后端架构
### 模型配置
扩展现有 `ModelConfig` 支持 `provider=deepseek`，并为对话模型保存以下字段：
- `name`
- `capability=chat`
- `provider` (`ollama` / `deepseek`)
- `model_name`
- `base_url`
- `api_key`
- `temperature`
- `max_tokens`
- `is_active`

如果当前模型表没有可承载这些字段的结构，则在兼容现有数据的前提下补齐字段或将 provider 额外配置收敛到统一配置字段中。激活逻辑继续保持“同一 capability 仅一个 active”。

### Provider 运行时
新增 `DeepSeekChatProvider`，内部使用 LangChain 的 OpenAI 兼容聊天模型适配 DeepSeek API。`runtime_service` 根据当前激活的 `chat` 配置构建不同 provider：
- `ollama` 继续走现有 provider
- `deepseek` 走 `DeepSeekChatProvider`

统一 provider 接口仍返回字符串答案，保持与现有 `chat.services.ask_service` 的契约一致，避免上层控制器和序列化结构大改。

### 管理接口
复用现有模型配置接口，支持创建、更新和读取 `deepseek` 类型对话模型。接口行为：
- 列表返回 provider、能力、模型名、启用状态、更新时间
- 详情返回 key 是否已配置及掩码占位，不回传明文
- 保存时允许新增或替换 `api_key`
- 激活某条 `chat` 配置时，自动停用其他 `chat` 活跃配置

建议增加“测试连接”接口，管理员可在保存前后验证 `base_url + api_key + model_name` 是否可用。

## 前端管理端
在现有模型配置页扩展 `DeepSeek` 对话模型表单，不新增割裂页面。管理员可配置：
- 配置名称
- 提供方
- 模型名
- Base URL
- API Key
- 温度
- 最大输出
- 是否设为启用模型

页面需区分“已保存 key”和“输入新 key”状态，编辑时不回显明文。列表页需要明确展示 provider 和当前启用项，并提供测试连接动作。

## 智能问答联通
`FinancialQA` 继续调用 `/api/chat/ask`。后端 `chat` 控制器和服务不感知具体厂商，只依赖 `get_chat_provider()` 返回的当前 provider。这样 DeepSeek 切换完成后，智能问答、后续复用 `chat` provider 的功能都能自动继承新配置。

## 错误处理
需要统一翻译以下错误：
- 未配置可用 `chat` 模型
- `api_key` 无效或缺失
- 上游限流
- 上游服务不可达
- 模型名无效或 provider 配置不完整

`/api/chat/ask` 和模型测试连接接口都返回结构化错误码，前端展示管理员可理解的中文提示，而不是原始上游异常。

## 测试范围
- `runtime_service` 能基于数据库配置构建 `DeepSeekChatProvider`
- `DeepSeekChatProvider` 能正确转换消息并调用 LangChain 客户端
- `chat_ask_view` 在 DeepSeek 正常、认证失败、限流、上游不可达时返回正确响应
- 模型配置接口正确处理 key 掩码、激活切换和 provider 字段
- 前端模型配置页能新增和编辑 `DeepSeek` 配置并触发测试连接

## 非目标
- 普通用户自定义 API Key
- 流式输出
- 多模型路由与 fallback
- DeepSeek embedding / rerank
- 全量重写现有 provider 抽象

## 验收标准
- 管理员可在后台新增一条 `DeepSeek` 对话模型配置并设为启用
- 智能问答页在不改接口的前提下成功返回 DeepSeek 生成结果
- 接口不会向前端返回明文 `api_key`
- 认证失败、限流、配置错误时，管理员和终端用户都能看到明确错误提示
- 现有 `ollama` 路径仍可继续工作，不被此次扩展破坏
