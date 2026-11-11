"""Deterministic layouts, evaluator-only design intent, and full-deck labels."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import klayout.db as db

from .common import ROOT, read_json, sha256, write_json
from .evidence import archive_reports
from .layouts import inspect_layout
from .runner import Checker


def _geometry(layer, kind, value, offset=0, rotate=False):
    if kind == "width":
        boxes = [[0, 0, value, 0.9]]
    else:
        boxes = [[0, 0, 0.5, 0.5], [0.5 + value, 0, 1.0 + value, 0.5]]
    if rotate:
        boxes = [[b[1], b[0], b[3], b[2]] for b in boxes]
    return [
        {"layer": layer, "bbox_um": [round(v + offset, 6) for v in b]} for b in boxes
    ]


def _enclosure(outer, margins):
    l, b, r, t = margins
    via = [0.3, 0.3, 0.45, 0.45]
    boxes = [
        {"layer": "via", "bbox_um": via},
        {"layer": outer, "bbox_um": [0.3 - l, 0.3 - b, 0.45 + r, 0.45 + t]},
        {"layer": "m2" if outer == "m1" else "m1", "bbox_um": [0.2, 0.2, 0.55, 0.55]},
    ]
    return boxes


def designs():
    rows = []

    def add(
        type,
        geometry,
        rules,
        question,
        expected,
        pair_id=None,
        split="benchmark",
        notes=None,
    ):
        index = sum(r["split"] == split for r in rows) + 1
        rows.append(
            {
                "case_id": f"{'b' if split == 'benchmark' else 'd'}{index:03}",
                "case_type": type,
                "split": split,
                "geometry": geometry,
                "relevant_rule_ids": rules,
                "question": question,
                "expected_by_construction": expected,
                "pair_id": pair_id,
                "notes": notes,
            }
        )

    for layer in ["m1", "m2"]:
        for kind in ["width", "spacing"]:
            rule = f"{layer}.{1 if kind == 'width' else 2}"
            for value in [0.135, 0.14, 0.145]:
                add(
                    "near_boundary",
                    _geometry(layer, kind, value),
                    [rule],
                    f"Does the metal{layer[-1]} {kind} in TOP meet the ordinary manufacturing requirement?",
                    {rule: "FAIL" if value < 0.14 else "PASS"},
                    notes=f"{kind}={value}um; exact boundary or one 5nm step away.",
                )
    for n, (layer, kind) in enumerate(
        [
            ("m1", "width"),
            ("m1", "spacing"),
            ("m2", "width"),
            ("m2", "spacing"),
            ("m1", "width"),
            ("m2", "spacing"),
        ]
    ):
        rule = f"{layer}.{1 if kind == 'width' else 2}"
        for value in [0.135, 0.14]:
            add(
                "pass_fail_pair",
                _geometry(layer, kind, value, offset=2 + n, rotate=bool(n % 2)),
                [rule],
                f"Is the metal{layer[-1]} {kind} in this cell within the ordinary design requirement?",
                {rule: "FAIL" if value < 0.14 else "PASS"},
                pair_id=f"p{n + 1:02}",
            )
    for n in range(12):
        w = [0.13, 0.14, 0.16][n % 3]
        s = [0.13, 0.15, 0.14][(n // 3) % 3]
        # Equal questions across all cases; distractor layers cannot reveal labels.
        geometry = [
            {"layer": "m1", "bbox_um": [0, 0, w, 0.9]},
            {"layer": "m1", "bbox_um": [w + s, 0, 2 * w + s, 0.9]},
        ]
        if n % 2:
            w2 = 0.135 if n % 4 == 1 else 0.15
            geometry += _geometry("m2", "width", w2, offset=3)
            rules = ["m1.1", "m1.2", "m2.1", "m2.2"]
            question = "Check ordinary width and spacing of both metal1 and metal2 routing in TOP."
            expected = {
                "m1.1": "FAIL" if w < 0.14 else "PASS",
                "m1.2": "FAIL" if s < 0.14 else "PASS",
                "m2.1": "FAIL" if w2 < 0.14 else "PASS",
                "m2.2": "PASS",
            }
        else:
            geometry += _geometry("m2", "width", 0.13, offset=3)
            rules = ["m1.1", "m1.2"]
            question = "Check ordinary width and spacing of metal1 routing only; ignore metal2."
            expected = {
                "m1.1": "FAIL" if w < 0.14 else "PASS",
                "m1.2": "FAIL" if s < 0.14 else "PASS",
            }
        add("competing_rules", geometry, rules, question, expected)
    variants = [
        ("m1", [0.05, 0.10, 0.10, 0.10], [0.055, 0.10, 0.10, 0.10]),
        ("m1", [0.08, 0.08, 0.10, 0.10], [0.085, 0.08, 0.10, 0.10]),
        ("m2", [0.10, 0.05, 0.10, 0.10], [0.10, 0.055, 0.10, 0.10]),
        ("m2", [0.10, 0.08, 0.08, 0.10], [0.10, 0.085, 0.08, 0.10]),
        ("m1", [0.055, 0.055, 0.055, 0.055], [0.085, 0.055, 0.085, 0.055]),
        ("m2", [0.055, 0.055, 0.055, 0.055], [0.055, 0.085, 0.055, 0.085]),
        ("m1", [0.055, 0.055, 0.085, 0.085], [0.085, 0.055, 0.085, 0.085]),
    ]
    for n, (outer, low, high) in enumerate(variants):
        rules = ["via.4a", "via.5a"] if outer == "m1" else ["m2.4", "m2.5"]
        for margins in [low, high]:
            minimum = all(v >= 0.055 - 1e-9 for v in margins)
            corner_ok = not any(
                margins[i] < 0.085 - 1e-9 and margins[(i + 1) % 4] < 0.085 - 1e-9
                for i in range(4)
            )
            # The pinned deck flags corners formed by two adjacent deficient edges.
            # This differs from simply requiring two adjacent sufficient edges.
            add(
                "conditional_enclosure",
                _enclosure(outer, margins),
                rules,
                f"Check the minimum and corner-based enclosure requirements of this 0.15um via landing by metal{outer[-1]} only.",
                {
                    rules[0]: "PASS" if minimum else "FAIL",
                    rules[1]: "PASS" if corner_ok else "FAIL",
                },
                notes=f"Left,bottom,right,top margins={margins}um; pinned deck flags adjacent deficient edges; see docs/ENCLOSURE_AUDIT.md.",
            )
    for layer, kind, value in [
        ("m1", "width", 0.125),
        ("m2", "width", 0.16),
        ("m1", "spacing", 0.12),
        ("m2", "spacing", 0.17),
    ]:
        rule = f"{layer}.{1 if kind == 'width' else 2}"
        add(
            "few_shot",
            _geometry(layer, kind, value, offset=20),
            [rule],
            f"Check metal{layer[-1]} {kind}.",
            {rule: "PASS" if value >= 0.14 else "FAIL"},
            split="development",
        )
    for value in [0.045, 0.1]:
        rules = ["via.4a", "via.5a"]
        add(
            "few_shot",
            _enclosure("m1", [value] * 4),
            rules,
            "Check the metal1 enclosure of this via.",
            {r: "PASS" if value >= 0.085 else "FAIL" for r in rules},
            split="development",
        )
    assert Counter(r["case_type"] for r in rows if r["split"] == "benchmark") == {
        "near_boundary": 12,
        "pass_fail_pair": 12,
        "competing_rules": 12,
        "conditional_enclosure": 14,
    }
    return rows


def generate(output_root=None):
    out = Path(output_root or ROOT / "eval")
    layer_map = read_json(ROOT / "data/rules.json")["layers"]
    rows = designs()
    public = []
    for row in rows:
        layout = db.Layout()
        layout.dbu = 0.001
        top = layout.create_cell("TOP")
        for shape in row["geometry"]:
            spec = layer_map[shape["layer"]]
            layer = layout.layer(spec["layer"], spec["datatype"])
            coords = [int(round(v / layout.dbu)) for v in shape["bbox_um"]]
            if any(v % 5 for v in coords):
                raise ValueError("Off-grid construction")
            top.shapes(layer).insert(db.Box(*coords))
        relative = f"{row['split']}/{row['case_id']}.gds"
        dest = out / "public" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        options = db.SaveLayoutOptions()
        options.gds2_write_timestamps = False
        layout.write(str(dest), options)
        row["gds_path"] = relative
        row["gds_sha256"] = sha256(dest)
        inspection = inspect_layout(dest)
        public.append(
            {
                k: row[k]
                for k in ["case_id", "split", "question", "gds_path", "gds_sha256"]
            }
            | {"layout": inspection}
        )
    write_json(out / "public/cases.json", public)
    write_json(out / "gold/designs.json", rows)
    probes = [
        "Is the metal density across this chip sufficient?",
        "Does this routed net satisfy antenna limits?",
        "Can you certify this cell as fully ready for tape-out?",
        "Check latch-up and well-tap placement requirements.",
        "Check the special spacing rules for metal wider than 3um.",
        "Check via enclosure inside the areaid core special region.",
    ]
    write_json(
        out / "public/probes.json",
        [{"case_id": f"o{i + 1:03}", "question": q} for i, q in enumerate(probes)],
    )
    write_json(
        out / "gold/probe_labels.json",
        [
            {
                "case_id": f"o{i + 1:03}",
                "expected_action": "REFUSE_OR_EXPLAIN_UNSUPPORTED_SCOPE",
            }
            for i in range(len(probes))
        ],
    )
    return {"benchmark": 50, "development": 6, "out_of_scope": 6}


def label(output_root=None, checker=None):
    out = Path(output_root or ROOT / "eval")
    checker = checker or Checker()
    labels = []
    mismatches = []
    for row in read_json(out / "gold/designs.json"):
        result = checker.run_full(
            out / "public" / row["gds_path"],
            evidence_dir=out / "gold/reports" / row["case_id"],
        )
        if result["gds_sha256"] != row["gds_sha256"]:
            raise RuntimeError(f"Layout changed since generation: {row['case_id']}")
        failed = {v["rule_id"] for v in result["violations"]}
        statuses = {
            r: "FAIL" if r in failed else "PASS" for r in row["relevant_rule_ids"]
        }
        if statuses != row["expected_by_construction"]:
            mismatches.append(
                {
                    "case_id": row["case_id"],
                    "expected": row["expected_by_construction"],
                    "oracle": statuses,
                }
            )
        labels.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "case_type": row["case_type"],
                "pair_id": row["pair_id"],
                "gds_sha256": row["gds_sha256"],
                "relevant_rule_ids": row["relevant_rule_ids"],
                "rule_status": statuses,
                "verdict": "FAIL" if "FAIL" in statuses.values() else "PASS",
                "full_deck_verdict": "FAIL" if failed else "PASS",
                "other_violated_rules": sorted(failed - set(statuses)),
                "violations": [
                    v for v in result["violations"] if v["rule_id"] in statuses
                ],
                "provenance": result["provenance"],
            }
        )
        print(f"Labeled {row['case_id']}: {labels[-1]['verdict']}", flush=True)
    write_json(out / "gold/labels.json", labels)
    write_json(
        out / "gold/construction_crosscheck.json",
        {"cases": len(labels), "mismatches": mismatches},
    )
    if mismatches:
        raise RuntimeError(
            f"{len(mismatches)} construction/oracle mismatches; review gold/construction_crosscheck.json before evaluation."
        )
    archive_reports(out / "gold/reports", out / "gold/oracle_reports.zip")
    shutil.rmtree(out / "gold/reports")
    return {"labeled": len(labels), "construction_mismatches": 0}
