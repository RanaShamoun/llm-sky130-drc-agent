# First Six-Query Pilot Review

The first pilot used commit `41227972505bb5ae4488c01d334936a298e5251c`, local `qwen3:8b`, and already inspected cases b001/b002. Original evidence remains under `runs/experiments/pilot/`. This note does not replace or rewrite those records.

## Observed Results

| Case | Condition | Saved verdict | Latency seconds | External tool calls |
|---|---|---|---|---|
| b001 | A | ERROR | 132.893914 | 0 |
| b001 | B | ERROR | 135.464862 | 1 |
| b001 | C | FAIL, verified | 292.495202 | 3 |
| b002 | A | ERROR | 47.414885 | 0 |
| b002 | B | ERROR | 118.387081 | 1 |
| b002 | C | PASS, verified | 298.090093 | 3 |

All six records and aggregate scoring outputs exist. Total recorded query latency is 1024.746037 seconds, about 17.1 minutes, excluding other overhead. Trace checks confirmed A invoked no external tools, B invoked only retrieval, and C successfully invoked DRC for m1.1 and accepted evidence on both cases.

The displayed A/B accuracy and grounding are zero because their results are ERROR. C scored 1.0 for verdict, selection recall, and structured grounding on these two cases. Refusal is N/A because no probes were run. These tiny, previously inspected examples are not final benchmark accuracy or statistical evidence of the ablation's value.

## Why A/B Failed

Every baseline final submission omitted the schema-required `refusal_reason` field. Even a PASS/FAIL answer must supply this field as JSON null. The baseline's structural validator rejected the submissions with `Invalid prediction fields` and previously stopped immediately.

The raw drafts also contain substantive prediction errors. A used invented IDs R1001 and M1_WIDTH, a 0.15 um threshold, and PASS judgments inconsistent with the stated dimensions. B retrieved m1.1 correctly, but its b001 draft combined overall PASS with per-rule FAIL. Some drafts also supplied distances for passing claims despite the instruction to use an empty list.

Thus the error is not simply four wrong geometric predictions, and fixing the schema does not prove that those predictions will become correct. Preserve both format failures and raw semantic mistakes in analysis.

## Narrow Protocol Repair

[experiments.py](../src/drc_explain/experiments.py) now logs a rejected final call and returns structural validation feedback to the model, allowing resubmission within the existing eight-turn budget. This follows the full agent's existing bounded correction pattern.

Feedback identifies missing/unexpected fields and explains the required null refusal field. The harness does not auto-fill fields, repair verdicts, choose rules, substitute thresholds, check predictions against gold, or provide checker access to A/B. Structurally valid wrong predictions remain wrong observations for scoring. Rejected drafts remain in traces, and retry inference contributes to usage and latency.

[tests/test_experiments.py](../tests/test_experiments.py) verifies missing-field correction, unchanged semantic mistakes, no external tool calls for A, retained rejected-call events, and bounded failure when submissions remain invalid. The seven experiment tests passed after the repair using fake clients. No new live model query was launched during repair; real-model correction success remains unverified until another pilot.

This is a protocol change motivated by a pipeline failure, not prompt tuning to the case's gold geometry. Nevertheless, disclose it before final evaluation. The model may alter its own predictions during correction; the harness does not force them to remain identical.

## Next Run (historical; completed in pilot-v2)

Do not resume the original output directory with changed implementation. It will fail its manifest comparison, and saved ERROR records are skipped rather than retried. Do not delete or relabel those errors to improve the original scores.

Review/test and commit the repair as a new checkpoint, record its hash, then run a separate six-query pilot:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
.\.venv\Scripts\python.exe run.py experiments run --models qwen3:8b --conditions A B C --cases b001 b002 --no-probes --output runs/experiments/pilot-v2
```

Inspect the new records and correction traces before launching 168 queries. No need for A/B to score perfectly: structurally valid inaccurate predictions are useful evaluation data. Repeated schema exhaustion or infrastructure failures need investigation before scaling. Keep both pilot versions, and do not pool them into a single experiment condition.

## Follow-up: pilot-v2

The separate six-record run in `runs/experiments/pilot-v2/` completed after the schema-repair change. A on b001 returned ERROR because local Ollama was unavailable; A on b002 returned FAIL, which is incorrect. B returned the correct FAIL/PASS pair, and C returned the same pair with verified evidence. Aggregate verdict accuracy was A 0/2, B 2/2, C 2/2; C grounding was 2/2.

This confirms the repaired protocol can produce valid A/B submissions, but the pilot still had a runtime failure and covers only two previously inspected cases. It does not validate the full benchmark or the model's unseen-case accuracy. Keep this output separate from the initial pilot and from the full run.

## Follow-up: Llama 3.1 A/B protocol review

The initial 168-record Llama 3.1 8B grid completed, but all 56 A records and all 56 B records were `ERROR`. A traces showed plain-text JSON actions with unregistered names such as `get_rule_selections`. B traces showed repeated `retrieve_rules` calls with string or out-of-range `limit` values, plus attempts to call the unavailable `calculate_distance` tool. C had 15 errors in 56 records; its exploratory benchmark verdict accuracy was 78%.

A follow-up compatibility change accepts a `parameters` JSON-action envelope only for a registered tool and normalizes a decimal-string `retrieve_rules.limit` only when it is in range. Baseline A/B now allow one logged protocol-repair attempt. Rejected calls are returned as errors and are never executed; A still has only `finalize_answer`, and B still has only `retrieve_rules` and `finalize_answer`. The attempt count is pinned in the experiment manifest.

The separate two-case retry smoke (`runs/experiments/llama31-protocol-retry-20261121/`) still produced A 0/2 and B 0/2 valid predictions, while C produced 2/2 outputs. The traces show that the retry did not resolve Llama's unsupported-tool and final-schema failures. Keep this diagnostic run separate from the initial full grid; do not describe the A/B errors as ordinary answer-accuracy measurements or pool these runs.

Any new final cross-model comparison must disclose which protocol version each run used. If the retry policy is used for final results, use it consistently for every model and preserve prior runs as historical evidence rather than overwriting them.

## Follow-up: Qwen3 C request-timeout diagnostic

The Qwen3 full-grid `main` run recorded 17 C benchmark errors. Fifteen result files say `Local Ollama is unavailable`, but this message alone did not identify whether the cause was a server outage or a request timeout. The original `main` manifest does not record an inference-timeout value.

For b026 and b041, the experiment trace and `%LOCALAPPDATA%\\Ollama\\server-3.log` align: the final `/api/chat` request ended with HTTP 500 after exactly 180 seconds. The Ollama log shows token generation continuing until the task was canceled; subsequent requests were served. This is strong evidence for a request cutoff/client cancellation in those cases, not a server crash, but it does not prove that all 15 `unavailable` errors had the same cause.

A separate run, `runs/experiments/qwen-b041-timeout-diagnostic-20261121/`, retried only b041 in condition C with `--timeout-s 1200`. It completed in 694.9 seconds, with model requests lasting about 236, 135, and 319 seconds. The structured result was accepted and the overall verdict was correct, but it included three irrelevant citations, 40% selection precision, and 0 grounding under the saved metric. This supports testing longer request timeouts; it does not replace or alter the original full-grid result, nor establish that a full Qwen rerun would have the same performance.