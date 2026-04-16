# FinModPro LLaMA-Factory 训练子系统接入设计

日期：2026-04-16

## 1. 目标

为 FinModPro 补齐“训练执行面”的系统边界，但不把 GPU 训练本身塞进 Django 主系统。

第一阶段目标不是实现“一键在线训练”，而是把当前已经存在的微调登记能力升级为一个可对接外部训练系统的 control plane，使 FinModPro 可以稳定完成四件事：

- 导出可供 LLaMA-Factory 使用的训练数据集
- 发起并跟踪外部训练任务
- 接收训练状态与产物回写
- 将训练产物注册回 LiteLLM 可消费的模型入口

## 2. 当前事实

当前仓库已经具备训练登记雏形，但仍停留在 registry 层：

- `llm.models.FineTuneRun` 目前只保存 `base_model / dataset_name / dataset_version / strategy / status / artifact_path / metrics / notes`
- `llm.services.fine_tune_service` 当前只做 CRUD，不负责任务下发、回调验签、状态同步
- `llm.controllers.fine_tune_controller` 目前是管理台 CRUD API，不是训练执行 API
- `frontend/src/components/ModelConfig.vue` 已有“微调登记”界面，但文案也明确它还是“外部训练回写后登记”
- `LiteLLM` 已经接入，未来外部训练模型只要能暴露成 OpenAI-compatible / LiteLLM alias，就可以被应用层复用

这说明当前系统缺的不是“再做一个训练页面”，而是：

- 训练数据导出契约
- 外部任务调度与状态回写契约
- 训练产物到推理入口的回流契约

## 3. 范围

### 3.1 In Scope

- 为 `FineTuneRun` 定义更完整的任务元数据边界
- 为训练数据导出定义 LLaMA-Factory 可消费的数据包格式
- 定义 FinModPro 与外部训练执行器之间的 API / callback 边界
- 定义训练产物如何回流到推理服务和 LiteLLM
- 保持当前管理台“微调登记”语义向“微调任务”平滑演进
- 为后续实现准备最小数据库与 API 变更方向

### 3.2 Out of Scope

- 在 Django / Celery 中直接运行 `llamafactory-cli`
- 在主系统中直接管理 GPU、CUDA、Deepspeed、vLLM 进程
- 数据标注平台、训练集清洗平台、自动评测平台的完整建设
- 复杂的训练策略编排，例如多阶段 SFT -> DPO pipeline
- 在第一阶段支持所有 LLaMA-Factory 算法与导出组合

## 4. 设计原则

- 训练执行与在线应用必须解耦
- Django 只做 control plane，不做 GPU worker
- 训练结果必须最终落回当前 `ModelConfig -> runtime_service -> LiteLLM` 的既有调用边界
- 数据集导出格式必须优先兼容 LLaMA-Factory 官方约定，而不是自定义一套闭门格式
- 回调与状态同步必须显式鉴权，不能复用后台人工操作权限
- 第一阶段先做 LoRA / QLoRA 风格任务，避免范围爆炸

## 5. 官方能力边界对 FinModPro 的含义

LLaMA-Factory 官方文档当前稳定强调几件事：

- 支持以 YAML / CLI 方式执行 SFT、LoRA、QLoRA、DPO 等训练
- 自定义数据集仍以 `dataset_info.json` 作为数据集注册入口
- 训练后可以执行导出 / merge / quantization
- 推理侧支持 `Transformers` 与 `vLLM`
- 可以暴露 API 服务，但它本质上仍属于训练/推理子系统，不属于业务应用层

这对 FinModPro 的直接含义是：

1. FinModPro 不应该直接变成训练运行器
2. FinModPro 需要对外提供“训练任务输入”
3. 外部训练系统需要对内回写“训练结果”
4. 最终线上推理最好由 `vLLM` 或其他 OpenAI-compatible 服务承接，再由 LiteLLM 收口

## 6. 目标架构

### 6.1 组件职责

