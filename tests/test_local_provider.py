"""Local inference protocol and zero-API-spend routing checks."""

import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from drc_explain.agent import model_tools
from drc_explain.local_provider import DEFAULT_TIMEOUT_S, OllamaClient
from drc_explain.local_runtime import runtime_environment
from drc_explain.provider import ProviderError


@pytest.mark.parametrize(
    "model", ["qwen3:cloud", "gemma:cloud", "https://remote/model", "user/remote"]
)
def test_cloud_and_remote_models_are_rejected(model):
    with pytest.raises(ProviderError):
        OllamaClient(model=model)


def test_local_inference_timeout_is_recorded_and_distinguished(monkeypatch):
    class TimedOutOpener:
        def open(self, request, timeout):
            assert timeout == DEFAULT_TIMEOUT_S == 1200
            raise TimeoutError

    client = OllamaClient(model="qwen3:8b")
    client._opener = TimedOutOpener()
    with pytest.raises(ProviderError, match="request timed out after 1200 seconds"):
        client._request("/api/chat", {})


def test_wrapped_local_inference_timeout_is_not_reported_unavailable():
    class TimedOutOpener:
        def open(self, request, timeout):
            raise URLError(TimeoutError("timed out"))

    client = OllamaClient(model="qwen3:8b")
    client._opener = TimedOutOpener()
    with pytest.raises(ProviderError, match="request timed out after 1200 seconds"):
        client._request("/api/chat", {})


def test_unavailable_local_runtime_is_not_reported_as_timeout(monkeypatch):
    class UnavailableOpener:
        def open(self, request, timeout):
            raise URLError("connection refused")

    client = OllamaClient(model="qwen3:8b")
    client._opener = UnavailableOpener()
    with pytest.raises(ProviderError, match="Local Ollama is unavailable"):
        client._request("/api/chat", {})


def test_native_history_keeps_tool_names_and_arguments():
    messages = OllamaClient._messages(
        [
            {"role": "user", "content": "Check width."},
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "retrieve_rules",
                "arguments": '{"query":"width"}',
            },
            {"type": "function_call_output", "call_id": "c1", "output": '{"ok":true}'},
        ],
        "Instructions",
    )
    assert messages[0]["role"] == "system"
    assert messages[2]["tool_calls"][0]["function"]["arguments"] == {"query": "width"}
    assert messages[3] == {
        "role": "tool",
        "tool_name": "retrieve_rules",
        "content": '{"ok":true}',
    }
    with pytest.raises(ProviderError):
        OllamaClient._messages(
            [{"type": "function_call_output", "call_id": "unknown", "output": "{}"}], ""
        )


def test_local_protocol_is_real_inference_with_zero_api_cost(tmp_path, monkeypatch):
    monkeypatch.setattr("drc_explain.local_provider.ensure_server", lambda: None)
    monkeypatch.setattr("drc_explain.local_provider.ROOT", tmp_path)
    client = OllamaClient(model="qwen3:8b")
    requests = []

    def request(path, payload=None):
        requests.append((path, payload))
        if path == "/api/tags":
            return {
                "models": [
                    {
                        "name": "qwen3:8b",
                        "size": 5_000_000_000,
                        "digest": "sha256:fixture",
                    }
                ]
            }
        if path == "/api/version":
            return {"version": "test-version"}
        return {
            "done": True,
            "done_reason": "stop",
            "model": "qwen3:8b",
            "prompt_eval_count": 100,
            "eval_count": 20,
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "retrieve_rules",
                            "arguments": {"query": "metal1 spacing", "limit": "1"},
                        }
                    }
                ],
            },
        }

    monkeypatch.setattr(client, "_request", request)
    result = client.respond(
        [{"role": "user", "content": "Check geometry."}], model_tools(), "Instructions"
    )
    assert result["output"][0]["type"] == "function_call"
    assert json.loads(result["output"][0]["arguments"]) == {
        "query": "metal1 spacing",
        "limit": 1,
    }
    assert [entry["fields"] for entry in result["local_argument_normalizations"]] == [
        ["limit"]
    ]
    assert result["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert client.is_live and client.api_cost_usd == 0.0
    payload = requests[-1][1]
    assert payload["think"] is False and payload["stream"] is False
    assert payload["options"]["num_ctx"] == 32768
    assert payload["tools"][0]["function"]["name"] == "retrieve_rules"
    assert "Authorization" not in json.dumps(payload)


def test_absent_weights_do_not_trigger_cloud_fallback(monkeypatch):
    monkeypatch.setattr("drc_explain.local_provider.ensure_server", lambda: None)
    client = OllamaClient(model="qwen3:8b")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: {"models": []})
    with pytest.raises(ProviderError, match="cloud fallback is disabled"):
        client.respond([], model_tools(), "")


