#!/usr/bin/env python3
import json
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "datasets" / "finmodpro-qwen35-4b-zh-v1"
DATASET_NAME = "finmodpro_zh_sft_v1"
TARGET_COUNT = 30000
SEED = 20260503

SYSTEM_PROMPT = (
    "你是 FinModPro 平台内置的专业金融分析助手，服务于企业财务、风险、知识库和投研分析场景。"
    "回答应专业、审慎、结构清晰；不要编造数据或来源。"
    "当参考资料不足时，明确说明不确定性。"
)

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
    "南山装备",
    "江河环保",
    "银海文旅",
    "天成零售",
]

INDUSTRIES = [
    "能源",
    "制造",
    "房地产",
    "医药",
    "物流",
    "消费",
    "电子材料",
    "金融服务",
    "环保",
    "文旅",
]

DOC_TYPES = ["年报", "半年报", "审计报告", "债券募集说明书", "经营简报", "风险排查纪要", "舆情快讯"]
METRICS = ["营业收入", "净利润", "经营现金流", "资产负债率", "短期借款", "应收账款", "毛利率", "存货周转率"]
RISK_TYPES = ["流动性风险", "信用风险", "市场风险", "合规风险", "经营风险", "操作风险"]
RISK_LEVELS = ["low", "medium", "high", "critical"]
SENTIMENTS = [
    ("positive", "low", "正面"),
    ("neutral", "moderate", "中性"),
    ("negative", "elevated", "负面"),
    ("negative", "high", "明显负面"),
]


def one(items, index, salt=0):
    return items[(index + salt) % len(items)]


def money(value):
    return f"{value:,}".replace(",", "")


def make_messages(system, user, assistant):
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}]}


def identity_sample(index):
    scenes = [
        "财务负责人刚上传年报，需要确认助手能做什么",
        "风控专员准备审核风险事件，需要了解平台能力",
        "投研同事想基于知识库做问答，需要确认回答边界",
        "管理员准备切换微调模型，需要了解助手定位",
    ]
    questions = [
        "你是谁？",
        "请介绍一下你自己。",
        "你能帮我完成哪些金融分析工作？",
        "你和通用聊天助手有什么区别？",
        "使用你回答知识库问题时需要注意什么？",
    ]
    scene = one(scenes, index)
    question = one(questions, index, 2)
    answer_variants = [
        "我是 FinModPro 平台内置的专业金融分析助手，主要服务于企业财务、风险、知识库和投研分析场景。我会优先依据用户上传的资料和检索到的上下文回答；当资料不足时，我会明确说明不确定性，而不是编造结论。",
        "我是 FinModPro 的平台助手。我的重点是金融文档问答、风险线索识别、舆情倾向判断、财务指标解释和报告草拟。涉及具体公司、数值或来源时，我会尽量基于参考资料说明，并提示需要补充的证据。",
        "我可以协助你在 FinModPro 中完成知识库问答、财报摘要、风险事件抽取、风险报告整理和模型训练数据审核。对于没有依据的问题，我会保持审慎，说明无法仅凭当前资料作出确定判断。",
    ]
    answer = f"{one(answer_variants, index)}\n\n当前场景是：{scene}。在这个场景下，我会把资料来源、风险证据和结论边界放在优先位置。"
    return make_messages(SYSTEM_PROMPT, f"样本编号：FMP-ID-{index:05d}\n场景：{scene}\n问题：{question}", answer)


