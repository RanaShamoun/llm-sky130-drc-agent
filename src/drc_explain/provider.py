"""Small OpenAI Responses API adapter; credentials never enter trace files."""

from __future__ import annotations

import getpass
import json
import math
import os
import socket
import ssl
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from .common import ROOT, read_json, write_json

DEFAULT_MODEL = "gpt-5.4-mini-2026-03-17"
OPENAI_PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing/"
OPENAI_PRICING_AS_OF = "2026-11-20"
GPT4O_PRICES_PER_MILLION = {
    "input": Decimal("2.50"),
    "cached_input": Decimal("1.25"),
    "output": Decimal("10.00"),
}


class ProviderError(RuntimeError):
    """A model request failed; no geometric verdict can be inferred."""


def _gpt4o_pricing(model):
    if model == "gpt-4o" or model.startswith("gpt-4o-"):
        return GPT4O_PRICES_PER_MILLION
    return None


def openai_cost_usd(model, usage):
    prices = _gpt4o_pricing(model)
    if prices is None or not isinstance(usage, dict):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cached_tokens = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
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


class TokenBudget:
    """Persisted API spend cap with conservative per-request token reservations."""

    def __init__(
        self,
        cap_usd,
        ledger_path,
        provider_name,
        pricing_source,
        pricing_as_of,
        pricing_lookup,
    ):
        if (
            isinstance(cap_usd, bool)
            or not isinstance(cap_usd, (int, float))
            or not math.isfinite(cap_usd)
            or cap_usd <= 0
        ):
            raise ValueError(
                f"{provider_name} API budget must be a positive finite dollar amount."
            )
        self.cap = Decimal(str(cap_usd))
        self.path = Path(ledger_path)
        self.provider_name = provider_name
        self.pricing_source = pricing_source
        self.pricing_as_of = pricing_as_of
        self.pricing_lookup = pricing_lookup
        self.spent = Decimal("0")
        self.reservations = {}
        if self.path.exists():
            state = read_json(self.path)
            if (
                state.get("version") != 1
                or Decimal(str(state.get("cap_usd"))) != self.cap
                or state.get("provider", provider_name) != provider_name
            ):
                raise ProviderError(
                    f"{provider_name} budget ledger does not match this run's cap."
                )
            self.spent = Decimal(str(state["spent_usd"]))
            self.reservations = {
                key: Decimal(str(value))
                for key, value in state.get("reservations_usd", {}).items()
            }

    @property
    def cap_usd(self):
        return float(self.cap)

    @property
    def spent_usd(self):
        return float(self.spent)

    @property
    def pending_usd(self):
        return float(sum(self.reservations.values(), Decimal("0")))

    def _save(self):
        write_json(
            self.path,
            {
                "version": 1,
                "provider": self.provider_name,
                "cap_usd": str(self.cap),
                "spent_usd": str(self.spent),
                "reservations_usd": {
                    key: str(value) for key, value in self.reservations.items()
                },
                "pricing_source": self.pricing_source,
                "pricing_as_of": self.pricing_as_of,
            },
        )

    def reserve(self, model, request_body, max_output_tokens):
        prices = self.pricing_lookup(model)
        if prices is None:
            raise ProviderError(
                f"No budget pricing is configured for {self.provider_name} model {model!r}."
            )
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer.")

        input_token_bound = len(request_body) + 4096
        amount = (
            input_token_bound * prices["input"]
            + max_output_tokens * prices["output"]
        ) / Decimal(1_000_000)
        pending = sum(self.reservations.values(), Decimal("0"))
        if self.spent + pending + amount > self.cap:
            raise ProviderError(
                f"{self.provider_name} budget cap reached; this request was blocked before sending."
            )

        reservation_id = uuid.uuid4().hex
        self.reservations[reservation_id] = amount
        self._save()
        return reservation_id, amount

    def settle(self, reservation_id, actual_cost_usd):
        reserved = self.reservations.get(reservation_id)
        if reserved is None:
            raise ProviderError(f"{self.provider_name} budget reservation is missing.")
        actual = Decimal(str(actual_cost_usd))
        del self.reservations[reservation_id]
        self.spent += actual
        self._save()
        if actual > reserved:
            raise ProviderError(
                f"{self.provider_name} usage exceeded its conservative budget reservation; stopping."
            )

    def release(self, reservation_id):
        if reservation_id not in self.reservations:
            raise ProviderError(f"{self.provider_name} budget reservation is missing.")
        del self.reservations[reservation_id]
        self._save()


