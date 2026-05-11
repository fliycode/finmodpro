# FinModPro Qwen 3.5 4B 中文 SFT 数据集 v2

本目录包含 30,000 条可直接用于 LLaMA-Factory 的中文 SFT 数据，目标模型为 **Qwen 3.5 4B**。

这份数据集的定位不是“大规模基础金融知识预训练语料”，而是更偏向 **FinModPro 主助手的多任务 SFT/行为对齐数据**：它同时训练结构化 JSON 输出、平台边界回答、财务计算、风险摘要和基于资料的文本回答。

## 一句话结论

- **最有价值的部分**：风险抽取、舆情分析、资料不足处理、平台边界、部分财务计算
- **最需要谨慎的部分**：通用 RAG 问答、文档摘要
- **适合当前系统的使用方式**：不要整包直接上；更适合先拆分、清洗，再作为主助手训练数据使用

## 数据定位

从当前仓库的训练链路和系统提示词看，`v2` 更适合承担以下目标：

1. 让模型学会当前系统要求的回答风格：专业、审慎、结构清晰、避免编造
2. 让模型学会当前系统专属输出约束：风险抽取/舆情分析 JSON、资料不足时的边界回答
3. 补足一部分金融任务能力：财务指标计算、风险摘要、文档问答

它 **不等价于** 以下两类数据：

1. **基础金融知识 continued pretrain 语料**：如大量财报、公告、研报原文
2. **高质量金融 reasoning 基准集**：如专门用于复杂金融问答和推理的公开 benchmark

如果后续需要提升模型对金融概念、报表结构、行业常识的理解，建议额外补一层“基础金融知识数据”，不要只依赖这份 `v2`。

## 相比 v1 的改进

- 公司名从 16 个扩充至 378 个，覆盖 12 个行业
- 每个任务类型 8-12 种 prompt 变体
- 置信度分数使用连续随机值（0.55-0.95）
- `risk_type` 与后端 schema 对齐（`liquidity/credit/market/compliance/operation`）
- 增加边缘样本：多事件文档、无事件文档、混合情绪文本
- 增加平台身份与边界 Q&A（含拒绝场景）
- 增加资料不足处理场景

## 文件

- `data.json`：30,000 条 OpenAI messages 格式样本
- `dataset_info.json`：LLaMA-Factory 数据集注册配置
- `manifest.json`：生成信息和分类统计
- `train_config.yaml`：LLaMA-Factory 训练配置
- `TRAINING.md`：训练参数与启动方式说明

## 官方任务构成

以下统计来自 `manifest.json`：

| 类型 | 数量 |
|---|---:|
| `risk_extraction` | 5850 |
| `sentiment` | 4000 |
| `rag_qa` | 6850 |
| `risk_report` | 3000 |
| `insufficient_info` | 2000 |
| `platform_identity` | 300 |
| `document_summary` | 4000 |
| `financial_calc` | 4000 |

## 当前仓库审阅结论

基于 `data.json` 的实际样本审阅，这份数据集更准确的理解方式是：

- 共 30,000 条样本
- 仅使用 3 个 system prompt：
  - `FinModPro 平台内置的专业金融分析助手`
  - `金融风险抽取助手`
  - `金融舆情分析助手`
- 输出风格分为两类：
  - **JSON 输出**：9850 条
  - **文本输出**：20150 条

按实际内容重分桶后，可近似理解为：

| 实际类型 | 数量 | 说明 |
|---|---:|---|
| `rag_qa` | 10676 | 基于资料回答问题，混入了较多平台边界问答和一般问答 |
| `risk_extraction` | 5850 | 风险事件抽取，严格 JSON 输出 |
| `sentiment` | 4000 | 舆情情绪与风险倾向分析，严格 JSON 输出 |
| `financial_calc` | 3906 | 财务指标计算、公式解释 |
| `risk_report` | 3000 | 风险线索到摘要的文本生成 |
| `insufficient_info` | 1483 | 资料不足处理、无法确定时的边界回答 |
| `document_summary` | 1007 | 文档摘要 |
| `platform_identity` | 78 | “你是谁/能做什么/不能做什么” |

> 上表是对当前静态数据的内容审阅结果，用于帮助理解训练风险和使用方式，不替代 `manifest.json` 的原始生成统计。

## 任务类型说明

### 1. 风险抽取 `risk_extraction`

- system prompt：`你是金融风险抽取助手。严格输出 JSON，不要输出 Markdown 或额外解释。`
- 输出 schema 与当前后端风险抽取接口保持一致
- 关键字段包括：
  - `company_name`
  - `risk_type`
  - `risk_level`
  - `event_time`
  - `summary`
  - `evidence_text`
  - `confidence_score`
  - `chunk_id`

