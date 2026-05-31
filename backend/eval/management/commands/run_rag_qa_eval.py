
"""
Section 6.3: RAG QA Quality Evaluation.

Usage:
    python manage.py run_rag_qa_eval --dataset eval_datasets/rag_qa/qa_30_questions.json
    python manage.py run_rag_qa_eval --strategies keyword,vector,hybrid_rerank --limit 5
    python manage.py run_rag_qa_eval --output results/rag_qa_results.json
"""

import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from eval.services.rag_qa_evaluator import run_qa_evaluation


class Command(BaseCommand):
    help = "Run RAG QA quality evaluation (Section 6.3)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="eval_datasets/rag_qa/qa_30_questions.json",
            help="Path to QA dataset JSON file",
        )
        parser.add_argument(
            "--strategies",
            default="keyword,vector,hybrid,hybrid_rerank",
            help="Comma-separated retrieval strategies to test",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Number of retrieval results",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of questions (for testing)",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output JSON file path for results",
        )
        parser.add_argument(
            "--no-llm-judge",
            action="store_true",
            help="Disable LLM judge scoring (use keyword match only)",
        )

    def handle(self, *args, **options):
        dataset_path = options["dataset"]
        strategies = [s.strip() for s in options["strategies"].split(",")]
        top_k = options["top_k"]
        limit = options["limit"]
        output_path = options["output"]
        use_llm_judge = not options["no_llm_judge"]

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("RAG QA Quality Evaluation (Section 6.3)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        results = run_qa_evaluation(
            dataset_path=dataset_path,
            strategies=strategies,
            top_k=top_k,
            use_llm_judge=use_llm_judge,
            limit=limit,
            verbose=True,
        )

        # 打印汇总对比表
        self.stdout.write("\n")
        self.stdout.write("=" * 80)
        self.stdout.write("STRATEGY COMPARISON SUMMARY")
        self.stdout.write("=" * 80)
        header = f"{'Strategy':<25} {'Accuracy':<12} {'Cit.Recall':<12} {'Cit.Consistency':<15} {'Avg FTT(ms)':<14}"
        self.stdout.write(header)
        self.stdout.write("-" * 80)

        for strategy, result in results.items():
            m = result["aggregate_metrics"]
            self.stdout.write(
                f"{strategy:<25} "
                f"{m['answer_accuracy']['mean']:.1%}±{m['answer_accuracy']['std']:.1%}  "
                f"{m['citation_recall']['mean']:.1%}±{m['citation_recall']['std']:.1%}  "
                f"{m['citation_consistency']['mean']:.1%}±{m['citation_consistency']['std']:.1%}     "
                f"{m['average_first_token_time_ms']['mean']:.0f}±{m['average_first_token_time_ms']['std']:.0f}"
            )

        # 保存结果
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            output_data = {
                "run_type": "rag_qa",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "dataset": dataset_path,
                    "strategies": strategies,
                    "top_k": top_k,
                    "use_llm_judge": use_llm_judge,
                },
                "results": {
                    strategy: {
                        "aggregate_metrics": r["aggregate_metrics"],
                        "by_category": r.get("by_category", {}),
                        "total": r["total"],
                        "completed": r["completed"],
                    }
                    for strategy, r in results.items()
                },
                # 详细结果不写入主报告（太大），单独保存
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nResults saved to: {output_path}"))

            # 保存详细结果
            detail_path = output_path.replace(".json", "_details.json")
            detail_data = {
                strategy: r["details"] for strategy, r in results.items()
            }
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Details saved to: {detail_path}"))

        self.stdout.write(self.style.SUCCESS("\nEvaluation complete."))
