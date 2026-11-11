"""Agent tests use explicit model doubles, never claim real LLM accuracy."""

import copy
import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from drc_explain.agent import Agent, model_tools
from drc_explain.provider import OpenAIResponses, ProviderError, load_local_config
from drc_explain.tools import Toolset
from drc_explain.verification import VerificationError, verify_answer

HASH = "layout-hash"
CHECKS = [
    {"rule_id": "m1.1", "status": "PASS", "limit_um": 0.14, "violations": []},
    {
        "rule_id": "m1.2",
        "status": "FAIL",
        "limit_um": 0.14,
        "violations": [
            {
                "rule_id": "m1.2",
                "cell": "TOP",
                "markers": [{"measured_um": 0.135, "raw": "fixture"}],
            }
        ],
    },
]


def evidence():
    return {
        "lookup": {
            "tool": "retrieve_rules",
            "response": {
                "ok": True,
                "result": {"rules": [{"rule_id": "m1.1"}, {"rule_id": "m1.2"}]},
            },
        },
        "drc": {
            "tool": "run_drc",
            "response": {
                "ok": True,
                "result": {"gds_sha256": HASH, "checks": copy.deepcopy(CHECKS)},
            },
        },
    }


def answer():
    return {
        "verdict": "FAIL",
        "selections": [
            {"rule_id": r, "justification": "Question asks width and spacing."}
            for r in ["m1.1", "m1.2"]
        ],
        "claims": [
            {
                "rule_id": c["rule_id"],
                "status": c["status"],
                "limit_um": 0.14,
                "measured_values_um": [] if c["status"] == "PASS" else [0.135],
                "evidence_call_id": "drc",
            }
            for c in CHECKS
        ],
        "refusal_reason": None,
    }


def test_verified_result_contains_only_supported_facts():
    result = verify_answer(answer(), evidence(), HASH)
    assert result["verdict"] == "FAIL"
    assert "0.135 um" in result["explanation"]
    assert "no passing distance was measured" in result["explanation"]
    assert all(
        c["source_url"].startswith("https://github.com/") for c in result["checks"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "verdict",
        "limit",
        "measurement",
        "passing_measurement",
        "citation",
        "omit_failure",
        "duplicate",
        "wrong_call",
        "wrong_hash",
        "not_retrieved",
        "nan",
        "bool",
    ],
)
def test_fabricated_or_incomplete_claims_are_rejected(mutation):
    proposal = answer()
    tools = evidence()
    hash = HASH
    if mutation == "verdict":
        proposal["verdict"] = "PASS"
    elif mutation == "limit":
        proposal["claims"][1]["limit_um"] = 0.15
    elif mutation == "measurement":
        proposal["claims"][1]["measured_values_um"] = [0.14]
    elif mutation == "passing_measurement":
        proposal["claims"][0]["measured_values_um"] = [0.14]
    elif mutation == "citation":
        proposal["selections"][0]["rule_id"] = "m1.999"
    elif mutation == "omit_failure":
        proposal["selections"] = proposal["selections"][:1]
        proposal["claims"] = proposal["claims"][:1]
        proposal["verdict"] = "PASS"
    elif mutation == "duplicate":
        proposal["claims"].append(copy.deepcopy(proposal["claims"][0]))
    elif mutation == "wrong_call":
        proposal["claims"][0]["evidence_call_id"] = "lookup"
    elif mutation == "wrong_hash":
        hash = "another-layout"
    elif mutation == "not_retrieved":
        tools.pop("lookup")
    elif mutation == "nan":
        proposal["claims"][1]["measured_values_um"] = [float("nan")]
    elif mutation == "bool":
        proposal["claims"][0]["limit_um"] = True
    with pytest.raises(VerificationError):
        verify_answer(proposal, tools, hash)


def test_refusal_is_distinct_from_geometric_verdict():
    proposal = {
        "verdict": "REFUSE",
        "selections": [],
        "claims": [],
        "refusal_reason": "Density is outside the supported scope.",
    }
    result = verify_answer(proposal, {})
    assert result["verdict"] == "REFUSE"
    assert "scored separately" in result["verification_scope"]
    proposal["claims"] = answer()["claims"]
    with pytest.raises(VerificationError):
        verify_answer(proposal, {})


def call(name, arguments, id):
    return {
        "type": "function_call",
        "name": name,
        "arguments": json.dumps(arguments),
        "call_id": id,
        "id": "fc_" + id,
        "status": "completed",
    }


class SequenceClient:
    model = "test-fixture-not-an-llm"
    is_live = False

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.inputs = []

    def respond(self, inputs, tools, instructions):
        self.inputs.append(copy.deepcopy(inputs))
        return {
            "id": f"response_{len(self.inputs)}",
            "model": self.model,
            "status": "completed",
            "output": [next(self.outputs)],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "input_tokens_details": {"cached_tokens": 2},
            },
        }


