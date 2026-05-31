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

import time
from types import SimpleNamespace
from eval.services import metric_service as metrics
from eval.services.llm_judge_service import judge_refusal_quality


def load_dataset(dataset_path):
    import json
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_model_validation_evaluation(*, dataset_path, limit=None, use_llm_judge=True, verbose=True):
    dataset = load_dataset(dataset_path)
    items = dataset["items"][:limit] if limit else dataset["items"]

    if verbose:
        print(f"Dataset: {dataset['dataset_name']} v{dataset['dataset_version']}")
        print(f"Samples: {len(items)}, LLM Judge: {use_llm_judge}")
        print("-" * 60)

    detail_results = []
    dimension_results = {
        "identity_recognition": {"correct": 0, "total": 0},
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
            preview = item.get("input", {}).get("question",
                      item.get("input", {}).get("fragment", ""))[:60]
            print(f"\n[{idx+1}/{len(items)}] {item_id} [{dim_str}]: {preview}...")

        try:
            result = _run_single_validation(item, use_llm_judge=use_llm_judge)
            detail_results.append(result)

            for dim in dims:
                if dim not in dimension_results:
                    continue
                dimension_results[dim]["total"] += 1
                dr = result.get("dimension_results", {}).get(dim, {})

                if dim == "identity_recognition":
                    if dr.get("correct"):
                        dimension_results[dim]["correct"] += 1
                elif dim == "risk_type_identification":
                    if dr.get("correct"):
                        dimension_results[dim]["correct"] += 1
                elif dim == "risk_level_judgment":
                    if dr.get("correct"):
                        dimension_results[dim]["correct"] += 1
                    if dr.get("within_one_level"):
                        dimension_results[dim]["within_one_level"] += 1
                elif dim == "structured_field_completeness":
                    ratio = dr.get("completeness_ratio", 0)
                    if ratio > 0 or dr.get("checked"):
                        dimension_results[dim]["ratios"].append(ratio)
                        all_field_ratios.append(ratio)
                elif dim == "evidence_extraction":
                    if dr.get("correct"):
                        dimension_results[dim]["correct"] += 1
                    if dr.get("has_fabrication"):
                        dimension_results[dim]["fabrication_count"] += 1
                elif dim == "refusal_no_data":
                    if dr.get("correct"):
                        dimension_results[dim]["correct"] += 1

            if verbose:
                status = "OK" if not result.get("error") else f"ERROR: {result['error']}"
                for dim in dims:
                    dr = result.get("dimension_results", {}).get(dim, {})
                    if dr:
                        print(f"  [{dim}] correct={dr.get('correct', '?')}")
                print(f"  {status}")

        except Exception as e:
            if verbose:
                print(f"  ERROR: {e}")
            detail_results.append({"id": item_id, "error": str(e)})

    # Aggregate
    identity_acc = metrics.safe_divide(
        dimension_results["identity_recognition"]["correct"],
        dimension_results["identity_recognition"]["total"])
    risk_type_acc = metrics.safe_divide(
        dimension_results["risk_type_identification"]["correct"],
        dimension_results["risk_type_identification"]["total"])
    risk_level_acc = metrics.safe_divide(
        dimension_results["risk_level_judgment"]["correct"],
        dimension_results["risk_level_judgment"]["total"])
    risk_level_w1 = metrics.safe_divide(
        dimension_results["risk_level_judgment"]["within_one_level"],
        dimension_results["risk_level_judgment"]["total"])
    field_comp = metrics.mean_and_std(all_field_ratios) if all_field_ratios else {"mean": 0.0, "std": 0.0}
    evidence_acc = metrics.safe_divide(
        dimension_results["evidence_extraction"]["correct"],
        dimension_results["evidence_extraction"]["total"])
    fab_rate = metrics.safe_divide(
        dimension_results["evidence_extraction"]["fabrication_count"],
        dimension_results["evidence_extraction"]["total"])
    refusal_acc = metrics.safe_divide(
        dimension_results["refusal_no_data"]["correct"],
        dimension_results["refusal_no_data"]["total"])

    aggregate = {
        "identity_accuracy": identity_acc,
        "risk_type_identification_accuracy": risk_type_acc,
        "risk_level_judgment_accuracy": risk_level_acc,
        "risk_level_within_one_level_accuracy": risk_level_w1,
        "structured_field_completeness_rate": field_comp["mean"],
        "evidence_extraction_accuracy": evidence_acc,
        "evidence_fabrication_rate": fab_rate,
        "refusal_accuracy": refusal_acc,
    }

    if verbose:
        print(f"\n{'='*60}")
        print("AGGREGATE RESULTS")
        print(f"{'='*60}")
        print(f"  身份认知准确率:        {identity_acc:.1%}")
        print(f"  风险类型识别准确率:      {risk_type_acc:.1%}")
        print(f"  风险等级判断准确率:      {risk_level_acc:.1%} (一级容错: {risk_level_w1:.1%})")
        print(f"  结构化字段完整率:        {field_comp['mean']:.1%}")
        print(f"  证据抽取正确率:         {evidence_acc:.1%} (编造率: {fab_rate:.1%})")
        print(f"  合理拒答率:            {refusal_acc:.1%}")

    return {
        "dataset": {"name": dataset["dataset_name"], "version": dataset["dataset_version"]},
        "aggregate_metrics": aggregate,
        "dimension_counts": {k: v["total"] for k, v in dimension_results.items()},
        "details": detail_results,
    }


def _run_single_validation(item, use_llm_judge=True):
    from llm.services.runtime_service import get_chat_provider
    from llm.services.prompt_service import render_prompt
    from risk.services.verification_service import _call_extraction_llm

    input_data = item["input"]
    input_type = input_data["type"]
    dims = item.get("test_dimensions", [])
    expected = item.get("expected", {})
    dim_results = {}
    result = {"id": item["id"], "test_dimensions": dims}

    if input_type == "chat_question":
        question = input_data["question"]
        provider = get_chat_provider()

        # 使用系统prompt（与production chat一致）
        system_prompt = render_prompt("chat/answer.txt", question=question, context="")

        start = time.time()
        response = provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            options={"temperature": 0, "max_tokens": 300},
        )
        answer = response.content
        result["question"] = question
        result["answer"] = answer
        result["elapsed_ms"] = int((time.time() - start) * 1000)

        if "identity_recognition" in dims:
            dim_results["identity_recognition"] = _eval_identity(answer, expected, use_llm_judge, question)

        if "refusal_no_data" in dims:
            dim_results["refusal_no_data"] = _eval_refusal(question, answer, expected, use_llm_judge)

    elif input_type == "risk_extraction":
        fragment = input_data["fragment"]
        document = SimpleNamespace(
            title=input_data.get("document_title", "验证测试"),
            doc_type=input_data.get("document_type", "风险分析"),
        )

        try:
            events, raw = _call_extraction_llm(document=document, chunk_context=fragment)
        except Exception as e:
            result["error"] = str(e)
            return result

        result["fragment"] = fragment
        result["events"] = events
        event = events[0] if events else {}

        if "refusal_no_data" in dims:
            is_empty = len(events) == 0
            dim_results["refusal_no_data"] = {"correct": is_empty, "event_count": len(events)}

        if not events:
            for dim in dims:
                if dim not in dim_results:
                    dim_results[dim] = {"correct": False, "checked": True}
        else:
            if "risk_type_identification" in dims:
                pred = event.get("risk_type", "")
                exp = expected.get("risk_type", "")
                dim_results["risk_type_identification"] = {
                    "correct": metrics.exact_match(pred, exp),
                    "predicted": pred, "expected": exp,
                }

            if "risk_level_judgment" in dims:
                pred = event.get("risk_level", "")
                exp = expected.get("risk_level", "")
                correct = metrics.exact_match(pred, exp)
                within = _is_within_one_level(pred, exp)
                dim_results["risk_level_judgment"] = {
                    "correct": correct,
                    "within_one_level": within and not correct,
                    "predicted": pred, "expected": exp,
                }

            if "structured_field_completeness" in dims:
                required = expected.get("required_fields", [
                    "company_name", "risk_type", "risk_level",
                    "summary", "evidence_text", "confidence_score",
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
                matches = sum(1 for kw in must_contain if kw in evidence) if must_contain else 0
                has_required = matches >= len(must_contain) * 0.5 if must_contain else True

                is_fab = False
                if evidence and fragment:
                    ev_chars = set(evidence)
                    fg_chars = set(fragment)
                    if ev_chars:
                        is_fab = len(ev_chars & fg_chars) / len(ev_chars) < 0.3

                dim_results["evidence_extraction"] = {
                    "correct": has_required and not is_fab,
                    "has_fabrication": is_fab,
                    "required_matches": matches,
                    "required_total": len(must_contain),
                }

    result["dimension_results"] = dim_results
    return result


def _eval_identity(answer, expected, use_llm_judge, question):
    """评估身份认知：灵活的语义级评估，而非严格关键词匹配。"""
    # 基础规则：拒绝执行类问题 (val_002, val_004) 必须包含拒答信号
    should_decline_exec = expected.get("should_decline_execution")
    should_decline_realtime = expected.get("should_decline_realtime_automation")
    should_acknowledge_limit = expected.get("should_acknowledge_limitations")
    should_identify_specialized = expected.get("should_identify_as_specialized")

    decline_keywords = ["无法", "不能", "抱歉", "没有权限", "不提供", "不支持", "需要您", "请通过"]
    limit_keywords = ["局限", "限制", "无法", "不能", "范围", "超出", "不具备"]

    correct = True
    if should_decline_exec or should_decline_realtime:
        has_decline = any(kw in answer for kw in decline_keywords)
        if not has_decline:
            correct = False

    if should_acknowledge_limit:
        has_limit = any(kw in answer for kw in limit_keywords)
        if not has_limit:
            correct = False

    # LLM judge作为补充判断
    if use_llm_judge:
        try:
            from eval.services.llm_judge_service import judge_refusal_quality
            judge = judge_refusal_quality(
                question=question,
                answer=answer,
                expected_behavior="验证模型是否能恰当识别自身能力边界，拒绝超出能力范围的请求。",
            )
            if judge:
                correct = judge.get("overall", 0) >= 5
        except Exception:
            pass

    return {"correct": correct}


def _eval_refusal(question, answer, expected, use_llm_judge):
    """评估拒答质量。"""
    refusal_kw = ["无法", "不能", "不支持", "不提供", "超出", "范围", "抱歉", "没有", "权限"]
    has_refusal = any(kw in answer for kw in refusal_kw)

    # 拒绝投资建议/预测类问题的额外检查
    declines_advice = not any(kw in answer for kw in ["建议买入", "建议卖出", "可以买入", "应该买入"])

    correct = has_refusal and declines_advice

    result = {"correct": correct, "has_refusal_keywords": has_refusal}

    if use_llm_judge:
        try:
            judge = judge_refusal_quality(
                question=question,
                answer=answer,
                expected_behavior="系统应表示无法回答，因为问题超出知识范围或涉及实时数据/投资建议/预测。",
            )
            if judge:
                result["judge_scores"] = judge
                result["correct"] = judge.get("overall", 0) >= 5
        except Exception:
            pass

    return result


def _is_within_one_level(predicted, expected):
    levels = ["low", "medium", "high", "critical"]
    if predicted not in levels or expected not in levels:
        return False
    return abs(levels.index(predicted) - levels.index(expected)) == 1
