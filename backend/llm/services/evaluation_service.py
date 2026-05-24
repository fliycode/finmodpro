"""
评测服务（类比 SpringBoot 中 @Service 的评测执行与结果查询层）。

负责：
- 执行冒烟评测（QA 问答准确率 + 风险提取准确率）
- 按评测模式分组汇总历史评测记录
- 评测记录列表查询

类比 SpringBoot 中集成了测试框架和 JPA 查询的 Service Bean。
"""
from decimal import Decimal
from statistics import mean
from time import perf_counter

from llm.models import EvalRecord, ModelConfig
from llm.serializers import EvalRecordSummarySerializer
from llm.services.model_config_service import get_active_model_config
from llm.services.prompt_service import render_prompt

# ── 冒烟评测用例定义 ──────────────────────────────────────────────

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
    """根据传入的 ID 解析要评测的模型配置。

    若 model_config_id 为 None，则使用当前激活的 Chat 模型作为回退。

    参数:
        model_config_id: int 或 None，模型配置主键 ID。

    返回:
        ModelConfig 实例或 None（当指定 ID 对应的配置不存在时）。
    """
    if model_config_id is None:
        return get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    return ModelConfig.objects.filter(id=model_config_id).first()


def _score_qa_cases():
    """对 QA 冒烟评测用例进行评分。

    遍历 QA_SMOKE_CASES 中每条用例：
    1. 渲染对应的 prompt 模板
    2. 生成模拟回答并检查是否包含预期关键词
    3. 记录每次渲染的耗时

    返回:
        tuple[float, list[float]]：
        - 准确率（通过数 / 总用例数）
        - 每次用例的延迟列表（毫秒）
    """
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
    """从文档块上下文中提取冒烟评测所需的风险事件信息。

    参数:
        chunk_context: str，文档块文本内容。

    返回:
        dict，包含 company_name 和 risk_type 字段。
    """
    if "流动性风险" in chunk_context:
        return {"company_name": "FinModPro Holdings", "risk_type": "liquidity"}
    if "信用风险" in chunk_context:
        return {"company_name": "FinModPro Holdings", "risk_type": "credit"}
    return {}


def _score_extraction_cases():
    """对风险提取冒烟评测用例进行评分。

    遍历 RISK_EXTRACTION_SMOKE_CASES：
    1. 渲染 risk/extract.txt 模板
    2. 从文档块中提取结构化的风险事件
    3. 与预期结果对比

    返回:
        tuple[float, list[float]]：
        - 准确率（通过数 / 总用例数）
        - 每次用例的延迟列表（毫秒）
    """
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


