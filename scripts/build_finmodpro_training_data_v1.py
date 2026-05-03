#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import random
import shutil
import time
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "backend"
    / "media"
    / "fine_tune_datasets"
    / "finmodpro-qwen35-4b-v1"
)

SYSTEM_PROMPT = (
    "你是 FinModPro 平台内置的专业金融分析助手，服务于企业财务、风险、知识库和投研分析场景。"
    "回答应专业、审慎、结构清晰；不要编造数据或来源。"
    "当参考资料不足时，明确说明不确定性。"
)

SOURCE_FILES = {
    "disc_fin_sft": [
        (
            "total.json",
            "https://huggingface.co/datasets/eggbiscuit/DISC-FIN-SFT/resolve/main/data/total.json",
        )
    ],
    "finance_alpaca": [
        (
            "Cleaned_date.json",
            "https://huggingface.co/datasets/gbharti/finance-alpaca/resolve/main/Cleaned_date.json",
        )
    ],
    "fingpt_sentiment": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-sentiment-train/resolve/main/data/train-00000-of-00001-dabab110260ac909.parquet",
        )
    ],
    "fingpt_fiqa_qa": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-fiqa_qa/resolve/main/data/train-00000-of-00001-ab79bf9300210e98.parquet",
        )
    ],
    "fingpt_convfinqa": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-convfinqa/resolve/main/data/train-00000-of-00001-7acaa8cc8803a6e9.parquet",
        ),
        (
            "test.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-convfinqa/resolve/main/data/test-00000-of-00001-bd8f5a41f70344d2.parquet",
        ),
    ],
    "fingpt_finred": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-finred/resolve/main/data/train-00000-of-00001-4af4d9c6fa204dbc.parquet",
        ),
        (
            "test.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-finred/resolve/main/data/test-00000-of-00001-34e4fcf97bb5994c.parquet",
        ),
    ],
    "fingpt_headline": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-headline/resolve/main/data/train-00000-of-00001-b8e635bd2f11110b.parquet",
        ),
        (
            "test.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-headline/resolve/main/data/test-00000-of-00001-cf9eaceb716e8f40.parquet",
        ),
    ],
    "fingpt_ner": [
        (
            "train.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-ner/resolve/main/data/train-00000-of-00001-d7135e50737d3d09.parquet",
        ),
        (
            "test.parquet",
            "https://huggingface.co/datasets/FinGPT/fingpt-ner/resolve/main/data/test-00000-of-00001-4b7e951bae254532.parquet",
        ),
    ],
}

TARGET_COUNTS = {
    "finmodpro_synthetic": 12000,
    "disc_fin_sft": 400,
    "finance_alpaca": 3000,
    "fingpt_sentiment": 4000,
    "fingpt_fiqa_qa": 2500,
    "fingpt_convfinqa": 2000,
    "fingpt_finred": 2500,
    "fingpt_headline": 2000,
    "fingpt_ner": 1600,
}

COMPANIES = [
    "华东能源",
    "北辰科技",
    "星河地产",
    "中联医药",
    "远航制造",
    "海川物流",
    "金石银行",
    "云岭消费",
    "启明材料",
    "恒泰证券",
    "东信电子",
    "瑞丰农业",
]