def rag_sample(index):
    company = one(COMPANIES, index)
    industry = one(INDUSTRIES, index, 1)
    doc_type = one(DOC_TYPES, index, 2)
    metric = one(METRICS, index, 3)
    year = 2022 + (index % 4)
    base = 8000 + (index % 4200)
    change = [-12.4, -6.8, -2.1, 3.5, 7.6, 11.2, 18.9][index % 7]
    risk = one(RISK_TYPES, index, 4)
    page_a = 8 + index % 30
    page_b = 42 + index % 18
    context = (
        f"[1] 《{company}{year}{doc_type}》第 {page_a} 页：公司属于{industry}行业，{metric}为 {money(base)} 万元，同比变化 {change}%。\n"
        f"[2] 《{company}{year}{doc_type}》第 {page_b} 页：管理层提示{risk}需要持续跟踪，主要原因是客户回款周期、融资环境和原材料价格存在波动。"
    )
    question_templates = [
        f"根据资料，概括{company}{year}年的经营变化和风险点。",
        f"{company}{year}年的{metric}表现如何？需要关注什么风险？",
        f"请基于参考资料判断{company}是否存在需要持续跟踪的风险。",
    ]
    question = one(question_templates, index)
    direction = "改善" if change > 0 else "承压"
    answer = (
        f"根据资料[1]，{company}{year}年的{metric}为 {money(base)} 万元，同比变化 {change}%，整体表现可以概括为{direction}。"
        f"资料[2]进一步提示，{risk}需要持续跟踪，相关压力主要来自客户回款周期、融资环境和原材料价格波动。\n\n"
        "因此，当前可以形成的审慎结论是：该公司已有可识别的风险线索，但仍需要结合后续现金流、债务到期结构和经营计划继续验证。"
    )
    return make_messages(SYSTEM_PROMPT, f"资料编号：FMP-RAG-{index:05d}\n问题：{question}\n\n参考资料：\n{context}", answer)


def risk_extraction_sample(index):
    company = one(COMPANIES, index)
    risk_type = one(RISK_TYPES, index, 2)
    level = one(RISK_LEVELS, index, 1)
    chunk_id = 100000 + index
    evidence_options = [
        f"{company}短期借款余额较上年末增加 {(index % 35) + 18}%，一年内到期债务集中，经营现金流覆盖倍数下降。",
        f"{company}主要客户回款延迟，应收账款账龄超过一年的比例上升，坏账准备计提压力增加。",
        f"{company}因信息披露不完整收到监管问询，整改措施仍在推进，后续合规结果存在不确定性。",
        f"{company}原材料采购价格波动较大，部分订单毛利率连续两个季度下降。",
    ]
    no_event = index % 11 == 0
    if no_event:
        chunk_text = f"[chunk_id={chunk_id}][chunk_index=0] {company}披露本期治理结构保持稳定，未发现重大异常事项。"
        output = {"events": [], "message": "未识别到明确风险事件"}
    else:
        evidence = one(evidence_options, index)
        chunk_text = f"[chunk_id={chunk_id}][chunk_index=0] {evidence}"
        output = {
            "events": [
                {
                    "company_name": company,
                    "risk_type": risk_type,
                    "risk_level": level,
                    "event_time": None,
                    "summary": f"{company}出现{risk_type}线索。",
                    "evidence_text": evidence,
                    "confidence_score": round(0.72 + (index % 20) / 100, 3),
                    "chunk_id": chunk_id,
                }
            ]
        }
    user = (
        "请从以下金融文档切块中抽取风险事件，严格输出 JSON，不要输出 Markdown 或额外解释。\n\n"
        f"资料编号：FMP-RISK-{index:05d}\n"
        f"文档标题：{company}风险排查纪要\n"
        f"文档类型：风险排查纪要\n"
        f"文档切块：\n{chunk_text}"
    )
    system = "你是金融风险抽取助手。严格输出 JSON，不要输出 Markdown 或额外解释。"
    return make_messages(system, user, json.dumps(output, ensure_ascii=False))


def sentiment_sample(index):
    company = one(COMPANIES, index)
    sentiment, tendency, label = one(SENTIMENTS, index)
    evidence = {
        "positive": f"{company}公告显示订单恢复、现金流改善，市场反馈较为积极。",
        "neutral": f"{company}近期经营数据变化有限，市场观点分歧不大。",
        "negative": f"{company}出现债务集中到期、投诉增加和利润承压等迹象。",
    }[sentiment]
    text = f"{evidence} 管理层表示将继续跟踪经营变化，并在必要时调整融资和采购安排。"
    output = {
        "sentiment": sentiment,
        "risk_tendency": tendency,
        "summary": f"舆情整体为{label}，需要结合后续公告继续验证。",
        "confidence_score": round(0.7 + (index % 18) / 100, 3),
        "evidence": [evidence],
    }
    user = (
        "请根据以下金融文本判断情绪和风险倾向，只返回 JSON，不要输出 Markdown 或解释。\n\n"
        f"资料编号：FMP-SENT-{index:05d}\n"
        f"文档标题：{company}舆情快讯\n"
        f"正文：{text}"
    )
    system = "你是金融舆情分析助手。严格输出 JSON，不要输出 Markdown 或额外说明。"
    return make_messages(system, user, json.dumps(output, ensure_ascii=False))


