"""Ollama adapter: real local inference, loopback only, no paid API fallback."""

from __future__ import annotations

import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from .common import ROOT, read_json
from .local_runtime import ensure_server
from .provider import ProviderError, load_local_config

DEFAULT_LOCAL_MODEL = "qwen3:8b"
LOCAL_URL = "http://127.0.0.1:11434"


class OllamaClient:
    is_live = True
    provider_name = "ollama-local"
    api_cost_usd = 0.0

    def __init__(self, model=None, timeout_s=180):
        load_local_config()
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_LOCAL_MODEL)
        if (
            not isinstance(self.model, str)
            or not self.model
            or ":cloud" in self.model
            or "/" in self.model
            or "://" in self.model
        ):
            raise ProviderError(
                "Use an installed local model name. Cloud models and remote endpoints are disabled."
            )
        self.timeout_s = timeout_s
        self.metadata = {}
        # Avoid proxy environment settings redirecting a loopback request.
        self._opener = build_opener(ProxyHandler({}))

    def _request(self, path, payload=None):
        request = Request(
            LOCAL_URL + path,
            data=json.dumps(payload, allow_nan=False).encode()
            if payload is not None
            else None,
            headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout_s) as response:
                body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ProviderError("Local model response exceeded the size limit.")
            value = json.loads(body)
        except HTTPError as exc:
            raise ProviderError(
                f"Local Ollama returned HTTP {exc.code}. Check the installed model and server log."
            ) from None
        except (URLError, TimeoutError):
            raise ProviderError(
                "Local Ollama is unavailable. Run python run.py serve-local in another terminal; no paid API was contacted."
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("Invalid JSON from the local model runtime.") from None
        if not isinstance(value, dict):
            raise ProviderError("Invalid local model response structure.")
        return value

    def _check_model(self):
        if self.metadata:
            return
        ensure_server()
        tags = self._request("/api/tags")
        entry = next(
            (
                m
                for m in tags.get("models", [])
                if m.get("name") == self.model or m.get("model") == self.model
            ),
            None,
        )
        if (
            not entry
            or entry.get("size", 0) < 1_000_000
            or entry.get("remote_host")
            or entry.get("remote_model")
        ):
            raise ProviderError(
                "The requested model is not installed as local weights. Use python run.py pull-local; cloud fallback is disabled."
            )
        lock_path = ROOT / "data/local_model.lock.json"
        if lock_path.exists():
            lock = read_json(lock_path)
            if self.model == lock.get("model") and entry.get("digest") != lock.get(
                "model_digest"
            ):
                raise ProviderError(
                    "Local model digest differs from the recorded pin; review the model before updating its lock."
                )
        version = self._request("/api/version").get("version")
        self.metadata = {
            "runtime": "ollama",
            "runtime_version": version,
            "model_digest": entry["digest"],
            "model_size_bytes": entry["size"],
            "endpoint": LOCAL_URL,
            "cloud_fallback": False,
        }

    @staticmethod
    def _messages(inputs, instructions):
        messages = [
            {
                "role": "system",
                "content": instructions
                + "\nCall exactly one function per turn. Always finish by calling finalize_answer, not prose.",
            }
        ]
        names = {}
        for item in inputs:
            kind = item.get("type")
            if kind == "function_call":
                names[item["call_id"]] = item["name"]
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": item["name"],
                                    "arguments": json.loads(item["arguments"]),
                                },
                            }
                        ],
                    }
                )
            elif kind == "function_call_output":
                if item["call_id"] not in names:
                    raise ProviderError("Local tool result has no matching model call.")
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": names[item["call_id"]],
                        "content": item["output"],
                    }
                )
            elif item.get("role") == "user":
                messages.append({"role": "user", "content": item["content"]})
            elif kind == "message":
                content = "".join(
                    part.get("text", "")
                    for part in item.get("content", [])
                    if part.get("type") == "output_text"
                )
                messages.append({"role": "assistant", "content": content})
        return messages

    def respond(self, inputs, tools, instructions):
        self._check_model()
        native_tools = [
            {
                "type": "function",
                "function": {k: t[k] for k in ["name", "description", "parameters"]},
            }
            for t in tools
        ]
        result = self._request(
            "/api/chat",
            {
                "model": self.model,
                "messages": self._messages(inputs, instructions),
                "tools": native_tools,
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "num_ctx": 32768, "num_predict": 4096},
            },
        )
        if result.get("done") is not True or result.get("done_reason") == "length":
            raise ProviderError(
                "Local inference was incomplete; no verdict was accepted."
            )
        message = result.get("message")
        if not isinstance(message, dict):
            raise ProviderError("Local model returned no assistant message.")
        calls = message.get("tool_calls") or []
        action_format = "native_tool_calls"
        if not calls and isinstance(message.get("content"), str):
            # Some local runtimes return an exact JSON action in content rather
            # than tool_calls. Accept only the same explicit name/arguments
            # envelope; all actions still pass through the normal verifier.
            try:
                action = json.loads(message["content"])
            except json.JSONDecodeError:
                action = None
            if (
                isinstance(action, dict)
                and set(action) == {"name", "arguments"}
                and action["name"] in {tool["name"] for tool in tools}
                and isinstance(action["arguments"], dict)
            ):
                calls = [{"function": action}]
                action_format = "json_action"
        output = []
        for call in calls:
            function = call.get("function", {})
            arguments = function.get("arguments")
            if not isinstance(arguments, dict) or not isinstance(
                function.get("name"), str
            ):
                raise ProviderError("Local model emitted malformed tool arguments.")
            output.append(
                {
                    "type": "function_call",
                    "call_id": "local_" + uuid.uuid4().hex,
                    "name": function["name"],
                    "arguments": json.dumps(arguments, allow_nan=False),
                }
            )
        if not output:
            output = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": message.get("content", "")}
                    ],
                }
            ]
        return {
            "id": "ollama_" + uuid.uuid4().hex,
            "status": "completed",
            "model": result.get("model", self.model),
            "output": output,
            "usage": {
                "input_tokens": result.get("prompt_eval_count", 0),
                "output_tokens": result.get("eval_count", 0),
            },
            "local_runtime": self.metadata,
            "local_action_format": action_format,
            "local_assistant_content": message.get("content", ""),
            "local_timings_ns": {
                k: result[k]
                for k in [
                    "total_duration",
                    "load_duration",
                    "prompt_eval_duration",
                    "eval_duration",
                ]
                if k in result
            },
        }