#### FinModPro

负责：

- 训练任务登记
- 数据集版本与来源登记
- 训练输入打包与导出
- 外部任务状态同步
- 产物注册与模型候选管理

不负责：

- 实际 GPU 训练
- 长时间占用显卡资源
- 在业务进程内加载大模型权重

#### LLaMA-Factory Runner

负责：

- 拉取或接收训练数据包
- 按指定训练配置运行 `llamafactory-cli`
- 输出 adapter / merged model / 指标 / 日志
- 将最终状态回写给 FinModPro

不负责：

- 业务权限判断
- 平台主模型选择逻辑
- 在线业务路由

#### Inference Deployment

负责：

- 承载训练后的推理模型
- 暴露 OpenAI-compatible 或其他可接入 LiteLLM 的接口
- 输出 endpoint / model alias / 部署状态

### 6.2 推荐边界

推荐采用 4 层结构：

1. `FinModPro control plane`
2. `Dataset export bundle`
3. `LLaMA-Factory execution plane`
4. `Inference deployment + LiteLLM registration`

这 4 层之间只交换明确工件，不共享运行时进程。

## 7. 运行时数据流

第一阶段建议的数据流：

1. 管理员在 FinModPro 里选择基础模型、数据集、训练策略，创建 `FineTuneRun`
2. FinModPro 生成训练输入快照：
   - 训练参数摘要
   - 数据集导出包
   - callback 地址与鉴权 token
3. 外部执行器拉取数据包或由 FinModPro 主动下发任务描述
4. LLaMA-Factory Runner 执行训练
5. 训练中回写：
   - `pending -> running`
   - 进度摘要
   - 日志链接或运行 id
6. 训练完成后回写：
   - `succeeded` / `failed`
   - metrics
   - artifact manifest
   - 可选部署建议
7. 如产物已部署到推理服务：
   - FinModPro 创建或更新候选 `ModelConfig`
   - 将 endpoint / alias 指向 LiteLLM 或上游推理服务
8. 应用层继续通过当前 `runtime_service` 调用，不感知该模型是否来自外部训练

## 8. 数据集导出契约

### 8.1 第一阶段目标格式

第一阶段不要把训练数据直接塞进数据库 JSON 字段里，而应导出一个可审计的数据包目录，例如：

```text
exports/fine-tune-runs/ft-20260416-001/
  manifest.json
  dataset_info.json
  train.jsonl
  eval.jsonl
  prompt_template.md
  README.md
```

其中：

- `dataset_info.json` 对齐 LLaMA-Factory 官方数据集注册格式
- `train.jsonl` / `eval.jsonl` 存放实际样本
- `manifest.json` 记录 FinModPro 侧导出元信息
- `prompt_template.md` 记录本次数据构造使用的模板摘要

### 8.2 Manifest 最小字段

建议 `manifest.json` 至少包含：

- `fine_tune_run_id`
- `base_model_id`
- `base_model_name`
- `dataset_name`
- `dataset_version`
- `exported_at`
- `task_type`
- `sample_count`
- `format`
- `created_by`
- `source_snapshot`

### 8.3 为什么先做导出快照

训练问题最难排查的地方，不是“有没有按钮”，而是“本次训练到底用的什么数据”。  
因此第一阶段必须优先保证：

- 数据可复现
- 配置可复现
- 训练结果能追溯到具体快照

## 9. FineTuneRun 的演进方向

当前 `FineTuneRun` 字段太轻，只够做登记，不够做任务控制面。  
第一阶段建议把它演进为“任务记录 + 产物登记”的承载面。

### 9.1 建议新增的字段族

- 任务标识：
  - `run_key`
  - `external_job_id`
  - `runner_name`
- 数据快照：
  - `export_path`
  - `dataset_manifest`
  - `sample_counts`
- 训练配置：
  - `training_config`
  - `export_config`
  - `base_model_ref`
- 状态同步：
  - `queued_at`
  - `started_at`
  - `finished_at`
  - `failure_reason`
  - `last_heartbeat_at`