def calculation_sample(index):
    company = one(COMPANIES, index)
    metric = one(METRICS, index)
    current = 9000 + (index % 7000)
    previous = 7600 + (index % 5600)
    ratio = (current - previous) / previous * 100
    context = (
        f"资料编号：FMP-CALC-{index:05d}\n"
        f"{company}本期{metric}为 {money(current)} 万元，上期为 {money(previous)} 万元。"
        "请计算同比变化率，并给出简短分析。"
    )
    answer = (
        f"{metric}同比变化率 = （{money(current)} - {money(previous)}） / {money(previous)} × 100% = {ratio:.2f}%。\n\n"
        f"如果只看该指标，{company}本期{metric}较上期{'上升' if ratio >= 0 else '下降'}。"
        "但该结论仍需要结合收入结构、现金流质量和一次性因素判断，不能单独作为完整投资或风控结论。"
    )
    return make_messages(SYSTEM_PROMPT, context, answer)


def summary_sample(index):
    company = one(COMPANIES, index)
    year = 2022 + index % 4
    risk_type = one(RISK_TYPES, index)
    metric = one(METRICS, index, 2)
    text = (
        f"《{company}{year}年报》显示，公司本期{metric}有所波动，管理层认为主要受市场需求、采购价格和项目交付节奏影响。"
        f"报告同时提示，{risk_type}仍需关注。公司计划通过优化客户结构、加强回款管理和控制资本开支改善经营质量。"
    )
    answer = (
        f"摘要：{company}{year}年报显示，{metric}出现波动，主要影响因素包括市场需求、采购价格和项目交付节奏。"
        f"风险方面，报告提示{risk_type}仍需关注。后续可重点跟踪回款管理、客户结构优化和资本开支控制效果。"
    )
    user = f"资料编号：FMP-SUM-{index:05d}\n请用专业、简洁的中文总结以下金融文档片段。\n\n文档片段：{text}"
    return make_messages(SYSTEM_PROMPT, user, answer)


def report_sample(index):
    company = one(COMPANIES, index)
    risk_type = one(RISK_TYPES, index, 1)
    level = one(["中", "较高", "高"], index)
    evidence = (
        f"证据一：{company}短期债务规模上升；证据二：经营现金流覆盖能力下降；"
        f"证据三：管理层提示{risk_type}需要持续跟踪。"
    )
    user = (
        f"资料编号：FMP-REPORT-{index:05d}\n请根据以下风险线索，为{company}生成一段风险报告摘要。\n\n"
        f"风险等级：{level}\n风险类型：{risk_type}\n证据：{evidence}"
    )
    answer = (
        f"风险报告摘要：{company}当前{risk_type}等级为{level}。从现有证据看，公司短期债务规模上升，"
        "经营现金流覆盖能力下降，说明偿付和经营周转压力需要持续观察。建议后续重点跟踪债务到期结构、"
        "现金流改善计划、融资进展以及管理层披露的整改措施。当前结论基于已有线索形成，不应替代正式审计或评级判断。"
    )
    return make_messages(SYSTEM_PROMPT, user, answer)


def uncertainty_sample(index):
    company = one(COMPANIES, index)
    metric = one(METRICS, index, 2)
    user = (
        f"资料编号：FMP-UNCERTAIN-{index:05d}\n请判断{company}未来一年{metric}是否会明显改善。\n\n"
        f"参考资料：[1] {company}公告称，公司将继续推进数字化系统建设，但未披露{metric}预测数据。"
    )
    answer = (
        f"当前参考资料不足以判断{company}未来一年{metric}是否会明显改善。资料[1]只提到数字化系统建设，"
        f"没有提供{metric}预测、历史对比、管理层量化指引或可验证假设。\n\n"
        "更稳妥的做法是补充预算计划、经营目标、历史财务数据和管理层说明后再分析。"
    )
    return make_messages(SYSTEM_PROMPT, user, answer)


BUILDERS = [
    ("平台身份与边界", 2500, identity_sample),
    ("知识库引用问答", 7000, rag_sample),
    ("风险事件抽取", 6000, risk_extraction_sample),
    ("舆情倾向判断", 4000, sentiment_sample),
    ("财务指标计算", 3500, calculation_sample),
    ("文档摘要", 3000, summary_sample),
    ("风险报告摘要", 2500, report_sample),
    ("资料不足处理", 1500, uncertainty_sample),
]


