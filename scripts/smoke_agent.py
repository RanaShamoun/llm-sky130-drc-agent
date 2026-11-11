"""Scripted agent integration checks using REAL KLayout, with NO LLM requests.

This fixture validates dispatch and verification only. It is not model evaluation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drc_explain.agent import Agent


class ScriptedClient:
    model = "scripted-integration-fixture-NOT-AN-LLM"
    is_live = False

    def __init__(self, gds_path, rules, refusal=False):
        self.gds_path = gds_path
        self.rules = rules
        self.refusal = refusal
        self.turn = 0

    def respond(self, inputs, tools, instructions):
        self.turn += 1
        if self.refusal:
            name = "finalize_answer"
            arguments = {
                "verdict": "REFUSE",
                "selections": [],
                "claims": [],
                "refusal_reason": "This question requests unsupported antenna checks.",
            }
        elif self.turn == 1:
            name = "retrieve_rules"
            arguments = {"query": "metal1 width spacing via enclosure", "limit": 8}
        elif self.turn == 2:
            name = "run_drc"
            arguments = {"gds_path": self.gds_path, "rule_ids": self.rules}
        else:
            result = json.loads(inputs[-1]["output"])["result"]
            name = "finalize_answer"
            arguments = {
                "verdict": result["status"],
                "selections": [
                    {
                        "rule_id": rule,
                        "justification": "Scripted integration fixture selection; not LLM reasoning.",
                    }
                    for rule in self.rules
                ],
                "claims": [
                    {
                        "rule_id": c["rule_id"],
                        "status": c["status"],
                        "limit_um": c["limit_um"],
                        "measured_values_um": sorted(
                            {
                                m["measured_um"]
                                for v in c["violations"]
                                for m in v["markers"]
                                if m.get("measured_um") is not None
                            }
                        ),
                        "evidence_call_id": "fixture_2",
                    }
                    for c in result["checks"]
                ],
                "refusal_reason": None,
            }
        return {
            "id": f"fixture_response_{self.turn}",
            "model": self.model,
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": f"fixture_{self.turn}",
                    "name": name,
                    "arguments": json.dumps(arguments),
                }
            ],
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


def main():
    print(
        "SCRIPTED INTEGRATION TEST: real KLayout, no LLM inference or accuracy claim."
    )
    for id, rules, expected in [
        ("b004", ["m1.1", "m1.2"], "FAIL"),
        ("b005", ["m1.1", "m1.2"], "PASS"),
        ("b039", ["via.4a", "via.5a"], "FAIL"),
        ("b040", ["via.4a", "via.5a"], "PASS"),
    ]:
        gds = f"benchmark/{id}.gds"
        result = Agent(ScriptedClient(gds, rules)).run(
            "Check the selected width/spacing or enclosure properties.", gds
        )
        assert result["verdict"] == expected, result
        assert result["verification"]["accepted"] and result["live_model"] is False
        print(f"{id}: {result['verdict']}; verified; {result['result_path']}")
    refused = Agent(ScriptedClient(None, [], refusal=True)).run(
        "Does this satisfy antenna rules?"
    )
    assert refused["verdict"] == "REFUSE" and refused["tool_call_count"] == 0
    print("Unsupported probe: REFUSE; no geometric verdict.")
    print(
        "All 5 scripted agent integration scenarios passed. Live OpenAI demo remains separate."
    )


if __name__ == "__main__":
    main()
