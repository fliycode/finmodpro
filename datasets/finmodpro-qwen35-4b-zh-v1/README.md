# FinModPro Qwen 3.5 4B 中文 SFT 数据集 v1

本目录包含 30,000 条可直接用于 LLaMA-Factory 的中文 SFT 数据。

## 文件

- `data.json`：30,000 条 OpenAI messages 格式样本
- `dataset_info.json`：LLaMA-Factory 数据集注册配置
- `manifest.json`：生成信息和分类统计

## 使用方式

将本目录作为 `--dataset_dir`，数据集名称使用 `finmodpro_zh_sft_v1`。

```bash
llamafactory-cli train \
  --stage sft \
  --do_train true \
  --model_name_or_path <你的-qwen3.5-4b-路径> \
  --dataset_dir datasets/finmodpro-qwen35-4b-zh-v1 \
  --dataset finmodpro_zh_sft_v1 \
  --finetuning_type lora
```

如需自动切分验证集，可在训练参数中使用 LLaMA-Factory 的 `val_size`。
