"""
Section 6.5: Model Validation Set & Safety Boundary Testing.

Usage:
    python manage.py run_model_validation_eval --dataset eval_datasets/model_validation/validation_50_samples.json
    python manage.py run_model_validation_eval --limit 10
    python manage.py run_model_validation_eval --output results/model_validation_results.json
"""

import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from eval.services.model_validation_evaluator import run_model_validation_evaluation


class Command(BaseCommand):
    help = "Run model validation set evaluation (Section 6.5)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="eval_datasets/model_validation/validation_50_samples.json",
            help="Path to model validation dataset JSON file",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of samples (for testing)",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output JSON file path for results",
        )
        parser.add_argument(
            "--no-llm-judge",
            action="store_true",
            help="Disable LLM judge for refusal quality scoring",
        )

    def handle(self, *args, **options):
        dataset_path = options["dataset"]
        limit = options["limit"]
        output_path = options["output"]
        use_llm_judge = not options["no_llm_judge"]

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Model Validation Set Evaluation (Section 6.5)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        results = run_model_validation_evaluation(
            dataset_path=dataset_path,
            limit=limit,
            use_llm_judge=use_llm_judge,
            verbose=True,
        )

        # 打印汇总表
        self.stdout.write("\n")
        self.stdout.write("=" * 70)
        self.stdout.write("VALIDATION RESULTS BY DIMENSION")
        self.stdout.write("=" * 70)
        m = results["aggregate_metrics"]

        self.stdout.write(f"  身份认知准确率:        {m['identity_accuracy']:.1%}")
        self.stdout.write(f"  风险类型识别准确率:      {m['risk_type_identification_accuracy']:.1%}")
        self.stdout.write(f"  风险等级判断准确率:      {m['risk_level_judgment_accuracy']:.1%} (within-1-level: {m['risk_level_within_one_level_accuracy']:.1%})")
        self.stdout.write(f"  结构化字段完整率:        {m['structured_field_completeness_rate']:.1%}")
        self.stdout.write(f"  证据抽取正确率:         {m['evidence_extraction_accuracy']:.1%} (编造率: {m['evidence_fabrication_rate']:.1%})")
        self.stdout.write(f"  缺少数据时合理拒答率:    {m['refusal_accuracy']:.1%}")

        # 保存结果
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            output_data = {
                "run_type": "model_validation",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "dataset": dataset_path,
                    "use_llm_judge": use_llm_judge,
                },
                "aggregate_metrics": m,
                "dimension_counts": results["dimension_counts"],
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nResults saved to: {output_path}"))

            detail_path = output_path.replace(".json", "_details.json")
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(results["details"], f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Details saved to: {detail_path}"))

        self.stdout.write(self.style.SUCCESS("\nEvaluation complete."))
