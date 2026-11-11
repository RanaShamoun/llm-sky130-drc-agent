# Free local model setup

The default agent uses **Qwen3 8B through local Ollama**. It makes no paid API requests and needs no API key, credits, or cloud account. Model weights require about 5.2 GB of disk space; inference uses your computer's memory and processor/GPU.

## Prepared Mac

From the repository root:

```sh
source .venv/bin/activate
python run.py agent --gds benchmark/b004.gds
```

The project starts its local Ollama server automatically if needed. Calls go only to `127.0.0.1:11434`. Model weights are under `.tools/ollama-models/`; server logs are in `runs/ollama-server.log`. Both directories are ignored by Git.

## Another computer

1. Install [Ollama](https://ollama.com/download) for your platform.
2. Install the repository's Python dependencies and KLayout as described in [Setup](SETUP.md).
3. From the activated project environment, run:

```sh
python run.py pull-local
python run.py agent --gds benchmark/b004.gds
```

`pull-local` downloads the model once. Normal inference then runs locally. If the Ollama application is already running, the project uses that local server; otherwise its launcher starts one with `OLLAMA_NO_CLOUD=1`. The adapter rejects cloud tags, remote URLs, and model entries that do not contain downloaded local weights. There is no automatic fallback to a paid API.

The prepared Mac uses a project-local Ollama executable. Other computers may use their installed Ollama application or CLI. Windows is supported by Ollama, but this project setup has been exercised on this Mac; rerun the checks on another platform.

## Commands

```sh
python run.py check
python run.py agent-smoke
python run.py agent --gds benchmark/b004.gds --question "Check ordinary metal1 width and spacing."
python run.py agent --gds benchmark/b005.gds --question "Check ordinary metal1 width and spacing."
python run.py agent --question "Check antenna rules."
```

`agent-smoke` is an explicitly scripted integration test. The `agent` commands run actual local model inference. Keep that distinction in the report.

The default model is `qwen3:8b`, with 32K context, a 4096-token output limit per turn, non-thinking mode, and temperature zero. Exact runtime version and downloaded model digest are recorded in `data/local_model.lock.json` once the model is pinned. A changed digest for that model is rejected until deliberately reviewed. Each result records the provider, runtime version, model digest, token counts, latency, and tool evidence.

`cost_usd: 0.0` represents **API charges only**. Hardware, electricity, and download costs are not estimated. Local token counters are Ollama's `prompt_eval_count` and `eval_count`; do not treat them as OpenAI billing records or infer cache savings from absent cache counters.

## Scope of the experiment

This local setup establishes a no-API-cost agent demo. It does not by itself satisfy the proposal's original comparison of one open-weights and two closed models. Agree on accessible free model options or document an approved change to that comparison before claiming the final experiment is complete. Model accuracy remains an empirical result; a successful demo is not a 50-case evaluation.

## Optional OpenAI adapter

The OpenAI adapter is retained for an explicitly selected provider, but it is not used by default. An existing OpenAI key in `.env` does not activate it. Do not select `--provider openai` for the zero-spend workflow.

References: [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling), [local-only mode](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features), and [Qwen3 8B weights](https://ollama.com/library/qwen3:8b).
