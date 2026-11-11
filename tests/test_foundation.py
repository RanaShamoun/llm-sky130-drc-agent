import json
from pathlib import Path

import pytest

from drc_explain.benchmark import designs, generate
from drc_explain.common import read_json
from drc_explain.layouts import inspect_layout
from drc_explain.reports import ReportError, marker_measurement, parse_report
from drc_explain.runner import Checker, CheckerError
from drc_explain.tools import Toolset, retrieve_rules


def test_original_marker_has_correct_units():
    m = marker_measurement("edge-pair: (0.505,0;0.505,0.5)/(0.5,0.5;0.5,0)")
    assert m["measured_um"] == 0.005
    assert (
        marker_measurement("edge-pair: (0,0;0,0.9)|(0.135,0.9;0.135,0)")["measured_um"]
        == 0.135
    )
    assert marker_measurement("polygon: (0,0;1,0;1,1)")["measured_um"] is None
    assert marker_measurement("edge-pair: (0,0;1,1)/(1,0;2,1)")["measured_um"] is None


@pytest.mark.parametrize(
    "xml",
    [
        "<report-database><categories/><items/></report-database>",
        "<report-database><categories><category><name>m1.1</name></category></categories></report-database>",
        "<report-database><categories><category><name>m1.1</name></category></categories><items><item><category>bogus</category></item></items></report-database>",
        "<wrong/>",
        "<report-database>",
    ],
)
def test_invalid_reports_cannot_pass(tmp_path, xml):
    path = tmp_path / "r.lyrdb"
    path.write_text(xml)
    with pytest.raises(ReportError):
        parse_report(path)


def test_benchmark_integrity_and_public_separation(tmp_path):
    generate(tmp_path)
    public = read_json(tmp_path / "public/cases.json")
    gold = read_json(tmp_path / "gold/designs.json")
    assert len(public) == len(gold) == 56
    for p, g in zip(public, gold):
        assert set(p) == {
            "case_id",
            "split",
            "question",
            "gds_path",
            "gds_sha256",
            "layout",
        }
        assert p["layout"]["shape_count"] >= 1
        assert all(
            poly["is_rectangle"]
            for layer in p["layout"]["layers"]
            for poly in layer["polygons"]
        )
        assert g["gds_sha256"] == p["gds_sha256"]
    pairs = {g["pair_id"] for g in gold if g["pair_id"]}
    assert len(pairs) == 6
    for pair in pairs:
        values = [g["expected_by_construction"] for g in gold if g["pair_id"] == pair]
        assert {next(iter(v.values())) for v in values} == {"PASS", "FAIL"}
    assert len({p["gds_sha256"] for p in public}) == 56
    generate(tmp_path)
    assert read_json(tmp_path / "public/cases.json") == public


def test_tool_path_boundary_and_no_gold_exposure(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (tmp_path / "secret.gds").write_text("secret")
    tools = Toolset(public, tmp_path / "calls.jsonl")
    for path in ["../secret.gds", str(tmp_path / "secret.gds"), "missing.gds"]:
        r = tools.call("inspect_layout", {"gds_path": path})
        assert not r["ok"] and r["verdict"] is None
    (public / "link.gds").symlink_to(tmp_path / "secret.gds")
    assert not tools.call("inspect_layout", {"gds_path": "link.gds"})["ok"]
    assert len((tmp_path / "calls.jsonl").read_text().splitlines()) == 4
    assert not tools.call("run_full", {})["ok"]


def test_filtering_returns_only_requested_results(tmp_path):
    generate(tmp_path)

    class FakeChecker(Checker):
        def run_full(self, *a, **kw):
            return {
                "violations": [
                    {"rule_id": "m1.2", "markers": []},
                    {"rule_id": "m2.1", "markers": []},
                ],
                "categories": {"m1.1": "width", "m1.2": "spacing"},
                "provenance": {},
                "gds_sha256": "abc",
            }

    c = FakeChecker()
    # b004 is m1 spacing with two rectangles. The unrelated m2 error must not leak.
    r = c.run_selected(tmp_path / "public/benchmark/b004.gds", ["m1.1"])
    assert r["status"] == "PASS"
    assert [v["rule_id"] for v in r["checks"]] == ["m1.1"]
    assert "m2" not in json.dumps(r)
    with pytest.raises(CheckerError):
        c.run_selected(tmp_path / "public/benchmark/b004.gds", ["m2.1"])
    with pytest.raises(CheckerError):
        c.run_selected(tmp_path / "public/benchmark/b004.gds", [])
    with pytest.raises(CheckerError):
        c.run_selected(tmp_path / "public/benchmark/b004.gds", ["made.up"])


def test_retrieval_is_cited_and_validated():
    r = retrieve_rules("metal1 spacing", 8)
    assert r["rules"][0]["rule_id"] == "m1.2"
    assert all(
        rule["source_url"].startswith("https://github.com/efabless/")
        for rule in r["rules"]
    )
    with pytest.raises(ValueError):
        retrieve_rules("", 2)


@pytest.mark.parametrize("failure", ["timeout", "exit", "missing_report"])
def test_checker_failures_never_return_a_verdict(tmp_path, monkeypatch, failure):
    import subprocess

    gds = tmp_path / "input.gds"
    gds.write_bytes(b"placeholder")
    c = Checker(timeout_s=0.01)
    monkeypatch.setattr(c, "provenance", lambda: {})

    def run(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args[0], 0.01)
        return subprocess.CompletedProcess(
            args[0],
            1 if failure == "exit" else 0,
            "",
            "failure" if failure == "exit" else "",
        )

    monkeypatch.setattr("drc_explain.runner.subprocess.run", run)
    with pytest.raises(CheckerError):
        c.run_full(gds)


def test_source_drift_is_rejected(tmp_path):
    c = Checker(source_dir=tmp_path)
    with pytest.raises(CheckerError, match="Pinned source absent or changed"):
        c.provenance()


def test_oracle_evidence_archive_preserves_bytes(tmp_path):
    import shutil

    from drc_explain.evidence import archive_reports, report_bytes

    gold = tmp_path / "gold"
    report = gold / "reports/b001/report.lyrdb"
    report.parent.mkdir(parents=True)
    report.write_bytes(b"<report-database>original evidence</report-database>")
    original = report.read_bytes()
    assert archive_reports(gold / "reports", gold / "oracle_reports.zip") == 1
    shutil.rmtree(gold / "reports")
    assert report_bytes(gold, "b001") == original
    with pytest.raises(ValueError):
        report_bytes(gold, "../b001")
