# FinModPro 训练数据集审核清单

更新日期：2026-05-03

本文档用于审核 FinModPro 智能助手的候选训练数据集。当前目标是先确定数据源和训练用途，暂不处理统一格式转换。后续如果确认采用，再把数据转换为 LLaMA-Factory 可消费的 `dataset_info.json`、`train.jsonl` 和 `eval.jsonl`。

## 1. 项目训练目标

FinModPro 当前助手不是通用聊天助手，而是金融知识库和风险分析平台助手。训练数据应优先服务以下能力：

- 平台身份和回答风格：明确自己是 FinModPro 平台助手，回答专业、审慎，不编造来源。
- 知识库问答：根据上传文档、财报、报告片段回答，并能承认上下文不足。
- 风险事件抽取：从金融文档中抽取公司、风险类型、等级、时间、证据和置信度。
- 舆情和情绪分析：判断金融文本情绪、风险倾向和证据。
- 财报数值问答：围绕财报表格和文字做问答、计算、推理。

仓库当前已有 LLaMA-Factory 控制面和 runner 客户端，但训练导出服务仍是占位样本，不是真实监督数据导出。因此数据集确认后，下一步应替换 `backend/llm/services/fine_tune_export_service.py` 中的占位样本生成逻辑。

## 2. 本地下载情况

本次下载目录：

```text
tmp/training-dataset-downloads/
```

说明：

- 该目录仅用于本机临时审核，没有提交到 Git。
- 当前机器磁盘空间很紧张，根分区剩余约 264MB，因此没有下载 SEC、BBT-FinCorpus 等大体量原始语料。
- Parquet 文件已下载，但本机未安装 `pyarrow` / `fastparquet`，本次没有在服务器上读取 parquet 内容，只记录文件、大小和公开数据集页面信息。

| 数据集 | 本地状态 | 本地文件 | 大小 | 审核用途 |
| --- | --- | --- | ---: | --- |
| Finance-Alpaca | 已下载 | `tmp/training-dataset-downloads/finance-alpaca/Cleaned_date.json` | 40.8MB | 通用英文金融问答 SFT |
| FinGPT FIQA QA | 已下载 | `tmp/training-dataset-downloads/fingpt-fiqa-qa/train.parquet` | 10.3MB | 金融问答 |
| FinGPT ConvFinQA | 已下载 | `tmp/training-dataset-downloads/fingpt-convfinqa/train.parquet`, `test.parquet` | 10.9MB | 财报多轮问答和数值推理 |
| FinGPT Sentiment | 已下载 | `tmp/training-dataset-downloads/fingpt-sentiment/train.parquet` | 6.1MB | 舆情/情绪分析 |
| FinGPT FinRED | 已下载 | `tmp/training-dataset-downloads/fingpt-finred/train.parquet`, `test.parquet` | 2.0MB | 金融关系抽取 |
| DISC-FIN-SFT 样例 | 已下载 | `tmp/training-dataset-downloads/disc-fin-sft/total.json` | 830KB | 中文金融助手样例审核 |
| FinGPT Headline | 已下载 | `tmp/training-dataset-downloads/fingpt-headline/train.parquet`, `test.parquet` | 632KB | 金融标题分类/事件判断 |
| FinGPT NER | 已下载 | `tmp/training-dataset-downloads/fingpt-ner/train.parquet`, `test.parquet` | 105KB | 金融实体识别 |
| DocFEE | 未下载 | Figshare 下载接口返回 403 | - | 中文金融事件抽取 |
| SEC / EDGAR 语料 | 未下载 | 空间不足 | - | continued pretrain 或 RAG 语料 |
| BBT-FinCorpus | 未下载 | 体量约 300GB，不适合当前机器 | - | 中文金融 continued pretrain |

## 3. 推荐优先级

### P0：优先采用

#### 3.1 DISC-FIN-SFT / DISC-FinLLM

来源：

- 模型卡：https://huggingface.co/Go4miii/DISC-FinLLM
- 样例数据：https://huggingface.co/datasets/eggbiscuit/DISC-FIN-SFT

适配度：高。

原因：

- 中文金融助手方向最贴近 FinModPro。
- 公开说明覆盖金融咨询、金融任务、金融计算、检索增强问答。
- 适合补平台助手的中文金融表达、咨询类问答和 RAG 风格回答。

