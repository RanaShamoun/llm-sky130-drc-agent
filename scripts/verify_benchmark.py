"""Cross-check the XML parser against KLayout's independent native RDB reader."""

import json
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import klayout.db
import klayout.rdb as rdb

from drc_explain.common import ROOT, read_json, sha256, write_json
from drc_explain.evidence import report_bytes
from drc_explain.layouts import inspect_layout
from drc_explain.reports import marker_measurement, parse_report

labels = read_json(ROOT / "eval/gold/labels.json")
cases = {c["case_id"]: c for c in read_json(ROOT / "eval/public/cases.json")}
designs = {c["case_id"]: c for c in read_json(ROOT / "eval/gold/designs.json")}
checks = []
for label in labels:
    id = label["case_id"]
    case = cases[id]
    assert (
        label["gds_sha256"]
        == case["gds_sha256"]
        == sha256(ROOT / "eval/public" / case["gds_path"])
    )
    assert case["layout"] == inspect_layout(ROOT / "eval/public" / case["gds_path"])
    raw_report = report_bytes(ROOT / "eval/gold", id)
    parsed = parse_report(BytesIO(raw_report))
    assert label["violations"] == [
        v for v in parsed["violations"] if v["rule_id"] in label["relevant_rule_ids"]
    ]
    native = rdb.ReportDatabase()
    with TemporaryDirectory(prefix="drc-report-review-") as temp:
        path = Path(temp) / "report.lyrdb"
        path.write_bytes(raw_report)
        native.load(str(path))
    numeric_checked = 0
    for item in native.each_item():
        for value in item.each_value():
            marker = marker_measurement(value.to_s())
            if marker.get("measured_um") is not None:
                ep = value.edge_pair()
                distance = min(
                    abs(ep.first.distance(ep.second.p1)),
                    abs(ep.first.distance(ep.second.p2)),
                    abs(ep.second.distance(ep.first.p1)),
                    abs(ep.second.distance(ep.first.p2)),
                )
                assert abs(distance - marker["measured_um"]) < 1e-8, (
                    id,
                    distance,
                    marker,
                )
                numeric_checked += 1
    native_counts = Counter(
        native.category_by_id(item.category_id()).name() for item in native.each_item()
    )
    xml_counts = Counter(v["rule_id"] for v in parsed["violations"])
    assert native_counts == xml_counts, (id, native_counts, xml_counts)
    assert len(list(native.each_category())) == len(parsed["categories"])
    assert label["rule_status"] == designs[id]["expected_by_construction"]
    for rule, status in label["rule_status"].items():
        assert status == ("FAIL" if native_counts[rule] else "PASS")
    checks.append(
        {
            "case_id": id,
            "native_rdb_matches_xml": True,
            "marker_count": native.num_items(),
            "category_count": len(parsed["categories"]),
            "numeric_markers_crosschecked": numeric_checked,
        }
    )
summary = {
    "cases": len(checks),
    "checks": checks,
    "benchmark_verdict_counts": dict(
        Counter(c["verdict"] for c in labels if c["split"] == "benchmark")
    ),
    "benchmark_case_types": dict(
        Counter(c["case_type"] for c in labels if c["split"] == "benchmark")
    ),
    "scope": "Parser/data verification only. Same KLayout engine; not an independent physical signoff oracle.",
}
write_json(ROOT / "eval/gold/validation.json", summary)
print(json.dumps({k: v for k, v in summary.items() if k != "checks"}, indent=2))