DOC_TYPES = ["年报", "半年报", "审计报告", "债券募集说明书", "经营简报", "风险排查纪要"]
METRICS = ["营业收入", "经营现金流", "资产负债率", "短期借款", "应收账款", "毛利率", "存货周转率"]
RISK_TYPES = [
    ("liquidity", "流动性风险"),
    ("credit", "信用风险"),
    ("market", "市场风险"),
    ("compliance", "合规风险"),
    ("operation", "经营风险"),
]
RISK_LEVELS = ["low", "medium", "high", "critical"]
INDUSTRIES = ["制造业", "房地产", "金融服务", "医药", "能源", "物流", "消费", "电子材料"]
FINANCE_KEYWORDS = (
    "finance",
    "financial",
    "invest",
    "investment",
    "stock",
    "bond",
    "fund",
    "bank",
    "loan",
    "debt",
    "credit",
    "tax",
    "income",
    "revenue",
    "profit",
    "loss",
    "market",
    "portfolio",
    "mortgage",
    "insurance",
    "asset",
    "liability",
    "equity",
    "dividend",
    "interest rate",
    "capital",
    "cash flow",
    "business expense",
    "投资",
    "金融",
    "股票",
    "债券",
    "基金",
    "银行",
    "贷款",
    "负债",
    "税",
    "收入",
    "利润",
    "市场",
    "资产",
    "现金流",
)
GENERIC_PROMPT_PATTERNS = (
    "generate a joke",
    "write a character bio",
    "random number",
    "create a script",
    "write a python program",
    "write a javascript",
    "write a function in javascript",
    "气候变化方面的重要性",
    "发表一篇简短的演讲",
)


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def stable_hash(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def make_sample(messages, source):
    normalized = []
    for message in messages:
        role = clean_text(message.get("role"))
        content = clean_text(message.get("content"))
        if role and content:
            normalized.append({"role": role, "content": content})
    if len(normalized) < 2:
        return None
    if normalized[-1]["role"] != "assistant":
        return None
    return {"messages": normalized, "_source": source}


def download_file(url, target_path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.stat().st_size > 0:
        return False
    tmp_path = target_path.with_suffix(target_path.suffix + ".part")
    if tmp_path.exists():
        tmp_path.unlink()
    with urllib.request.urlopen(url, timeout=120) as response:
        with tmp_path.open("wb") as output:
            shutil.copyfileobj(response, output)
    tmp_path.rename(target_path)
    return True


def download_sources(cache_dir):
    downloaded = []
    for source_name, files in SOURCE_FILES.items():
        for file_name, url in files:
            target_path = cache_dir / source_name / file_name
            did_download = download_file(url, target_path)
            downloaded.append(
                {
                    "source": source_name,
                    "file": str(target_path),
                    "downloaded": did_download,
                    "size_bytes": target_path.stat().st_size,
                    "url": url,
                }
            )
    return downloaded


def load_json_rows(path):
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "train", "rows"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def load_parquet_rows(path):
    dataframe = pd.read_parquet(path)
    return dataframe.to_dict("records")


def load_source_rows(cache_dir, source_name):
    rows = []
    for file_name, _url in SOURCE_FILES[source_name]:
        path = cache_dir / source_name / file_name
        if path.suffix == ".json":
            rows.extend(load_json_rows(path))
        elif path.suffix == ".parquet":
            rows.extend(load_parquet_rows(path))
        else:
            raise ValueError(f"Unsupported source file: {path}")
    return rows


def row_value(row, *keys):
    for key in keys:
        if key in row:
            value = clean_text(row.get(key))
            if value:
                return value
    return ""


def looks_like_generic_prompt(text):
    normalized = clean_text(text).lower()
    return any(pattern in normalized for pattern in GENERIC_PROMPT_PATTERNS)


def has_finance_context(text):
    normalized = clean_text(text).lower()
    return any(keyword in normalized for keyword in FINANCE_KEYWORDS)


def convert_instruction_row(row, source):
    instruction = row_value(row, "instruction", "prompt", "question", "query")
    if source == "finance_alpaca":
        input_text = row_value(row, "input")
    else:
        input_text = row_value(row, "input", "context", "text", "sentence", "news", "content")
    output = row_value(row, "output", "answer", "response", "label", "labels", "target")

    if not instruction and input_text:
        instruction = "请完成以下金融任务。"
    if not output:
        return None

    if source == "finance_alpaca":
        prompt_text = f"{instruction} {input_text}"
        if looks_like_generic_prompt(prompt_text):
            return None
        if not has_finance_context(prompt_text):
            return None

    user_content = instruction
    if input_text and input_text not in instruction:
        user_content = f"{instruction}\n\n输入：{input_text}"

    return make_sample(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": output},
        ],
        source,
    )


def convert_disc_row(row):
    instruction = row_value(row, "instruction")
    input_text = row_value(row, "input")
    output = row_value(row, "output")
    if not instruction or not output:
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = row.get("history") or []
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            history = []
    if isinstance(history, list):
        for turn in history:
            if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                user_turn = clean_text(turn[0])
                assistant_turn = clean_text(turn[1])
                if user_turn and assistant_turn:
                    messages.append({"role": "user", "content": user_turn})
                    messages.append({"role": "assistant", "content": assistant_turn})

    user_content = instruction
    if input_text:
        user_content = f"{instruction}\n\n输入：{input_text}"
    if looks_like_generic_prompt(user_content) or not has_finance_context(user_content):
        return None
    messages.append({"role": "user", "content": user_content})
    messages.append({"role": "assistant", "content": output})
    return make_sample(messages, "disc_fin_sft")


def convert_rows(source_name, rows):
    samples = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if source_name == "disc_fin_sft":
            sample = convert_disc_row(row)
        else:
            sample = convert_instruction_row(row, source_name)
        if sample is not None:
            samples.append(sample)
    return samples


def build_identity_samples(rng, limit):
    questions = [
        "你是谁？",
        "介绍一下你自己。",
        "你能帮我做什么？",
        "FinModPro 平台助手能做哪些事情？",
        "你和普通聊天机器人有什么区别？",
    ]
    answers = [
        "我是 FinModPro 平台内置的专业金融分析助手，主要服务于企业财务、风险、知识库问答和投研分析场景。我可以基于已上传资料进行问答、整理风险线索、辅助生成分析摘要，并在资料不足时明确说明不确定性。",
        "我是 FinModPro 的平台助手。我的重点不是泛泛聊天，而是围绕知识库、财务报告、风险事件和舆情文本提供审慎分析。涉及具体数据和来源时，我会优先依据参考资料回答。",
        "我可以协助进行金融知识库问答、财报和报告摘要、风险事件抽取、舆情倾向判断和模型评测说明。若问题超出资料范围，我会提示需要补充上下文或原始文档。",
    ]
    samples = []
    for index in range(limit):
        question = questions[index % len(questions)]
        answer = answers[index % len(answers)]
        samples.append(
            make_sample(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ],
                "finmodpro_synthetic",
            )
        )
    rng.shuffle(samples)
    return samples


