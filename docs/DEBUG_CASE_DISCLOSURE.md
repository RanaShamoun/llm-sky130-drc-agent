# Debug and Demonstration Case Disclosure

Recorded November 11, 2026, before the planned six-query pilot and full A/B/C evaluation. This note identifies known live-model exposure; it is not a claim of an exhaustive audit of all historical tests.

## Why Record This?

We already inspected some answers while setting up the system. Later runs on those cases are reproducible evaluation observations, but those cases must not be described as never previously inspected. The setup demonstrations are not part of the new experiment's accuracy denominator and must not be copied into experiment records as if newly run.

This disclosure does not assert model-weight training on these layouts. It records project-team exposure to cases and outputs during debugging. Prompts should be tuned only on separate development examples, not these benchmark gold answers.

## Windows Demonstrations Identified from Saved Results

The previously unidentified PASS case is **b002**, confirmed by its saved `gds_path`, not inferred from the dropdown or verdict.

| Case | Saved run ID | Verdict | Selected rule | Verification | Latency | Tool calls |
|---|---|---|---|---|---|---|
| b001 | `4cc01a91761f4966a08ce58ad6fc5d85` | FAIL | `m1.1` | Accepted | 345.576846 s | 3 |
| b002 | `5152edaa7b254ae99f9ed3e8d68a5312` | PASS | `m1.1` | Accepted | 313.488256 s | 3 |

Both used local `qwen3:8b`, the same width question, and zero API charges. Hardware/electricity costs are unestimated. b001 reported a 0.135 um violation distance against a 0.14 um minimum. b002 reported no violation and no scalar passing measurement.

The saved event timestamps are UTC. These executions occurred on November 11 UTC, corresponding to November 10 evening in the user's Windows session:

| Case | First event UTC | Final event UTC |
|---|---|---|
| b001 | `2026-11-11T06:50:55.718690+00:00` | `2026-11-11T06:56:41.303958+00:00` |
| b002 | `2026-11-11T07:00:34.130184+00:00` | `2026-11-11T07:05:47.625462+00:00` |

Saved evidence resides locally under `runs/agent/<run_id>/`: `result.json`, `trace.jsonl`, and `tool_calls.jsonl`. These ignored runtime files should be backed up separately, not silently discarded or automatically committed.

Result-file SHA256 fingerprints captured when making this disclosure:

| Case | Result SHA256 |
|---|---|
| b001 | `dff1bfc2e77bab3a758c91808adf7d75f44eae3b4df27290d35b35c0083e88e0` |
| b002 | `0b7fedcf4f76c1d15c47a2a6bea27a748b1e85b36711858b5c115fad8b876968` |

Both result records identify model digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`. The original result files have not been rewritten to create this disclosure.

## Earlier Windows Setup Errors

Four saved b001 attempts returned ERROR before the accepted demonstration:

| Run ID | Latency |
|---|---|
| `87c8dc9ba9694184b3f39e3298e30f75` | 0.106114 s |
| `577dbc7efbc74a218491e387bd120545` | 1.059727 s |
| `5bc09860aa6d47a9b0c75cec4a6f9144` | 34.678666 s |
| `d52e6a40a63e4c67a2fbab42b993802d` | 223.883611 s |

These are retained setup failures, not geometric FAIL verdicts. An ERROR attempt need not have completed model inference, but it is still part of the setup history. Do not count these as successful acceptance examples or conceal them by presenting only the final working run.

## Historical Handoff Exposure

The prior handoff records four accepted local-model demonstrations: `b004`, `b005`, `b039`, and `o002`. See [local acceptance summary](../eval/gold/local_agent_acceptance.json) and [archived traces](../eval/gold/local_agent_traces.zip). Scripted checks and historical rejected attempts used additional cases; the accepted-case list alone is not a complete exposure inventory.

Known accepted live-demonstration IDs, combining that record and Windows setup: **b001, b002, b004, b005, b039, o002**.

## How Future Experiments Use This Note

[experiments.py](../src/drc_explain/experiments.py) records the accepted IDs, Windows demonstration run references, and Windows setup error IDs in its manifest. This is output metadata only. `model_input()` continues to allow only the public question, layout path, top cell, and coordinates. Gold answers, historical verdicts, and these disclosure fields are not added to prompts.

The new [experiment test](../tests/test_experiments.py) checks manifest recording and input isolation using a fake client, without live model inference or DRC. Older manifests are not edited in place; the runner may refuse resume after this implementation change. Use a new output directory if a prior experiment's manifest no longer matches.

The proposed b001/b002 six-query pilot is explicitly a pipeline smoke test on already inspected cases. Keep its output separate from the full experiment. Do not claim a development-only pilot, because the current CLI does not select development cases.

For the final report, disclose the full benchmark's prior exposure. A secondary analysis excluding known accepted demonstration IDs may be useful, but it is not proof that every remaining case is untouched; do not replace the predefined full benchmark with a favorable subset or selectively remove model failures.

## Suggested Report Wording

> Before evaluation, we inspected historical local-model demonstrations on b004, b005, b039, and o002, and Windows setup demonstrations on b001 and b002. Four earlier b001 setup attempts returned execution errors. These runs are integration/debug evidence, not new evaluation observations. The b001/b002 pilot is a pipeline smoke test. Historical scripted tests and rejected attempts also exposed additional cases, so we do not describe the benchmark as wholly untouched. Disclosure metadata is stored in experiment manifests and is not supplied to models.

Update this note if more cases are manually inspected or used for debugging before the final evaluation. No benchmark labels, layout files, or model weights were changed by this disclosure step.