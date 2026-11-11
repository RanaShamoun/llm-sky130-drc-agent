"""Small working example for Rana: retrieve, inspect, then check geometry.

Run `python run.py demo`. No LLM credentials are needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drc_explain.tools import Toolset


def main():
    tools = Toolset()
    lookup = tools.call("retrieve_rules", {"query": "metal1 spacing", "limit": 3})
    layout = tools.call("inspect_layout", {"gds_path": "benchmark/b004.gds"})
    result = tools.call(
        "run_drc",
        {
            "gds_path": "benchmark/b004.gds",
            "rule_ids": ["m1.1", "m1.2"],
        },
    )
    for name, response in [
        ("Rule lookup", lookup),
        ("Layout inspection", layout),
        ("DRC", result),
    ]:
        if not response["ok"]:
            raise RuntimeError(f"{name} failed: {response['error']['message']}")
    print("Layout: benchmark/b004.gds")
    print(
        "Retrieved rules:",
        ", ".join(rule["rule_id"] for rule in lookup["result"]["rules"]),
    )
    print("Geometry shapes:", layout["result"]["shape_count"])
    for check in result["result"]["checks"]:
        measured = [
            marker["measured_um"]
            for violation in check["violations"]
            for marker in violation["markers"]
            if marker.get("measured_um") is not None
        ]
        print(f"{check['rule_id']}: {check['status']} (limit {check['limit_um']} um)")
        if measured:
            print("  Measured violation distances (um):", measured)
    print("Overall:", result["result"]["status"], "- requested rules only.")
    print("Full tool trace: runs/tool_calls.jsonl")


if __name__ == "__main__":
    main()