def test_model_digest_pin_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr("drc_explain.local_provider.ensure_server", lambda: None)
    monkeypatch.setattr("drc_explain.local_provider.ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/local_model.lock.json").write_text(
        json.dumps({"model": "qwen3:8b", "model_digest": "expected"})
    )
    client = OllamaClient(model="qwen3:8b")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *a, **kw: {
            "models": [{"name": "qwen3:8b", "size": 5_000_000_000, "digest": "changed"}]
        },
    )
    with pytest.raises(ProviderError, match="digest differs"):
        client.respond([], model_tools(), "")


def test_spawned_runtime_disables_cloud_and_omits_paid_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-only-cloud-key")
    env = runtime_environment()
    assert env["OLLAMA_NO_CLOUD"] == "1" and env["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert "OPENAI_API_KEY" not in env and "OLLAMA_API_KEY" not in env


def test_cli_defaults_to_local_even_when_openai_key_exists(monkeypatch):
    from drc_explain.cli import main

    monkeypatch.setattr(
        "sys.argv", ["drc-explain", "agent", "--gds", "benchmark/b004.gds"]
    )
    monkeypatch.delenv("DRC_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr("drc_explain.provider.load_local_config", lambda: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("Default must not construct the paid client.")

    monkeypatch.setattr("drc_explain.provider.OpenAIResponses", forbidden)
    monkeypatch.setattr(
        "drc_explain.local_provider.OllamaClient",
        lambda **kwargs: SimpleNamespace(model="local"),
    )

    class FakeAgent:
        def __init__(self, client, **kwargs):
            assert client.model == "local"

        def run(self, *args):
            return {
                "verdict": "PASS",
                "explanation": "Routing fixture only.",
                "model": "local",
                "verification": {"accepted": True},
                "result_path": "fixture",
                "checks": [],
            }

    monkeypatch.setattr("drc_explain.agent.Agent", FakeAgent)
    assert main() == 0


@pytest.mark.parametrize("argument_field", ["arguments", "parameters"])
def test_json_action_uses_the_same_verified_tool_path(
    tmp_path, monkeypatch, argument_field
):
    client = OllamaClient(model="qwen3:8b")
    client.metadata = {"runtime": "test"}
    arguments = {
        "verdict": "REFUSE",
        "selections": [],
        "claims": [],
        "refusal_reason": "Unsupported scope.",
    }
    action = {
        "name": "finalize_answer",
        argument_field: arguments,
    }
    monkeypatch.setattr(
        client,
        "_request",
        lambda *a, **kw: {
            "done": True,
            "done_reason": "stop",
            "message": {"content": json.dumps(action)},
        },
    )
    result = client.respond([], model_tools(), "Instructions")
    assert result["local_action_format"] == "json_action"
    assert result["output"][0]["name"] == "finalize_answer"
    assert json.loads(result["output"][0]["arguments"]) == arguments
    assert result["local_assistant_content"] == json.dumps(action)
    action["name"] = "run_shell"
    result = client.respond([], model_tools(), "Instructions")
    assert result["output"][0]["type"] == "message"


@pytest.mark.parametrize("limit", ["0", "9", "10", "one", 0, 9])
def test_invalid_retrieval_limit_is_not_normalized(limit):
    arguments = {"query": "metal1 spacing", "limit": limit}
    normalized, fields = OllamaClient._normalize_arguments(
        "retrieve_rules", arguments
    )
    assert normalized == arguments
    assert fields == []


def test_stringified_final_arrays_are_unwrapped_as_strict_json(monkeypatch):
    client = OllamaClient(model="llama3.1:8b")
    client.metadata = {"runtime": "test"}
    arguments = {
        "verdict": "PASS",
        "selections": json.dumps(
            [{"rule_id": "m1.1", "justification": "Requested metal1 width."}]
        ),
        "claims": json.dumps(
            [
                {
                    "rule_id": "m1.1",
                    "status": "PASS",
                    "limit_um": 0.14,
                    "measured_values_um": [],
                    "evidence_call_id": "local-drc-call",
                }
            ]
        ),
        "refusal_reason": "null",
    }
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {
            "done": True,
            "done_reason": "stop",
            "message": {
                "tool_calls": [
                    {"function": {"name": "finalize_answer", "arguments": arguments}}
                ]
            },
        },
    )

    result = client.respond([], model_tools(), "Instructions")
    output = result["output"][0]
    normalized = json.loads(output["arguments"])
    assert isinstance(normalized["selections"], list)
    assert isinstance(normalized["claims"], list)
    assert normalized["refusal_reason"] is None
    assert result["local_argument_normalizations"] == [
        {
            "call_id": output["call_id"],
            "fields": ["selections", "claims", "refusal_reason"],
        }
    ]


def test_python_style_final_arguments_are_not_interpreted():
    arguments = {
        "selections": "[{'rule_id': 'm1.1'}]",
        "claims": "[]",
        "refusal_reason": "",
    }

    normalized, fields = OllamaClient._normalize_arguments(
        "finalize_answer", arguments
    )

    assert normalized["selections"] == arguments["selections"]
    assert normalized["claims"] == []
    assert normalized["refusal_reason"] == ""
    assert fields == ["claims"]
