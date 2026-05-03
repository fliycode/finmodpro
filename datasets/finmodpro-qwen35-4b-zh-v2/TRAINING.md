# Qwen 3.5 4B LoRA 训练指南

## 快速开始

```bash
# 1. 安装 LLaMA-Factory
pip install llamafactory[torch]

# 2. 下载模型（如果还没有）
# 方式 A：从 HuggingFace
huggingface-cli download Qwen/Qwen3.5-4B --local-dir /data/models/Qwen3.5-4B

# 方式 B：从 ModelScope（国内更快）
modelscope download Qwen/Qwen3.5-4B --local_dir /data/models/Qwen3.5-4B

# 3. 开始训练
cd /root/finmodpro
llamafactory-cli train datasets/finmodpro-qwen35-4b-zh-v2/train_config.yaml
```

## 关键参数解释

### LoRA 参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `lora_rank` | **16** | LoRA 矩阵的秩。4B 模型用 16 足够，用 32 容易过拟合 |
| `lora_alpha` | **32** | 缩放因子，通常 = 2 × rank。控制 LoRA 更新的幅度 |
| `lora_dropout` | **0.05** | 随机丢弃 5% 的 LoRA 参数，正则化防过拟合 |
| `lora_target` | **all** | 对所有线性层（q/k/v/o/gate/up/down）都加 LoRA |

**为什么 rank=16 而不是 32/64？**
- 4B 模型参数量小，LoRA rank 过大会让可训练参数占比过高，失去 LoRA 的意义
- 30K 数据集不算大，rank=16 的容量已经足够
- 实测 rank=16 和 rank=32 效果差异很小，但 rank=16 训练更快、显存更省

### 训练超参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `learning_rate` | **2e-4** | LoRA SFT 的标准学习率。太高会震荡，太低收敛慢 |
| `num_train_epochs` | **3** | 30K 数据跑 3 轮。跑太多轮会过拟合 |
| `batch_size` | **4** | 单卡实际 batch size |
| `gradient_accumulation` | **8** | 有效 batch size = 4 × 8 = 32 |
| `warmup_ratio` | **0.05** | 前 5% steps 线性升温，避免初期不稳定 |
| `lr_scheduler` | **cosine** | 余弦退火，比 linear 更平滑 |

**有效 batch size 为什么选 32？**
- batch size 太小（如 8）：梯度噪声大，loss 震荡
- batch size 太大（如 128）：泛化能力下降，显存压力大
- 32 是 SFT 的 sweet spot，兼顾稳定性和泛化

### 显存需求估算

| 配置 | 显存占用 | 适用显卡 |
|------|----------|----------|
| bf16 + rank16 + batch4 | ~14 GB | RTX 4090 / A100 40GB |
| bf16 + rank16 + batch4 + grad_ckpt | ~10 GB | RTX 3090 / A100 40GB |
| 4bit量化 + rank16 + batch4 | ~6 GB | RTX 3080 / RTX 4070 |

### cutoff_len 选择

我们的数据集最大样本 ~464 字符 ≈ ~300 token（中文），设置 `cutoff_len: 1024` 留有充足余量。
如果显存紧张，可以降到 512，但需要先确认没有样本被截断。

## 多任务 SFT 的注意事项

数据集包含 8 种任务类型，其中有两种输出风格：
- **JSON 输出**（风险抽取、舆情分析）：需要严格格式
- **文本输出**（RAG 问答、摘要、计算）：自由文本

训练时不需要特别处理，LLaMA-Factory 会自动根据 messages 格式训练。
但要注意：
1. **系统提示词（system prompt）在训练中会被学习**，推理时必须使用相同的 system prompt
2. **JSON 输出任务**的格式一致性很重要——我们的数据集已经保证了这一点

## 训练监控

```bash
# 查看训练 loss 曲线（训练完成后）
cat output/finmodpro-qwen35-4b-v2-lora/trainer_state.json | python3 -c "
import json, sys
state = json.load(sys.stdin)
for log in state['log_history'][-10:]:
    step = log.get('step', '?')
    loss = log.get('loss', log.get('eval_loss', '?'))
    print(f'Step {step}: loss={loss}')
"
```

## 训练完成后

### 合并 LoRA 权重（可选）

```bash
llamafactory-cli export \
  --model_name_or_path /data/models/Qwen3.5-4B \
  --adapter_name_or_path output/finmodpro-qwen35-4b-v2-lora \
  --template qwen3 \
  --finetuning_type lora \
  --export_dir output/finmodpro-qwen35-4b-v2-merged \
  --export_size 2
```

### 推理测试

```bash
llamafactory-cli chat \
  --model_name_or_path /data/models/Qwen3.5-4B \
  --adapter_name_or_path output/finmodpro-qwen35-4b-v2-lora \
  --template qwen3
```

## 调参建议

如果训练效果不理想，按以下优先级调整：

### Loss 不下降
- 检查数据集格式是否正确
- 检查 template 是否匹配模型（Qwen 3.x 用 `qwen3`）
- 降低学习率到 1e-4

### 过拟合（train loss 下降但 eval loss 上升）
- 减少 epochs（3 → 2）
- 增加 lora_dropout（0.05 → 0.1）
- 减小 lora_rank（16 → 8）

### JSON 输出格式不对
- 检查推理时的 system prompt 是否与训练数据一致
- 增加 JSON 输出任务的样本比例

### 生成质量差
- 增加 epochs（3 → 5）
- 降低学习率（2e-4 → 1e-4）
- 检查数据质量（是否有标注错误）
