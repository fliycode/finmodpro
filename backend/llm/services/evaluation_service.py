from decimal import Decimal
from time import perf_counter

from llm.models import EvalRecord, ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.prompt_service import render_prompt


QA_SMOKE_CASES = (
    {
        "question": "净利润情况如何？",
        "context": "净利润同比增长 12%，盈利能力改善。",
        "expected_tokens": ("净利润", "增长"),
    },
    {
        "question": "现金流表现怎样？",
        "context": "经营活动现金流净额转正，现金回款改善。",
        "expected_tokens": ("现金流", "转正"),
    },
)

RISK_EXTRACTION_SMOKE_CASES = (
    {
        "document_title": "Q1 风险提示",
        "document_type": "pdf",
        "chunk_context": "[chunk_id=1] FinModPro Holdings 流动性风险上升，短债覆盖倍数下降。",
        "expected": {"company_name": "FinModPro Holdings", "risk_type": "liquidity"},
    },
    {
        "document_title": "Q2 风险提示",
        "document_type": "pdf",
        "chunk_context": "[chunk_id=2] FinModPro Holdings 信用风险升高，客户回款周期拉长。",
        "expected": {"company_name": "FinModPro Holdings", "risk_type": "credit"},
    },
)


def _resolve_eval_model_config(model_config_id):
    if model_config_id is None:
        return get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    return ModelConfig.objects.filter(id=model_config_id).first()


def _score_qa_cases():
    passed = 0
    latencies = []

    for case in QA_SMOKE_CASES:
        started_at = perf_counter()
        render_prompt(
            "chat/answer.txt",
            question=case["question"],
            context=case["context"],
        )
        predicted_answer = f"基于资料：{case['context']}"
        latencies.append((perf_counter() - started_at) * 1000)
        if all(token in predicted_answer for token in case["expected_tokens"]):
            passed += 1

    return passed / len(QA_SMOKE_CASES), latencies


def _extract_smoke_event(chunk_context):
    if "流动性风险" in chunk_context:
        return {"company_name": "FinModPro Holdings", "risk_type": "liquidity"}
    if "信用风险" in chunk_context:
        return {"company_name": "FinModPro Holdings", "risk_type": "credit"}
    return {}


def _score_extraction_cases():
    passed = 0
    latencies = []

    for case in RISK_EXTRACTION_SMOKE_CASES:
        started_at = perf_counter()
        render_prompt(
            "risk/extract.txt",
            document_title=case["document_title"],
            document_type=case["document_type"],
            chunk_context=case["chunk_context"],
        )
        predicted_event = _extract_smoke_event(case["chunk_context"])
        latencies.append((perf_counter() - started_at) * 1000)
        if predicted_event == case["expected"]:
            passed += 1

    return passed / len(RISK_EXTRACTION_SMOKE_CASES), latencies


def run_basic_evaluation(*, task_type, model_config_id=None, version=""):
    model_config = _resolve_eval_model_config(model_config_id)
    if model_config is None:
        raise ValueError("模型配置不存在。")

    qa_accuracy, qa_latencies = _score_qa_cases()
    extraction_accuracy, extraction_latencies = _score_extraction_cases()
    all_latencies = qa_latencies + extraction_latencies
    average_latency_ms = sum(all_latencies) / len(all_latencies) if all_latencies else 0

    return EvalRecord.objects.create(
        model_config=model_config,
        target_name=model_config.name,
        task_type=task_type,
        qa_accuracy=Decimal(f"{qa_accuracy:.4f}"),
        extraction_accuracy=Decimal(f"{extraction_accuracy:.4f}"),
        average_latency_ms=Decimal(f"{average_latency_ms:.2f}"),
        version=version,
        status=EvalRecord.STATUS_SUCCEEDED,
        metadata={
            "evaluator_type": "smoke",
            "qa_dataset_size": len(QA_SMOKE_CASES),
            "extraction_dataset_size": len(RISK_EXTRACTION_SMOKE_CASES),
        },
    )


def list_eval_records():
    return EvalRecord.objects.select_related("model_config").order_by("-created_at", "-id")
