"""Small OpenAI Responses API adapter; credentials never enter trace files."""

from __future__ import annotations

import getpass
import json
import os
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from .common import ROOT

DEFAULT_MODEL = "gpt-5.4-mini-2026-03-17"


class ProviderError(RuntimeError):
    """A model request failed; no geometric verdict can be inferred."""


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

    def __init__(self, model=None, api_key=None, timeout_s=60, max_output_tokens=4096):
        load_local_config()
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout_s = timeout_s
        self.max_output_tokens = max_output_tokens
        if not self.model or self.model == "your-model-id":
            raise ProviderError(
                "Set OPENAI_MODEL to a function-calling model available in your OpenAI account. See docs/AGENT.md."
            )
        if not self._api_key or self._api_key == "your-api-key":
            raise ProviderError(
                "Set OPENAI_API_KEY locally in .env or your terminal. Do not paste the key into chat."
            )

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
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload, allow_nan=False).encode(),
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
