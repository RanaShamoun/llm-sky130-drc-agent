"""Google Gemini adapter with the existing agent protocol as its boundary."""

from __future__ import annotations

import json
import math
import os
import ssl
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from .provider import ProviderError, TokenBudget, load_local_config

DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_TIMEOUT_S = 60
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MIN_REQUEST_INTERVAL_S = 6.1
DEFAULT_MAX_429_RETRIES = 5
DEFAULT_429_BACKOFF_S = 5.0
MAX_429_BACKOFF_S = 60.0
MAX_RETRY_AFTER_S = 120.0
GEMINI_PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
GEMINI_PRICING_AS_OF = "2026-11-21"
GEMINI_25_FLASH_PRICES_PER_MILLION = {
    "input": Decimal("0.30"),
    "cached_input": Decimal("0.03"),
    "output": Decimal("2.50"),
}
GEMINI_35_FLASH_LITE_PRICES_PER_MILLION = {
    "input": Decimal("0.30"),
    "cached_input": Decimal("0.03"),
    "output": Decimal("2.50"),
}
GEMINI_MODEL_PRICING = {
    "gemini-2.5-flash": {
        "prices": GEMINI_25_FLASH_PRICES_PER_MILLION,
        "source": f"{GEMINI_PRICING_SOURCE}#gemini-2.5-flash",
    },
    "gemini-3.5-flash-lite": {
        "prices": GEMINI_35_FLASH_LITE_PRICES_PER_MILLION,
        "source": f"{GEMINI_PRICING_SOURCE}#gemini-3.5-flash-lite",
    },
}


def _gemini_model_pricing(model):
    return GEMINI_MODEL_PRICING.get(model)


def _gemini_pricing(model):
    model_pricing = _gemini_model_pricing(model)
    return model_pricing["prices"] if model_pricing else None


def gemini_cost_usd(model, usage):
    prices = _gemini_pricing(model)
    if prices is None or not isinstance(usage, dict):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cached_tokens = (usage.get("input_tokens_details") or {}).get(
        "cached_tokens", 0
    )
    values = (input_tokens, output_tokens, cached_tokens)
    if any(type(value) is not int or value < 0 for value in values):
        return None
    if cached_tokens > input_tokens:
        return None
    cost = (
        (input_tokens - cached_tokens) * prices["input"]
        + cached_tokens * prices["cached_input"]
        + output_tokens * prices["output"]
    ) / Decimal(1_000_000)
    return float(cost)


class GeminiBudget(TokenBudget):
    """Per-run Gemini budget using standard paid-tier model pricing."""

    def __init__(self, cap_usd, ledger_path):
        super().__init__(
            cap_usd,
            ledger_path,
            "Gemini",
            GEMINI_PRICING_SOURCE,
            GEMINI_PRICING_AS_OF,
            _gemini_pricing,
        )


def _schema(schema):
    result = {}
    for key in ("type", "enum", "format", "minimum", "maximum", "description"):
        if key in schema:
            value = schema[key]
            if key == "type" and isinstance(value, list):
                non_null = [item for item in value if item != "null"]
                if non_null:
                    result["type"] = non_null[0].upper()
                if "null" in value:
                    result["nullable"] = True
                continue
            if key == "type" and isinstance(value, str):
                value = value.upper()
            result[key] = value
    if "properties" in schema:
        result["properties"] = {name: _schema(value) for name, value in schema["properties"].items()}
    if "required" in schema:
        result["required"] = list(schema["required"])
    if "items" in schema:
        result["items"] = _schema(schema["items"])
    return result


def _http_error_detail(exc, api_key):
    body = exc.read(16 * 1024)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return None
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return message[:1000] or None


def _retry_after_seconds(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, seconds) if math.isfinite(seconds) else None