class FakeChecker:
    def run_selected(self, gds_path, rule_ids, top_cell="TOP"):
        from drc_explain.common import sha256

        return {"checks": copy.deepcopy(CHECKS), "gds_sha256": sha256(gds_path)}


def factory(**kwargs):
    return Toolset(checker=FakeChecker(), **kwargs)


def good_sequence(final=None):
    return [
        call("retrieve_rules", {"query": "metal1 width spacing", "limit": 8}, "lookup"),
        call(
            "run_drc",
            {"gds_path": "benchmark/b004.gds", "rule_ids": ["m1.1", "m1.2"]},
            "drc",
        ),
        call("finalize_answer", final or answer(), "final"),
    ]


def test_agent_full_flow_saves_logs_and_never_reads_gold(tmp_path):
    client = SequenceClient(good_sequence())
    result = Agent(client, tmp_path, toolset_factory=factory).run(
        "Check metal1 width and spacing.", "benchmark/b004.gds"
    )
    assert result["verdict"] == "FAIL" and result["verification"]["accepted"]
    assert not result["live_model"]
    assert result["tool_call_count"] == 3 and result["model_turn_count"] == 3
    assert result["usage"] == {
        "input_tokens": 30,
        "output_tokens": 15,
        "cached_input_tokens": 6,
    }
    assert (tmp_path / result["run_id"] / "result.json").exists()
    assert (tmp_path / result["run_id"] / "trace.jsonl").exists()
    assert "full_deck_verdict" not in json.dumps(client.inputs)
    assert "eval/gold" not in json.dumps(client.inputs)
    returned = next(
        item
        for item in client.inputs[-1]
        if item.get("type") == "function_call_output" and item["call_id"] == "drc"
    )
    assert json.loads(returned["output"])["evidence_call_id"] == "drc"


def test_agent_can_correct_rejected_final_claim(tmp_path):
    bad = answer()
    bad["claims"][1]["measured_values_um"] = [0.14]
    client = SequenceClient(
        good_sequence(bad) + [call("finalize_answer", answer(), "corrected")]
    )
    result = Agent(client, tmp_path, toolset_factory=factory).run(
        "Check width and spacing.", "benchmark/b004.gds"
    )
    assert result["verdict"] == "FAIL" and result["model_turn_count"] == 4
    assert any(
        item.get("type") == "function_call_output"
        and "do not exactly match" in item["output"]
        for item in client.inputs[-1]
    )


def test_agent_cannot_check_another_layout(tmp_path):
    calls = good_sequence()
    calls[1] = call(
        "run_drc",
        {"gds_path": "benchmark/b005.gds", "rule_ids": ["m1.1", "m1.2"]},
        "drc",
    )
    result = Agent(
        SequenceClient(calls), tmp_path, toolset_factory=factory, max_turns=3
    ).run("Check spacing.", "benchmark/b004.gds")
    assert result["verdict"] == "ERROR" and not result["verification"]["accepted"]


def test_agent_stops_on_tool_failure(tmp_path):
    class BrokenChecker:
        def run_selected(self, *args, **kwargs):
            raise RuntimeError("Checker failed.")

    def broken_factory(**kwargs):
        return Toolset(checker=BrokenChecker(), **kwargs)

    result = Agent(
        SequenceClient(good_sequence()), tmp_path, toolset_factory=broken_factory
    ).run("Check spacing.", "benchmark/b004.gds")
    assert result["verdict"] == "ERROR" and result["model_turn_count"] == 2
    assert "Tool execution failed" in result["explanation"]


def test_refusal_needs_no_layout_or_engine(tmp_path):
    refusal = {
        "verdict": "REFUSE",
        "selections": [],
        "claims": [],
        "refusal_reason": "Antenna is unsupported.",
    }
    result = Agent(
        SequenceClient([call("finalize_answer", refusal, "done")]), tmp_path
    ).run("Check antenna rules.")
    assert result["verdict"] == "REFUSE" and result["tool_call_count"] == 0


def test_invalid_model_output_has_no_verdict(tmp_path):
    client = SequenceClient([{"type": "message", "content": []}])
    result = Agent(client, tmp_path).run("Check spacing.")
    assert result["verdict"] == "ERROR"


def test_model_budget_is_enforced(tmp_path):
    client = SequenceClient([call("retrieve_rules", {"query": "metal1"}, "lookup")])
    result = Agent(client, tmp_path, max_turns=1).run("Check spacing.")
    assert result["verdict"] == "ERROR" and "budget exhausted" in result["explanation"]


def test_openai_request_uses_responses_protocol(monkeypatch):
    captured = {}

    def open_request(request, timeout, context):
        assert context.check_hostname
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return BytesIO(
            json.dumps(
                {
                    "id": "resp_1",
                    "model": "test-model",
                    "status": "completed",
                    "output": [],
                }
            ).encode()
        )

    monkeypatch.setattr("drc_explain.provider.urlopen", open_request)
    client = OpenAIResponses(model="test-model", api_key="test-only-secret")
    client.respond(
        [{"role": "user", "content": "Question"}], model_tools(), "Instructions"
    )
    payload = captured["payload"]
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert payload["store"] is False and payload["parallel_tool_calls"] is False
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert "test-only-secret" not in json.dumps(payload)
    assert payload["tools"][-1]["strict"] is True


