#!/usr/bin/env python3
"""Run evaluation scenarios against a chat API."""

import argparse
import json
import time
from pathlib import Path

import requests

from metrics import evaluate_turn, summarize_results

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset" / "product_questions.json"
REPORT_PATH = BASE_DIR / "evaluation_report.json"

DEFAULT_API_URL = "http://localhost:8000/chat"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate chatbot scenarios")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    return parser.parse_args()


def main():
    args = parse_args()
    api_url = args.api_url

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    results = []

    for scenario in dataset["scenarios"]:
        conversation_id = None

        for index, turn in enumerate(scenario["turns"], start=1):
            payload = {"message": turn["message"]}

            if conversation_id is not None:
                payload["conversation_id"] = conversation_id

            started = time.perf_counter()

            try:
                response = requests.post(
                    api_url,
                    json=payload,
                    timeout=60,
                )
                latency_ms = (
                    time.perf_counter() - started
                ) * 1000

                response.raise_for_status()
                body = response.json()

                conversation_id = body.get(
                    "conversation_id",
                    conversation_id,
                )

                actual = {
                    "answer": body.get("answer", ""),
                    "tool_calls": body.get("tool_calls", []),
                    "latency_ms": round(latency_ms, 2),
                }

                checks = evaluate_turn(turn, actual)

                result = {
                    "scenario_id": scenario["id"],
                    "category": scenario["category"],
                    "turn": index,
                    "message": turn["message"],
                    **actual,
                    "checks": checks,
                    "passed": all(checks.values()),
                }

            except (requests.RequestException, ValueError) as exc:
                result = {
                    "scenario_id": scenario["id"],
                    "category": scenario["category"],
                    "turn": index,
                    "message": turn["message"],
                    "error": str(exc),
                    "passed": False,
                }

            results.append(result)

            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"[{status}] {scenario['id']} "
                f"turn={index}"
            )

    summary = summarize_results(results)

    report = {
        "summary": summary,
        "results": results,
    }

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2))
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
