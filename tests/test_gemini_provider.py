import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from drc_explain.agent import model_tools
from drc_explain.gemini_provider import (
    GeminiBudget,
    GeminiClient,
    _schema,
    gemini_cost_usd,
)
from drc_explain.provider import ProviderError


@pytest.fixture(autouse=True)
def disable_request_pacing_in_tests(monkeypatch):
    monkeypatch.setattr(
        "drc_explain.gemini_provider.DEFAULT_MIN_REQUEST_INTERVAL_S",
        0.0,
    )


def test_gemini_requires_local_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(
        "drc_explain.gemini_provider.load_local_config",
        lambda path=None: None,
    )
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_gemini_request_and_function_call(monkeypatch):
    captured = {}

    def open_request(request, timeout, context):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data)
        return BytesIO(json.dumps({
            "responseId": "gemini-response-1",
            "modelVersion": "gemini-3.5-flash-lite",
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "retrieve_rules",
                            "args": {"query": "metal1 width", "limit": 2},
                        },
                        "thoughtSignature": "opaque-thought-signature",
                    }]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 31,
                "candidatesTokenCount": 7,
                "thoughtsTokenCount": 2,
                "cachedContentTokenCount": 3,
            },
        }).encode())

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", open_request)
    client = GeminiClient(model="gemini-3.5-flash-lite", api_key="test-secret")
    response = client.respond(
        [{"role": "user", "content": "Check metal1 width"}],
        model_tools(),
        "Instructions",
    )

    assert captured["url"].endswith(
        "/models/gemini-3.5-flash-lite:generateContent"
    )
    assert "test-secret" not in json.dumps(captured["payload"])
    assert captured["payload"]["tools"][0]["functionDeclarations"]
    assert captured["payload"]["generationConfig"]["maxOutputTokens"] == 4096
    assert response["status"] == "completed"
    assert response["model_version"] == "gemini-3.5-flash-lite"
    assert response["usage"]["input_tokens"] == 31
    assert response["usage"]["output_tokens"] == 9
    call = response["output"][0]
    assert call["type"] == "function_call"
    assert call["name"] == "retrieve_rules"
    assert json.loads(call["arguments"]) == {"query": "metal1 width", "limit": 2}
    assert call["thought_signature"] == "opaque-thought-signature"
    continuation = GeminiClient._contents([
        call,
        {
            "type": "function_call_output",
            "call_id": call["call_id"],
            "output": json.dumps({"ok": True}),
        },
    ])
    assert continuation[0]["parts"][0]["thoughtSignature"] == (
        "opaque-thought-signature"
    )
    assert client.api_cost_usd == pytest.approx(0.00003099)


def test_gemini_cost_includes_cached_input_and_thought_tokens():
    usage = {
        "input_tokens": 100,
        "output_tokens": 25,
        "input_tokens_details": {"cached_tokens": 10},
    }
    assert gemini_cost_usd("gemini-2.5-flash", usage) == pytest.approx(0.0000898)
    assert gemini_cost_usd(
        "gemini-3.5-flash-lite", usage
    ) == pytest.approx(0.0000898)
    assert gemini_cost_usd("gemini-2.5-flash", {"input_tokens": 1}) is None


def test_gemini_defaults_to_priced_flash_lite_model(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(
        "drc_explain.gemini_provider.load_local_config",
        lambda path=None: None,
    )
    client = GeminiClient(
        api_key="test-secret",
        budget=GeminiBudget(1, tmp_path / "gemini_budget.json"),
        min_request_interval_s=6.1,
    )
    client._check_model()

    assert client.model == "gemini-3.5-flash-lite"
    assert client.metadata["pricing_source"].endswith("#gemini-3.5-flash-lite")
    assert client.metadata["minimum_request_interval_s"] == 6.1
    assert client.metadata["max_429_retries"] == 5


def test_gemini_schema_preserves_nested_enums_and_nullable_types():
    converted = _schema({
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["PASS", "FAIL", "REFUSE"],
            },
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["PASS", "FAIL"],
                        }
                    },
                },
            },
            "refusal_reason": {"type": ["string", "null"]},
        },
    })

    properties = converted["properties"]
    assert properties["verdict"] == {
        "type": "STRING",
        "enum": ["PASS", "FAIL", "REFUSE"],
    }
    assert properties["claims"]["items"]["properties"]["status"] == {
        "type": "STRING",
        "enum": ["PASS", "FAIL"],
    }
    assert properties["refusal_reason"] == {
        "type": "STRING",
        "nullable": True,
    }