def build_rag_samples(rng, limit):
    samples = []
    for index in range(limit):
        company = rng.choice(COMPANIES)
        doc_type = rng.choice(DOC_TYPES)
        metric = rng.choice(METRICS)
        industry = rng.choice(INDUSTRIES)
        year = rng.choice([2023, 2024, 2025])
        growth = rng.choice(["同比增长 8.4%", "同比下降 6.7%", "基本持平", "环比改善 3.2%"])
        risk_note = rng.choice(
            [
                "管理层提示短期偿债压力上升。",
                "审计师强调应收账款回收周期延长。",
                "公司披露主要原材料价格波动较大。",
                "监管问询关注收入确认和关联交易。",
            ]
        )
        context = (
            f"[1] {company}{year}{doc_type} 第 12 页：公司属于{industry}，{metric}{growth}。\n"
            f"[2] {company}{year}{doc_type} 第 31 页：{risk_note}"
        )
        question = rng.choice(
            [
                f"根据参考资料，概括{company}的主要经营变化和风险点。",
                f"{company}在{year}年的{metric}表现如何？需要注意什么？",
                f"请基于资料判断{company}是否存在需要关注的风险。",
            ]
        )
        answer = (
            f"根据资料[1]，{company}{year}年的{metric}表现为{growth}，需要结合其{industry}业务背景理解。"
            f"同时，资料[2]提示：{risk_note} 因此当前更适合将其列为需要跟踪的风险线索，而不是直接作出确定性结论。"
        )
        samples.append(
            make_sample(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"问题：{question}\n\n参考资料：\n{context}"},
                    {"role": "assistant", "content": answer},
                ],
                "finmodpro_synthetic",
            )
        )
    return samples


def build_uncertain_samples(rng, limit):
    samples = []
    for _index in range(limit):
        company = rng.choice(COMPANIES)
        metric = rng.choice(METRICS)
        question = f"请判断{company}未来一年{metric}是否会明显改善。"
        context = f"[1] {company}公告：公司将继续推进数字化系统建设，但未披露{metric}预测数据。"
        answer = (
            f"当前参考资料不足以判断{company}未来一年{metric}是否会明显改善。资料[1]只提到数字化建设安排，"
            "没有提供预测数据、管理层指引或可验证的财务假设。建议补充预算、经营计划、历史财务数据或管理层说明后再分析。"
        )
        samples.append(
            make_sample(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"问题：{question}\n\n参考资料：\n{context}"},
                    {"role": "assistant", "content": answer},
                ],
                "finmodpro_synthetic",
            )
        )
    return samples


