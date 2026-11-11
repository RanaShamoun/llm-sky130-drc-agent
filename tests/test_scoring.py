from drc_explain.scoring import aggregate, score_case


CATALOG = {"m1.1": {"limit_um": 0.14}, "m1.2": {"limit_um": 0.14}}


def label(case_id="b001", verdict="PASS", pair_id=None):
    return {"case_id": case_id, "verdict": verdict, "full_deck_verdict": "FAIL", "relevant_rule_ids": ["m1.1"], "rule_status": {"m1.1": verdict}, "pair_id": pair_id, "violations": []}


def answer(verdict="PASS"):
    return {"verdict": verdict, "selections": [{"rule_id": "m1.1", "justification": "width"}], "checks": [{"rule_id": "m1.1", "status": verdict, "limit_um": 0.14, "measured_values_um": []}]}


def test_relevant_verdict_not_full_deck():
    score = score_case(answer(), label(), CATALOG)
    assert score["verdict_correct"] and score["grounded"]
    assert not score["measurement_eligible"]


def test_missing_pair_member_counts_as_failure():
    labels = [label("b001", pair_id="pair"), label("b002", "FAIL", "pair")]
    metrics = aggregate([{"case_id": "b001", "result": answer()}], labels, catalog=CATALOG)
    assert metrics["verdict_accuracy"] == 0.5
    assert metrics["pair_accuracy"] == 0
    assert metrics["missing_count"] == 1


def test_error_is_not_refusal():
    metrics = aggregate([{"case_id": "o001", "result": {"verdict": "ERROR"}}], [{"case_id": "o001", "verdict": "REFUSE"}], catalog=CATALOG)
    assert metrics["refusal_correctness"] == 0
    assert metrics["verdict_counts"] == {"ERROR": 1}


def test_passing_distance_is_not_grounded():
    result = answer()
    result["checks"][0]["measured_values_um"] = [0.14]
    score = score_case(result, label(), CATALOG)
    assert score["unavailable_measurement_claims"] == 1
    assert not score["grounded"]


def test_numeric_grounding_and_missing_passing_rule():
    gold = label(verdict="FAIL")
    gold["violations"] = [{"rule_id": "m1.1", "markers": [{"measured_um": 0.135}]}]
    result = answer("FAIL")
    result["checks"][0]["measured_values_um"] = [0.135]
    assert score_case(result, gold, CATALOG)["grounded"]
    gold["relevant_rule_ids"].append("m1.2")
    gold["rule_status"]["m1.2"] = "PASS"
    score = score_case(result, gold, CATALOG)
    assert score["selection_false_negative"] == 1
    assert not score["grounded"]


def test_known_unsupported_is_not_fabricated():
    result = answer()
    result["selections"].append({"rule_id": "m1.99"})
    score = score_case(result, label(), CATALOG, set(CATALOG) | {"m1.99"})
    assert score["unsupported_citations"] == 1
    assert score["fabricated_citations"] == 0


def test_duplicate_claims_do_not_receive_grounding_credit():
    result = answer()
    result["checks"].append(result["checks"][0].copy())
    score = score_case(result, label(), CATALOG)
    assert score["duplicate_claims"] == 1
    assert not score["grounded"]