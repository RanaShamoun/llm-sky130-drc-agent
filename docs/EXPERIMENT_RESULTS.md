# Experiment Results and Remaining Evaluation Gaps

This report summarizes the Qwen3 8B full grid, the GPT-4o and Llama 3.1 8B full grids completed November 20-21, 2026, and the separate Llama protocol-retry smoke. The raw experiment directories are under `runs/experiments/`, which is ignored by Git; preserve those records and manifests separately when preparing a submission. The full grids share the same 56 cases, conditions, and one repetition. However, Qwen's prompt and implementation hashes differ from the matching GPT-4o/Llama hashes, so the three runs do not constitute a fully controlled three-model comparison. Report the Qwen results as contextual evidence, not as a strict model-only ranking against the other two.

## Main Qwen3 A/B/C Run

The `main` run completed 56 records in each condition: 50 benchmark layouts and six unsupported-scope probes, with one repetition of `qwen3:8b`. Verdict accuracy, selection, and grounding below use the 50 benchmark cases; refusal correctness uses the six probes. `ERROR` is counted as incorrect for verdict accuracy. Latency and error counts cover all 56 records.

| Condition | Information/tools | Verdict accuracy | Selection recall (all cases; ERROR counts as missed) | Grounding | Refusal correct | ERROR records | Mean latency |
|---|---|---:|---:|---:|---:|---:|---:|
| A | Coordinates only | 0.400 (20/50) | 0.000 | 0.000 | 0.833 (5/6) | 1/56 | 94.8 s |
| B | Coordinates + rule retrieval | 0.620 (31/50) | 0.591 | 0.120 | 0.667 (4/6) | 6/56 | 196.2 s |
| C | Agent + retrieval + KLayout + deterministic verification | 0.660 (33/50) | 0.477 | 0.660 | 0.833 (5/6) | 18/56 | 328.0 s |

Additional recorded metrics:

- Pair accuracy across six pass/fail pairs was 0/6 for A, 4/6 for B, and 6/6 for C.
- Among accepted benchmark outputs only, B selected 52 of 66 required rule instances (78.8% recall, 100% precision); C selected 42 of 42 (100% recall and precision). These conditional metrics exclude B's six and C's 17 benchmark errors. The all-case recall in the table includes those errors as missed selections, so report both views rather than interpreting the aggregate C recall as incompleteness among its accepted answers.
- Numeric grounding on the 21 benchmark cases with scalar measurements was 0/21 for A, 7/21 for B, and 15/21 for C.
- C had zero scored citation, limit, duplicate, or unavailable-measurement errors. B had seven irrelevant citations and 36 unavailable-measurement claims. A had 74 fabricated citations, 74 irrelevant citations, 74 limit errors, and 62 unavailable-measurement claims.
- C recorded 18 errors total: 17 benchmark cases and one probe. Fifteen explicitly report that local Ollama was unavailable; the other benchmark errors were a model-turn-budget exhaustion and a refusal caused by required geometry being absent. Correlating the b026 and b041 traces with the rotated Ollama server log showed each final `/api/chat` request ending in HTTP 500 after exactly 180 seconds while token generation was still in progress and then canceled. This suggests a request cutoff/client cancellation for at least those failures, but does not establish the cause of all 15 `unavailable` errors. The historical Qwen manifest does not record its inference timeout. A separate b041 C diagnostic with a 1200-second request timeout completed in 694.9 seconds and returned the correct overall verdict; however, it had three irrelevant citations and 40% selection precision. Keep this single-case diagnostic separate from the full-grid scores. Thus C's 33/50 overall benchmark accuracy includes 17 execution errors; all 33 non-error benchmark outputs were correct. The latter is a conditional, failure-selected statistic and must not replace the fixed-denominator 33/50 result.
- C's p95 latency was 463.5 seconds. The API charge was zero; local hardware and electricity costs were not measured.

The main result suggests retrieval improved the coordinate-only baseline's verdict accuracy, while C improved grounding and pair accuracy. It does **not** show reliable end-to-end C operation: C had 18 errors, and logs suggest a request cutoff may explain at least some errors labeled as Ollama unavailability. The benchmark run used one model and one repetition. C also combines retrieval, DRC access, deterministic verification, and verified rendering, so this is a system comparison, not an isolated causal estimate of KLayout's effect.

## Full-grid model outcomes