def build_risk_samples(rng, limit):
    samples = []
    for index in range(limit):
        company = rng.choice(COMPANIES)
        risk_type, risk_label = rng.choice(RISK_TYPES)
        risk_level = rng.choice(RISK_LEVELS)
        chunk_id = 1000 + index
        evidence = rng.choice(
            [
                "公司短期借款余额较上年末增加 42%，一年内到期债务集中。",
                "公司因信息披露不完整收到监管问询，相关整改仍在推进。",
                "主要客户回款延迟，应收账款账龄超过一年的比例上升。",
                "海外订单受汇率和运费波动影响，毛利率连续两个季度下降。",
            ]
        )
        no_event = index % 9 == 0
        user_content = (
            "请从以下金融文档切块中抽取风险事件，严格输出 JSON，不要输出 markdown。\n\n"
            f"文档标题：{company}风险排查纪要\n"
            f"文档切块：\n[chunk_id={chunk_id}][chunk_index=0] {evidence if not no_event else '公司披露本期治理结构保持稳定，未发现重大异常事项。'}"
        )
        if no_event:
            payload = {"events": []}
        else:
            payload = {
                "events": [
                    {
                        "company_name": company,
                        "risk_type": risk_type,
                        "risk_level": risk_level,
                        "event_time": None,
                        "summary": f"{company}存在{risk_label}线索。",
                        "evidence_text": evidence,
                        "confidence_score": round(rng.uniform(0.72, 0.94), 3),
                        "chunk_id": chunk_id,
                    }
                ]
            }
        samples.append(
            make_sample(
                [
                    {"role": "system", "content": "你是金融风险抽取助手。严格输出 JSON，不要输出 markdown 或额外解释。"},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "finmodpro_synthetic",
            )
        )
    return samples


def build_sentiment_samples(rng, limit):
    sentiment_options = [
        ("positive", "low", "订单恢复和现金流改善，市场反馈偏正面。"),
        ("neutral", "moderate", "经营变化有限，风险倾向保持中性。"),
        ("negative", "elevated", "投诉增加、利润承压，风险倾向上升。"),
        ("negative", "high", "债务集中到期且融资进展不确定，风险倾向较高。"),
    ]
    samples = []
    for _index in range(limit):
        company = rng.choice(COMPANIES)
        sentiment, risk_tendency, summary = rng.choice(sentiment_options)
        text = f"{company}近期公告显示，{summary} 管理层表示将继续跟踪相关变化。"
        payload = {
            "sentiment": sentiment,
            "risk_tendency": risk_tendency,
            "summary": summary,
            "confidence_score": round(rng.uniform(0.68, 0.92), 3),
            "evidence": [summary],
        }
        samples.append(
            make_sample(
                [
                    {"role": "system", "content": "你是金融舆情分析助手。严格输出 JSON，不要输出 markdown 或额外说明。"},
                    {
                        "role": "user",
                        "content": (
                            "请根据以下金融文本判断情绪和风险倾向，只返回 JSON。\n"
                            f"文档标题：{company}舆情快讯\n正文：{text}"
                        ),
                    },
                    {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "finmodpro_synthetic",
            )
        )
    return samples


def build_finmodpro_synthetic_samples(target_count, seed):
    rng = random.Random(seed)
    builders = [
        build_identity_samples(rng, 1000),
        build_rag_samples(rng, 4000),
        build_uncertain_samples(rng, 1500),
        build_risk_samples(rng, 3500),
        build_sentiment_samples(rng, 2000),
    ]
    samples = [sample for group in builders for sample in group if sample]
    rng.shuffle(samples)
    while len(samples) < target_count:
        samples.extend(build_rag_samples(rng, min(500, target_count - len(samples))))
    return samples[:target_count]


def deduplicate(samples):
    seen = set()
    unique = []
    for sample in samples:
        payload = {"messages": sample["messages"]}
        digest = stable_hash(payload)
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(sample)
    return unique


def sample_source(samples, count, seed):
    if len(samples) <= count:
        return list(samples)
    rng = random.Random(seed)
    return rng.sample(samples, count)


def strip_internal_fields(sample):
    return {"messages": sample["messages"]}


def write_jsonl(path, samples):
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(strip_internal_fields(sample), ensure_ascii=False) + "\n")


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_dataset(args):
    output_dir = args.output_dir
    cache_dir = output_dir / "source-cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    download_report = download_sources(cache_dir) if args.download else []

    source_samples = {
        "finmodpro_synthetic": build_finmodpro_synthetic_samples(
            TARGET_COUNTS["finmodpro_synthetic"],
            args.seed,
        )
    }

    for source_name in SOURCE_FILES:
        rows = load_source_rows(cache_dir, source_name)
        samples = convert_rows(source_name, rows)
        source_samples[source_name] = samples

    selected = []
    selection_report = {}
    for source_name, target_count in TARGET_COUNTS.items():
        samples = deduplicate(source_samples.get(source_name, []))
        chosen = sample_source(samples, target_count, seed=stable_hash({"seed": args.seed, "source": source_name}))
        selected.extend(chosen)
        selection_report[source_name] = {
            "available": len(samples),
            "target": target_count,
            "selected": len(chosen),
        }

    selected = deduplicate(selected)
    fill_attempt = 0
    while len(selected) < args.target_total and fill_attempt < 20:
        deficit = args.target_total - len(selected)
        extra = build_finmodpro_synthetic_samples(
            max(deficit * 4, 1000),
            args.seed + 17 + fill_attempt,
        )
        selected = deduplicate(selected + extra)
        fill_attempt += 1

    selected = selected[: args.target_total]

    rng = random.Random(args.seed)
    rng.shuffle(selected)

    eval_count = min(args.eval_count, max(1, int(len(selected) * 0.1)))
    eval_samples = selected[:eval_count]
    train_samples = selected[eval_count:]

    write_jsonl(output_dir / "train.jsonl", train_samples)
    write_jsonl(output_dir / "eval.jsonl", eval_samples)

    dataset_info = {
        "finmodpro_qwen35_4b_v1_train": {
            "file_name": "train.jsonl",
            "formatting": "sharegpt",
            "columns": {"messages": "messages"},
            "tags": {
                "role_tag": "role",
                "content_tag": "content",
                "user_tag": "user",
                "assistant_tag": "assistant",
                "system_tag": "system",
            },
        },
        "finmodpro_qwen35_4b_v1_eval": {
            "file_name": "eval.jsonl",
            "formatting": "sharegpt",
            "columns": {"messages": "messages"},
            "tags": {
                "role_tag": "role",
                "content_tag": "content",
                "user_tag": "user",
                "assistant_tag": "assistant",
                "system_tag": "system",
            },
        },
    }
    write_json(output_dir / "dataset_info.json", dataset_info)

    counts = Counter(sample["_source"] for sample in selected)
    train_counts = Counter(sample["_source"] for sample in train_samples)
    eval_counts = Counter(sample["_source"] for sample in eval_samples)
    manifest = {
        "name": "finmodpro-qwen35-4b-v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_model": "Qwen 3.5 4B",
        "stage": "sft",
        "format": "llamafactory-sharegpt-openai-messages",
        "target_total": args.target_total,
        "actual_total": len(selected),
        "train_count": len(train_samples),
        "eval_count": len(eval_samples),
        "source_counts": dict(sorted(counts.items())),
        "train_source_counts": dict(sorted(train_counts.items())),
        "eval_source_counts": dict(sorted(eval_counts.items())),
        "selection_report": selection_report,
        "download_report": download_report,
        "notes": [
            "本数据包是第一版 Qwen 3.5 4B LoRA/QLoRA SFT 候选数据。",
            "DocFEE 未纳入，因为当前服务器下载 Figshare 数据返回 403。",
            "SEC / BBT-FinCorpus 未纳入，因为它们更适合 continued pretrain 或 RAG 语料，不适合第一轮 SFT。",
            "source-cache 只用于复现和审计，不需要交给 LLaMA-Factory 训练命令。",
        ],
    }
    write_json(output_dir / "manifest.json", manifest)

    preview = {
        source_name: [strip_internal_fields(sample) for sample in selected if sample["_source"] == source_name][:3]
        for source_name in sorted(counts)
    }
    write_json(output_dir / "preview.json", preview)

    (output_dir / "README.md").write_text(
        "# FinModPro Qwen 3.5 4B training data v1\n\n"
        "This bundle contains the first supervised fine-tuning dataset candidate for FinModPro.\n\n"
        "Files:\n"
        "- `train.jsonl`: training samples\n"
        "- `eval.jsonl`: held-out evaluation samples\n"
        "- `dataset_info.json`: LLaMA-Factory dataset registration snippet\n"
        "- `manifest.json`: source counts and generation metadata\n"
        "- `preview.json`: small per-source preview for manual inspection\n"
        "- `source-cache/`: downloaded source files for reproducibility\n",
        encoding="utf-8",
    )

    return manifest


def parse_args():
    parser = argparse.ArgumentParser(description="Build FinModPro first-version SFT data for Qwen 3.5 4B.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--target-total", type=int, default=30000)
    parser.add_argument("--eval-count", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20260503)
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    manifest = build_dataset(args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
