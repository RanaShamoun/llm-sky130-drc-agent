import json

import pytest

from drc_explain.experiments import (
    baseline,
    condition_tools,
    main as experiments_main,
    model_input,
    run_grid,
    score_grid,
)


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


class OpenAIFixture(Client):
    provider_name = "openai"

    def __init__(self, model, timeout_s, budget):
        super().__init__(("finalize_answer", {
            "verdict": "REFUSE",
            "claims": [],
            "selections": [],
            "refusal_reason": "Fixture only.",
        }))
        self.model = model
        self.timeout_s = timeout_s
        self.budget = budget

    def _check_model(self):
        self.metadata = {"model": self.model, "budget_cap_usd": self.budget.cap_usd}


class GeminiFixture(Client):
    provider_name = "gemini"

    def __init__(self, model, timeout_s, budget):
        super().__init__(("finalize_answer", {
            "verdict": "REFUSE",
            "claims": [],
            "selections": [],
            "refusal_reason": "Fixture only.",
        }))
        self.model = model
        self.timeout_s = timeout_s
        self.budget = budget

    def _check_model(self):
        self.metadata = {
            "model": self.model,
            "budget_cap_usd": self.budget.cap_usd,
            "pricing_source": "fixture",
            "pricing_as_of": "fixture",
        }


class SequenceClient(Client):
    def __init__(self, responses):
        self.responses = responses
        self.turn = 0
        self.requests = []

    def respond(self, inputs, tools, instructions):
        self.requests.append((inputs.copy(), tools, instructions))
        response = self.responses[min(self.turn, len(self.responses) - 1)]
        self.turn += 1
        return response


def _function_call(name, arguments, call_id="call1"):
    return {
        "status": "completed",
        "output": [{
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments),
        }],
    }


def _refusal_call():
    return _function_call("finalize_answer", {
        "verdict": "REFUSE",
        "claims": [],
        "selections": [],
        "refusal_reason": "Fixture only.",
    })


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
        def __init__(self, model, timeout_s):
            super().__init__(("finalize_answer", {"verdict": "REFUSE", "claims": [], "selections": [], "refusal_reason": "Fixture only."}))
            self.model = model
            self.timeout_s = timeout_s

        def _check_model(self):
            pass

    run_grid(tmp_path, ["fixture"], ["A"], ["b001"], probes=False, client_factory=LocalFixture)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["inference_timeout_s"] == 1200
    demonstrations = manifest["windows_setup_demonstrations"]
    assert [(entry["case_id"], entry["verdict"]) for entry in demonstrations] == [("b001", "FAIL"), ("b002", "PASS")]
    assert {"b001", "b002", "b004", "b005", "b039", "o002"} == set(manifest["previous_live_acceptance_cases"])
    assert len(manifest["windows_setup_error_run_ids"]) == 4
    events = json.loads((tmp_path / "model0/A/1/b001/trace.json").read_text())
    supplied = json.loads(events[0]["input"][0]["content"])
    assert set(supplied) == {"question", "gds_path", "top_cell", "layout"}
    assert demonstrations[0]["run_id"] not in json.dumps(events[0])
    assert "windows_setup_demonstrations" not in json.dumps(events[0])


def test_openai_experiments_require_budget_before_creating_clients(tmp_path):
    with pytest.raises(ValueError, match="require --api-budget-usd"):
        run_grid(
            tmp_path,
            ["gpt-4o"],
            ["A"],
            ["b001"],
            probes=False,
            client_factory=OpenAIFixture,
        )


