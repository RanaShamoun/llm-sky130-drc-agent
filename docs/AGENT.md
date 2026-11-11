# Run the LLM agent

The agent has passed four real local-model acceptance examples; results and rejected integration attempts are saved in `eval/gold/local_agent_acceptance.json` and `local_agent_traces.zip`. These are integration demonstrations, not an unbiased benchmark score. By default it uses a real local model for planning and the existing KLayout tools for geometric evidence. Scripted tests and actual model inference are recorded separately; neither a scripted test nor a few live examples establish benchmark accuracy.

## Free local model

The default provider is local Ollama with Qwen3 8B. No API key or paid credits are needed. Follow [Local model setup](LOCAL_MODEL.md); on the prepared Mac, run `python run.py agent --gds benchmark/b004.gds`. The local server starts automatically when necessary, and there is no cloud fallback.

The optional OpenAI adapter remains available only when explicitly selected with `--provider openai` or `DRC_PROVIDER=openai`. An existing OpenAI key does not change the local default. Its hidden-key configuration command is `python run.py configure`; it is not needed for the zero-spend workflow.

## Live examples

A deliberately failing layout:

```sh
python run.py agent --gds benchmark/b004.gds --question "Check ordinary width and spacing of metal1 routing."
```

A passing layout for the same checks:

```sh
python run.py agent --gds benchmark/b005.gds --question "Check ordinary width and spacing of metal1 routing."
```

A conditional enclosure case:

```sh
python run.py agent --gds benchmark/b039.gds --question "Check minimum and corner-based enclosure of this via by metal1 only."
```

An unsupported-scope probe, without a layout:

```sh
python run.py agent --question "Does this layout satisfy antenna rules?"
```

Use `--json` to print the complete structured result. `--max-turns` defaults to eight; the tool budget is twelve, including the automatic initial inspection. This loop is bounded and does not modify layouts or the checker.

## What the agent does

1. Inspects the requested layout and includes actual layer coordinates in the model input.
2. Lets the model retrieve rules, choose the relevant IDs, and request DRC checks.
3. Accepts a structured proposed answer through `finalize_answer`.
4. Verifies IDs were retrieved, all checked rules are represented, statuses and limits match the tool, scalar measurements match exactly, and the overall verdict follows the checks. Evidence must belong to the same unchanged input layout.
Local calls use native tool calls or an exact JSON `{name, arguments}` action envelope. The provider records which format was used. Both go through the same dispatch and verification; arbitrary prose is never accepted as a geometric answer. Prose-only drafts are asked to resubmit a structured action within the same turn budget.

5. Renders the authoritative plain-language explanation from the verified facts, with immutable rule source links and original marker evidence. Unsupported claims are rejected; a model can correct its proposal within the turn budget. A tool failure or exhausted budget produces ERROR, never PASS.

PASS and FAIL apply only to the model-selected rules. The verifier cannot prove that the model selected every relevant rule; that remains a benchmark metric. Selection justifications and refusal reasons are model-written text and are not certified geometric facts. Numeric passing distances are never invented. The final explanation is a deterministic rendering of accepted model claims, not unrestricted model prose; state this in the report.

## Files and outputs

- `src/drc_explain/agent.py`: prompt, bounded model/tool loop, trace capture.
- `src/drc_explain/local_provider.py`: local Ollama adapter; `local_runtime.py` starts the runtime.
- `src/drc_explain/provider.py`: optional OpenAI adapter and hidden-key configuration.
- `src/drc_explain/verification.py`: structured-claim verifier and explanation renderer.
- `runs/agent/<run_id>/result.json`: verdict, checked evidence, selections, requested/returned models, usage totals, response IDs, latency, prompt hash, and verification status.
- `runs/agent/<run_id>/trace.jsonl`: model inputs/outputs, rejected claims, and tool results.
- `runs/agent/<run_id>/tool_calls.jsonl`: original tool logs.

Credentials are never part of model payloads or logs. Local inference records zero API cost; the optional OpenAI adapter records null cost until the evaluator applies pricing. Do not interpret ERROR as a domain refusal or a successful query. `live_model: true` identifies actual inference rather than a scripted fixture; also require an accepted result and inspect the recorded provider. Ollama IDs are locally generated trace identifiers, not OpenAI response IDs.

Programmatic entry point:

```python
from drc_explain.agent import Agent
from drc_explain.local_provider import OllamaClient

result = Agent(OllamaClient()).run(
    "Check ordinary metal1 width and spacing.",
    "benchmark/b004.gds",
)
```

The agent never reads `eval/gold/`. Keep gold labels and scoring in the future evaluator. For A/B/C comparisons, preserve the same public base question, coordinate dump, and domain context; adapt permitted tools and verification honestly rather than counting scripted fixtures as baseline model answers.

## Verification without billing

```sh
python run.py check
python run.py agent-smoke
```

The smoke command uses an explicitly scripted model double with the real KLayout engine: passing/failing spacing, passing/failing corner enclosure, and refusal without geometry. It tests dispatch, tracing, and verification only. It is not live inference, model selection, or an accuracy experiment.

## Optional OpenAI failures

- HTTP 401: the saved API secret key was not accepted. Replace it with `configure`.
- HTTP 403/404: check model/account access and `OPENAI_MODEL`.
- HTTP 429 `credit_balance_exhausted`: add API credits in the [API billing settings](https://platform.openai.com/settings/organization/billing). This blocked the optional OpenAI demo; the zero-spend local workflow does not use those credits.
- Other HTTP 429 codes: check the reported quota, spend limit, or rate-limit cause. Repeated retries do not restore an exhausted balance.
- Connection failure: check network access. HTTPS validation uses the pinned `certifi` bundle; `SSL_CERT_FILE` can specify an organization-provided CA bundle. Verification is never disabled.

Implementation references: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create), and [the configured model snapshot](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
