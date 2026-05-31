"""
Run 4-strategy comparison for RAG QA (Section 6.3 Table 6.3).

Usage:
    python manage.py run_strategy_comparison --limit 5
    python manage.py run_strategy_comparison --output results/
"""

import json
import os
import time
from unittest.mock import patch
from datetime import datetime

from django.core.management.base import BaseCommand
from django.test.utils import override_settings


class Command(BaseCommand):
    help = "Run 4-strategy RAG QA comparison (Section 6.3)"

    def add_arguments(self, parser):
        parser.add_argument("--dataset", default="/app/eval_datasets/rag_qa/qa_30_questions.json")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--output", default="/app/eval_results")

    def handle(self, *args, **options):
        dataset_path = options["dataset"]
        limit = options["limit"]
        output_dir = options["output"]

        dataset = self._load_dataset(dataset_path)
        items = dataset["items"][:limit] if limit else dataset["items"]

        strategies = [
            ("keyword", "关键词检索"),
            ("vector", "向量检索"),
            ("hybrid", "向量+BM25/全文检索"),
            ("hybrid_rerank", "向量+BM25/全文检索+RRF+rerank"),
        ]

        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("RAG QA 4-Strategy Comparison (Section 6.3)"))
        self.stdout.write(self.style.SUCCESS(f"Questions: {len(items)}"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        all_results = {}

        for strategy_key, strategy_name in strategies:
            self.stdout.write(f"\n--- {strategy_name} ---")
            results = self._run_strategy(items, strategy_key)
            metrics = self._compute_metrics(results)
            all_results[strategy_key] = {
                "name": strategy_name,
                "results": results,
                "metrics": metrics,
            }

            self.stdout.write(
                f"  Accuracy={metrics['accuracy']:.1%} "
                f"Recall={metrics['citation_recall']:.1%} "
                f"Consist={metrics['citation_consistency']:.1%} "
                f"AvgTT={metrics['avg_first_token_ms']:.0f}ms"
            )

        # Print final comparison table
        self._print_table(all_results)

        # Save results
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"strategy_comparison_{ts}.json")

        clean = {}
        for key, val in all_results.items():
            clean[key] = {
                "name": val["name"],
                "metrics": val["metrics"],
                "results": [{k: v for k, v in r.items() if k != "judge_scores"}
                           for r in val["results"]],
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\nSaved: {output_path}"))

    def _load_dataset(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _run_strategy(self, items, strategy):
        from chat.services.ask_service import ask_question
        from eval.services.llm_judge_service import judge_rag_answer

        results = []

        for idx, item in enumerate(items):
            question = item["question"]
            qid = item["id"]
            category = item.get("category", "unknown")
            expected_type = item.get("expected_answer_type", "cited")
            expected_keywords = item.get("expected_answer_keywords", [])

            try:
                start = time.time()

                if strategy == "keyword":
                    # 仅BM25+全文检索 (禁用向量)
                    with patch("rag.services.llamaindex_store_service.search",
                              return_value=[]):
                        result = ask_question(question=question, top_k=5)
                elif strategy == "vector":
                    # 仅向量检索 (禁用BM25和全文)
                    with override_settings(RAG_BM25_ENABLED=False,
                                          RAG_MYSQL_FULLTEXT_ENABLED=False):
                        result = ask_question(question=question, top_k=5)
                elif strategy == "hybrid":
                    # 向量+BM25+全文，跳过rerank
                    with patch("rag.services.rerank_service.rerank_results",
                              side_effect=lambda results, **kwargs: results):
                        result = ask_question(question=question, top_k=5)
                else:
                    # hybrid_rerank: 完整链路
                    result = ask_question(question=question, top_k=5)

                elapsed_ms = int((time.time() - start) * 1000)
                answer = result.get("answer", "")
                citations = result.get("citations", [])

                ctx = ""
                if citations:
                    for i, c in enumerate(citations[:5]):
                        ctx += f"[{i+1}] {c.get('document_title','?')}: {c.get('snippet','')[:150]}\n"

                judge = judge_rag_answer(
                    question=question,
                    citations_context=ctx,
                    answer=answer,
                    expected_answer_type=expected_type,
                    expected_keywords=expected_keywords,
                    expected_sources=item.get("expected_document_sources", []),
                )

                if judge:
                    accuracy = judge["accuracy"] / 10.0
                    cit_recall = judge["citation_recall"] / 10.0
                    cit_consistency = judge["citation_consistency"] / 10.0
                    is_correct = judge["accuracy"] >= 5
                else:
                    accuracy = cit_recall = cit_consistency = 0.0
                    is_correct = False

                results.append({
                    "id": qid, "category": category, "question": question,
                    "answer": answer[:300],
                    "accuracy": accuracy, "citation_recall": cit_recall,
                    "citation_consistency": cit_consistency,
                    "is_correct": is_correct, "first_token_ms": elapsed_ms,
                })

                self.stdout.write(
                    f"  [{idx+1}/{len(items)}] {qid}: "
                    f"{'✓' if is_correct else '✗'} "
                    f"acc={accuracy:.1f} rec={cit_recall:.1f} "
                    f"con={cit_consistency:.1f} t={elapsed_ms}ms"
                )

            except Exception as e:
                self.stdout.write(f"  [{idx+1}/{len(items)}] {qid}: ERROR {e}")
                results.append({
                    "id": qid, "category": category, "question": question,
                    "error": str(e), "is_correct": False,
                })

        return results

    def _compute_metrics(self, results):
        valid = [r for r in results if "error" not in r]
        correct = [r for r in valid if r.get("is_correct")]

        def ms(vals):
            if not vals:
                return (0, 0)
            m = sum(vals) / len(vals)
            if len(vals) < 2:
                return (m, 0)
            v = sum((x-m)**2 for x in vals) / (len(vals)-1)
            return (m, v**0.5)

        accs = [r["accuracy"] for r in valid if "accuracy" in r]
        recs = [r["citation_recall"] for r in valid if "citation_recall" in r]
        cons = [r["citation_consistency"] for r in valid if "citation_consistency" in r]
        times = [r["first_token_ms"] for r in valid if "first_token_ms" in r]

        acc_m, _ = ms(accs)
        rec_m, _ = ms(recs)
        con_m, _ = ms(cons)
        time_m, _ = ms(times)

        return {
            "accuracy": len(correct) / len(valid) if valid else 0,
            "accuracy_mean": acc_m,
            "citation_recall": rec_m,
            "citation_consistency": con_m,
            "avg_first_token_ms": time_m,
            "total": len(results),
            "completed": len(valid),
            "errors": len(results) - len(valid),
        }

    def _print_table(self, all_results):
        self.stdout.write("\n")
        self.stdout.write("=" * 95)
        self.stdout.write("表6.3  RAG 问答质量评估结果")
        self.stdout.write("=" * 95)
        h = f"{'检索策略':<30} {'问题数':<8} {'回答准确率':<12} {'引用召回率':<12} {'引用一致率':<12} {'平均首token':<12}"
        self.stdout.write(h)
        self.stdout.write("-" * 95)

        for key in ["keyword", "vector", "hybrid", "hybrid_rerank"]:
            if key not in all_results:
                continue
            m = all_results[key]["metrics"]
            n = all_results[key]["name"]
            self.stdout.write(
                f"{n:<30} {m['total']:<8} "
                f"{m['accuracy']:.1%}        "
                f"{m['citation_recall']:.1%}        "
                f"{m['citation_consistency']:.1%}        "
                f"{m['avg_first_token_ms']:.0f}ms"
            )