**评价**：是当前数据集中最贴近线上系统的一类任务，建议优先保留。

### 2. 舆情分析 `sentiment`

- system prompt：`你是金融舆情分析助手。严格输出 JSON，不要输出 Markdown 或额外说明。`
- 输出字段包括：
  - `sentiment`
  - `risk_tendency`
  - `summary`
  - `confidence_score`
  - `evidence`

**评价**：质量相对稳定，也很贴近当前系统能力，建议优先保留。

### 3. 风险报告摘要 `risk_report`

- 输入通常是风险等级、风险类型和证据
- 输出是一段结构较统一的风险摘要

**评价**：可用，但模板感较强，更适合清洗后保留。

### 4. 财务计算 `financial_calc`

- 主要是财务指标计算和公式展开
- 有助于增强模型的解释型回答能力

**评价**：价值较高，但需要和低质量问答样本分开审视。

### 5. 资料不足 / 平台边界

- `insufficient_info`：训练模型在资料不足时明确说明不能确定
- `platform_identity`：训练模型说明自己是 FinModPro 助手、不能联网、不能执行交易、不能直接修改数据等边界

**评价**：这两类样本与当前系统“避免编造、明确边界”的产品定位高度一致，建议优先保留。

### 6. 通用问答与文档摘要

- `rag_qa`：基于资料回答问题
- `document_summary`：对文档正文生成摘要

**评价**：这两类是本数据集的主要风险来源，不能直接默认高质量。

## 已知风险与质量问题

### 1. `rag_qa` 中存在答非所问或引入题面外事实的样本

当前仓库审阅时发现，`rag_qa` 中有相当数量的样本带有以下特征：

- 用户给出的资料只包含 A 和 B
- 模型回答中引入了题面未出现的数字、财务指标或结论

这类样本会把模型训成“看起来像会答，但会补资料中没有的事实”，与当前系统要求的“基于资料、不要编造”相冲突。

### 2. `document_summary` 模板化明显

当前 `document_summary` 样本大量重复类似结构：

- “核心内容如下”
- “公司经营数据已包含在报告正文中”
- “建议结合其他资料综合判断”

这会让模型学会一种空泛、模板化的摘要风格，而不是真正提炼文档核心信息。

### 3. `risk_report` 语言风格偏单一

虽然 `risk_report` 基本符合任务方向，但不少样本只是固定模板替换公司名、风险类型和证据，语言多样性一般。

### 4. `risk_extraction` 中的空事件样本是有效负样本

当前审阅中可见一定数量的 `{"events": []}` 样本。这类样本通常用于教模型在“没有明显风险事件”时不要强行抽取，属于有效负样本，不应误删。

## 对当前系统的推荐用法

如果目标是训练 **FinModPro 主助手**，建议按以下方式处理：

| 分组 | 任务类型 | 建议 |
|---|---|---|
| A | `risk_extraction`, `sentiment`, `insufficient_info`, `platform_identity` | 直接作为高优先级保留 |
| B | `financial_calc`, `risk_report` | 清洗后保留 |
| C | `rag_qa`, `document_summary` | 默认高风险；建议重审、重写、降权或暂时移除 |

如果目标是训练 **专项结构化模型**（如风险抽取/舆情分析），则可以进一步提高 A 组权重，弱化文本自由生成任务。

## 是否包含基础金融知识训练

`v2` **包含一部分金融知识相关任务**，例如财务计算、资料问答、风险解释，但它本质上仍是 **多任务 SFT 数据**，不是大规模基础金融知识预训练集。

更准确地说：

- 它能教模型“怎么按 FinModPro 的方式回答金融问题”
- 但它不能替代“用大量金融原始语料做知识底座增强”

因此，如果后续需要提升模型的金融概念理解、财报结构感知或行业常识，建议另外补充：

1. 基础金融知识 SFT 数据
2. 或 continued pretrain 语料

## 使用方式

将本目录作为 `--dataset_dir`，数据集名称使用 `finmodpro_zh_sft_v2`。

```bash
llamafactory-cli train \
  --stage sft \
  --do_train true \
  --model_name_or_path <你的-qwen3.5-4b-路径> \
  --dataset_dir datasets/finmodpro-qwen35-4b-zh-v2 \
  --dataset finmodpro_zh_sft_v2 \
  --finetuning_type lora
```

完整训练参数与建议见 `TRAINING.md`。
