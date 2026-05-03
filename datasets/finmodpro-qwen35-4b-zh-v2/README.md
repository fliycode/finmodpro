# FinModPro Qwen 3.5 4B 中文 SFT 数据集 v2

本目录包含 30,000 条可直接用于 LLaMA-Factory 的中文 SFT 数据。

## 相比 v1 的改进

- 公司名从 16 个扩充至 378 个，覆盖 12 个行业
- 每个任务类型 8-12 种 prompt 变体，降低模板化程度
- 置信度分数使用连续随机值（0.55-0.95），非离散采样
- risk_type 与后端 schema 对齐（liquidity/credit/market/compliance/operation）
- 增加边缘样本：多事件文档、无事件文档、混合情绪文本
- 增加平台身份与边界 Q&A（含拒绝场景）
- 增加资料不足处理场景

## 文件

- `data.json`：30,000 条 OpenAI messages 格式样本
- `dataset_info.json`：LLaMA-Factory 数据集注册配置
- `manifest.json`：生成信息和分类统计

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