The three full grids each contain one record for every condition and each of the 56 inputs (50 benchmark layouts plus six unsupported-scope probes). Accuracy is over the fixed 50-case benchmark denominator; `ERROR` records count as incorrect. Accepted outputs are shown separately across all 56 records so protocol/runtime failures are visible.

| Model | A accuracy; accepted outputs | B accuracy; accepted outputs | C accuracy; accepted outputs |
|---|---|---|---|
| Qwen3 8B | 20/50 (40%); 55/56 | 31/50 (62%); 50/56 | 33/50 (66%); 38/56 |
| GPT-4o | 26/50 (52%); 56/56 | 28/50 (56%); 56/56 | 50/50 (100%); 56/56 |
| Llama 3.1 8B | 0/50 (0%); 0/56 | 0/50 (0%); 0/56 | 39/50 (78%); 41/56 |

The accuracy denominator includes errors, which is an end-to-end score and should not be interpreted by itself as answer quality when a model failed to produce an accepted output. In particular, Llama A and B had 56/56 `ERROR` records each: there are no accepted A/B predictions from which to estimate its semantic answer accuracy. The traces show incompatible tool requests and invalid protocol/schema outputs. Llama C did produce accepted outputs, alongside 15 errors among 56 records. Qwen completed its full grid with some errors (1 in A, 6 in B, and 18 in C); GPT-4o had no error records in this run.

### Archived rejected-call event audit

The original full-grid traces contain 141 rejected-call events for Qwen, none for GPT-4o, and 178 for Llama. These are event counts, not unique queries; a query can produce multiple rejected calls, and they do not count every `ERROR` record. Classifying from the saved error type/message, while separating final-answer schema failures and malformed tool/protocol calls from semantic C-condition verifier rejections, gives:

| Model | A schema/format | B schema/format | C schema/format | C tool/protocol | C verifier |
|---|---:|---:|---:|---:|---:|
| Qwen3 8B | 43 | 48 | 32 | 4 | 14 |
| GPT-4o | 0 | 0 | 0 | 0 | 0 |
| Llama 3.1 8B | 8 | 0 recorded | 0 | 161 | 9 |

The verifier column counts C-condition `VerificationError` events other than final-answer structure/format failures. It does not mean every rejected call is a rejected geometric claim: Qwen and Llama also had schema/protocol failures, and Llama's C events were predominantly malformed or incompatible tool arguments. Llama's B trace had no `rejected_call` events despite all 56 B records being `ERROR`, demonstrating that this event audit is not a complete error taxonomy. The separate two-case Llama protocol-retry smoke recorded A: 2 schema/format, B: 6 schema/format, and C: 5 tool/protocol plus 1 verifier event; it is not pooled with the full grid.

The GPT-4o and Llama full-grid manifests have matching prompt and core implementation hashes; their model/provider differs. The Qwen run has different prompt and implementation hashes, despite the same public inputs, cases, and condition labels. Therefore, GPT-4o versus Llama is the closer same-protocol comparison, while Qwen's results are useful context but do not support a clean three-model ranking. All runs use one repetition on a curated, previously exposed benchmark.

The separate `llama31-protocol-retry-20261121` smoke used only b004/b005, no probes, and a later implementation with one logged A/B protocol-repair attempt. A and B still had 0/2 accepted outputs each; C had 2/2. This diagnostic is not part of the full-grid table and must not be pooled with the original Llama run.

The separate `qwen-b041-timeout-diagnostic-20261121` run used only b041, condition C, and a 1200-second per-request timeout. It completed in 694.9 seconds with an accepted structured result and correct overall verdict, but had three irrelevant citations, 40% selection precision, and 0 grounding under the saved metric. The three model requests took approximately 236, 135, and 319 seconds, showing that this case required requests longer than 180 seconds. This is evidence for the timeout hypothesis on a single case, not a replacement score or proof that all Qwen C errors were timeouts.

After increasing the default timeout and distinguishing wrapped timeouts from connection failures, a separate local Qwen C smoke ran b004 (near-boundary), b026 (competing rules), and b037 (conditional enclosure) with `--timeout-s 1200`. All three outputs were accepted, matched their exact expected rule statuses/selections, were grounded, and had no citation or measurement errors. Latencies were 439.3, 1022.5, and 384.6 seconds (mean 615.4 seconds); the API cost was $0. This three-case diagnostic is not pooled with any full-grid score and does not establish that all historical errors were timeouts. Its prompt hash matches the GPT-4o/Llama full-grid prompt hash, but its implementation hash differs in `experiments.py` and `local_provider.py`. The run manifest and traces are preserved under `runs/experiments/qwen-c-timeout-smoke-20261122/`.

