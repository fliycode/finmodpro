"""
Section 6.4: Risk Event Extraction Evaluation.

Usage:
    python manage.py run_risk_extraction_eval --dataset eval_datasets/risk_extraction/risk_50_fragments.json
    python manage.py run_risk_extraction_eval --limit 10
    python manage.py run_risk_extraction_eval --output results/risk_extraction_results.json
"""

import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from eval.services.risk_extraction_evaluator import run_risk_extraction_evaluation


class Command(BaseCommand):
    help = "Run risk event extraction evaluation (Section 6.4)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="eval_datasets/risk_extraction/risk_50_fragments.json",
            help="Path to risk extraction dataset JSON file",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of fragments (for testing)",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output JSON file path for results",
        )

    def handle(self, *args, **options):
        dataset_path = options["dataset"]
        limit = options["limit"]
        output_path = options["output"]

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Risk Event Extraction Evaluation (Section 6.4)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        results = run_risk_extraction_evaluation(
            dataset_path=dataset_path,
            limit=limit,
            verbose=True,
        )

        # 打印汇总表
        self.stdout.write("\n")
        self.stdout.write("=" * 70)
        self.stdout.write("PER-FIELD PRECISION / RECALL / F1")
        self.stdout.write("=" * 70)
        header = f"{'Field':<20} {'Precision':<12} {'Recall':<12} {'F1':<12} {'TP/FP/FN':<15}"
        self.stdout.write(header)
        self.stdout.write("-" * 70)

        for field, prf in results["per_field_metrics"].items():
            self.stdout.write(
                f"{field:<20} "
                f"{prf['precision']:.1%}         "
                f"{prf['recall']:.1%}       "
                f"{prf['f1']:.1%}       "
                f"{prf['tp']}/{prf['fp']}/{prf['fn']}"
            )

        self.stdout.write(f"\nNo-risk fragment accuracy: {results['aggregate_metrics']['no_risk_accuracy']:.1%}")
        self.stdout.write(f"False positives on no-risk: {results['aggregate_metrics']['false_positives_on_no_risk']}/{results['aggregate_metrics']['no_risk_total']}")

        # 保存结果
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            output_data = {
                "run_type": "risk_extraction",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "dataset": dataset_path,
                },
                "aggregate_metrics": results["aggregate_metrics"],
                "per_field_metrics": results["per_field_metrics"],
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nResults saved to: {output_path}"))

            detail_path = output_path.replace(".json", "_details.json")
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(results["details"], f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Details saved to: {detail_path}"))

        self.stdout.write(self.style.SUCCESS("\nEvaluation complete."))
