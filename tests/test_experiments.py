import json

from drc_explain.experiments import baseline, condition_tools, model_input, run_grid


class Client:
    model = "fixture"
    is_live = False
    api_cost_usd = 0
    metadata = {}

    def __init__(self, action):
        self.action = action

    def respond(self, inputs, tools, instructions):
        self.inputs = inputs.copy()
        return {"status": "completed", "output": [{"type": "function_call", "call_id": "call1", "name": self.action[0], "arguments": json.dumps(self.action[1])}]}


def test_inputs_are_allowlisted():
    case = {"question": "width?", "layout": {"top_cell": "TOP"}, "case_id": "b001", "pair_id": "secret", "verdict": "FAIL", "case_type": "boundary"}
    assert set(model_input(case)) == {"question", "layout", "gds_path", "top_cell"}
    assert "secret" not in json.dumps(model_input(case))


def test_ablations_cannot_call_checker():
    assert [tool["name"] for tool in condition_tools("A")] == ["finalize_answer"]
    assert [tool["name"] for tool in condition_tools("B")] == ["retrieve_rules", "finalize_answer"]


def test_forbidden_action_is_error_and_saved(tmp_path):
    result = baseline({"question": "width?"}, "A", Client(("run_drc", {})), tmp_path)
    assert result["verdict"] == "ERROR"
    assert result["tool_call_count"] == 0
    assert (tmp_path / "trace.json").exists()


def test_baseline_refusal_is_not_engine_verified(tmp_path):
    client = Client(("finalize_answer", {"verdict": "REFUSE", "claims": [], "selections": [], "refusal_reason": "Antenna is unsupported."}))
    result = baseline({"question": "antenna?"}, "B", client, tmp_path)
    assert result["verdict"] == "REFUSE"
    assert not result["verification"]["accepted"]


def test_debug_disclosure_is_saved_not_sent_to_model(tmp_path):
    class LocalFixture(Client):
        def __init__(self, model):
            super().__init__(("finalize_answer", {"verdict": "REFUSE", "claims": [], "selections": [], "refusal_reason": "Fixture only."}))
            self.model = model

        def _check_model(self):
            pass

    run_grid(tmp_path, ["fixture"], ["A"], ["b001"], probes=False, client_factory=LocalFixture)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    demonstrations = manifest["windows_setup_demonstrations"]
    assert [(entry["case_id"], entry["verdict"]) for entry in demonstrations] == [("b001", "FAIL"), ("b002", "PASS")]
    assert {"b001", "b002", "b004", "b005", "b039", "o002"} == set(manifest["previous_live_acceptance_cases"])
    assert len(manifest["windows_setup_error_run_ids"]) == 4
    events = json.loads((tmp_path / "model0/A/1/b001/trace.json").read_text())
    supplied = json.loads(events[0]["input"][0]["content"])
    assert set(supplied) == {"question", "gds_path", "top_cell", "layout"}
    assert demonstrations[0]["run_id"] not in json.dumps(events[0])
    assert "windows_setup_demonstrations" not in json.dumps(events[0])