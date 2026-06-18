"""
main.py
-------
Orchestrates the full pipeline:
  1. Load 10 test scenarios
  2. Generate emails using Model A (basic) and Model B (role+few-shot)
  3. Score all 20 emails with 3 custom metrics
  4. Write results to CSV
  5. Print a summary comparison table

Usage:
  python main.py

Required:
  OPENROUTER_API_KEY environment variable set.

Output:
  reports/evaluation_results.csv   — full raw scores for all 20 evaluations
  reports/summary.txt              — model comparison summary
"""

import json
import os
import sys
import csv
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
from app.generator import run_all_generations
from app.evaluator import run_all_evaluations


SCENARIOS_PATH = os.path.join(os.path.dirname(__file__), "data", "scenarios.json")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
CSV_PATH = os.path.join(REPORTS_DIR, "evaluation_results.csv")
SUMMARY_PATH = os.path.join(REPORTS_DIR, "summary.txt")


def load_scenarios() -> list[dict]:
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(evaluated: list[dict]) -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    fieldnames = [
        "scenario_id",
        "model_variant",
        "tone",
        "intent",
        "metric_1_fact_recall",
        "metric_1_facts_found",
        "metric_1_total_facts",
        "metric_2_tone_alignment",
        "metric_2_tone_raw",
        "metric_2_tone_rationale",
        "metric_3_structure",
        "metric_3_has_subject",
        "metric_3_has_body",
        "metric_3_has_closing",
        "composite_score",
        "generated_email",
        "reference_email",
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(evaluated)

    print(f"\n  CSV written: {CSV_PATH}")


def compute_summary(evaluated: list[dict]) -> dict:
    """Compute per-variant averages across all 10 scenarios."""
    summary = {}

    for variant in ["A", "B"]:
        rows = [r for r in evaluated if r["model_variant"] == variant]

        avg = lambda key: round(sum(r[key] for r in rows) / len(rows), 4)

        summary[variant] = {
            "count": len(rows),
            "avg_fact_recall": avg("metric_1_fact_recall"),
            "avg_tone_alignment": avg("metric_2_tone_alignment"),
            "avg_structure": avg("metric_3_structure"),
            "avg_composite": avg("composite_score"),
            "tone_raw_avg": round(sum(r["metric_2_tone_raw"] for r in rows) / len(rows), 2),
        }

    return summary


def print_summary(summary: dict) -> None:
    a = summary["A"]
    b = summary["B"]

    lines = [
        "",
        "=" * 60,
        "  EVALUATION SUMMARY",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        f"{'Metric':<30} {'Model A':>10} {'Model B':>10}  {'Winner':>8}",
        "-" * 62,
        f"{'Fact Recall (M1)':<30} {a['avg_fact_recall']:>10.4f} {b['avg_fact_recall']:>10.4f}  {'B' if b['avg_fact_recall'] >= a['avg_fact_recall'] else 'A':>8}",
        f"{'Tone Alignment (M2 /10)':<30} {a['tone_raw_avg']:>10.2f} {b['tone_raw_avg']:>10.2f}  {'B' if b['tone_raw_avg'] >= a['tone_raw_avg'] else 'A':>8}",
        f"{'Email Structure (M3)':<30} {a['avg_structure']:>10.4f} {b['avg_structure']:>10.4f}  {'B' if b['avg_structure'] >= a['avg_structure'] else 'A':>8}",
        "-" * 62,
        f"{'COMPOSITE AVERAGE':<30} {a['avg_composite']:>10.4f} {b['avg_composite']:>10.4f}  {'B' if b['avg_composite'] >= a['avg_composite'] else 'A':>8}",
        "=" * 60,
        "",
        "  Model A = Basic Prompt (bare instruction, no role, no examples)",
        "  Model B = Role + Few-Shot Prompt (expert persona + 2 examples)",
        "",
        "  Generation model : gpt-4.1-mini",
        "  Judge model      : gpt-4.1",
        "  Scenarios        : 10",
        "  Total evaluations: 20",
        "=" * 60,
        "",
    ]

    text = "\n".join(lines)
    print(text)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Summary written: {SUMMARY_PATH}")


def main():
    print("\n" + "=" * 60)
    print("  EMAIL GENERATION ASSISTANT — EVALUATION PIPELINE")
    print("=" * 60)

    # Validate API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("\n  ERROR: OPENROUTER_API_KEY is not set.")
        print("  Run: export OPENROUTER_API_KEY='sk-...'")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    scenarios = load_scenarios()
    print(f"\n  Loaded {len(scenarios)} scenarios from {SCENARIOS_PATH}")

    # STEP 1: Generate
    print(f"\n  [STEP 1/3] Generating emails (20 total — 10 per variant)...")
    t0 = time.time()
    results = run_all_generations(scenarios)
    print(f"  Done in {time.time() - t0:.1f}s")

    # STEP 2: Evaluate
    print(f"\n  [STEP 2/3] Running 3 metrics on all 20 results...")
    t1 = time.time()
    evaluated = run_all_evaluations(client, results)
    print(f"  Done in {time.time() - t1:.1f}s")

    # STEP 3: Output
    print(f"\n  [STEP 3/3] Writing outputs...")
    write_csv(evaluated)
    summary = compute_summary(evaluated)
    print_summary(summary)


if __name__ == "__main__":
    main()
