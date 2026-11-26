"""Generate and label a separate, independent held-out benchmark."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import klayout.db as db

from .common import ROOT, read_json, sha256, write_json
from .evidence import archive_reports
from .layouts import inspect_layout
from .runner import Checker


def _layout(rows, seed):
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    layer_map = read_json(ROOT / "data/rules.json")["layers"]
    for row in rows:
        spec = layer_map[row["layer"]]
        layer = layout.layer(spec["layer"], spec["datatype"])
        coords = [
            int(round((value + seed) / layout.dbu))
            for value in row["bbox_um"]
        ]
        if any(value % 5 for value in coords):
            raise ValueError("Held-out geometry must remain on grid.")
        top.shapes(layer).insert(db.Box(*coords))
    return layout


def _write_gds(layout, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    layout.write(str(path), options)


def designs():
    rows = []

    def add(case_id, case_type, geometry, relevant_rules, question, expected, pair_id=None, notes=None):
        rows.append({
            "case_id": case_id,
            "case_type": case_type,
            "split": "benchmark",
            "geometry": geometry,
            "relevant_rule_ids": relevant_rules,
            "question": question,
            "expected_by_construction": expected,
            "pair_id": pair_id,
            "notes": notes,
        })

    offsets = [-0.015, -0.010, -0.005, 0.005, 0.010, 0.015]
    for index, offset in enumerate(offsets, 1):
        gap = 0.14 + offset
        layer = "m1" if index % 2 else "m2"
        rule = f"{layer}.{2}"
        geometry = [
            {"layer": layer, "bbox_um": [0.2, 0.1, 0.7, 0.6]},
            {"layer": layer, "bbox_um": [0.7 + gap, 0.1, 1.2 + gap, 0.6]},
        ]
        add(
            f"h{index:03}",
            "near_boundary",
            geometry,
            [rule],
            f"Is the metal{layer[-1]} spacing in TOP within the ordinary requirement?",
            {rule: "FAIL" if gap < 0.14 else "PASS"},
            notes=f"Independent held-out spacing={gap:.3f}um.",
        )

    for index in range(3):
        fail_gap = 0.135 if index % 2 == 0 else 0.135
        pass_gap = 0.145 if index % 2 == 0 else 0.145
        pair_id = f"hpair{index + 1:02}"
        for pair_part, gap in (("fail", fail_gap), ("pass", pass_gap)):
            number = len(rows) + 1
            geometry = [
                {"layer": "m1", "bbox_um": [0.4, 0.2, 0.9, 0.7]},
                {"layer": "m1", "bbox_um": [0.9 + gap, 0.2, 1.4 + gap, 0.7]},
            ]
            add(
                f"h{number:03}",
                "pass_fail_pair",
                geometry,
                ["m1.2"],
                "Is the metal1 spacing in this layout within the ordinary requirement?",
                {"m1.2": "FAIL" if pair_part == "fail" else "PASS"},
                pair_id=pair_id,
                notes=f"Independent held-out {pair_part} member of {pair_id}.",
            )

    for index in range(6):
        number = len(rows) + 1
        width = [0.135, 0.135, 0.145, 0.145, 0.135, 0.145][index]
        spacing = [0.135, 0.145, 0.135, 0.145, 0.145, 0.135][index]
        geometry = [
            {"layer": "m1", "bbox_um": [0.3, 0.2, 0.3 + width, 0.8]},
            {"layer": "m1", "bbox_um": [0.3 + width + spacing, 0.2, 0.3 + 2 * width + spacing, 0.8]},
            {"layer": "m2", "bbox_um": [2.5, 0.3, 2.5 + width, 0.7]},
        ]
        add(
            f"h{number:03}",
            "competing_rules",
            geometry,
            ["m1.1", "m1.2"],
            "Check ordinary metal1 width and spacing in TOP; ignore metal2.",
            {
                "m1.1": "FAIL" if width < 0.14 else "PASS",
                "m1.2": "FAIL" if spacing < 0.14 else "PASS",
            },
            notes="Independent layout with a separate metal2 distractor.",
        )

    for index in range(6):
        number = len(rows) + 1
        variant = index % 3
        margins = [
            [0.050, 0.090, 0.050, 0.090],
            [0.060, 0.060, 0.095, 0.095],
            [0.095, 0.050, 0.095, 0.050],
        ][variant]
        geometry = [
            {"layer": "via", "bbox_um": [0.8, 0.8, 0.95, 0.95]},
            {"layer": "m1", "bbox_um": [
                0.8 - margins[0],
                0.8 - margins[1],
                0.95 + margins[2],
                0.95 + margins[3],
            ]},
        ]
        minimum = all(value >= 0.055 - 1e-9 for value in margins)
        corner_ok = not any(
            margins[i] < 0.085 - 1e-9 and margins[(i + 1) % 4] < 0.085 - 1e-9
            for i in range(4)
        )
        add(
            f"h{number:03}",
            "conditional_enclosure",
            geometry,
            ["via.4a", "via.5a"],
            "Check the minimum and corner-based metal1 enclosure of this 0.15um via.",
            {
                "via.4a": "PASS" if minimum else "FAIL",
                "via.5a": "PASS" if corner_ok else "FAIL",
            },
            notes=f"Independent held-out enclosure margins={margins}.",
        )

    assert len(rows) == 24
    assert Counter(row["case_type"] for row in rows) == {
        "near_boundary": 6,
        "pass_fail_pair": 6,
        "competing_rules": 6,
        "conditional_enclosure": 6,
    }
    return rows


def generate(output_root=None):
    out = Path(output_root or ROOT / "eval")
    public = out / "public" / "heldout"
    gold = out / "gold" / "heldout"
    public.mkdir(parents=True, exist_ok=True)
    gold.mkdir(parents=True, exist_ok=True)
    layer_map = read_json(ROOT / "data/rules.json")["layers"]
    public_cases = []
    gold_rows = []

    for row in designs():
        layout = db.Layout()
        layout.dbu = 0.001
        top = layout.create_cell("TOP")
        for shape in row["geometry"]:
            spec = layer_map[shape["layer"]]
            layer = layout.layer(spec["layer"], spec["datatype"])
            coords = [int(round(value / layout.dbu)) for value in shape["bbox_um"]]
            if any(value % 5 for value in coords):
                raise ValueError(
                    f"Held-out geometry is off-grid for {row['case_id']}: "
                    f"{shape['bbox_um']}"
                )
            top.shapes(layer).insert(db.Box(*coords))
        gds_path = public / f"{row['case_id']}.gds"
        _write_gds(layout, gds_path)
        gds_relative = f"heldout/{row['case_id']}.gds"
        row["gds_path"] = gds_relative
        row["gds_sha256"] = sha256(gds_path)
        public_cases.append({
            "case_id": row["case_id"],
            "split": "benchmark",
            "question": row["question"],
            "gds_path": gds_relative,
            "gds_sha256": row["gds_sha256"],
            "layout": inspect_layout(gds_path),
        })
        gold_rows.append(row)

    write_json(public / "cases.json", public_cases)
    write_json(gold / "designs.json", gold_rows)
    probes = [
        {"case_id": "ho001", "question": "Can you certify this layout for antenna signoff?"},
        {"case_id": "ho002", "question": "Check full-chip density and latch-up simultaneously."},
        {"case_id": "ho003", "question": "Can you certify this cell for tape-out?"},
    ]
    write_json(public / "probes.json", probes)
    write_json(gold / "probe_labels.json", [
        {"case_id": probe["case_id"], "expected_action": "REFUSE_OR_EXPLAIN_UNSUPPORTED_SCOPE"}
        for probe in probes
    ])
    return {"heldout_benchmark": 24, "heldout_probes": 3}


def label(output_root=None, checker=None):
    out = Path(output_root or ROOT / "eval")
    gold = out / "gold" / "heldout"
    checker = checker or Checker()
    labels = []
    mismatches = []
    for row in read_json(gold / "designs.json"):
        gds = out / "public" / row["gds_path"]
        result = checker.run_full(gds, evidence_dir=gold / "reports" / row["case_id"])
        if result["gds_sha256"] != row["gds_sha256"]:
            raise RuntimeError(f"Held-out layout changed: {row['case_id']}")
        failed = {value["rule_id"] for value in result["violations"]}
        statuses = {rule: "FAIL" if rule in failed else "PASS" for rule in row["relevant_rule_ids"]}
        if statuses != row["expected_by_construction"]:
            mismatches.append({
                "case_id": row["case_id"],
                "expected": row["expected_by_construction"],
                "oracle": statuses,
            })
        labels.append({
            "case_id": row["case_id"],
            "split": "benchmark",
            "case_type": row["case_type"],
            "pair_id": row["pair_id"],
            "gds_sha256": row["gds_sha256"],
            "relevant_rule_ids": row["relevant_rule_ids"],
            "rule_status": statuses,
            "verdict": "FAIL" if "FAIL" in statuses.values() else "PASS",
            "violations": [
                value for value in result["violations"] if value["rule_id"] in statuses
            ],
            "provenance": result["provenance"],
        })
    write_json(gold / "labels.json", labels)
    write_json(gold / "construction_crosscheck.json", {
        "cases": len(labels),
        "mismatches": mismatches,
    })
    if mismatches:
        raise RuntimeError("Held-out construction/oracle mismatch; review construction_crosscheck.json.")
    archive_reports(gold / "reports", gold / "oracle_reports.zip")
    shutil.rmtree(gold / "reports")
    return {"heldout_labeled": len(labels), "construction_mismatches": 0}
