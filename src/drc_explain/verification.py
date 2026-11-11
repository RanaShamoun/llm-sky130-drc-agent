"""Verify the model's structured claims against current-query tool evidence."""

from __future__ import annotations

import math

from .common import ROOT, read_json


class VerificationError(ValueError):
    pass


def _number(value):
    return type(value) in {int, float} and math.isfinite(value)


def verify_answer(answer, evidence, inspected_hash=None):
    """No gold labels, question-specific rule list, or hidden oracle is consulted.

    Coverage/relevance of the model's chosen rules remains an evaluation target.
    This verifier establishes fidelity to the tools, not completeness of selection.
    """
    expected_keys = {"verdict", "selections", "claims", "refusal_reason"}
    if not isinstance(answer, dict) or set(answer) != expected_keys:
        raise VerificationError(
            "Final answer must contain exactly verdict, selections, claims, refusal_reason."
        )
    verdict = answer["verdict"]
    if verdict not in {"PASS", "FAIL", "REFUSE"}:
        raise VerificationError("Invalid verdict.")
    if not isinstance(answer["selections"], list) or not isinstance(
        answer["claims"], list
    ):
        raise VerificationError("Selections and claims must be lists.")
    if verdict == "REFUSE":
        if answer["selections"] or answer["claims"]:
            raise VerificationError("A refusal must not contain geometric claims.")
        if (
            not isinstance(answer["refusal_reason"], str)
            or not answer["refusal_reason"].strip()
        ):
            raise VerificationError("A refusal needs a reason.")
        return {
            "verdict": "REFUSE",
            "checks": [],
            "selections": [],
            "explanation": "No geometric verdict issued. " + answer["refusal_reason"],
            "verification_scope": "Refusal has no geometric claims. Whether refusal is appropriate is scored separately.",
        }
    if answer["refusal_reason"] is not None:
        raise VerificationError("PASS/FAIL must not contain a refusal reason.")
    if not inspected_hash:
        raise VerificationError("No successful inspection for this request.")
    if not answer["selections"] or not answer["claims"]:
        raise VerificationError(
            "A geometric verdict needs selected rules and evidence-backed claims."
        )
    catalog = {r["rule_id"]: r for r in read_json(ROOT / "data/rules.json")["rules"]}
    retrieved = set()
    checked = set()
    for entry in evidence.values():
        if not entry["response"]["ok"]:
            continue
        result = entry["response"]["result"]
        if entry["tool"] == "retrieve_rules":
            retrieved.update(r["rule_id"] for r in result["rules"])
        if entry["tool"] == "run_drc":
            checked.update(c["rule_id"] for c in result["checks"])
    selected = []
    for selection in answer["selections"]:
        if not isinstance(selection, dict) or set(selection) != {
            "rule_id",
            "justification",
        }:
            raise VerificationError("Invalid rule-selection structure.")
        rule = selection["rule_id"]
        if not isinstance(rule, str) or rule not in catalog or rule not in retrieved:
            raise VerificationError(
                "Every selected rule must exist in the supported retrieved corpus."
            )
        if (
            not isinstance(selection["justification"], str)
            or not selection["justification"].strip()
        ):
            raise VerificationError("Every selection needs a justification.")
        selected.append(rule)
    if len(set(selected)) != len(selected):
        raise VerificationError("Duplicate selected rules.")
    # A model cannot hide an inconvenient checked violation by omitting that rule.
    if set(selected) != checked:
        raise VerificationError(
            "Selections must cover every rule checked during this query."
        )
    verified = []
    claimed = []
    for claim in answer["claims"]:
        keys = {
            "rule_id",
            "status",
            "limit_um",
            "measured_values_um",
            "evidence_call_id",
        }
        if not isinstance(claim, dict) or set(claim) != keys:
            raise VerificationError("Invalid claim structure.")
        rule = claim["rule_id"]
        if not isinstance(rule, str) or rule not in selected:
            raise VerificationError("Claim cites an unselected or unsupported rule.")
        call_id = claim["evidence_call_id"]
        entry = evidence.get(call_id) if isinstance(call_id, str) else None
        if not entry or entry["tool"] != "run_drc" or not entry["response"]["ok"]:
            raise VerificationError("Claim has no successful DRC evidence call.")
        result = entry["response"]["result"]
        if result["gds_sha256"] != inspected_hash:
            raise VerificationError("DRC evidence does not match the inspected layout.")
        actual = next((c for c in result["checks"] if c["rule_id"] == rule), None)
        if actual is None or actual["status"] != claim["status"]:
            raise VerificationError("Claimed rule status contradicts the DRC result.")
        if (
            not _number(claim["limit_um"])
            or abs(claim["limit_um"] - actual["limit_um"]) > 1e-9
        ):
            raise VerificationError("Claimed limit does not match the rule tool.")
        measurements = sorted(
            {
                m["measured_um"]
                for v in actual["violations"]
                for m in v["markers"]
                if m.get("measured_um") is not None
            }
        )
        supplied = claim["measured_values_um"]
        if not isinstance(supplied, list) or not all(_number(v) for v in supplied):
            raise VerificationError("Measurements must be a list of finite numbers.")
        if len(supplied) != len(measurements) or any(
            abs(a - b) > 1e-9 for a, b in zip(sorted(supplied), measurements)
        ):
            raise VerificationError(
                f"Claimed measurements for {rule} do not exactly match available DRC marker distances. "
                f"Use measured_values_um={measurements}. A passing check has no DRC measurement."
            )
        verified.append(
            dict(
                actual,
                evidence_call_id=call_id,
                measured_values_um=measurements,
                source_url=catalog[rule]["source_url"],
            )
        )
        claimed.append(rule)
    if len(set(claimed)) != len(claimed) or set(claimed) != set(selected):
        raise VerificationError("Exactly one claim is required per selected rule.")
    actual_verdict = "FAIL" if any(c["status"] == "FAIL" for c in verified) else "PASS"
    if verdict != actual_verdict:
        raise VerificationError("Overall verdict contradicts the checked rules.")
    # Authoritative prose is rendered from verified claims, not unverified free text.
    sentences = [f"{verdict} for the requested rules."]
    for check in verified:
        sentence = f"{check['rule_id']}: {check['status']}; rule limit {check['limit_um']:g} um."
        if check["status"] == "FAIL":
            category = catalog[check["rule_id"]]["category"]
            if category == "spacing":
                sentence += " The shapes are too close together."
            elif category == "width":
                sentence += " The metal is narrower than the allowed minimum."
            elif check["rule_id"] in {"via.5a", "m2.5"}:
                sentence += " The pinned deck flagged adjacent via edges with insufficient metal enclosure."
            else:
                sentence += " The surrounding metal does not provide the required via enclosure."
        if check["measured_values_um"]:
            sentence += (
                " Measured violation distance(s): "
                + ", ".join(f"{v:g} um" for v in check["measured_values_um"])
                + "."
            )
        elif check["status"] == "PASS":
            sentence += " No violation was reported; no passing distance was measured."
        else:
            sentence += " See the returned marker coordinates; no scalar measurement is available."
        sentences.append(sentence)
    sentences.append(
        "This verdict covers the selected rules only and is not tape-out approval."
    )
    return {
        "verdict": verdict,
        "checks": verified,
        "selections": answer["selections"],
        "explanation": "\n".join(sentences),
        "verification_scope": "Rule IDs, statuses, limits, marker measurements, and overall verdict match tool evidence. Selection relevance/completeness and free-text selection justifications are not certified.",
    }
