import pytest

from drc_explain.ui import public_cases, run_request


def test_ui_only_lists_public_inputs():
    cases = public_cases()
    assert len(cases) == 62
    assert all("verdict" not in case and "pair_id" not in case for case in cases)


@pytest.mark.parametrize("payload", [{"case_id": "../../gold", "question": "check"}, {"case_id": "b001", "question": ""}, {"case_id": "b001", "question": "check", "gds_path": "secret.gds"}])
def test_ui_rejects_invalid_input(payload):
    with pytest.raises(ValueError):
        run_request(payload)


def test_ui_dispatches_existing_agent(tmp_path):
    class Fixture:
        def run(self, question, path, top):
            assert (question, path, top) == ("width?", "benchmark/b001.gds", "TOP")
            return {"verdict": "PASS", "result_path": str(tmp_path / "result.json")}
    result = run_request({"case_id": "b001", "question": "width?"}, Fixture)
    assert result["result"]["verdict"] == "PASS"
    assert result["tool_trace"] == []