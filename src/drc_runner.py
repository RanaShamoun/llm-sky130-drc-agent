"""
drc_runner.py

Reusable wrapper around the KLayout batch-mode DRC command validated in the
Week 1 feasibility spike (see spike/FEASIBILITY_SPIKE.md). Two jobs:

  1. run_drc(): run one GDS through the official SKY130 manufacturing rule
     deck (sky130A_mr.drc) and return a parsed result. This is also the
     function the agent's Executor tool will call in ablation Stage 3.
  2. label_manifest(): run every case in eval_manifest.json through the
     oracle and write eval_labeled.json with the real ground-truth labels.

Safety rails built in (each one guards a failure we have seen or could see):
  - feol=true and beol=true are ALWAYS passed. Without them the deck
    silently checks nothing (spike gotcha).
  - The script raises if a report has zero rule categories, i.e. the same
    silent-failure signature, so an empty report can never become a label.
  - Any stale report at the output path is deleted before each run, so a
    KLayout failure can never be mistaken for a previous run's result.

Usage (from the eval folder, where eval_manifest.json lives):
    python ..\\src\\drc_runner.py eval_manifest.json eval_labeled.json

Sanity check that the wrapper reproduces the Week 1 spike result:
    python ..\\src\\drc_runner.py --single ..\\spike\\test_violation.gds TOP
    (expect: violated rules = m1.2)

Environment: needs PDK_ROOT (and PDK, default sky130A) set, and `klayout`
on PATH. Optional overrides: KLAYOUT_BIN, SKY130_DRC_DECK.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

DECK_NAME = "sky130A_mr.drc"


def find_klayout() -> str:
    override = os.environ.get("KLAYOUT_BIN")
    if override:
        return override
    # shutil.which respects PATHEXT on Windows, so it finds klayout.bat (the
    # wrapper created in Week 1). subprocess alone would NOT find a .bat
    # given the bare name "klayout".
    for name in ("klayout", "klayout_app"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        "Could not find klayout on PATH. Set KLAYOUT_BIN to the full path of "
        "klayout.bat or klayout_app.exe."
    )


def find_deck() -> Path:
    override = os.environ.get("SKY130_DRC_DECK")
    if override:
        path = Path(override)
    else:
        pdk_root = os.environ.get("PDK_ROOT")
        pdk = os.environ.get("PDK", "sky130A")
        if not pdk_root:
            raise EnvironmentError(
                "PDK_ROOT is not set. Set it (see COMMAND_LOG.md step 4) or "
                "set SKY130_DRC_DECK to the full path of sky130A_mr.drc."
            )
        path = Path(pdk_root) / pdk / "libs.tech" / "klayout" / "drc" / DECK_NAME
    if not path.is_file():
        raise FileNotFoundError(f"DRC deck not found at {path}")
    return path


def parse_report(report_path: Path):
    """Return (number_of_rule_categories, {rule_id: [violation values]})."""
    root = ET.parse(str(report_path)).getroot()

    cats_el = root.find("categories")
    n_categories = len(cats_el.findall("category")) if cats_el is not None else 0
    if n_categories == 0:
        raise RuntimeError(
            f"Report {report_path} has ZERO rule categories. This is the "
            "silent-failure signature (deck ran no checks). Check that "
            "feol=true and beol=true were passed. Refusing to produce a label."
        )

    violations = {}
    items_el = root.find("items")
    if items_el is not None:
        for item in items_el.findall("item"):
            cat_el = item.find("category")
            if cat_el is None or not (cat_el.text or "").strip():
                continue
            rule_id = cat_el.text.strip().strip("'\"")
            values = [(v.text or "").strip() for v in item.findall("./values/value")]
            violations.setdefault(rule_id, []).extend(values)

    return n_categories, violations


def run_drc(gds_path, top_cell, report_path=None, timeout=300) -> dict:
    """Run one layout through the SKY130 deck and return a parsed result."""
    gds = Path(gds_path).resolve()
    if not gds.is_file():
        raise FileNotFoundError(f"GDS not found: {gds}")
    report = Path(report_path).resolve() if report_path else gds.with_suffix(".lyrdb")

    if report.exists():
        report.unlink()  # stale-report guard

    cmd = [
        find_klayout(), "-b", "-r", str(find_deck()),
        "-rd", f"input={gds}",
        "-rd", f"top_cell={top_cell}",
        "-rd", f"report={report}",
        "-rd", "feol=true",
        "-rd", "beol=true",
    ]

    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    elapsed = time.perf_counter() - start

    if proc.returncode != 0 or not report.is_file():
        raise RuntimeError(
            f"KLayout DRC failed for {gds.name} (exit code {proc.returncode}).\n"
            f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
        )

    n_categories, violations = parse_report(report)
    return {
        "gds": str(gds),
        "top_cell": top_cell,
        "report": str(report),
        "categories_checked": n_categories,
        "violations": violations,           # {rule_id: [values]}
        "violated_rules": sorted(violations),
        "passed_all": len(violations) == 0,
        "drc_seconds": round(elapsed, 2),
    }


def target_rules(case: dict):
    """(rule_id, predicted_pass) pairs this case is meant to test."""
    if case.get("case_type") == "competing_rules":
        return [
            (case["spacing_rule_id"], case["spacing_expected_pass"]),
            (case["width_rule_id"], case["width_expected_pass"]),
        ]
    return [(case["rule_id"], case["expected_pass"])]


def label_manifest(manifest_path, out_path):
    manifest_path = Path(manifest_path).resolve()
    base = manifest_path.parent
    with open(manifest_path) as f:
        cases = json.load(f)

    labeled, disagreements = [], []
    print(f"Labeling {len(cases)} cases with the KLayout SKY130 oracle...\n")
    print(f"{'file':34} {'target':7} {'predicted':9} {'oracle':7} {'agree':6} extra rules fired")
    print("-" * 95)

    for case in cases:
        gds = base / case["gds_path"]
        res = run_drc(gds, case["top_cell"])

        targets = target_rules(case)
        target_ids = {rid for rid, _ in targets}
        oracle_target_pass = {rid: (rid not in res["violations"]) for rid, _ in targets}
        agrees = all(oracle_target_pass[rid] == pred for rid, pred in targets)
        extra = sorted(set(res["violated_rules"]) - target_ids)

        out = dict(case)
        out.update({
            "oracle_target_pass": oracle_target_pass,
            "oracle_violated_rules": res["violated_rules"],
            "oracle_violation_values": res["violations"],
            "oracle_extra_rules_fired": extra,
            "prediction_matches_oracle": agrees,
            "drc_seconds": res["drc_seconds"],
        })
        labeled.append(out)
        if not agrees:
            disagreements.append(out)

        for rid, pred in targets:
            print(f"{Path(case['gds_path']).name:34} {rid:7} "
                  f"{'pass' if pred else 'FAIL':9} "
                  f"{'pass' if oracle_target_pass[rid] else 'FAIL':7} "
                  f"{'yes' if oracle_target_pass[rid] == pred else 'NO':6} "
                  f"{', '.join(extra) if extra else '-'}")

    with open(out_path, "w") as f:
        json.dump(labeled, f, indent=2)

    print(f"\nWrote {len(labeled)} labeled cases to {out_path}")
    print(f"Prediction matched oracle on {len(labeled) - len(disagreements)}/{len(labeled)} cases.")
    if disagreements:
        print("Disagreements are informative, not errors: the ORACLE is the label. "
              "Inspect each one (e.g., does a gap exactly equal to the threshold pass or fail?).")


def main():
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--single":
        res = run_drc(args[1], args[2])
        print(f"categories checked: {res['categories_checked']}")
        print(f"violated rules:     {res['violated_rules'] or 'none'}")
        for rid, vals in res["violations"].items():
            for v in vals:
                print(f"  {rid}: {v}")
        print(f"drc time:           {res['drc_seconds']}s")
    elif len(args) == 2:
        label_manifest(args[0], args[1])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