def test_api_errors_do_not_expose_keys(monkeypatch):
    def fail(*a, **kw):
        raise HTTPError(
            "https://api.openai.com",
            401,
            "echo test-only-secret",
            {},
            BytesIO(b"test-only-secret"),
        )

    monkeypatch.setattr("drc_explain.provider.urlopen", fail)
    with pytest.raises(ProviderError) as error:
        OpenAIResponses(model="test", api_key="test-only-secret").respond([], [], "")
    assert "test-only-secret" not in str(error.value)


def test_dotenv_only_loads_allowed_names_without_execution(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "existing")
    path = tmp_path / ".env"
    path.write_text(
        'OPENAI_MODEL="test-model"\nOPENAI_API_KEY=replacement\nUNRELATED=bad\n'
    )
    load_local_config(path)
    import os

    assert (
        os.environ["OPENAI_MODEL"] == "test-model"
        and os.environ["OPENAI_API_KEY"] == "existing"
    )
    assert "UNRELATED" not in os.environ


def test_hidden_key_configuration_preserves_other_settings(
    tmp_path, monkeypatch, capsys
):
    from drc_explain.provider import configure_api

    monkeypatch.setattr("drc_explain.provider.ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "# local settings\nOTHER_SETTING=keep\nOPENAI_MODEL=test-model\nOPENAI_API_KEY=old\n"
    )
    monkeypatch.setattr(
        "drc_explain.provider.getpass.getpass", lambda _: "sk-test-not-a-real-key"
    )
    configure_api()
    contents = path.read_text()
    assert "OTHER_SETTING=keep" in contents and "OPENAI_MODEL=test-model" in contents
    assert contents.count("OPENAI_API_KEY=") == 1
    assert "sk-test-not-a-real-key" not in capsys.readouterr().out
    assert path.stat().st_mode & 0o777 == 0o600


def test_invalid_key_entry_does_not_replace_existing_file(tmp_path, monkeypatch):
    from drc_explain.provider import configure_api

    monkeypatch.setattr("drc_explain.provider.ROOT", tmp_path)
    path = tmp_path / ".env"
    path.write_text("OTHER_SETTING=keep\n")
    monkeypatch.setattr(
        "drc_explain.provider.getpass.getpass", lambda _: "not-an-api-key"
    )
    with pytest.raises(ProviderError):
        configure_api()
    assert path.read_text() == "OTHER_SETTING=keep\n"


def test_layout_change_before_final_answer_is_rejected(tmp_path):
    import shutil
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    public = tmp_path / "public"
    (public / "benchmark").mkdir(parents=True)
    gds = public / "benchmark/b004.gds"
    shutil.copyfile(root / "eval/public/benchmark/b004.gds", gds)

    class ChangingClient(SequenceClient):
        def respond(self, *args, **kwargs):
            if len(self.inputs) == 2:
                gds.write_bytes(gds.read_bytes() + b"changed")
            return super().respond(*args, **kwargs)

    def isolated_factory(**kwargs):
        return Toolset(layout_root=public, checker=FakeChecker(), **kwargs)

    result = Agent(
        ChangingClient(good_sequence()),
        tmp_path / "runs",
        toolset_factory=isolated_factory,
        max_turns=3,
    ).run("Check width and spacing.", "benchmark/b004.gds")
    assert result["verdict"] == "ERROR" and not result["verification"]["accepted"]


def test_quota_error_is_distinguished_without_echoing_error_body(monkeypatch):
    def fail(*args, **kwargs):
        body = json.dumps(
            {
                "error": {
                    "code": "insufficient_quota",
                    "message": "secret echoed here test-only-secret",
                }
            }
        ).encode()
        raise HTTPError("https://api.openai.com", 429, "Quota error", {}, BytesIO(body))

    monkeypatch.setattr("drc_explain.provider.urlopen", fail)
    with pytest.raises(ProviderError) as error:
        OpenAIResponses(model="test", api_key="test-only-secret").respond([], [], "")
    assert "insufficient_quota" in str(error.value)
    assert "test-only-secret" not in str(error.value)


def test_prose_refusal_must_be_resubmitted_as_a_structured_answer(tmp_path):
    draft = {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Antenna is unsupported."}],
    }
    refusal = {
        "verdict": "REFUSE",
        "selections": [],
        "claims": [],
        "refusal_reason": "Antenna checks are outside scope.",
    }
    client = SequenceClient([draft, call("finalize_answer", refusal, "refusal")])
    result = Agent(client, tmp_path).run("Check antenna rules.")
    assert result["verdict"] == "REFUSE" and result["model_turn_count"] == 2
    assert result["verification"]["accepted"] and result["tool_call_count"] == 0
    assert "No answer has been accepted" in client.inputs[-1][-1]["content"]
