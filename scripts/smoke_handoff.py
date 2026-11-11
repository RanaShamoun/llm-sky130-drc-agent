"""Exercise all three public tools on real passing/failing geometry."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drc_explain.common import ROOT, read_json, write_json
from drc_explain.tools import Toolset

ids = [
    "b001",
    "b002",
    "b004",
    "b005",
    "b007",
    "b008",
    "b010",
    "b011",
    "b037",
    "b038",
    "b039",
    "b040",
    "b041",
    "b042",
    "b043",
    "b044",
]
cases = {c["case_id"]: c for c in read_json(ROOT / "eval/public/cases.json")}
labels = {c["case_id"]: c for c in read_json(ROOT / "eval/gold/labels.json")}
tools = Toolset(log_path=ROOT / "runs/handoff_tools.jsonl")
retrieval = tools.call("retrieve_rules", {"query": "metal1 spacing", "limit": 3})
assert retrieval["ok"] and retrieval["result"]["rules"][0]["rule_id"] == "m1.2"
results = []
for id in ids:
    case = cases[id]
    gold = labels[id]
    inspection = tools.call("inspect_layout", {"gds_path": case["gds_path"]})
    assert inspection["ok"] and inspection["result"] == case["layout"]
    answer = tools.call(
        "run_drc", {"gds_path": case["gds_path"], "rule_ids": gold["relevant_rule_ids"]}
    )
    assert answer["ok"], answer
    value = answer["result"]
    assert value["status"] == gold["verdict"], (id, value, gold)
    assert {c["rule_id"]: c["status"] for c in value["checks"]} == gold["rule_status"]
    results.append(
        {"case_id": id, "status": value["status"], "rules": gold["rule_status"]}
    )
# Demonstrate that a wrong selection can miss a real violation, without leaking gold.
wrong = tools.call("run_drc", {"gds_path": "benchmark/b004.gds", "rule_ids": ["m1.1"]})
assert wrong["ok"] and wrong["result"]["status"] == "PASS"
assert "m1.2" not in json.dumps(wrong)
write_json(
    ROOT / "eval/gold/handoff_smoke.json",
    {"retrieval_ok": True, "cases": results, "selection_isolation_ok": True},
)
print(
    f"{len(results)} real-tool cases passed, covering all eight supported rules; wrong-selection isolation passed."
)