当前风险：

- 本机下载的是 `eggbiscuit/DISC-FIN-SFT` 样例，只有 400 条，不是模型卡中描述的完整约 246k 条数据。
- 后续需要确认完整数据源、授权和可下载性。

建议用途：

- 作为中文金融 SFT 的核心数据源之一。
- 不建议只用该样例训练，只适合先审核字段和风格。

#### 3.2 DocFEE

来源：

- Figshare 页面：https://figshare.com/articles/dataset/_b_DocFEE_A_Document-Level_Chinese_Financial_Event_Extraction_Dataset_b_/28632464

适配度：高。

原因：

- 中文金融事件抽取数据集。
- 与 FinModPro 当前风险抽取链路直接对应。
- 可用于训练助手严格输出风险 JSON，而不是泛泛总结。

当前风险：

- 本次直接下载返回 403，需要通过浏览器、Figshare 登录态或备用镜像获取。
- 需要把事件标注映射到 FinModPro 当前字段：`company_name`、`risk_type`、`risk_level`、`event_time`、`summary`、`evidence_text`、`confidence_score`。

建议用途：

- 作为风险抽取能力的 P0 数据。
- 获取成功后，应优先做小样本人工审核，再转为 SFT JSON 输出样本。

#### 3.3 FinGPT 数据集套件

来源：

- 组织页：https://huggingface.co/FinGPT
- Sentiment：https://huggingface.co/datasets/FinGPT/fingpt-sentiment-train
- FIQA QA：https://huggingface.co/datasets/FinGPT/fingpt-fiqa_qa
- ConvFinQA：https://huggingface.co/datasets/FinGPT/fingpt-convfinqa
- FinRED：https://huggingface.co/datasets/FinGPT/fingpt-finred
- Headline：https://huggingface.co/datasets/FinGPT/fingpt-headline
- NER：https://huggingface.co/datasets/FinGPT/fingpt-ner

适配度：中高。

原因：

- 覆盖 FinModPro 需要的问答、舆情、关系抽取、实体识别、财报问答。
- 数据体量适中，已下载样本和 parquet 文件便于后续转换。
- 可作为多任务混合 SFT 的基础。

当前风险：

- 多数为英文或英文金融任务，不能替代中文金融助手数据。
- 结构化任务需要转换成 FinModPro 期望的助手输出，而不是直接按原标签训练。

建议用途：

- Sentiment：用于舆情和情绪分析模块。
- FIQA QA：用于金融问答能力。
- ConvFinQA：用于财报上下文和数值推理。
- FinRED / NER / Headline：用于抽取和分类能力增强。

### P1：可混入，但不做主数据

#### 3.4 Finance-Alpaca

来源：

- https://huggingface.co/datasets/gbharti/finance-alpaca

适配度：中。

原因：

- 本地 JSON 已确认 68,912 条。
- 字段包含 `instruction`、`input`、`output`、`text`，很容易转成 LLaMA-Factory Alpaca 或 messages 格式。
- 可增强通用金融问答能力。

当前风险：

- 主要是英文金融问答，偏通用金融知识，不够贴合 FinModPro 的中文知识库和风险抽取场景。
- 如果比例过高，可能把模型带向泛金融聊天，而不是平台助手。

建议用途：

- 作为低权重混入数据。
- 适合控制在 5% 到 10%。

#### 3.5 FinQA / TAT-QA / FinanceBench

来源：

- FinQA：https://finqasite.github.io/
- TAT-QA：https://nextplusplus.github.io/TAT-QA/
- FinanceBench：https://huggingface.co/datasets/PatronusAI/financebench

适配度：中。

原因：

- 适合财报问答、表格文字综合推理、金融 QA 评测。
- FinanceBench 更适合作为评测集，不适合做主训练集。

当前状态：

- 本次未下载。
- 建议先作为评测候选，不急于加入 SFT。

### P2：大语料，后续再考虑

#### 3.6 SEC / EDGAR 财报语料

来源：

- https://huggingface.co/datasets/PleIAs/SEC

适配度：中。

原因：

- 适合 continued pretrain 或构造 RAG 语料。
- 不适合直接作为 SFT 数据。

当前风险：

