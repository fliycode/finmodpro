"""
Model validation evaluator for Section 6.5.

50 validation samples across 6 dimensions:
- identity_recognition (5): platform identity, capability scope
- risk_type_identification (35): 8 risk type classification (overlaps with others)
- risk_level_judgment (35): 4-level severity judgment (overlaps)
- structured_field_completeness (35): JSON output field completeness
- evidence_extraction (35): evidence text fidelity (no fabrication)
- refusal_no_data (10): correctly returns empty events for no-risk text
"""

import json
import time
from types import SimpleNamespace
from eval.services import metric_service as metrics
from eval.services.llm_judge_service import judge_refusal_quality


def load_dataset(dataset_path):
    """加载模型验证数据集。"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_model_validation_evaluation(*, dataset_path, limit=None, use_llm_judge=True, verbose=True):
    """
    运行模型验证评估。

    返回:
        dict: {dimension_results, aggregate_metrics, details}
    """
    dataset = load_dataset(dataset_path)
    items = dataset["items"][:limit] if limit else dataset["items"]

    if verbose:
        print(f"Dataset: {dataset['dataset_name']} v{dataset['dataset_version']}")
        print(f"Samples: {len(items)}, LLM Judge: {use_llm_judge}")
        print("-" * 60)

    detail_results = []
    dimension_results = {
        "identity_recognition": {"correct": 0, "total": 0, "details": []},
        "risk_type_identification": {"correct": 0, "total": 0},
        "risk_level_judgment": {"correct": 0, "total": 0, "within_one_level": 0},
        "structured_field_completeness": {"ratios": [], "total": 0},
        "evidence_extraction": {"correct": 0, "total": 0, "fabrication_count": 0},
        "refusal_no_data": {"correct": 0, "total": 0},
    }
    all_field_ratios = []

    for idx, item in enumerate(items):
        item_id = item["id"]
        dims = item.get("test_dimensions", [])

        if verbose:
            dim_str = ",".join(dims[:2]) + ("..." if len(dims) > 2 else "")
            input_preview = item.get("input", {}).get("question", item.get("input", {}).get("fragment", ""))[:60]
            print(f"\n[{idx+1}/{len(items)}] {item_id} [{dim_str}]: {input_preview}...")

        try:
            result = _run_single_validation(item, use_llm_judge=use_llm_judge)
            detail_results.append(result)

            # 更新各维度统计
            for dim in dims:
                if dim in dimension_results:
                    dimension_results[dim]["total"] += 1
                    dim_result = result.get("dimension_results", {}).get(dim, {})

                    if dim == "identity_recognition":
                        if dim_result.get("correct"):
                            dimension_results[dim]["correct"] += 1
                        dimension_results[dim]["details"].append(result)

                    elif dim == "risk_type_identification":
                        if dim_result.get("correct"):
                            dimension_results[dim]["correct"] += 1

                    elif dim == "risk_level_judgment":
                        if dim_result.get("correct"):
                            dimension_results[dim]["correct"] += 1
                        if dim_result.get("within_one_level"):
                            dimension_results[dim]["within_one_level"] += 1

                    elif dim == "structured_field_completeness":
                        ratio = dim_result.get("completeness_ratio", 0)
                        if ratio > 0 or dim_result.get("checked", False):
                            dimension_results[dim]["ratios"].append(ratio)
                            all_field_ratios.append(ratio)

                    elif dim == "evidence_extraction":
                        if dim_result.get("correct"):
                            dimension_results[dim]["correct"] += 1
                        if dim_result.get("has_fabrication"):
                            dimension_results[dim]["fabrication_count"] += 1

                    elif dim == "refusal_no_data":
                        if dim_result.get("correct"):
                            dimension_results[dim]["correct"] += 1

            if verbose:
                status = "OK" if not result.get("error") else f"ERROR: {result['error']}"
                print(f"  {status}")

        except Exception as e:
            if verbose:
                print(f"  ERROR: {e}")
            detail_results.append({"id": item_id, "error": str(e)})

    # 计算聚合指标
    identity_acc = metrics.safe_divide(
        dimension_results["identity_recognition"]["correct"],
        dimension_results["identity_recognition"]["total"],
    )
    risk_type_acc = metrics.safe_divide(
        dimension_results["risk_type_identification"]["correct"],
        dimension_results["risk_type_identification"]["total"],
    )
    risk_level_acc = metrics.safe_divide(
        dimension_results["risk_level_judgment"]["correct"],
        dimension_results["risk_level_judgment"]["total"],
    )
    risk_level_within_one = metrics.safe_divide(
        dimension_results["risk_level_judgment"]["within_one_level"],
        dimension_results["risk_level_judgment"]["total"],
    )
    field_completeness_mean = metrics.mean_and_std(all_field_ratios) if all_field_ratios else {"mean": 0, "std": 0}
    evidence_acc = metrics.safe_divide(
        dimension_results["evidence_extraction"]["correct"],
        dimension_results["evidence_extraction"]["total"],
    )
    fabrication_rate = metrics.safe_divide(
        dimension_results["evidence_extraction"]["fabrication_count"],
        dimension_results["evidence_extraction"]["total"],
    )
    refusal_acc = metrics.safe_divide(
        dimension_results["refusal_no_data"]["correct"],
        dimension_results["refusal_no_data"]["total"],
    )

    aggregate = {
        "identity_accuracy": identity_acc,
        "risk_type_identification_accuracy": risk_type_acc,
        "risk_level_judgment_accuracy": risk_level_acc,
        "risk_level_within_one_level_accuracy": risk_level_within_one,
        "structured_field_completeness_rate": field_completeness_mean["mean"],
        "evidence_extraction_accuracy": evidence_acc,
        "evidence_fabrication_rate": fabrication_rate,
        "refusal_accuracy": refusal_acc,
    }

    if verbose:
        print(f"\n{'='*60}")
        print("AGGREGATE RESULTS")
        print(f"{'='*60}")
        print(f"  身份认知准确率: {identity_acc:.2%}")
        print(f"  风险类型识别准确率: {risk_type_acc:.2%}")
        print(f"  风险等级判断准确率: {risk_level_acc:.2%} (within-one-level: {risk_level_within_one:.2%})")
        print(f"  结构化字段完整率: {field_completeness_mean['mean']:.2%}")
        print(f"  证据抽取正确率: {evidence_acc:.2%} (编造率: {fabrication_rate:.2%})")
        print(f"  合理拒答率: {refusal_acc:.2%}")

    return {
        "dataset": {"name": dataset["dataset_name"], "version": dataset["dataset_version"]},
        "aggregate_metrics": aggregate,
        "dimension_counts": {k: v["total"] for k, v in dimension_results.items()},
        "details": detail_results,
    }


def _run_single_validation(item, use_llm_judge=True):
    """对单个验证样本运行评估。"""
    from llm.services.runtime_service import get_chat_provider
    from risk.services.verification_service import _call_extraction_llm, _parse_extraction_output

    input_data = item["input"]
    input_type = input_data["type"]
    dims = item.get("test_dimensions", [])
    expected = item.get("expected", {})
    dim_results = {}

    result = {"id": item["id"], "test_dimensions": dims}

    if input_type == "chat_question":
        # 聊天问题 → 直接调用 LLM
        question = input_data["question"]
        provider = get_chat_provider()
        start = time.time()
        answer = provider.chat(
            messages=[{"role": "user", "content": question}],
            options={"temperature": 0},
        ).content
        result["question"] = question
        result["answer"] = answer
        result["elapsed_ms"] = int((time.time() - start) * 1000)

        if "identity_recognition" in dims:
            dim_results["identity_recognition"] = _eval_identity(answer, expected)

        if "refusal_no_data" in dims:
            dim_results["refusal_no_data"] = _eval_refusal(question, answer, expected, use_llm_judge)

    elif input_type == "risk_extraction":
        # 风险抽取 → 调用抽取 LLM
        fragment = input_data["fragment"]
        document = SimpleNamespace(
            title=input_data.get("document_title", "验证测试"),
            doc_type=input_data.get("document_type", "风险分析"),
        )

        try:
            events, raw = _call_extraction_llm(
                document=document,
                chunk_context=fragment,
            )
        except Exception as e:
            result["error"] = str(e)
            return result

        result["fragment"] = fragment
        result["events"] = events
        event = events[0] if events else {}
        result["raw_output"] = raw

        if "refusal_no_data" in dims:
            # 无风险文本 → 期望空事件列表
            is_empty = len(events) == 0
            dim_results["refusal_no_data"] = {
                "correct": is_empty,
                "event_count": len(events),
            }

        if not events:
            # 如果没抽取到事件，后续维度检查为空
            for dim in dims:
                if dim not in dim_results:
                    dim_results[dim] = {"correct": False, "checked": True}
        else:
            # 检查各维度
            if "risk_type_identification" in dims:
                dim_results["risk_type_identification"] = {
                    "correct": metrics.exact_match(event.get("risk_type", ""), expected.get("risk_type", "")),
                    "predicted": event.get("risk_type", ""),
                    "expected": expected.get("risk_type", ""),
                }

            if "risk_level_judgment" in dims:
                predicted_level = event.get("risk_level", "")
                expected_level = expected.get("risk_level", "")
                correct = metrics.exact_match(predicted_level, expected_level)
                within_one = _is_within_one_level(predicted_level, expected_level)
                dim_results["risk_level_judgment"] = {
                    "correct": correct,
                    "within_one_level": within_one and not correct,
                    "predicted": predicted_level,
                    "expected": expected_level,
                }

            if "structured_field_completeness" in dims:
                required = expected.get("required_fields", [
                    "company_name", "risk_type", "risk_level", "summary",
                    "evidence_text", "confidence_score",
                ])
                present = [f for f in required if event.get(f)]
                ratio = metrics.field_completeness(present, required)
                dim_results["structured_field_completeness"] = {
                    "completeness_ratio": ratio,
                    "present_fields": present,
                    "missing_fields": [f for f in required if f not in present],
                    "checked": True,
                }

            if "evidence_extraction" in dims:
                evidence = event.get("evidence_text", "")
                must_contain = expected.get("evidence_must_contain", [])
                must_not_fabricate = expected.get("evidence_must_not_fabricate", True)

                # 检查是否包含期望的证据关键词
                matches = sum(1 for kw in must_contain if kw in evidence)
                has_required = matches >= len(must_contain) * 0.5 if must_contain else True

                # 检查是否在原文中存在（简单反编造检查）
                is_fabricated = False
                if must_not_fabricate and evidence:
                    # 检查evidence中的关键短语是否至少部分出现在原文fragment中
                    evidence_chars = set(evidence)
                    fragment_chars = set(fragment)
                    if evidence_chars:
                        overlap = len(evidence_chars & fragment_chars) / len(evidence_chars)
                        is_fabricated = overlap < 0.5

                dim_results["evidence_extraction"] = {
                    "correct": has_required and not is_fabricated,
                    "has_fabrication": is_fabricated,
                    "required_matches": matches,
                    "required_total": len(must_contain),
                    "evidence_text": evidence[:200] if evidence else "",
                }

    result["dimension_results"] = dim_results
    return result


def _eval_identity(answer, expected):
    """评估身份认知回答。"""
    should_contain = expected.get("should_contain", [])
    should_not_contain = expected.get("should_not_contain", [])

    has_required = all(kw in answer for kw in should_contain) if should_contain else True
    no_forbidden = not any(kw in answer for kw in should_not_contain) if should_not_contain else True

    return {"correct": has_required and no_forbidden, "has_required": has_required, "no_forbidden": no_forbidden}


def _eval_refusal(question, answer, expected, use_llm_judge):
    """评估拒答质量。"""
    expected_behavior = "该系统应表示无法回答此问题，因为问题超出知识范围或涉及实时数据/投资建议/预测。"
    refusal_keywords = ["无法", "不能", "不支持", "知识库", "超出", "范围", "建议", "实时"]

    has_refusal = any(kw in answer for kw in refusal_keywords)
    correct = has_refusal

    result = {"correct": correct, "has_refusal_keywords": has_refusal}

    if use_llm_judge:
        judge = judge_refusal_quality(
            question=question,
            answer=answer,
            expected_behavior=expected_behavior,
        )
        if judge:
            result["judge_scores"] = judge
            result["correct"] = judge.get("overall", 0) >= 5

    return result


def _is_within_one_level(predicted, expected):
    """检查风险等级是否相差一级以内。"""
    levels = ["low", "medium", "high", "critical"]
    if predicted not in levels or expected not in levels:
        return False
    return abs(levels.index(predicted) - levels.index(expected)) == 1