def test_openai_experiment_records_provider_and_budget(tmp_path):
    run_grid(
        tmp_path,
        ["gpt-4o"],
        ["A"],
        ["b001"],
        probes=False,
        client_factory=OpenAIFixture,
        api_budget_usd=1,
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    record = json.loads(
        (tmp_path / "model0/A/1/b001/record.json").read_text()
    )
    assert manifest["provider"] == "openai"
    assert manifest["api_budget_usd"] == 1
    assert manifest["api_budget_ledger"] == "api_budget.json"
    assert record["result"]["cost_usd"] == 0


def test_gemini_experiment_requires_budget_before_creating_clients(tmp_path):
    with pytest.raises(ValueError, match="Gemini experiment runs require --api-budget-usd"):
        run_grid(
            tmp_path,
            ["gemini-3.5-flash-lite"],
            ["A"],
            ["b001"],
            probes=False,
            client_factory=GeminiFixture,
        )


def test_gemini_experiment_records_provider_and_budget(tmp_path):
    run_grid(
        tmp_path,
        ["gemini-3.5-flash-lite"],
        ["A"],
        ["b001"],
        probes=False,
        client_factory=GeminiFixture,
        api_budget_usd=1,
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    record = json.loads(
        (tmp_path / "model0/A/1/b001/record.json").read_text()
    )
    assert manifest["provider"] == "gemini"
    assert manifest["api_budget_usd"] == 1
    assert manifest["api_budget_ledger"] == "gemini_budget.json"
    assert manifest["model_pins"]["gemini-3.5-flash-lite"]["budget_cap_usd"] == 1
    assert "gemini_provider.py" in manifest["implementation_sha256"]
    assert record["result"]["cost_usd"] == 0
    table = score_grid(tmp_path)[0]
    assert table["api_cost_usd"] == 0
    assert "Gemini API cost is estimated at Google's standard paid-tier" in (
        tmp_path / "results.md"
    ).read_text()


def test_gemini_experiment_cli_requires_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "experiments",
            "run",
            "--provider",
            "gemini",
            "--models",
            "gemini-3.5-flash-lite",
            "--conditions",
            "A",
            "--cases",
            "b001",
            "--no-probes",
            "--output",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit) as error:
        experiments_main()
    assert error.value.code == 2


def test_baseline_repairs_schema_without_correcting_prediction(tmp_path):
    draft = {"verdict": "PASS", "selections": [{"rule_id": "INVENTED", "justification": "prediction"}], "claims": [{"rule_id": "INVENTED", "status": "FAIL", "limit_um": 0.15, "measured_values_um": [0.135], "evidence_call_id": "none"}]}

    class RepairClient(Client):
        def __init__(self):
            self.turn = 0

        def respond(self, inputs, tools, instructions):
            self.turn += 1
            arguments = dict(draft)
            if self.turn == 2:
                feedback = json.loads(inputs[-1]["output"])
                assert "refusal_reason" in feedback["error"]["message"]
                assert "INVENTED" not in feedback["error"]["message"]
                assert "0.14" not in feedback["error"]["message"]
                arguments["refusal_reason"] = None
            return {"status": "completed", "output": [{"type": "function_call", "call_id": f"repair{self.turn}", "name": "finalize_answer", "arguments": json.dumps(arguments)}]}

    result = baseline({"question": "width?"}, "A", RepairClient(), tmp_path)
    assert result["verdict"] == "PASS"
    assert result["checks"] == draft["claims"]
    assert result["model_turn_count"] == 2
    assert result["tool_call_count"] == 0
    assert not result["verification"]["accepted"]
    events = json.loads((tmp_path / "trace.json").read_text())
    assert any(event["event"] == "rejected_call" for event in events)


def test_baseline_schema_repair_is_bounded(tmp_path):
    result = baseline({"question": "width?"}, "B", Client(("finalize_answer", {})), tmp_path, max_turns=2)
    assert result["verdict"] == "ERROR"
    assert result["model_turn_count"] == 2
    assert "budget exhausted" in result["error"]["message"]


def test_baseline_retries_missing_function_call_once(tmp_path):
    client = SequenceClient([
        {
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "unsupported JSON action"}],
            }],
        },
        _refusal_call(),
    ])
    result = baseline({"question": "unsupported?"}, "A", client, tmp_path)
    assert result["verdict"] == "REFUSE"
    assert result["protocol_repair_count"] == 1
    assert result["tool_call_count"] == 0
    repair = client.requests[1][0][-1]["content"]
    assert "finalize_answer" in repair
    assert "retrieve_rules" not in repair
    events = json.loads((tmp_path / "trace.json").read_text())
    assert [event["event"] for event in events].count("protocol_repair") == 1


def test_baseline_rejects_unregistered_tool_before_retry(tmp_path):
    client = SequenceClient([
        _function_call("calculate_distance", {"layer": "m1"}),
        _refusal_call(),
    ])
    result = baseline({"question": "spacing?"}, "B", client, tmp_path)
    assert result["verdict"] == "REFUSE"
    assert result["protocol_repair_count"] == 1
    assert result["tool_call_count"] == 0
    repair = client.requests[1][0][-1]["content"]
    assert "retrieve_rules, finalize_answer" in repair
    assert "No geometric tools are available." in repair
    events = json.loads((tmp_path / "trace.json").read_text())
    assert any(event["event"] == "rejected_call" for event in events)


def test_baseline_retries_invalid_retrieval_once(tmp_path):
    client = SequenceClient([
        _function_call("retrieve_rules", {"query": "metal1 width", "limit": 10}),
        _refusal_call(),
    ])
    result = baseline({"question": "width?"}, "B", client, tmp_path)
    assert result["verdict"] == "REFUSE"
    assert result["tool_call_count"] == 1
    assert result["protocol_repair_count"] == 1
    repair = client.requests[1][0][-1]["content"]
    assert "limit must be a JSON integer from 1 through 8" in repair


def test_baseline_protocol_repair_is_bounded(tmp_path):
    client = SequenceClient([{
        "status": "completed",
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "still not a function call"}],
        }],
    }])
    result = baseline({"question": "width?"}, "A", client, tmp_path, max_turns=4)
    assert result["verdict"] == "ERROR"
    assert result["protocol_repair_count"] == 1
    assert result["model_turn_count"] == 2
    assert "after the protocol-repair attempt" in result["error"]["message"]