## Earlier pilot and prior local-model comparison (historical)

The separate `pilot-v2` run contains six smoke-test records on previously inspected cases b001/b002. A returned one ERROR (Ollama unavailable) and one incorrect verdict (0/2). B returned 2/2 correct verdicts; C returned 2/2 correct verified verdicts. This validates the schema-repair path on a small sample, but it is not independent evaluation or a substitute for the full run.

The earlier `model-comparison` run evaluated condition C on ten near-boundary benchmark cases and six refusal probes for each of two local models:

| Model | Benchmark verdicts | Probe refusals | ERROR records | Interpretation |
|---|---:|---:|---:|---|
| qwen3:8b | 9/10 correct | 6/6 correct | 1/16 | One benchmark record failed because Ollama was unavailable. |
| llama3.1:8b | 0/10 correct | 0/6 correct | 16/16 | All records errored: 15 from invalid tool arguments and one from Ollama unavailability. This is a tool-protocol/runtime failure, not a valid estimate of answer quality. |

This historical run is exploratory only. It tests condition C on a small, narrow subset, not A/B/C across models. Its Llama errors and status predate the later full-grid run above; do not combine these observations with the full grid or rank answer quality from the Llama errors.

### Earlier tool-argument compatibility work (status as of November 15)

The saved Llama traces showed malformed calls such as string-valued integer/array fields and unexpected parameter names. The local adapter now unwraps only strict JSON strings for the final answer's array fields and JSON `null` for `refusal_reason`; all normalized answers still pass through the same deterministic verifier. Invalid tool calls receive schema-specific feedback, and experiment manifests record the per-request inference timeout. These changes have focused regression tests.

A live, single-case Llama smoke after the schema-feedback changes corrected malformed retrieval and DRC calls, but exhausted its turn budget on malformed final-answer fields. A later run for testing strict-JSON unwrapping was stopped before it completed. Therefore the end-to-end Llama compatibility fix has **not** yet been confirmed by an accepted live result.

A planned 16-case-per-model rerun was paused at the user's request at that time. The preserved `model-comparison-v3` directory contains two accepted Qwen3 C-condition records (b001, b002) and no Llama records. It is incomplete and is not part of the full-grid comparison. A second empty rerun manifest is preserved under `model-comparison-rerun-20261115`.

## Validity and Limitations

- The benchmark contains 50 curated layouts and six refusal probes, not a representative production workload. The full benchmark includes known prior team exposure documented in [DEBUG_CASE_DISCLOSURE.md](DEBUG_CASE_DISCLOSURE.md); it is not an untouched holdout.
- The archived labels were audited against KLayout's native report reader, but both use the same KLayout engine. This is not an independent foundry signoff oracle. The checker supports only eight curated rules and limited rectangular geometry.
- Each full-grid condition has one repetition. The observed proportions have no run-to-run uncertainty estimate; small subgroup results should not be generalized.
- A/B predictions are unverified. C reports only selected-rule results and is not full-chip signoff.
- The main run's errors must remain visible. Since the runner skips saved records on resume, any retry policy should be declared in advance, use a separate output directory, and preserve the original outcomes.

## Remaining Work

1. If a strictly controlled three-model comparison is required, freeze one prompt and implementation and rerun all selected models consistently. The current runs are exploratory; preserve them and use a new output directory for any rerun. Do not start another full run unless it is approved and necessary.
2. Use [the course report draft](COURSE_REPORT_DRAFT.md) and [the demo guide](DEMO_GUIDE.md) to finish the written and recorded deliverables. Clearly distinguish accepted outputs, errors, and accuracy denominators.
3. Choose which existing analysis scripts, plots, and generated layouts are intended submission artifacts. Do not add all untracked files automatically.

## Controlled frozen-grid comparison (November 22, 2026)

Three fresh 168-record grids were completed under matching public inputs, prompt text, and implementation hashes:

| Model | A accuracy; accepted | B accuracy; accepted | C accuracy; accepted | ERROR records |
|---|---:|---:|---:|---:|
| Qwen3 8B | 23/50 (46%); 55/56 | 29/50 (58%); 53/56 | 50/50 (100%); 54/56 | 5 |
| GPT-4o | 29/50 (58%); 56/56 | 27/50 (54%); 56/56 | 50/50 (100%); 56/56 | 0 |
| Gemini 3.5 Flash-Lite | 41/50 (82%); 53/56 | 43/50 (86%); 54/56 | 46/50 (92%); 52/56 | 9 |

