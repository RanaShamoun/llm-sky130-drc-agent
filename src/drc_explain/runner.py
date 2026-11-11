"""Run the unchanged upstream manufacturing deck; never use a custom oracle."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT, read_json, sha256, write_json
from .reports import ReportError, parse_report


class CheckerError(RuntimeError):
    pass


class Checker:
    def __init__(self, executable=None, source_dir=None, timeout_s=120):
        local = ROOT / ".tools/klayout.app/Contents/MacOS/klayout"
        self.executable = str(
            executable
            or os.environ.get("KLAYOUT_BIN")
            or (local if local.exists() else shutil.which("klayout") or "klayout")
        )
        self.source_dir = Path(
            source_dir
            or os.environ.get(
                "SKY130_KLAYOUT_SOURCE", ROOT / ".tools/sky130_klayout_pdk"
            )
        )
        self.timeout_s = timeout_s
        self.lock = read_json(ROOT / "data/sources.lock.json")
        self.deck = self.source_dir / "tech/sky130/drc/sky130A_mr.drc"

    def provenance(self):
        for file, expected in self.lock["files"].items():
            p = self.source_dir / file
            if not p.is_file() or sha256(p) != expected:
                raise CheckerError(
                    f"Pinned source absent or changed: {p}; follow docs/SETUP.md"
                )
        try:
            version = subprocess.run(
                [self.executable, "-b", "-v"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise CheckerError(f"Cannot run KLayout batch executable: {exc}") from exc
        if version != f"KLayout {self.lock['klayout_batch_version']}":
            raise CheckerError(
                f"Expected KLayout {self.lock['klayout_batch_version']}; found {version!r}"
            )
        return {
            "klayout_version": version,
            "source_revision": self.lock["revision"],
            "deck_sha256": sha256(self.deck),
            "layer_map_sha256": sha256(self.source_dir / "tech/sky130/sky130.lyp"),
        }

    def run_full(self, gds_path, top_cell="TOP", evidence_dir=None):
        """Evaluator-only full-deck result. Do not register this as an agent tool."""
        gds = Path(gds_path).resolve()
        if not gds.is_file():
            raise CheckerError(f"Missing GDS: {gds}")
        provenance = self.provenance()
        started = datetime.now(timezone.utc).isoformat()
        begin = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="drc-explain-") as temp:
            report = Path(temp) / "report.lyrdb"
            command = [
                self.executable,
                "-b",
                "-r",
                str(self.deck.resolve()),
                "-rd",
                f"input={gds}",
                "-rd",
                f"top_cell={top_cell}",
                "-rd",
                f"report={report}",
                "-rd",
                "feol=true",
                "-rd",
                "beol=true",
                "-rd",
                "seal=false",
                "-rd",
                "floating_met=false",
                "-rd",
                "offgrid=false",
                "-rd",
                "sram_exclude=false",
                "-rd",
                "thr=1",
            ]
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            try:
                proc = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    env=env,
                )
            except subprocess.TimeoutExpired as exc:
                raise CheckerError(
                    f"KLayout timed out after {self.timeout_s}s; no verdict."
                ) from exc
            except OSError as exc:
                raise CheckerError(f"KLayout failed to launch: {exc}") from exc
            if proc.returncode != 0 or "ERROR:" in proc.stderr:
                raise CheckerError(
                    f"KLayout failed ({proc.returncode}); no verdict.\n{proc.stderr[-2000:]}"
                )
            try:
                parsed = parse_report(report)
            except ReportError as exc:
                raise CheckerError(str(exc)) from exc
            # Categories alone do not prove both manufacturing rule groups ran.
            missing = {
                "m1.1",
                "m1.2",
                "m2.1",
                "m2.2",
                "via.4a",
                "via.5a",
                "m2.4",
                "m2.5",
            } - set(parsed["categories"])
            if missing:
                raise CheckerError(
                    f"Expected manufacturing checks absent: {sorted(missing)}"
                )
            result = dict(
                parsed,
                provenance=provenance,
                gds_sha256=sha256(gds),
                started_at=started,
                latency_s=round(time.perf_counter() - begin, 6),
                checked_category_count=len(parsed["categories"]),
            )
            if evidence_dir is not None:
                out = Path(evidence_dir)
                out.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(report, out / "report.lyrdb")
                (out / "stdout.log").write_text(proc.stdout)
                (out / "stderr.log").write_text(proc.stderr)
                write_json(out / "result.json", result)
            return result

    def run_selected(self, gds_path, rule_ids, top_cell="TOP"):
        """Full deck executes; only selected categories leave this boundary.

        This is result filtering, not faster selective execution. Oracle evidence
        is neither read from eval/gold nor returned to the agent.
        """
        from .layouts import inspect_layout

        catalog = {
            r["rule_id"]: r for r in read_json(ROOT / "data/rules.json")["rules"]
        }
        if (
            not isinstance(rule_ids, list)
            or not rule_ids
            or any(not isinstance(r, str) for r in rule_ids)
        ):
            raise CheckerError(
                "rule_ids must be a nonempty list of supported rule IDs."
            )
        if len(set(rule_ids)) != len(rule_ids):
            raise CheckerError("Duplicate requested rule IDs.")
        unknown = set(rule_ids) - set(catalog)
        if unknown:
            raise CheckerError(f"Unsupported rule IDs: {sorted(unknown)}")
        inspection = inspect_layout(gds_path, top_cell)
        by_name = {layer["name"]: layer for layer in inspection["layers"]}
        if set(by_name) - {"m1", "m2", "via", "li"}:
            raise CheckerError("Unrecognized layer outside the v1 input scope.")
        for layer in inspection["layers"]:
            for p in layer["polygons"]:
                if not p["is_rectangle"]:
                    raise CheckerError("V1 tool supports rectangular geometry only.")
                if any(
                    abs(v / 0.005 - round(v / 0.005)) > 1e-6
                    for xy in p["points_um"]
                    for v in xy
                ):
                    raise CheckerError("Off-grid geometry outside the v1 scope.")
                if (
                    layer["name"] in {"m1", "m2"}
                    and min(
                        p["bbox_um"][2] - p["bbox_um"][0],
                        p["bbox_um"][3] - p["bbox_um"][1],
                    )
                    >= 3
                ):
                    raise CheckerError("Wide-metal spacing variants are outside v1.")
                if layer["name"] == "via" and any(
                    abs(side - 0.15) > 1e-8
                    for side in [
                        p["bbox_um"][2] - p["bbox_um"][0],
                        p["bbox_um"][3] - p["bbox_um"][1],
                    ]
                ):
                    raise CheckerError("Only 0.15um square vias are supported in v1.")
        for id in rule_ids:
            if set(catalog[id]["layers"]) - set(by_name):
                raise CheckerError(
                    f"Required geometry absent for {id}; refusing vacuous PASS."
                )
        full = self.run_full(gds_path, top_cell)
        checks = []
        for id in rule_ids:
            violations = [v for v in full["violations"] if v["rule_id"] == id]
            checks.append(
                {
                    "rule_id": id,
                    "status": "FAIL" if violations else "PASS",
                    "limit_um": catalog[id]["limit_um"],
                    "description": full["categories"][id],
                    "violations": violations,
                    "measurement_note": "Report markers measure violations only. No violation does not imply a measured passing distance.",
                }
            )
        return {
            "status": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS",
            "scope": "Requested rules only; not tape-out approval.",
            "execution_mode": "full_deck_then_filter",
            "checks": checks,
            "units": "um",
            "provenance": full["provenance"],
            "gds_sha256": full["gds_sha256"],
        }
