# FinModPro Qwen 3.5 4B 第一版训练数据包

更新日期：2026-05-03

本文档记录第一版本地训练数据包的生成结果。数据包本体位于 `backend/media/`，该目录按仓库规则被 `.gitignore` 忽略，因此不随 Git 提交。

## 输出位置

```text
backend/media/fine_tune_datasets/finmodpro-qwen35-4b-v1/
```

核心文件：

- `train.jsonl`：27,000 条
- `eval.jsonl`：3,000 条
- `dataset_info.json`：LLaMA-Factory 数据集注册片段
- `manifest.json`：来源和数量统计
- `preview.json`：按来源抽样预览
- `source-cache/`：公开数据源下载缓存，仅用于复现和审计

当前数据包总大小约 108MB，其中 `source-cache/` 约 72MB。

## 数据规模

总样本数：30,000 条。

| 来源 | 条数 |
| --- | ---: |
| FinModPro 自建样本 | 13,143 |
| FinGPT Sentiment | 4,000 |
| Finance-Alpaca | 3,000 |
| FinGPT FIQA QA | 2,500 |
| FinGPT FinRED | 2,500 |
| FinGPT ConvFinQA | 2,000 |
| FinGPT Headline | 2,000 |
| FinGPT NER | 607 |
| DISC-FIN-SFT 样例 | 250 |

## 校验结果

已完成基础校验：

- `train.jsonl + eval.jsonl = 30,000` 行
- 所有样本均为 messages 格式
- 最后一条消息均为 `assistant`
- 未把内部 `_source` 字段写入训练 JSONL
- 已过滤明显非金融的通用写作、随机数、笑话类样本

## 复现命令

生成脚本：

```text
scripts/build_finmodpro_training_data_v1.py
```

首次生成并下载源文件：

```bash
backend/.venv/bin/python scripts/build_finmodpro_training_data_v1.py --download
```

复用已下载的 `source-cache/` 重新生成：

```bash
backend/.venv/bin/python scripts/build_finmodpro_training_data_v1.py
```

## LLaMA-Factory 用法

训练机上可使用类似命令：

```bash
llamafactory-cli train \
  --stage sft \
  --do_train true \
  --model_name_or_path <你的-qwen3.5-4b-路径> \
  --dataset_dir /root/finmodpro/backend/media/fine_tune_datasets/finmodpro-qwen35-4b-v1 \
  --dataset finmodpro_qwen35_4b_v1_train \
  --eval_dataset finmodpro_qwen35_4b_v1_eval \
  --finetuning_type lora
```

## 已知缺口

- DocFEE 未纳入，因为当前服务器下载 Figshare 数据返回 403。
- SEC / BBT-FinCorpus 未纳入，它们更适合 continued pretrain 或 RAG 原始语料，不适合第一轮 4B SFT。
- 当前自建样本用于第一版跑通和风格约束，后续应继续补人工审核样本。

