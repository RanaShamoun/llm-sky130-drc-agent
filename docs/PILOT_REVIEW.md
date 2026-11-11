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

## Next Run

Do not resume the original output directory with changed implementation. It will fail its manifest comparison, and saved ERROR records are skipped rather than retried. Do not delete or relabel those errors to improve the original scores.

Review/test and commit the repair as a new checkpoint, record its hash, then run a separate six-query pilot:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
.\.venv\Scripts\python.exe run.py experiments run --models qwen3:8b --conditions A B C --cases b001 b002 --no-probes --output runs/experiments/pilot-v2
```

Inspect the new records and correction traces before launching 168 queries. No need for A/B to score perfectly: structurally valid inaccurate predictions are useful evaluation data. Repeated schema exhaustion or infrastructure failures need investigation before scaling. Keep both pilot versions, and do not pool them into a single experiment condition.