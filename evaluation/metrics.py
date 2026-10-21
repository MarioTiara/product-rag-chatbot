# evaluation/metrics.py

from collections import defaultdict


def normalize_tool_name(tool):
    """Support tool names returned as strings or dictionaries."""
    if isinstance(tool, str):
        return tool

    if isinstance(tool, dict):
        return tool.get("name") or tool.get("tool_name", "")

    return ""


def evaluate_turn(expected, actual):
    answer = actual.get("answer", "").casefold()

    expected_contains = expected.get("expected_contains", [])
    expected_not_contains = expected.get(
        "expected_not_contains", []
    )

    checks = {
        "answer_contains_expected": all(
            phrase.casefold() in answer
            for phrase in expected_contains
        ),
        "answer_excludes_forbidden": all(
            phrase.casefold() not in answer
            for phrase in expected_not_contains
        ),
    }

    if "expected_tool_calls" in expected:
        actual_tools = {
            normalize_tool_name(tool)
            for tool in actual.get("tool_calls", [])
        }

        expected_tools = set(expected["expected_tool_calls"])

        # Every expected tool must have been called.
        checks["expected_tools_called"] = (
            expected_tools.issubset(actual_tools)
        )

    return checks


def summarize_results(results):
    total = len(results)
    passed = sum(result["passed"] for result in results)

    category_results = defaultdict(
        lambda: {"total": 0, "passed": 0}
    )

    latencies = []

    for result in results:
        category = result.get("category", "uncategorized")

        category_results[category]["total"] += 1
        category_results[category]["passed"] += int(
            result["passed"]
        )

        if "latency_ms" in result:
            latencies.append(result["latency_ms"])

    return {
        "total_turns": total,
        "passed_turns": passed,
        "failed_turns": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "average_latency_ms": (
            round(sum(latencies) / len(latencies), 2)
            if latencies else None
        ),
        "categories": dict(category_results),
    }