class OpenAIBudget(TokenBudget):
    """Per-run OpenAI budget using standard GPT-4o pricing."""

    def __init__(self, cap_usd, ledger_path):
        super().__init__(
            cap_usd,
            ledger_path,
            "OpenAI",
            OPENAI_PRICING_SOURCE,
            OPENAI_PRICING_AS_OF,
            _gpt4o_pricing,
        )


def load_local_config(path=None):
    """Read the two allowed .env settings as text, without executing shell code."""
    path = path or ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name = name.strip()
        if separator and name in {
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "DRC_PROVIDER",
            "OLLAMA_MODEL",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
        }:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                os.environ.setdefault(name, value)


class OpenAIResponses:
    """Provider boundary shared by the live agent and injectable test clients."""

    is_live = True
    provider_name = "openai"

    def __init__(
        self, model=None, api_key=None, timeout_s=60, max_output_tokens=4096, budget=None
    ):
        load_local_config()
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout_s = timeout_s
        self.max_output_tokens = max_output_tokens
        self.budget = budget
        self.metadata = {}
        if (
            not isinstance(self.model, str)
            or not self.model
            or self.model == "your-model-id"
        ):
            raise ProviderError(
                "Set OPENAI_MODEL to a function-calling model available in your OpenAI account. See docs/AGENT.md."
            )
        self.api_cost_usd = 0.0 if _gpt4o_pricing(self.model) else None
        if not self._api_key or self._api_key == "your-api-key":
            raise ProviderError(
                "Set OPENAI_API_KEY locally in .env or your terminal. Do not paste the key into chat."
            )

    def _check_model(self):
        if self.metadata:
            return
        if self.budget and _gpt4o_pricing(self.model) is None:
            raise ProviderError(
                f"No budget pricing is configured for OpenAI model {self.model!r}."
            )
        prices = _gpt4o_pricing(self.model)
        self.metadata = {
            "api": "openai_responses",
            "model": self.model,
            "endpoint": "https://api.openai.com/v1/responses",
            "request_timeout_s": self.timeout_s,
            "pricing_source": OPENAI_PRICING_SOURCE if prices else None,
            "pricing_as_of": OPENAI_PRICING_AS_OF if prices else None,
            "budget_cap_usd": self.budget.cap_usd if self.budget else None,
        }

    def respond(self, inputs, tools, instructions):
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": inputs,
            "tools": tools,
            "tool_choice": "required",
            "parallel_tool_calls": False,
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "max_output_tokens": self.max_output_tokens,
        }
        request_body = json.dumps(payload, allow_nan=False).encode()
        reservation_id = None
        if self.budget:
            reservation_id, _ = self.budget.reserve(
                self.model, request_body, self.max_output_tokens
            )
        request = Request(
            "https://api.openai.com/v1/responses",
            data=request_body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            context = ssl.create_default_context(
                cafile=os.environ.get("SSL_CERT_FILE") or certifi.where()
            )
            with urlopen(request, timeout=self.timeout_s, context=context) as response:
                body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ProviderError("Model response exceeded the response-size limit.")
            result = json.loads(body)
        except HTTPError as exc:
            # Do not expose error bodies or headers: they may echo credentials.
            known_codes = {
                "insufficient_quota": "API quota is unavailable. Check API billing and account limits.",
                "credit_balance_exhausted": "API credit balance is exhausted. Check API billing.",
                "organization_spend_limit_exceeded": "The organization API spend limit was reached.",
                "project_spend_limit_exceeded": "The project API spend limit was reached.",
                "organization_usage_limit_exceeded": "The organization API usage limit was reached.",
                "rate_limit_exceeded": "The API rate limit was reached. Retry later.",
                "slow_down": "The API requested a slower request rate. Retry later.",
            }
            if exc.code == 429:
                try:
                    error = json.loads(exc.read(16384)).get("error", {})
                    code = error.get("code")
                    if code not in known_codes:
                        code = error.get("type")
                    if code in known_codes:
                        raise ProviderError(
                            f"OpenAI HTTP 429 ({code}). {known_codes[code]}"
                        ) from None
                except (
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                    AttributeError,
                    TypeError,
                ):
                    pass
            hint = {
                401: "Check the local API key.",
                403: "Check model/account access.",
                404: "Check OPENAI_MODEL.",
                429: "Check API quota or rate limits.",
            }.get(exc.code, "Check the API request and service status.")
            raise ProviderError(f"OpenAI HTTP {exc.code}. {hint}") from None
        except (URLError, socket.timeout, TimeoutError):
            raise ProviderError(
                "OpenAI request could not complete. Check network access or retry later."
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("OpenAI returned an invalid JSON response.") from None
        if not isinstance(result, dict):
            raise ProviderError("OpenAI returned an invalid response structure.")
        cost = openai_cost_usd(self.model, result.get("usage"))
        if self.budget and cost is None:
            raise ProviderError(
                "OpenAI response omitted valid token usage; its budget reservation remains held."
            )
        if cost is not None:
            if self.api_cost_usd is None:
                self.api_cost_usd = 0.0
            self.api_cost_usd += cost
            if self.budget:
                self.budget.settle(reservation_id, cost)
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderError(
                "Model response was incomplete or failed; no verdict was accepted."
            )
        if not isinstance(result.get("output"), list):
            raise ProviderError("Model response has no valid output list.")
        return result


def configure_api():
    """Local terminal only: hidden input, no shell-history entry for the key."""
    path = ROOT / ".env"
    if path.is_symlink():
        raise ProviderError(
            "Refusing to replace a symlink at .env; configure the environment directly."
        )
    key = getpass.getpass("OpenAI API key (hidden; Enter cancels): ").strip()
    if not key:
        print("Configuration cancelled; no files changed.")
        return
    if not key.startswith("sk-"):
        raise ProviderError(
            "That does not look like an OpenAI API secret key. Create one at https://platform.openai.com/api-keys; no files changed."
        )
    if any(c.isspace() for c in key):
        raise ProviderError("The API key must not contain whitespace.")
    lines = path.read_text().splitlines() if path.exists() else []
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    for line in lines:
        if line.strip().startswith("OPENAI_MODEL="):
            candidate = line.split("=", 1)[1].strip().strip("\"'")
            if candidate and candidate != "your-model-id":
                model = candidate
    preserved = [
        line
        for line in lines
        if line.partition("=")[0].strip() not in {"OPENAI_API_KEY", "OPENAI_MODEL"}
    ]
    contents = (
        "\n".join(preserved + [f"OPENAI_API_KEY={key}", f"OPENAI_MODEL={model}"]) + "\n"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(contents)
    path.chmod(0o600)
    print(f"Configuration saved locally to {path}. API key hidden and ignored by Git.")
    print(f"Model: {model}")


def configure_gemini():
    """Local terminal only: hidden Gemini API key, no shell-history entry."""
    path = ROOT / ".env"
    if path.is_symlink():
        raise ProviderError(
            "Refusing to replace a symlink at .env; configure the environment directly."
        )
    key = getpass.getpass("Gemini API key (hidden; Enter cancels): ").strip()
    if not key:
        print("Configuration cancelled; no files changed.")
        return
    if any(c.isspace() for c in key):
        raise ProviderError("The API key must not contain whitespace.")
    lines = path.read_text().splitlines() if path.exists() else []
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    preserved = [
        line
        for line in lines
        if line.partition("=")[0].strip()
        not in {"GEMINI_API_KEY", "GEMINI_MODEL"}
    ]
    contents = (
        "\n".join(preserved + [f"GEMINI_API_KEY={key}", f"GEMINI_MODEL={model}"]) + "\n"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(contents)
    path.chmod(0o600)
    print(f"Gemini configuration saved locally to {path}. API key hidden and ignored by Git.")
