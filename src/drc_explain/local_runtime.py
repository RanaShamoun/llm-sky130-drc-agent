"""Start the local-only Ollama runtime and explicitly download local weights."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from .common import ROOT
from .provider import ProviderError, load_local_config


def runtime_binary():
    candidates = [
        ROOT / ".tools/ollama/ollama",
        Path("/Applications/Ollama.app/Contents/Resources/ollama"),
    ]
    installed = shutil.which("ollama")
    if installed:
        candidates.append(Path(installed))
    for path in candidates:
        if path.is_file():
            return str(path.resolve())
    raise ProviderError(
        "Install Ollama from https://ollama.com/download first. No paid API is needed."
    )


def runtime_environment():
    local_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_API_KEY"}
    }
    return dict(
        local_environment,
        OLLAMA_NO_CLOUD="1",
        OLLAMA_HOST="127.0.0.1:11434",
        OLLAMA_MODELS=str(ROOT / ".tools/ollama-models"),
    )


def _running():
    try:
        with build_opener(ProxyHandler({})).open(
            "http://127.0.0.1:11434/api/version", timeout=1
        ) as response:
            return isinstance(json.load(response).get("version"), str)
    except (URLError, TimeoutError, ValueError, OSError):
        return False


def ensure_server():
    if _running():
        return
    binary = runtime_binary()
    log = ROOT / "runs/ollama-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        process = subprocess.Popen(
            [binary, "serve"],
            env=runtime_environment(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(50):
        if _running():
            return
        if process.poll() is not None:
            break
        time.sleep(0.2)
    raise ProviderError(
        f"Local Ollama did not start. See {log}. No paid API was called."
    )


def pull_model():
    load_local_config()
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    if ":cloud" in model or "/" in model or "://" in model:
        raise ProviderError("Cloud and remote models are disabled for this setup.")
    ensure_server()
    subprocess.run(
        [runtime_binary(), "pull", model], env=runtime_environment(), check=True
    )
