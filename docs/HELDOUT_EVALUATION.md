# Independent Held-Out Evaluation

## Purpose

The original 56-case public benchmark is useful for development and preliminary evidence, but several layouts and answers were inspected during debugging. The held-out workflow creates a separate 24-layout dataset that was not used to tune prompts or implementation.

## Dataset

- 24 benchmark layouts
- 6 near-boundary metal1/metal2 spacing cases
- 3 matched pass/fail pairs (6 layouts)
- 6 competing-rule layouts
- 6 conditional-enclosure layouts
- 3 unsupported-scope probes

Public files are under `eval/public/heldout/`. Private construction intent and oracle labels are under `eval/gold/heldout/`.

## Reproducibility

Generate layouts and private construction metadata:

```powershell
.\.venv\Scripts\python.exe run.py generate-heldout
```

Run the pinned full-deck oracle and archive reports:

```powershell
.\.venv\Scripts\python.exe run.py label-heldout
```

Cross-check public hashes, layout inspections, native RDB reports, and private labels:

```powershell
.\.venv\Scripts\python.exe scripts\verify_heldout.py
```

The held-out label set passed 24/24 construction/oracle comparisons with no mismatches.

## First local held-out result

On November 24, 2026, Qwen3 8B condition C completed one repetition of all 24
held-out benchmark layouts and three refusal probes:

- Fixed-denominator benchmark verdict accuracy: 24/24 (100%)
- Execution ERROR records: 0/27
- Probe refusal correctness: 3/3 (100%)
- Selection recall: 24/24 required rule instances
- Selection precision: 85.7% by the evaluator's submitted-rule-instance metric
- Pair accuracy: 3/3
- Numeric grounding: 15/15 eligible measurements
- Mean latency: 281.4 seconds per record

Across the conditional-enclosure layouts, the result audit recorded six irrelevant
rule citations; grounded DRC verdicts still matched the layout status. This run is
one local-model repetition, not a repeated stability study or a three-model held-out
result.

## Three-repetition local held-out result

On November 24-25, 2026, Qwen3 8B condition C was repeated three times in a separate
run directory. Every repetition completed all 27 records and produced the same
fixed-denominator result:

| Repetition | Benchmark verdict accuracy | Probe refusals | ERROR records |
|---|---:|---:|---:|
| 1 | 24/24 (100%) | 3/3 | 0/27 |
| 2 | 24/24 (100%) | 3/3 | 0/27 |
| 3 | 24/24 (100%) | 3/3 | 0/27 |

Across repetitions, the mean fixed-denominator accuracy was 100% with a range of
100-100%. Selection recall was 1.000, refusal correctness was 1.000, and numeric
grounding was 1.000 for every repetition. The raw records and traces are preserved
under `runs/experiments/heldout-qwen3-c3-20261124/`.

This is repeated held-out evidence for one local model only. It does not establish
a three-model ranking and is still not an independent foundry oracle.

## Three-model held-out repetition result

On November 25, 2026, matching condition-C runs were completed for GPT-4o and
Gemini 3.5 Flash-Lite in separate three-repetition directories. Together with the
three Qwen3 repetitions, the held-out comparison is:

| Model | Repeat 1 | Repeat 2 | Repeat 3 | ERROR records |
|---|---:|---:|---:|---:|
| Qwen3 8B | 24/24 | 24/24 | 24/24 | 0/81 |
| GPT-4o | 24/24 | 24/24 | 24/24 | 0/81 |
| Gemini 3.5 Flash-Lite | 20/24 | 14/24 | 15/24 | 23/81 |

Gemini fixed-denominator repetition accuracies were 83.3%, 58.3%, and 62.5%.
Across all 81 Gemini records, there were 23 execution ERROR records: 22 HTTP 503
records and one protocol-failure record. All 9 Gemini probes were refused correctly.
GPT-4o and Qwen3 also had 3/3 probe refusals in every repetition. GPT-4o cost was
$0.350, $0.346, and $0.355 per repetition in the recorded estimate ledger.

## HTTP 503 retry fix

The Gemini adapter now retries bounded HTTP 503 service-unavailable responses with
exponential backoff and honors Retry-After. A fresh 81-record run used up to five
service retries:

| Repetition | Fixed-denominator accuracy | ERROR records | Refusals |
|---|---:|---:|---:|
| 1 | 22/24 (91.7%) | 4/27 | 1/3 |
| 2 | 21/24 (87.5%) | 4/27 | 2/3 |
| 3 | 19/24 (79.2%) | 5/27 | 3/3 |

The separate fixed run had 13/81 errors, compared with 23/81 in the historical
run. Across 78 records that encountered one or more 503 responses, 65 later
completed and 13 exhausted retries. These runs differ in implementation and
provider conditions, so the comparison does not establish a causal effect.

## Eight-retry run and daily quota

A subsequent Gemini run allowed up to eight service retries. Its fixed-denominator
benchmark accuracies were 18/24, 0/24, and 0/24, with 0/3 correct probe refusals
in each repetition. It recorded 9, 27, and 27 errors, all HTTP 429 after the
free-tier daily request quota was exhausted. This run is separate from the earlier
ones and measures quota-limited execution, not model answer quality.

## Repeat-ready experiment

One local run:

```powershell
.\.venv\Scripts\python.exe run.py experiments run `
  --heldout --provider ollama `
  --models qwen3:8b `
  --conditions A B C `
  --repetitions 1 `
  --timeout-s 1200 `
  --no-probes `
  --output runs\experiments\heldout-qwen3-20261122
```

For hosted providers, keep separate approved estimate guards:

```powershell
--provider openai --models gpt-4o --api-budget-usd 5
--provider gemini --models gemini-3.5-flash-lite --api-budget-usd 2
```

Use `--repetitions 3` for a repeat study. The runner writes each repetition under the selected output directory and records the public/cases/gold dataset paths in the manifest.

## Scoring rules

- Accuracy uses the fixed 24-layout denominator.
- `ERROR` counts as incorrect and is not a model REFUSE or a geometric verdict.
- Repeated results should report the mean and range across repetitions.
- A/B results are unverified predictions.
- C results are selected-rule, KLayout-backed verifier-accepted outputs.
- Do not selectively retry or replace saved errors.

## Limitations

The held-out set is newly separated for the project, but it is generated by the same geometry builder and verified by the same KLayout engine. It is independent of the original public/evaluator examples for this workflow, but it is not an external foundry signoff or independent oracle implementation.