- 产物登记：
  - `artifact_manifest`
  - `deployment_endpoint`
  - `deployment_model_name`
  - `registered_model_config`

### 9.2 为什么不直接拆很多新表

第一阶段更适合先把高波动字段放在 JSON 和少量关键索引字段里，而不是一开始就设计重型训练域模型。  
原因是：

- 训练产物类型会快速变化
- 还没到需要多层训练工作流编排的阶段
- 当前仓库需要先把“控制面跑通”，不是先做训练平台建模论文

## 10. API 边界设计

### 10.1 FinModPro 对管理台

继续保留当前 CRUD API，但语义升级为：

- 创建 `FineTuneRun`
- 查看任务状态
- 查看数据集导出信息
- 查看产物与回流状态

### 10.2 FinModPro 对外部 Runner

第一阶段建议新增两类接口：

1. 任务输入接口
   - 获取某次训练的 export manifest / 数据包地址 / callback 信息
2. 状态回写接口
   - 更新状态
   - 回写 metrics
   - 回写 artifact manifest
   - 回写部署入口

### 10.3 鉴权要求

外部 Runner 不能复用后台管理员登录态。  
建议第一阶段使用：

- 每次任务生成独立 callback token
- token 只允许更新指定 `FineTuneRun`
- token 可过期、可撤销

这样可以避免把训练节点暴露成“有后台写权限的系统用户”。

## 11. 与 LiteLLM 的集成边界

训练完成后，FinModPro 不应直接让业务配置指向一条生裸 endpoint。  
推荐路径是：

1. 训练产物部署到 `vLLM` 或其他 OpenAI-compatible 推理服务
2. LiteLLM 为该模型创建统一 alias
3. FinModPro 创建新的 `ModelConfig(provider=litellm)`
4. 管理员决定是否将其切换为 active chat 模型

这样当前应用层不会区分：

- DeepSeek 官方模型
- Ollama 本地模型
- 外部训练后的自有模型

所有模型都沿用同一条 runtime 边界。

## 12. 第一阶段明确不做

- 不在 Django 请求内直接触发训练
- 不在 Celery worker 里执行 GPU 训练
- 不做自动部署到生产推理集群
- 不做训练日志全文存储
- 不做复杂实验管理平台
- 不做自动选择最优 checkpoint 并替换线上模型

## 13. 验证标准

当这一阶段真正实施时，最小完成标准应是：

1. 可以从 FinModPro 生成一份 LLaMA-Factory 可消费的数据导出包
2. 可以创建一条带 job metadata 的 `FineTuneRun`
3. 外部 Runner 能安全回写状态与产物信息
4. 训练成功后，能在管理台看到：
   - 数据集快照
   - 训练状态
   - 产物位置
   - 候选部署入口
5. 成功把一个外部训练产物注册成新的 `litellm` 候选模型

## 14. 风险与后续顺序

### 14.1 主要风险

- 数据集格式如果和业务任务类型脱节，会导致“能训练但没价值”
- 如果没有快照与回调鉴权，训练链路会不可审计
- 如果训练产物不经过 LiteLLM 收口，应用层会重新分叉成多种模型接法

### 14.2 建议顺序

1. 先做 `FineTuneRun` 控制面扩展设计
2. 再做训练数据集导出与 manifest
3. 再做 callback / 状态同步 API
4. 最后做训练产物回流到 LiteLLM / ModelConfig 的闭环

## 15. 结论

FinModPro 当前已经有训练登记层，但还没有训练控制面。  
`LLaMA-Factory` 的正确接法不是“塞进主系统”，而是作为独立训练执行子系统，由 FinModPro 负责 control plane、数据导出、状态同步和产物回流。

只要沿着这个边界推进，当前已经落地的 `LiteLLM + Langfuse + Unstructured` 不需要返工；未来外部训练模型也能继续复用当前应用层的统一模型入口。