def test_gemini_budget_reserves_then_settles_reported_usage(tmp_path, monkeypatch):
    captured = {}

    def open_request(request, timeout, context):
        captured["payload"] = json.loads(request.data)
        return BytesIO(json.dumps({
            "responseId": "gemini-budget-response",
            "modelVersion": "gemini-2.5-flash-001",
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "finalize_answer",
                            "args": {
                                "verdict": "REFUSE",
                                "claims": [],
                                "selections": [],
                                "refusal_reason": "Fixture only.",
                            },
                        }
                    }]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 100,
                "cachedContentTokenCount": 10,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 5,
            },
        }).encode())

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", open_request)
    budget = GeminiBudget(0.10, tmp_path / "gemini_budget.json")
    client = GeminiClient(
        model="gemini-2.5-flash",
        api_key="test-secret",
        max_output_tokens=100,
        budget=budget,
    )
    client._check_model()
    client.respond([], model_tools(), "Instructions")

    assert captured["payload"]["generationConfig"]["maxOutputTokens"] == 100
    assert client.api_cost_usd == pytest.approx(0.0000898)
    assert budget.spent_usd == pytest.approx(0.0000898)
    assert budget.pending_usd == 0
    ledger = json.loads((tmp_path / "gemini_budget.json").read_text())
    assert ledger["provider"] == "Gemini"
    assert ledger["pricing_as_of"] == "2026-11-21"
    resumed = GeminiBudget(0.10, tmp_path / "gemini_budget.json")
    assert resumed.spent_usd == pytest.approx(0.0000898)
    assert resumed.pending_usd == 0


def test_gemini_budget_blocks_request_before_network_call(tmp_path, monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("budget should block before network access")

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", unexpected_request)
    budget = GeminiBudget(0.000001, tmp_path / "gemini_budget.json")
    client = GeminiClient(
        model="gemini-2.5-flash",
        api_key="test-secret",
        max_output_tokens=10,
        budget=budget,
    )
    with pytest.raises(ProviderError, match="blocked before sending"):
        client.respond([], model_tools(), "Instructions")


def test_gemini_budget_requires_pricing_for_the_selected_model(tmp_path):
    client = GeminiClient(
        model="gemini-3.8-flash",
        api_key="test-secret",
        budget=GeminiBudget(1, tmp_path / "gemini_budget.json"),
    )
    with pytest.raises(ProviderError, match="No budget pricing"):
        client._check_model()


def test_gemini_errors_do_not_echo_api_key(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError(
            "https://generativelanguage.googleapis.com",
            403,
            "test-secret",
            {},
            BytesIO(b"test-secret"),
        )

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", fail)
    client = GeminiClient(model="gemini-2.5-flash", api_key="test-secret")
    with pytest.raises(ProviderError) as error:
        client.respond([], model_tools(), "Instructions")
    assert "test-secret" not in str(error.value)


def test_gemini_bad_request_exposes_sanitized_validation_detail(monkeypatch):
    def fail(*args, **kwargs):
        body = json.dumps({
            "error": {
                "code": 400,
                "message": "Invalid schema; test-secret must not be echoed.",
            }
        }).encode()
        raise HTTPError(
            "https://generativelanguage.googleapis.com",
            400,
            "Bad Request",
            {},
            BytesIO(body),
        )

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", fail)
    client = GeminiClient(model="gemini-2.5-flash", api_key="test-secret")
    with pytest.raises(ProviderError) as error:
        client.respond([], model_tools(), "Instructions")
    assert "Invalid schema" in str(error.value)
    assert "[redacted]" in str(error.value)
    assert "test-secret" not in str(error.value)


def test_gemini_not_found_exposes_model_detail(monkeypatch):
    def fail(*args, **kwargs):
        body = json.dumps({
            "error": {
                "code": 404,
                "message": "models/gemini-2.5-flash is not available.",
            }
        }).encode()
        raise HTTPError(
            "https://generativelanguage.googleapis.com",
            404,
            "Not Found",
            {},
            BytesIO(body),
        )

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", fail)
    client = GeminiClient(model="gemini-2.5-flash", api_key="test-secret")
    with pytest.raises(ProviderError) as error:
        client.respond([], model_tools(), "Instructions")
    assert "Gemini HTTP 404" in str(error.value)
    assert "gemini-2.5-flash is not available" in str(error.value)


def test_gemini_retries_503_and_records_wait(monkeypatch):
    attempts = []
    sleeps = []

    def open_request(request, timeout, context):
        attempts.append(request)
        if len(attempts) == 1:
            raise HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                {"Retry-After": "2"},
                BytesIO(b'{"error":{"message":"Service temporarily unavailable."}}'),
            )
        return BytesIO(json.dumps({
            "responseId": "retry-response",
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "finalize_answer",
                            "args": {"verdict": "REFUSE"},
                        }
                    }]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
            },
        }).encode())

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", open_request)
    monkeypatch.setattr("drc_explain.gemini_provider.time.sleep", sleeps.append)
    client = GeminiClient(model="gemini-3.5-flash-lite", api_key="test-secret")

    response = client.respond([], model_tools(), "Instructions")

    assert len(attempts) == 2
    assert response["status"] == "completed"
    assert client.metadata["request_attempt_count"] == 2
    assert client.metadata["service_unavailable_retry_count"] == 1
    assert client.metadata["service_unavailable_retry_wait_s"] == 2
    assert sleeps == [2]


