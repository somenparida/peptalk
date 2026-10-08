#!/usr/bin/env python3
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from evaluation.evaluate import evaluate_split, print_evaluation_summary
from evaluation.ablation import run_ablation_study
from evaluation.compare import generate_comparison_charts


def main():
    print("========================================")
    print("EXECUTING MASTER EVALUATION SUITE")
    print("========================================\n")

    print("[1/4] Running Development Set Evaluation...")
    dev_results = evaluate_split("development")
    print_evaluation_summary(dev_results)
    print("\n" + "-"*60 + "\n")

    print("[2/4] Running Held-out Benchmark Evaluation...")
    held_results = evaluate_split("heldout")
    print_evaluation_summary(held_results)
    print("\n" + "-"*60 + "\n")

    print("[3/4] Running Ablation Study...")
    run_ablation_study("heldout")
    print("\n" + "-"*60 + "\n")

    print("[4/4] Generating Comparison Charts...")
    generate_comparison_charts()
    print("\nMaster evaluation suite complete!")


if __name__ == "__main__":
    main()
