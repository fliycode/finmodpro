"""
Risk extraction evaluator for Section 6.4.

Evaluates 50 financial risk text fragments against human annotations.
Computes precision, recall, F1 for each field:
- company_name
- risk_type
- risk_level
- event_time (year+month tolerance)
- evidence_text (substring overlap)
- overall (all fields correct)
"""

import json
import time
from types import SimpleNamespace
from eval.services import metric_service as metrics


def load_dataset(dataset_path):
    """加载风险抽取评测数据集。"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_risk_extraction_evaluation(*, dataset_path, limit=None, verbose=True):
    """
    运行风险事件抽取评测。

    参数:
        dataset_path: 数据集 JSON 文件路径
        limit: 限制测试片段数量
        verbose: 输出详细信息

    返回:
        dict: {aggregate_metrics, per_field_metrics, details}
    """
    dataset = load_dataset(dataset_path)
    items = dataset["items"][:limit] if limit else dataset["items"]

    if verbose:
        print(f"Dataset: {dataset['dataset_name']} v{dataset['dataset_version']}")
        print(f"Fragments: {len(items)}")
        print("-" * 60)

    detail_results = []
    field_tp = {"company_name": 0, "risk_type": 0, "risk_level": 0, "event_time": 0, "evidence_text": 0, "overall": 0}
    field_fp = {"company_name": 0, "risk_type": 0, "risk_level": 0, "event_time": 0, "evidence_text": 0, "overall": 0}
    field_fn = {"company_name": 0, "risk_type": 0, "risk_level": 0, "event_time": 0, "evidence_text": 0, "overall": 0}

    for idx, item in enumerate(items):
        if verbose:
            print(f"\n[{idx+1}/{len(items)}] {item['id']}: {item['fragment'][:60]}...")

        try:
            result = _run_single_extraction(item)
            detail_results.append(result)

            # 累加 TP/FP/FN
            for field in ["company_name", "risk_type", "risk_level", "event_time", "evidence_text", "overall"]:
                field_tp[field] += result["per_field"][field]["tp"]
                field_fp[field] += result["per_field"][field]["fp"]
                field_fn[field] += result["per_field"][field]["fn"]

            if verbose:
                pf = result["per_field"]
                print(f"  company: tp={pf['company_name']['tp']}/{pf['company_name']['fp']}/{pf['company_name']['fn']}"
                      f" | risk_type: tp={pf['risk_type']['tp']}"
                      f" | risk_level: tp={pf['risk_level']['tp']}"
                      f" | overall: correct={result['overall_correct']}")

        except Exception as e:
            if verbose:
                print(f"  ERROR: {e}")
            detail_results.append({"id": item["id"], "error": str(e)})

    # 计算每个字段的精确率/召回率/F1
    per_field_metrics = {}
    for field in field_tp:
        prf = metrics.precision_recall_f1(field_tp[field], field_fp[field], field_fn[field])
        per_field_metrics[field] = {
            **prf,
            "tp": field_tp[field],
            "fp": field_fp[field],
            "fn": field_fn[field],
        }

    # 无风险片段误报率
    no_risk_items = [r for r in detail_results if r.get("expected_output") == "events_empty"]
    false_positives = sum(1 for r in no_risk_items if not r.get("is_empty_output", True))
    no_risk_accuracy = 1.0 - (false_positives / len(no_risk_items)) if no_risk_items else 1.0

    completed = len([r for r in detail_results if "error" not in r])

    if verbose:
        print(f"\n{'='*60}")
        print("AGGREGATE RESULTS")
        print(f"{'='*60}")
        for field, prf in per_field_metrics.items():
            print(f"  {field}: P={prf['precision']:.2%}, R={prf['recall']:.2%}, F1={prf['f1']:.2%}")
        print(f"  no_risk_accuracy: {no_risk_accuracy:.2%}")

    return {
        "aggregate_metrics": {
            "total": len(items),
            "completed": completed,
            "errors": len(detail_results) - completed,
            "no_risk_accuracy": no_risk_accuracy,
            "false_positives_on_no_risk": false_positives,
            "no_risk_total": len(no_risk_items),
        },
        "per_field_metrics": per_field_metrics,
        "details": detail_results,
    }


def _run_single_extraction(item):
    """对单个文本片段运行风险抽取并逐字段对比标注。"""
    from risk.services.verification_service import _call_extraction_llm, _parse_extraction_output

    fragment = item["fragment"]
    document_title = item.get("document_title", "评估测试文档")
    document_type = item.get("document_type", "风险分析")
    annotations = item.get("annotations", {})

    # 如果标注中标明预期输出为空
    if annotations.get("expected_output") == "events_empty":
        document = SimpleNamespace(title=document_title, doc_type=document_type)
        try:
            raw_content = None
            events = _call_extraction_llm(
                document=document,
                chunk_context=fragment,
            )[0]  # events list
        except Exception:
            events = []

        return {
            "id": item["id"],
            "fragment": fragment,
            "expected_output": "events_empty",
            "actual_events": events,
            "is_empty_output": len(events) == 0,
            "overall_correct": len(events) == 0,
            "per_field": _empty_per_field(),
        }

    # 正常风险事件条目
    expected_company = annotations.get("company_name", "")
    expected_risk_type = annotations.get("risk_type", "")
    expected_risk_level = annotations.get("risk_level", "")
    expected_event_time = annotations.get("event_time", "")
    expected_evidence = annotations.get("evidence_text", "")

    document = SimpleNamespace(title=document_title, doc_type=document_type)

    try:
        start = time.time()
        events, raw_content = _call_extraction_llm(
            document=document,
            chunk_context=fragment,
        )
        elapsed_ms = int((time.time() - start) * 1000)
    except Exception as e:
        return {
            "id": item["id"],
            "fragment": fragment,
            "expected": annotations,
            "error": str(e),
            "per_field": _empty_per_field(),
        }

    # 取第一个抽取的事件进行对比（如果标注只有一条）
    if events:
        event = {k: _to_str(v) for k, v in events[0].items()}
    else:
        event = {}

    # 逐字段对比
    company_tp, company_fp, company_fn = _compare_field(
        predicted=event.get("company_name", ""),
        expected=expected_company,
        match_fn=lambda p, e: metrics.fuzzy_match(p, e, threshold=0.7),
    )

    risk_type_tp, risk_type_fp, risk_type_fn = _compare_field(
        predicted=event.get("risk_type", ""),
        expected=expected_risk_type,
        match_fn=metrics.exact_match,
    )

    risk_level_tp, risk_level_fp, risk_level_fn = _compare_field(
        predicted=event.get("risk_level", ""),
        expected=expected_risk_level,
        match_fn=metrics.exact_match,
    )

    event_time_tp, event_time_fp, event_time_fn = _compare_field(
        predicted=event.get("event_time", ""),
        expected=expected_event_time,
        match_fn=lambda p, e: _year_month_match(p, e),
    )

    evidence_tp, evidence_fp, evidence_fn = _compare_field(
        predicted=event.get("evidence_text", ""),
        expected=expected_evidence,
        match_fn=lambda p, e: metrics.substring_overlap_ratio(p, e) >= 0.3,
    )

    # 整体正确（所有字段都正确）
    all_correct = all([
        company_tp and not company_fp and not company_fn,
        risk_type_tp and not risk_type_fp and not risk_type_fn,
        risk_level_tp and not risk_level_fp and not risk_level_fn,
        evidence_tp and not evidence_fp and not evidence_fn,
    ])
    overall_tp = 1 if all_correct else 0
    overall_fp = 0 if all_correct else (1 if events else 0)
    overall_fn = 0 if all_correct else 1

    return {
        "id": item["id"],
        "fragment": fragment,
        "expected": annotations,
        "actual_event": event,
        "raw_output": raw_content if 'raw_content' in dir() else None,
        "elapsed_ms": elapsed_ms if 'elapsed_ms' in dir() else None,
        "overall_correct": all_correct,
        "per_field": {
            "company_name": {"tp": company_tp, "fp": company_fp, "fn": company_fn},
            "risk_type": {"tp": risk_type_tp, "fp": risk_type_fp, "fn": risk_type_fn},
            "risk_level": {"tp": risk_level_tp, "fp": risk_level_fp, "fn": risk_level_fn},
            "event_time": {"tp": event_time_tp, "fp": event_time_fp, "fn": event_time_fn},
            "evidence_text": {"tp": evidence_tp, "fp": evidence_fp, "fn": evidence_fn},
            "overall": {"tp": overall_tp, "fp": overall_fp, "fn": overall_fn},
        },
    }


def _compare_field(predicted, expected, match_fn):
    """
    对比单个字段，返回 (tp, fp, fn)。

    match_fn(predicted, expected) -> bool
    """
    if not expected:
        # 标注中没有该字段，不评估
        return 0, 0, 0
    if not predicted:
        # 有标注但未抽取到
        return 0, 0, 1
    if match_fn(predicted, expected):
        return 1, 0, 0
    else:
        return 0, 1, 1


def _to_str(value):
    """将值安全转换为字符串。"""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    # datetime / date 对象
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _year_month_match(predicted_time, expected_time):
    """检查时间是否在年+月级别匹配。"""
    pred_str = _to_str(predicted_time)
    exp_str = _to_str(expected_time)
    if not pred_str or not exp_str:
        return False
    # 取 YYYY-MM 部分
    pred_ym = pred_str[:7] if len(pred_str) >= 7 else pred_str
    exp_ym = exp_str[:7] if len(exp_str) >= 7 else exp_str
    return pred_ym == exp_ym


def _empty_per_field():
    return {
        "company_name": {"tp": 0, "fp": 0, "fn": 0},
        "risk_type": {"tp": 0, "fp": 0, "fn": 0},
        "risk_level": {"tp": 0, "fp": 0, "fn": 0},
        "event_time": {"tp": 0, "fp": 0, "fn": 0},
        "evidence_text": {"tp": 0, "fp": 0, "fn": 0},
        "overall": {"tp": 0, "fp": 0, "fn": 0},
    }