def stable_key(sample):
    return json.dumps(sample, ensure_ascii=False, sort_keys=True)


def generate_samples():
    samples = []
    source_names = []
    offset = 0
    for name, count, builder in BUILDERS:
        for local_index in range(count):
            samples.append(builder(offset + local_index))
            source_names.append(name)
        offset += count

    seen = set()
    unique_samples = []
    unique_sources = []
    for sample, source in zip(samples, source_names):
        key = stable_key(sample)
        if key in seen:
            continue
        seen.add(key)
        unique_samples.append(sample)
        unique_sources.append(source)

    if len(unique_samples) != TARGET_COUNT:
        raise RuntimeError(f"Expected {TARGET_COUNT} unique samples, got {len(unique_samples)}")

    paired = list(zip(unique_samples, unique_sources))
    random.Random(SEED).shuffle(paired)
    return paired


def validate_samples(samples):
    chinese_re = re.compile(r"[\u4e00-\u9fff]")
    for index, (sample, _source) in enumerate(samples, start=1):
        messages = sample.get("messages") or []
        if len(messages) != 3:
            raise RuntimeError(f"Sample {index} must contain exactly 3 messages.")
        if messages[0].get("role") != "system" or messages[1].get("role") != "user" or messages[2].get("role") != "assistant":
            raise RuntimeError(f"Sample {index} has invalid role order.")
        for message in messages:
            content = message.get("content") or ""
            if not content.strip():
                raise RuntimeError(f"Sample {index} has empty content.")
            if message.get("role") in {"system", "user", "assistant"} and not chinese_re.search(content):
                raise RuntimeError(f"Sample {index} content has no Chinese characters.")


def write_outputs(samples):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = OUTPUT_DIR / "data.json"
    data_path.write_text(
        json.dumps([sample for sample, _source in samples], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    dataset_info = {
        DATASET_NAME: {
            "file_name": "data.json",
            "formatting": "sharegpt",
            "columns": {"messages": "messages"},
            "tags": {
                "role_tag": "role",
                "content_tag": "content",
                "user_tag": "user",
                "assistant_tag": "assistant",
                "system_tag": "system",
            },
        }
    }
    (OUTPUT_DIR / "dataset_info.json").write_text(
        json.dumps(dataset_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = Counter(source for _sample, source in samples)
    manifest = {
        "name": "finmodpro-qwen35-4b-zh-v1",
        "dataset_name": DATASET_NAME,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_model": "Qwen 3.5 4B",
        "stage": "sft",
        "format": "llamafactory-openai-messages",
        "sample_count": len(samples),
        "language": "zh",
        "source_counts": dict(counts),
        "notes": [
            "自然语言内容全部使用中文。",
            "role/content 等结构字段遵循 LLaMA-Factory OpenAI messages 格式。",
            "风险和舆情 JSON 中的字段名与枚举值保留 FinModPro 后端约定。",
        ],
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readme = (
        "# FinModPro Qwen 3.5 4B 中文 SFT 数据集 v1\n\n"
        "本目录包含 30,000 条可直接用于 LLaMA-Factory 的中文 SFT 数据。\n\n"
        "## 文件\n\n"
        "- `data.json`：30,000 条 OpenAI messages 格式样本\n"
        "- `dataset_info.json`：LLaMA-Factory 数据集注册配置\n"
        "- `manifest.json`：生成信息和分类统计\n\n"
        "## 使用方式\n\n"
        "将本目录作为 `--dataset_dir`，数据集名称使用 `finmodpro_zh_sft_v1`。\n\n"
        "```bash\n"
        "llamafactory-cli train \\\n"
        "  --stage sft \\\n"
        "  --do_train true \\\n"
        "  --model_name_or_path <你的-qwen3.5-4b-路径> \\\n"
        "  --dataset_dir datasets/finmodpro-qwen35-4b-zh-v1 \\\n"
        "  --dataset finmodpro_zh_sft_v1 \\\n"
        "  --finetuning_type lora\n"
        "```\n\n"
        "如需自动切分验证集，可在训练参数中使用 LLaMA-Factory 的 `val_size`。\n"
    )
    (OUTPUT_DIR / "README.md").write_text(readme, encoding="utf-8")


def main():
    samples = generate_samples()
    validate_samples(samples)
    write_outputs(samples)
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "sample_count": len(samples)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
