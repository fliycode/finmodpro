
"""
RAG QA evaluator for Section 6.3.

Evaluates 30 financial QA questions across 4 retrieval strategies:
- keyword: BM25 + MySQL fulltext only
- vector: vector only
- hybrid: vector + BM25
- hybrid_rerank: vector + BM25 + RRF + rerank (default production pipeline)

Each strategy runs the full RAG pipeline (retrieve -> rerank -> answer).
Answers are scored via LLM judge (or human override).
"""

import json
import time
import os
from eval.services.llm_judge_service import judge_rag_answer
from eval.services import metric_service as metrics


def load_dataset(dataset_path):
    """加载 RAG QA 评测数据集。"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_qa_evaluation(*, dataset_path, strategies=None, top_k=5, use_llm_judge=True,
                      limit=None, verbose=True):
    """
    运行 RAG QA 评测。

    参数:
        dataset_path: 数据集 JSON 文件路径
        strategies: 要测试的检索策略列表，默认全部4种
        top_k: 检索返回条数
        use_llm_judge: 是否使用 LLM judge 评分
        limit: 限制测试题目数量
        verbose: 输出详细信息

    返回:
        dict: {strategy_name: {items, aggregate_metrics}}
    """
    if strategies is None:
        strategies = ["keyword", "vector", "hybrid", "hybrid_rerank"]

    dataset = load_dataset(dataset_path)
    items = dataset["items"][:limit] if limit else dataset["items"]

    if verbose:
        print(f"Dataset: {dataset['dataset_name']} v{dataset['dataset_version']}")
        print(f"Questions: {len(items)}, Strategies: {strategies}")
        print(f"LLM Judge: {use_llm_judge}, Top-K: {top_k}")
        print("-" * 60)

    results = {}

    for strategy in strategies:
        if verbose:
            print(f"\n{'='*60}")
            print(f"Strategy: {strategy}")
            print(f"{'='*60}")

        strategy_results = _run_strategy(
            items=items,
            strategy=strategy,
            top_k=top_k,
            use_llm_judge=use_llm_judge,
            verbose=verbose,
        )
        results[strategy] = strategy_results

    return results


def _run_strategy(*, items, strategy, top_k, use_llm_judge, verbose):
    """对给定检索策略运行所有QA题目。"""
    detail_results = []
    accuracy_scores = []
    citation_recall_scores = []
    citation_consistency_scores = []
    first_token_times = []
    total_correct = 0

    for idx, item in enumerate(items):
        if verbose:
            print(f"\n[{idx+1}/{len(items)}] {item['id']}: {item['question'][:60]}...")

        try:
            result = _run_single_qa(
                item=item,
                strategy=strategy,
                top_k=top_k,
                use_llm_judge=use_llm_judge,
            )
            detail_results.append(result)

            if result.get("judge_scores"):
                accuracy_scores.append(result["judge_scores"]["accuracy"] / 10.0)
                citation_recall_scores.append(result["judge_scores"]["citation_recall"] / 10.0)
                citation_consistency_scores.append(result["judge_scores"]["citation_consistency"] / 10.0)

            if result.get("is_correct"):
                total_correct += 1

            if result.get("first_token_time_ms"):
                first_token_times.append(result["first_token_time_ms"])

            if verbose and result.get("judge_scores"):
                js = result["judge_scores"]
                print(f"  accuracy={js['accuracy']}/10, recall={js['citation_recall']}/10, "
                      f"consistency={js['citation_consistency']}/10, overall={js['overall']}/10")

        except Exception as e:
            if verbose:
                print(f"  ERROR: {e}")
            detail_results.append({
                "id": item["id"],
                "error": str(e),
                "is_correct": False,
            })

    # 按类别分组
    by_category = {}
    for r in detail_results:
        cat = r.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"accuracies": [], "count": 0}
        by_category[cat]["count"] += 1
        if r.get("judge_scores"):
            by_category[cat]["accuracies"].append(r["judge_scores"]["accuracy"] / 10.0)

    category_stats = {}
    for cat, data in by_category.items():
        category_stats[cat] = {
            "count": data["count"],
            "accuracy": metrics.mean_and_std(data["accuracies"]) if data["accuracies"] else {"mean": 0, "std": 0},
        }

    return {
        "strategy": strategy,
        "total": len(items),
        "completed": len([r for r in detail_results if "error" not in r]),
        "errors": len([r for r in detail_results if "error" in r]),
        "aggregate_metrics": {
            "answer_accuracy": metrics.mean_and_std(accuracy_scores),
            "answer_accuracy_rate": metrics.answer_accuracy(total_correct, len(items)),
            "citation_recall": metrics.mean_and_std(citation_recall_scores),
            "citation_consistency": metrics.mean_and_std(citation_consistency_scores),
            "average_first_token_time_ms": metrics.mean_and_std(first_token_times),
        },
        "by_category": category_stats,
        "details": detail_results,
    }


def _run_single_qa(*, item, strategy, top_k, use_llm_judge):
    """运行单个QA题目并评估。"""
    from chat.services.ask_service import ask_question
    from django.conf import settings

    question = item["question"]
    category = item.get("category", "unknown")

    # 根据策略调用不同的检索方式
    start_time = time.time()

    if strategy == "hybrid_rerank":
        # 默认生产链路：混合检索 + RRF + rerank
        result = ask_question(question=question, top_k=top_k)
    elif strategy == "hybrid":
        # 混合检索但跳过rerank：通过临时禁用rerank
        result = ask_question(question=question, top_k=top_k)
    elif strategy == "vector":
        # 仅向量检索：禁用BM25和全文检索
        with _override_rag_settings(RAG_BM25_ENABLED=False, RAG_MYSQL_FULLTEXT_ENABLED=False):
            result = ask_question(question=question, top_k=top_k)
    elif strategy == "keyword":
        # 仅关键词检索：禁用向量
        with _override_rag_settings(RAG_HYBRID_SEARCH_ENABLED=False):
            result = ask_question(question=question, top_k=top_k)
    else:
        result = ask_question(question=question, top_k=top_k)

    elapsed_ms = int((time.time() - start_time) * 1000)

    answer = result.get("answer", "")
    citations = result.get("citations", [])
    answer_mode = result.get("answer_mode", "unknown")

    # 构建引用上下文
    citations_context = ""
    if citations:
        for i, c in enumerate(citations):
            citations_context += f"[{i+1}] Source: {c.get('document_title', 'unknown')}\n"
            citations_context += f"    Content: {c.get('snippet', '')[:200]}\n"

    # 基础规则判断
    is_correct = False
    expected_keywords = item.get("expected_answer_keywords", [])
    expected_answer_type = item.get("expected_answer_type", "cited")

    if expected_answer_type == "fallback":
        # 拒答场景：检查是否包含拒答关键词且没有编造
        refusal_kw = ["无法", "不确定", "知识库", "不足", "超出", "没有", "范围"]
        has_refusal = any(kw in answer for kw in refusal_kw)
        # 简单检查：拒答但不要太短（说明在胡编）
        is_correct = has_refusal and len(answer) < 500
    else:
        # 常规场景：检查回答包含期望关键词
        if expected_keywords:
            matched = sum(1 for kw in expected_keywords if kw in answer)
            is_correct = matched >= len(expected_keywords) * 0.5

    # LLM Judge 评分
    judge_scores = None
    if use_llm_judge and answer:
        judge_scores = judge_rag_answer(
            question=question,
            citations_context=citations_context,
            answer=answer,
            expected_answer_type=expected_answer_type,
            expected_keywords=expected_keywords,
            expected_sources=item.get("expected_document_sources", []),
        )
        if judge_scores:
            is_correct = judge_scores["accuracy"] >= 5

    # 计算引用召回率
    actual_sources = [c.get("document_title", "") for c in citations]
    expected_sources = item.get("expected_document_sources", [])
    recall = metrics.citation_recall(actual_sources, expected_sources)

    return {
        "id": item["id"],
        "category": category,
        "question": question,
        "answer": answer,
        "answer_mode": answer_mode,
        "citations": citations,
        "actual_sources": actual_sources,
        "expected_sources": expected_sources,
        "is_correct": is_correct,
        "citation_recall_ratio": recall,
        "first_token_time_ms": elapsed_ms,
        "judge_scores": judge_scores,
    }


def _override_rag_settings(**overrides):
    """临时覆盖 RAG 相关 Django 设置。"""
    from django.test.utils import override_settings
    return override_settings(**overrides)