def test_gemini_exhausted_503_releases_budget_reservation(monkeypatch, tmp_path):
    sleeps = []

    def fail(request, timeout, context):
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            {},
            BytesIO(b'{"error":{"message":"Model overloaded."}}'),
        )

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", fail)
    monkeypatch.setattr("drc_explain.gemini_provider.time.sleep", sleeps.append)
    budget = GeminiBudget(0.10, tmp_path / "gemini_budget.json")
    client = GeminiClient(
        model="gemini-3.5-flash-lite",
        api_key="test-secret",
        budget=budget,
        max_service_retries=1,
    )

    with pytest.raises(ProviderError, match="HTTP 503 after 2 attempts"):
        client.respond([], model_tools(), "Instructions")

    assert budget.pending_usd == 0
    assert client.metadata["request_attempt_count"] == 2
    assert client.metadata["service_unavailable_retry_count"] == 1
    assert sleeps == [5]
    ledger = json.loads((tmp_path / "gemini_budget.json").read_text())
    assert ledger["reservations_usd"] == {}


def test_gemini_retries_429_and_records_wait(monkeypatch):
    attempts = []
    sleeps = []

    def open_request(request, timeout, context):
        attempts.append(request)
        if len(attempts) == 1:
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "2"},
                BytesIO(b'{"error":{"message":"Rate limited."}}'),
            )
        return BytesIO(json.dumps({
            "responseId": "retry-response",
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "finalize_answer",
                            "args": {"verdict": "REFUSE"},
                        }
                    }]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
            },
        }).encode())

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", open_request)
    monkeypatch.setattr("drc_explain.gemini_provider.time.sleep", sleeps.append)
    client = GeminiClient(model="gemini-3.5-flash-lite", api_key="test-secret")

    response = client.respond([], model_tools(), "Instructions")

    assert len(attempts) == 2
    assert response["status"] == "completed"
    assert client.metadata["request_attempt_count"] == 2
    assert client.metadata["rate_limit_retry_count"] == 1
    assert client.metadata["rate_limit_retry_wait_s"] == 2
    assert sleeps == [2]


def test_gemini_exhausted_429_releases_budget_reservation(monkeypatch, tmp_path):
    sleeps = []

    def fail(request, timeout, context):
        raise HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {},
            BytesIO(b'{"error":{"message":"Rate limited."}}'),
        )

    monkeypatch.setattr("drc_explain.gemini_provider.urlopen", fail)
    monkeypatch.setattr("drc_explain.gemini_provider.time.sleep", sleeps.append)
    budget = GeminiBudget(0.10, tmp_path / "gemini_budget.json")
    client = GeminiClient(
        model="gemini-3.5-flash-lite",
        api_key="test-secret",
        budget=budget,
        max_429_retries=1,
    )

    with pytest.raises(ProviderError, match="HTTP 429 after 2 attempts"):
        client.respond([], model_tools(), "Instructions")

    assert budget.pending_usd == 0
    assert client.metadata["request_attempt_count"] == 2
    assert client.metadata["rate_limit_retry_count"] == 1
    assert sleeps == [5]
    ledger = json.loads((tmp_path / "gemini_budget.json").read_text())
    assert ledger["reservations_usd"] == {}


def test_gemini_request_pacing_is_shared_across_clients(monkeypatch):
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(
        "drc_explain.gemini_provider.time.monotonic",
        lambda: now[0],
    )
    monkeypatch.setattr("drc_explain.gemini_provider.time.sleep", sleep)
    monkeypatch.setattr(GeminiClient, "_last_request_started", None)
    first = GeminiClient(
        model="gemini-3.5-flash-lite",
        api_key="test-secret",
        min_request_interval_s=6.1,
    )
    second = GeminiClient(
        model="gemini-3.5-flash-lite",
        api_key="test-secret",
        min_request_interval_s=6.1,
    )

    assert first._wait_for_request_slot() == 0
    assert second._wait_for_request_slot() == pytest.approx(6.1)
    assert sleeps == [pytest.approx(6.1)]