class GeminiClient:
    is_live = True
    provider_name = "gemini"
    _rate_limit_lock = threading.Lock()
    _last_request_started = None

    def __init__(
        self,
        model=None,
        api_key=None,
        timeout_s=DEFAULT_TIMEOUT_S,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        budget=None,
        min_request_interval_s=None,
        max_429_retries=None,
    ):
        load_local_config()
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.timeout_s = timeout_s
        self.max_output_tokens = max_output_tokens
        self.budget = budget
        self.min_request_interval_s = (
            DEFAULT_MIN_REQUEST_INTERVAL_S
            if min_request_interval_s is None
            else min_request_interval_s
        )
        self.max_429_retries = (
            DEFAULT_MAX_429_RETRIES
            if max_429_retries is None
            else max_429_retries
        )
        self.api_cost_usd = 0.0 if _gemini_pricing(self.model) else None
        self.metadata = {}
        if not isinstance(self.model, str) or not self.model or "/" in self.model:
            raise ProviderError("Set a valid Gemini model ID in GEMINI_MODEL.")
        if type(self.max_output_tokens) is not int or self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer.")
        if (
            isinstance(self.min_request_interval_s, bool)
            or not isinstance(self.min_request_interval_s, (int, float))
            or not math.isfinite(self.min_request_interval_s)
            or self.min_request_interval_s < 0
        ):
            raise ValueError("min_request_interval_s must be finite and non-negative.")
        if type(self.max_429_retries) is not int or self.max_429_retries < 0:
            raise ValueError("max_429_retries must be a non-negative integer.")
        if not self._api_key:
            raise ProviderError(
                "Set GEMINI_API_KEY locally in .env or the terminal. Do not place it in chat or traces."
            )

    def _wait_for_request_slot(self):
        with self._rate_limit_lock:
            now = time.monotonic()
            last_started = GeminiClient._last_request_started
            wait_s = (
                max(0.0, self.min_request_interval_s - (now - last_started))
                if last_started is not None
                else 0.0
            )
            if wait_s:
                time.sleep(wait_s)
            GeminiClient._last_request_started = time.monotonic()
        return wait_s

    @staticmethod
    def _contents(inputs, instructions=None):
        contents = []
        names = {}
        for item in inputs:
            kind = item.get("type")
            if kind == "function_call":
                names[item["call_id"]] = item["name"]
                part = {
                    "functionCall": {
                        "name": item["name"],
                        "args": json.loads(item["arguments"]),
                    }
                }
                thought_signature = item.get("thought_signature")
                if thought_signature is not None:
                    if not isinstance(thought_signature, str):
                        raise ProviderError(
                            "Gemini thought signature must be a string."
                        )
                    part["thoughtSignature"] = thought_signature
                contents.append({"role": "model", "parts": [part]})
            elif kind == "function_call_output":
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": names.get(item["call_id"], "tool"),
                            "response": json.loads(item["output"]),
                        }
                    }],
                })
            elif item.get("role") == "user":
                contents.append({"role": "user", "parts": [{"text": item["content"]}]})
        return contents

    def _check_model(self):
        if not self.metadata:
            model_pricing = _gemini_model_pricing(self.model)
            if self.budget and model_pricing is None:
                raise ProviderError(
                    f"No budget pricing is configured for Gemini model {self.model!r}."
                )
            self.metadata = {
                "api": "gemini_generateContent",
                "model": self.model,
                "endpoint": "https://generativelanguage.googleapis.com",
                "request_timeout_s": self.timeout_s,
                "max_output_tokens": self.max_output_tokens,
                "pricing_source": model_pricing["source"] if model_pricing else None,
                "pricing_as_of": GEMINI_PRICING_AS_OF if model_pricing else None,
                "pricing_tier": "standard_paid" if model_pricing else None,
                "budget_cap_usd": self.budget.cap_usd if self.budget else None,
                "minimum_request_interval_s": self.min_request_interval_s,
                "max_429_retries": self.max_429_retries,
                "rate_limit_retry_backoff_s": DEFAULT_429_BACKOFF_S,
                "max_retry_after_s": MAX_RETRY_AFTER_S,
                "request_attempt_count": 0,
                "request_pacing_wait_s": 0.0,
                "rate_limit_retry_count": 0,
                "rate_limit_retry_wait_s": 0.0,
            }

    def respond(self, inputs, tools, instructions):
        self._check_model()
        declarations = []
        for tool in tools:
            declarations.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": _schema(tool["parameters"]),
            })
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": self._contents(inputs, "Follow the system instructions. Return one function call per turn."),
            "tools": [{"functionDeclarations": declarations}],
            "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
            "generationConfig": {"maxOutputTokens": self.max_output_tokens},
        }
        request_body = json.dumps(payload, allow_nan=False).encode()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        request = Request(
            url,
            data=request_body,
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        reservation_id = None
        if self.budget:
            reservation_id, _ = self.budget.reserve(
                self.model, request_body, self.max_output_tokens
            )
        retries = 0
        request_attempts = 0
        while True:
            pacing_wait_s = self._wait_for_request_slot()
            self.metadata["request_pacing_wait_s"] = round(
                self.metadata["request_pacing_wait_s"] + pacing_wait_s, 3
            )
            self.metadata["request_attempt_count"] += 1
            request_attempts += 1
            try:
                context = ssl.create_default_context(
                    cafile=os.environ.get("SSL_CERT_FILE") or certifi.where()
                )
                with urlopen(request, timeout=self.timeout_s, context=context) as response:
                    body = response.read(8 * 1024 * 1024 + 1)
                break
            except HTTPError as exc:
                if exc.code == 429:
                    detail = _http_error_detail(exc, self._api_key)
                    suffix = f" Provider detail: {detail}" if detail else ""
                    if retries >= self.max_429_retries:
                        if self.budget and reservation_id:
                            self.budget.release(reservation_id)
                        raise ProviderError(
                            f"Gemini HTTP 429 after {request_attempts} attempts; "
                            f"retry limit ({self.max_429_retries}) reached."
                            f"{suffix}"
                        ) from None
                    retry_after = _retry_after_seconds(
                        (exc.headers or {}).get("Retry-After")
                    )
                    delay_s = (
                        retry_after
                        if retry_after is not None
                        else min(MAX_429_BACKOFF_S, DEFAULT_429_BACKOFF_S * (2**retries))
                    )
                    if delay_s > MAX_RETRY_AFTER_S:
                        if self.budget and reservation_id:
                            self.budget.release(reservation_id)
                        raise ProviderError(
                            "Gemini HTTP 429; server Retry-After exceeds the "
                            f"{MAX_RETRY_AFTER_S:g}-second retry limit.{suffix}"
                        ) from None
                    retries += 1
                    self.metadata["rate_limit_retry_count"] += 1
                    self.metadata["rate_limit_retry_wait_s"] = round(
                        self.metadata["rate_limit_retry_wait_s"] + delay_s, 3
                    )
                    time.sleep(delay_s)
                    continue
                if exc.code in {401, 403}:
                    raise ProviderError("Gemini authentication or model access failed. Check GEMINI_API_KEY and model access.") from None
                if exc.code in {400, 404}:
                    detail = _http_error_detail(exc, self._api_key)
                    suffix = f": {detail}" if detail else ""
                    raise ProviderError(
                        f"Gemini HTTP {exc.code}{suffix}. Check model access and request parameters."
                    ) from None
                raise ProviderError(f"Gemini HTTP {exc.code}. Check model access and request parameters.") from None
            except (URLError, TimeoutError):
                raise ProviderError("Gemini request could not complete. Check network access or retry later.") from None

        if len(body) > 8 * 1024 * 1024:
            raise ProviderError("Gemini response exceeded the size limit.")
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("Gemini returned invalid JSON.") from None

        usage_metadata = result.get("usageMetadata")
        if not isinstance(usage_metadata, dict):
            usage_metadata = {}
        input_tokens = usage_metadata.get("promptTokenCount")
        cached_tokens = usage_metadata.get("cachedContentTokenCount", 0)
        candidate_tokens = usage_metadata.get("candidatesTokenCount")
        thoughts_tokens = usage_metadata.get("thoughtsTokenCount", 0)
        output_tokens = (
            candidate_tokens + thoughts_tokens
            if type(candidate_tokens) is int
            and candidate_tokens >= 0
            and type(thoughts_tokens) is int
            and thoughts_tokens >= 0
            else None
        )
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_tokens_details": {"cached_tokens": cached_tokens},
        }
        cost = gemini_cost_usd(self.model, usage)
        if cost is None:
            self.api_cost_usd = None
            if self.budget:
                raise ProviderError(
                    "Gemini response omitted valid token usage; its budget reservation remains held."
                )
        else:
            if self.api_cost_usd is not None:
                self.api_cost_usd += cost
            if self.budget:
                self.budget.settle(reservation_id, cost)

        model_version = result.get("modelVersion")
        if isinstance(model_version, str):
            self.metadata["model_version"] = model_version
        service_tier = usage_metadata.get("serviceTier")
        if isinstance(service_tier, str):
            self.metadata["service_tier"] = service_tier

        candidates = result.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError("Gemini returned no candidate response.")
        parts = candidates[0].get("content", {}).get("parts", [])
        output = []
        for part in parts:
            function_call = part.get("functionCall")
            if not isinstance(function_call, dict):
                continue
            name = function_call.get("name")
            args = function_call.get("args", {})
            if not isinstance(name, str) or not isinstance(args, dict):
                raise ProviderError("Gemini returned malformed function-call arguments.")
            call = {
                "type": "function_call",
                "call_id": "gemini_" + uuid.uuid4().hex,
                "name": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            }
            thought_signature = part.get("thoughtSignature")
            if thought_signature is not None:
                if not isinstance(thought_signature, str):
                    raise ProviderError(
                        "Gemini returned a malformed thought signature."
                    )
                call["thought_signature"] = thought_signature
            output.append(call)
        return {
            "id": result.get("responseId") or "gemini_" + uuid.uuid4().hex,
            "model": self.model,
            "model_version": model_version,
            "status": "completed",
            "output": output,
            "usage": usage,
        }
