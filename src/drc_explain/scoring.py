"""Evaluator-only scoring. Never import this module into model input construction."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from .common import ROOT, read_json


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _numbers_match(actual, expected, tolerance=1e-9):
    return (
        isinstance(actual, list)
        and all(type(value) in {int, float} and math.isfinite(value) for value in actual)
        and len(actual) == len(expected)
        and all(
            abs(supplied - reference) <= tolerance
            for supplied, reference in zip(sorted(actual), sorted(expected))
        )
    )


def score_case(result, gold, catalog=None, known_ids=None):
    catalog = catalog or {
        rule["rule_id"]: rule for rule in read_json(ROOT / "data/rules.json")["rules"]
    }
    known_ids = set(known_ids or catalog)
    relevant = set(gold.get("relevant_rule_ids", []))
    selections = result.get("selections", [])
    selected_list = [entry.get("rule_id") for entry in selections if isinstance(entry, dict)]
    selected = {rule for rule in selected_list if isinstance(rule, str)}
    checks = result.get("checks", result.get("claims", []))
    checks = [entry for entry in checks if isinstance(entry, dict)]
    claims = {entry.get("rule_id"): entry for entry in checks if isinstance(entry.get("rule_id"), str)}
    cited = selected | set(claims)
    measurements = defaultdict(set)
    for violation in gold.get("violations", []):
        for marker in violation["markers"]:
            if marker.get("measured_um") is not None:
                measurements[violation["rule_id"]].add(marker["measured_um"])
    eligible = bool(measurements)
    verdict_correct = result.get("verdict") == gold["verdict"]
    selection_correct = selected == relevant and len(selected_list) == len(selected)
    statuses_correct = len(checks) == len(claims) and set(claims) == relevant and all(
        claims[rule].get("status") == status
        for rule, status in gold.get("rule_status", {}).items()
        if rule in claims
    )
    limits_correct = all(
        rule in catalog
        and _numbers_match([claim.get("limit_um")], [catalog[rule]["limit_um"]])
        for rule, claim in claims.items()
    )
    numeric_correct = eligible and all(
        rule in claims
        and _numbers_match(claims[rule].get("measured_values_um"), list(values))
        for rule, values in measurements.items()
    )
    unavailable_measurement_claims = sum(
        bool(claim.get("measured_values_um"))
        for rule, claim in claims.items()
        if not measurements.get(rule)
    )
    grounding = (
        verdict_correct
        and selection_correct
        and statuses_correct
        and limits_correct
        and not unavailable_measurement_claims
        and (not eligible or numeric_correct)
    )
    if gold["verdict"] == "REFUSE":
        grounding = verdict_correct and not cited and bool(result.get("explanation") or result.get("refusal_reason"))
    return {
        "case_id": gold["case_id"],
        "verdict_correct": verdict_correct,
        "selection_exact": selection_correct,
        "selection_true_positive": len(selected & relevant),
        "selection_false_positive": len(selected - relevant),
        "selection_false_negative": len(relevant - selected),
        "rule_status_correct": statuses_correct,
        "fabricated_citations": len(cited - known_ids),
        "unsupported_citations": len((cited & known_ids) - set(catalog)),
        "irrelevant_citations": len(cited - relevant),
        "duplicate_selections": len(selected_list) - len(selected),
        "duplicate_claims": len(checks) - len(claims),
        "limit_errors": sum(
            rule not in catalog
            or not _numbers_match([claim.get("limit_um")], [catalog[rule]["limit_um"]])
            for rule, claim in claims.items()
        ),
        "measurement_eligible": eligible,
        "numeric_grounding_correct": bool(numeric_correct),
        "unavailable_measurement_claims": unavailable_measurement_claims,
        "grounded": bool(grounding),
        "predicted_verdict": result.get("verdict", "ERROR"),
    }


def aggregate(records, labels, expected_case_ids=None, catalog=None, known_ids=None):
    """Score one model/condition/repetition; missing runs remain in denominators."""
    gold = {label["case_id"]: label for label in labels}
    expected = set(expected_case_ids if expected_case_ids is not None else gold)
    if expected - set(gold):
        raise ValueError("Expected cases are missing gold labels.")
    indexed = {}
    for record in records:
        case_id = record["case_id"]
        if case_id not in expected or case_id in indexed:
            raise ValueError("Unexpected or duplicate case result; score repetitions separately.")
        indexed[case_id] = record["result"]
    scores = {
        case_id: score_case(indexed.get(case_id, {}), gold[case_id], catalog, known_ids)
        for case_id in sorted(expected)
    }
    benchmark = [value for case_id, value in scores.items() if gold[case_id]["verdict"] != "REFUSE"]
    probes = [value for case_id, value in scores.items() if gold[case_id]["verdict"] == "REFUSE"]
    pairs = defaultdict(list)
    for label in labels:
        if label.get("pair_id"):
            pairs[label["pair_id"]].append(label["case_id"])
    complete_pairs = [members for members in pairs.values() if set(members) <= expected]
    true_positive = sum(value["selection_true_positive"] for value in benchmark)
    false_positive = sum(value["selection_false_positive"] for value in benchmark)
    false_negative = sum(value["selection_false_negative"] for value in benchmark)
    eligible = [value for value in benchmark if value["measurement_eligible"]]
    latencies = sorted(result["latency_s"] for result in indexed.values() if isinstance(result.get("latency_s"), (int, float)))
    costs = [result.get("cost_usd") for result in indexed.values()]
    return {
        "expected_count": len(expected),
        "completed_count": len(indexed),
        "missing_count": len(expected - set(indexed)),
        "verdict_counts": dict(Counter(value["predicted_verdict"] for value in scores.values())),
        "verdict_accuracy": _ratio(sum(value["verdict_correct"] for value in benchmark), len(benchmark)),
        "pair_count": len(complete_pairs),
        "pair_accuracy": _ratio(sum(all(scores[case_id]["verdict_correct"] for case_id in members) for members in complete_pairs), len(complete_pairs)),
        "selection_precision": _ratio(true_positive, true_positive + false_positive),
        "selection_recall": _ratio(true_positive, true_positive + false_negative),
        "selection_exact_accuracy": _ratio(sum(value["selection_exact"] for value in benchmark), len(benchmark)),
        "grounding_rate": _ratio(sum(value["grounded"] for value in benchmark), len(benchmark)),
        "measurement_eligible_count": len(eligible),
        "numeric_grounding_rate": _ratio(sum(value["numeric_grounding_correct"] for value in eligible), len(eligible)),
        "refusal_count": len(probes),
        "refusal_correctness": _ratio(sum(value["grounded"] for value in probes), len(probes)),
        "citation_errors": {key: sum(value[key] for value in scores.values()) for key in ["fabricated_citations", "unsupported_citations", "irrelevant_citations", "limit_errors", "unavailable_measurement_claims", "duplicate_selections", "duplicate_claims"]},
        "mean_latency_s": _ratio(sum(latencies), len(latencies)),
        "p95_latency_s": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
        "mean_tool_calls": _ratio(sum(result.get("tool_call_count", 0) for result in indexed.values()), len(indexed)),
        "api_cost_usd": sum(costs) if costs and all(type(cost) in {int, float} for cost in costs) else None,
        "hardware_electricity_cost_usd": None,
        "case_scores": list(scores.values()),
    }