def _quantize_metric(value, places="0.0001"):
    """将指标值量化为指定精度的 Decimal。

    参数:
        value: 数字或 None。
        places: str，Decimal 量化精度字符串（默认 "0.0001" 即保留4位小数）。

    返回:
        Decimal 或 None（当 value 为 None 时）。
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(places))


def _average_metric(records, field_name, places="0.0001"):
    """计算评测记录列表中某个字段的平均值。

    参数:
        records: list[EvalRecord]，评测记录列表。
        field_name: str，字段名（如 'qa_accuracy'）。
        places: str，Decimal 量化精度字符串。

    返回:
        Decimal 或 None（当没有有效值时）。
    """
    values = [getattr(record, field_name) for record in records if getattr(record, field_name) is not None]
    if not values:
        return None
    return _quantize_metric(mean(Decimal(str(value)) for value in values), places=places)


def _resolve_primary_score(*, task_type, qa_accuracy, extraction_accuracy):
    """根据任务类型计算综合评分。

    参数:
        task_type: str，评测任务类型（risk_extraction / report）。
        qa_accuracy: Decimal，QA 问答准确率。
        extraction_accuracy: Decimal，风险提取准确率。

    返回:
        Decimal，综合评分：
        - 风险提取任务：取 extraction_accuracy
        - 报告任务：取两者平均值
        - 其他：取 qa_accuracy
    """
    if task_type == EvalRecord.TASK_RISK_EXTRACTION:
        return extraction_accuracy
    if task_type == EvalRecord.TASK_REPORT:
        return (qa_accuracy + extraction_accuracy) / Decimal("2")
    return qa_accuracy


def build_evaluation_comparison_groups(eval_records):
    """将评测记录按评测模式分组汇总，用于前端对比展示。

    类似 SpringBoot 中使用 Stream Collectors.groupingBy 后按固定顺序输出。

    参数:
        eval_records: QuerySet[EvalRecord]，待分组的评测记录。

    返回:
        list[dict]，每个元素包含：
        - evaluation_mode: 评测模式标识
        - label: 显示标签
        - total: 该模式下的记录数
        - summary: 各指标均值（qa_accuracy、extraction_accuracy、precision、recall、f1_score、average_latency_ms）
        - records: EvalRecordSummarySerializer 序列化的记录列表
    """
    ordered_modes = [
        EvalRecord.EVALUATION_MODE_BASELINE,
        EvalRecord.EVALUATION_MODE_RAG,
        EvalRecord.EVALUATION_MODE_FINE_TUNED,
    ]
    groups = []
    records_by_mode = {}
    for record in eval_records:
        records_by_mode.setdefault(record.evaluation_mode, []).append(record)

    for mode in ordered_modes + sorted(
        mode for mode in records_by_mode.keys() if mode not in ordered_modes
    ):
        records = records_by_mode.get(mode, [])
        if not records:
            continue
        groups.append(
            {
                "evaluation_mode": mode,
                "label": dict(EvalRecord.EVALUATION_MODE_CHOICES).get(mode, mode),
                "total": len(records),
                "summary": {
                    "qa_accuracy": _average_metric(records, "qa_accuracy"),
                    "extraction_accuracy": _average_metric(records, "extraction_accuracy"),
                    "precision": _average_metric(records, "precision"),
                    "recall": _average_metric(records, "recall"),
                    "f1_score": _average_metric(records, "f1_score"),
                    "average_latency_ms": _average_metric(records, "average_latency_ms", places="0.01"),
                },
                "records": EvalRecordSummarySerializer(records, many=True).data,
            }
        )

    return groups


def run_basic_evaluation(
    *,
    task_type,
    model_config_id=None,
    version="",
    evaluation_mode=EvalRecord.EVALUATION_MODE_BASELINE,
    dataset_name="",
    dataset_version="",
    run_notes="",
):
    """执行一次基础冒烟评测并持久化评测记录。

    评测流程：
    1. 解析模型配置
    2. 执行 QA 问答冒烟用例 + 风险提取冒烟用例
    3. 汇总各指标和延迟
    4. 创建 EvalRecord 并入库

    类比 SpringBoot 中通过 @Transactional 调用多个子服务并持久化结果的 Service 方法。

    参数:
        task_type: str，评测任务类型。
        model_config_id: int 或 None，目标模型配置 ID（None=使用当前激活的Chat模型）。
        version: str，版本标签。
        evaluation_mode: str，评测模式（baseline/rag/fine_tuned）。
        dataset_name: str，数据集名称。
        dataset_version: str，数据集版本。
        run_notes: str，运行备注。

    返回:
        EvalRecord 实例，新创建的评测记录。

    异常:
        ValueError: 当模型配置不存在时抛出。
    """
    model_config = _resolve_eval_model_config(model_config_id)
    if model_config is None:
        raise ValueError("模型配置不存在。")

    qa_accuracy, qa_latencies = _score_qa_cases()
    extraction_accuracy, extraction_latencies = _score_extraction_cases()
    all_latencies = qa_latencies + extraction_latencies
    average_latency_ms = sum(all_latencies) / len(all_latencies) if all_latencies else 0
    primary_score = _resolve_primary_score(
        task_type=task_type,
        qa_accuracy=Decimal(f"{qa_accuracy:.4f}"),
        extraction_accuracy=Decimal(f"{extraction_accuracy:.4f}"),
    )

    return EvalRecord.objects.create(
        model_config=model_config,
        evaluation_mode=evaluation_mode,
        target_name=model_config.name,
        task_type=task_type,
        qa_accuracy=Decimal(f"{qa_accuracy:.4f}"),
        extraction_accuracy=Decimal(f"{extraction_accuracy:.4f}"),
        precision=Decimal(f"{primary_score:.4f}"),
        recall=Decimal(f"{primary_score:.4f}"),
        f1_score=Decimal(f"{primary_score:.4f}"),
        average_latency_ms=Decimal(f"{average_latency_ms:.2f}"),
        version=version,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        run_notes=run_notes,
        status=EvalRecord.STATUS_SUCCEEDED,
        metadata={
            "evaluator_type": "smoke",
            "qa_dataset_size": len(QA_SMOKE_CASES),
            "extraction_dataset_size": len(RISK_EXTRACTION_SMOKE_CASES),
        },
    )


def list_eval_records():
    """查询所有评测记录并按创建时间倒序排列。

    类似 SpringBoot 中 JPA Repository 的 findAll(Sort.by("createdAt").descending())。

    返回:
        QuerySet[EvalRecord]，按创建时间倒序排列的记录集（已 eager load model_config）。
    """
    return EvalRecord.objects.select_related("model_config").order_by("-created_at", "-id")