- 体量大，当前服务器剩余空间不足。
- 英文原始财报语料需要清洗和切块。

建议用途：

- 暂不下载到当前生产机。
- 后续在训练机或对象存储中处理。

#### 3.7 BBT-FinCorpus

来源：

- 论文：https://huggingface.co/papers/2302.09432

适配度：中高。

原因：

- 中文金融大语料，适合 continued pretrain。

当前风险：

- 体量约 300GB，远超当前机器可用空间。
- 不适合放在业务服务器处理。

建议用途：

- 后续如果要做中文金融 continued pretrain，再放到专门训练环境。

## 4. 推荐训练配比

第一轮建议先做 LoRA / QLoRA SFT，不做 continued pretrain。

建议混合比例：

| 数据来源 | 建议比例 | 目的 |
| --- | ---: | --- |
| FinModPro 自建样本 | 30% 到 40% | 平台身份、引用规则、风险 JSON 输出、知识库问答风格 |
| DISC-FIN-SFT 完整数据或精选中文金融样本 | 20% 到 30% | 中文金融助手能力 |
| DocFEE 转换样本 | 15% 到 25% | 风险事件抽取 |
| FinGPT Sentiment / Headline / FinRED / NER | 10% 到 20% | 舆情、分类、抽取 |
| FinGPT FIQA / ConvFinQA / Finance-Alpaca | 5% 到 15% | 金融问答和财报推理 |

不建议：

- 不建议只用 Finance-Alpaca 或 FinGPT 英文数据训练。
- 不建议把 SEC / BBT 原始语料直接放入 SFT。
- 不建议在没有 FinModPro 自建样本的情况下训练上线模型，否则模型不会稳定遵守平台引用和 JSON 输出契约。

## 5. 后续处理顺序

建议按以下顺序推进：

1. 审核本文档中的数据源，确认哪些可用于项目训练。
2. 解决 DocFEE 下载问题，补齐中文风险事件抽取数据。
3. 编写数据转换脚本，把已下载数据转成统一 `messages` JSONL。
4. 补 FinModPro 自建样本，至少覆盖：
   - 平台身份问答
   - 知识库引用回答
   - 上下文不足时的拒答/不确定表达
   - 风险抽取 JSON
   - 舆情 JSON
5. 替换 `backend/llm/services/fine_tune_export_service.py` 的占位导出。
6. 第一轮只训练小规模 LoRA，先跑评测，再决定是否扩大数据量。

## 6. 暂定保留的下载命令

以下命令仅供后续在训练机或空间充足环境中复现下载。本机临时下载文件不提交到 Git。

```bash
mkdir -p tmp/training-dataset-downloads

curl -L --fail --retry 3 --continue-at - \
  --output tmp/training-dataset-downloads/fingpt-sentiment/train.parquet \
  https://huggingface.co/datasets/FinGPT/fingpt-sentiment-train/resolve/main/data/train-00000-of-00001-dabab110260ac909.parquet

curl -L --fail --retry 3 --continue-at - \
  --output tmp/training-dataset-downloads/fingpt-fiqa-qa/train.parquet \
  https://huggingface.co/datasets/FinGPT/fingpt-fiqa_qa/resolve/main/data/train-00000-of-00001-ab79bf9300210e98.parquet

curl -L --fail --retry 3 --continue-at - \
  --output tmp/training-dataset-downloads/fingpt-convfinqa/train.parquet \
  https://huggingface.co/datasets/FinGPT/fingpt-convfinqa/resolve/main/data/train-00000-of-00001-7acaa8cc8803a6e9.parquet

curl -L --fail --retry 3 --continue-at - \
  --output tmp/training-dataset-downloads/finance-alpaca/Cleaned_date.json \
  https://huggingface.co/datasets/gbharti/finance-alpaca/resolve/main/Cleaned_date.json
```

## 7. 审核结论

当前已下载的数据足够做数据源审核和转换方案设计，但还不够直接训练一个符合 FinModPro 项目目标的模型。

最关键的缺口不是下载更多英文金融数据，而是补齐两类数据：

- FinModPro 自建监督样本，确保模型遵守平台身份、引用和 JSON 输出规则。
- 中文金融风险抽取数据，优先解决 DocFEE 或同类数据的可用性。

