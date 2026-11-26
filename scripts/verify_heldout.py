"""Cross-check held-out public layouts and private labels."""

import json
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import klayout.rdb as rdb

from drc_explain.common import ROOT, read_json, sha256
from drc_explain.evidence import report_bytes
from drc_explain.layouts import inspect_layout
from drc_explain.reports import parse_report


public_root = ROOT / "eval/public"
heldout_root = public_root / "heldout"
gold_root = ROOT / "eval/gold/heldout"

cases = read_json(heldout_root / "cases.json")
labels = read_json(gold_root / "labels.json")
if len(cases) != 24 or len(labels) != 24:
    raise RuntimeError("Held-out dataset must contain exactly 24 layouts.")

case_by_id = {case["case_id"]: case for case in cases}
checks = []
for label in labels:
    case = case_by_id[label["case_id"]]
    gds = public_root / case["gds_path"]
    if case["gds_sha256"] != sha256(gds) or case["gds_sha256"] != label["gds_sha256"]:
        raise RuntimeError(f"Held-out layout hash mismatch: {label['case_id']}")
    if case["layout"] != inspect_layout(gds):
        raise RuntimeError(f"Held-out layout inspection mismatch: {label['case_id']}")

    raw_report = report_bytes(gold_root, label["case_id"])
    parsed = parse_report(BytesIO(raw_report))
    native = rdb.ReportDatabase()
    with TemporaryDirectory(prefix="heldout-rdb-") as temp:
        report_path = Path(temp) / "report.lyrdb"
        report_path.write_bytes(raw_report)
        native.load(str(report_path))

    native_counts = Counter(
        native.category_by_id(item.category_id()).name()
        for item in native.each_item()
    )
    xml_counts = Counter(value["rule_id"] for value in parsed["violations"])
    if native_counts != xml_counts:
        raise RuntimeError(f"Held-out native report mismatch: {label['case_id']}")
    for rule_id, status in label["rule_status"].items():
        expected = "FAIL" if native_counts[rule_id] else "PASS"
        if status != expected:
            raise RuntimeError(
                f"Held-out label mismatch: {label['case_id']} {rule_id}"
            )
    checks.append(label["case_id"])

summary = {
    "heldout_layouts": len(checks),
    "case_ids": checks,
    "native_rdb_verified": True,
    "construction_mismatches": 0,
}
print(json.dumps(summary, indent=2))