Accepted counts use all 56 records, while accuracy remains a fixed 50-case benchmark denominator. The frozen Qwen, GPT-4o, and Gemini runs share the same prompt and implementation hashes. This is a more controlled comparison than the earlier historical grids, but it is still one repetition and uses the same previously exposed benchmark. Local hardware and electricity costs for Qwen remain unestimated. GPT-4o's locally estimated API cost was $1.346; Gemini's settled paid-tier estimate was $0.294, with three $0.012-$0.013 uncertain reservations from HTTP 503 requests. The Gemini records contained no 429 retries, only no-429 pacing and retries for service availability; local cost estimates are not Google billing confirmations.

- GPT-4o: 168/168 completed, 0 errors. C scored 50/50.
- Qwen3: 168/168 completed, 5 errors (3 B and 2 C). C scored 50/50 benchmark verdicts and completed 54/56 records; this is the strongest Qwen C result in the frozen-grid set.
- Gemini: 168/168 completed, 9 errors (3 A HTTP 503s, 2 B turn-budget failures, and 4 C protocol failures). C scored 46/50 benchmark verdicts and 52/56 accepted records.

The raw records and manifests are under `runs/experiments/final-comparison-{qwen3,gpt4o,gemini35}-20261121/`. Do not pool these results with historical full grids or diagnostic runs: the implementation and prompt versions differ.

Gemini experiment support defaults to `gemini-3.5-flash-lite`, records model-specific paid-tier estimates and uses a persisted reservation ledger; its `--api-budget-usd` option is an application-level estimate guard, not a Google billing cap. The adapter retains `gemini-2.5-flash` pricing for historical compatibility. In a separate three-case diagnostic, A produced correct predictions for all three layouts. After the adapter began preserving `thoughtSignature`, B completed b004/b026 but exhausted its eight-turn limit on b037 after repeatedly omitting geometric claims. C produced verifier-accepted results for b004/b026 and an isolated b037 retry after its first attempt received HTTP 429. These diagnostic outcomes are not full-grid results; report the B b037 reliability error rather than selectively retrying it. Earlier 2.5 attempts failed on schema conversion and then HTTP 404. Google lists 3.5 Flash-Lite as stable, with standard paid-tier rates of $0.30/1M input, $0.03/1M cached input, and $2.50/1M output tokens as of November 21, 2026. See Google's [model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) and [pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite).

On November 21, 2026, the user's AI Studio Free-tier page showed peak Gemini 3.5 Flash-Lite usage of 18/15 RPM, 41.81K/250K TPM, and 38/500 RPD over 28 days. RPM was the only displayed limit exceeded, consistent with the earlier HTTP 429; the page did not indicate a payment failure. To reduce rate-limit failures before a controlled rerun, the adapter now spaces request starts by at least 6.1 seconds and retries 429 responses up to five times, honoring `Retry-After` or applying bounded exponential backoff. Request attempts, retry counts, and wait time are retained in provider metadata. A 429 that persists after retries remains an `ERROR` (never a verdict); its confirmed failed-request reservation is released from the local estimate ledger. This throttle is process-local, so no other Gemini client should run concurrently with the grid. The runner's paid-tier estimate and `--api-budget-usd` are not Google's billing controls.

This rate-limit handling changes the implementation hash. The existing Gemini pilot records must remain historical; for an apples-to-apples three-model comparison, run fresh Qwen, GPT-4o, and Gemini grids under this frozen code, using identical cases, conditions, and repetitions. Do not selectively retry individual model failures when scoring the comparison.

After adding the throttle, a fresh single-record A/b004 smoke in `runs/experiments/gemini35-throttle-smoke-20261121-1610/` returned the expected FAIL prediction with model version `gemini-3.5-flash-lite`, one request attempt, zero 429 retries, and zero pacing wait. Its recorded $0.0006534 is the runner's standard paid-tier estimate, not a Google billing confirmation; the Free-tier dashboard is authoritative for actual charges. This A-condition smoke is unverified by design and is not rate-limit stress evidence or a full-grid result.

The saved full-grid aggregates and records inspected for this report are local under `runs/experiments/main/`, `runs/experiments/gpt4o-full-20261120/`, and `runs/experiments/llama31-full-20261121/`. The later retry smoke and historical pilot/comparison outputs are in their own directories. These ignored raw records should be retained for reproducibility but are not automatically included in a Git submission.
