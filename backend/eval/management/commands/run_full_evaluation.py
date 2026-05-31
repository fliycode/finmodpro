"""
Run all three evaluation sections at once.

Usage:
    python manage.py run_full_evaluation
    python manage.py run_full_evaluation --limit 5
    python manage.py run_full_evaluation --output-dir results/
"""

import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError

from eval.services.rag_qa_evaluator import run_qa_evaluation
from eval.services.risk_extraction_evaluator import run_risk_extraction_evaluation
from eval.services.model_validation_evaluator import run_model_validation_evaluation


class Command(BaseCommand):
    help = "Run full evaluation suite (Sections 6.3, 6.4, 6.5)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rag-qa-dataset",
            default="eval_datasets/rag_qa/qa_30_questions.json",
            help="Path to RAG QA dataset",
        )
        parser.add_argument(
            "--risk-dataset",
            default="eval_datasets/risk_extraction/risk_50_fragments.json",
            help="Path to risk extraction dataset",
        )
        parser.add_argument(
            "--validation-dataset",
            default="eval_datasets/model_validation/validation_50_samples.json",
            help="Path to model validation dataset",
        )
        parser.add_argument(
            "--strategies",
            default="keyword,vector,hybrid,hybrid_rerank",
            help="Retrieval strategies for RAG QA (comma-separated)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit items per section (for smoke testing)",
        )
        parser.add_argument(
            "--output-dir",
            default="eval_results",
            help="Output directory for result JSON files",
        )
        parser.add_argument(
            "--no-llm-judge",
            action="store_true",
            help="Disable LLM judge scoring",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        output_dir = options["output_dir"]
        use_llm_judge = not options["no_llm_judge"]
        strategies = [s.strip() for s in options["strategies"].split(",")]

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("FULL EVALUATION SUITE"))
        self.stdout.write(self.style.SUCCESS(f"Sections 6.3, 6.4, 6.5"))
        self.stdout.write(self.style.SUCCESS(f"Output: {output_dir}/"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        all_results = {
            "run_type": "full",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "strategies": strategies,
                "use_llm_judge": use_llm_judge,
                "limit": limit,
            },
        }

        # Section 6.3: RAG QA
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SECTION 6.3: RAG QA Quality Evaluation")
        self.stdout.write("=" * 60)
        try:
            rag_results = run_qa_evaluation(
                dataset_path=options["rag_qa_dataset"],
                strategies=strategies,
                top_k=5,
                use_llm_judge=use_llm_judge,
                limit=limit,
                verbose=False,  # Less verbose for full run
            )
            all_results["section_6_3"] = {
                strategy: {
                    "aggregate_metrics": r["aggregate_metrics"],
                    "total": r["total"],
                    "completed": r["completed"],
                }
                for strategy, r in rag_results.items()
            }

            # Print comparison table
            self.stdout.write("\nStrategy Comparison:")
            header = f"{'Strategy':<25} {'Accuracy':<12} {'Cit.Recall':<12} {'Cit.Consistency':<15} {'Avg FTT(ms)':<14}"
            self.stdout.write(header)
            self.stdout.write("-" * 80)
            for strategy, r in rag_results.items():
                m = r["aggregate_metrics"]
                self.stdout.write(
                    f"{strategy:<25} "
                    f"{m['answer_accuracy']['mean']:.1%}±{m['answer_accuracy']['std']:.1%}  "
                    f"{m['citation_recall']['mean']:.1%}±{m['citation_recall']['std']:.1%}  "
                    f"{m['citation_consistency']['mean']:.1%}±{m['citation_consistency']['std']:.1%}     "
                    f"{m['average_first_token_time_ms']['mean']:.0f}±{m['average_first_token_time_ms']['std']:.0f}"
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Section 6.3 failed: {e}"))
            all_results["section_6_3"] = {"error": str(e)}

        # Section 6.4: Risk Extraction
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SECTION 6.4: Risk Event Extraction Evaluation")
        self.stdout.write("=" * 60)
        try:
            risk_results = run_risk_extraction_evaluation(
                dataset_path=options["risk_dataset"],
                limit=limit,
                verbose=False,
            )
            all_results["section_6_4"] = {
                "aggregate_metrics": risk_results["aggregate_metrics"],
                "per_field_metrics": risk_results["per_field_metrics"],
            }

            self.stdout.write("\nPer-Field P/R/F1:")
            header = f"{'Field':<20} {'Precision':<12} {'Recall':<12} {'F1':<12}"
            self.stdout.write(header)
            self.stdout.write("-" * 56)
            for field, prf in risk_results["per_field_metrics"].items():
                self.stdout.write(
                    f"{field:<20} {prf['precision']:.1%}         {prf['recall']:.1%}       {prf['f1']:.1%}"
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Section 6.4 failed: {e}"))
            all_results["section_6_4"] = {"error": str(e)}

        # Section 6.5: Model Validation
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SECTION 6.5: Model Validation & Safety Boundary")
        self.stdout.write("=" * 60)
        try:
            val_results = run_model_validation_evaluation(
                dataset_path=options["validation_dataset"],
                limit=limit,
                use_llm_judge=use_llm_judge,
                verbose=False,
            )
            all_results["section_6_5"] = {
                "aggregate_metrics": val_results["aggregate_metrics"],
                "dimension_counts": val_results["dimension_counts"],
            }

            self.stdout.write("\nValidation Results by Dimension:")
            m = val_results["aggregate_metrics"]
            self.stdout.write(f"  身份认知准确率:        {m['identity_accuracy']:.1%}")
            self.stdout.write(f"  风险类型识别准确率:      {m['risk_type_identification_accuracy']:.1%}")
            self.stdout.write(f"  风险等级判断准确率:      {m['risk_level_judgment_accuracy']:.1%} (within-1-level: {m['risk_level_within_one_level_accuracy']:.1%})")
            self.stdout.write(f"  结构化字段完整率:        {m['structured_field_completeness_rate']:.1%}")
            self.stdout.write(f"  证据抽取正确率:         {m['evidence_extraction_accuracy']:.1%} (编造率: {m['evidence_fabrication_rate']:.1%})")
            self.stdout.write(f"  缺少数据时合理拒答率:    {m['refusal_accuracy']:.1%}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Section 6.5 failed: {e}"))
            all_results["section_6_5"] = {"error": str(e)}

        # Save results
        output_path = os.path.join(output_dir, f"full_evaluation_{timestamp}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\nFull results saved to: {output_path}"))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Full evaluation suite complete."))
        self.stdout.write(self.style.SUCCESS("=" * 60))
