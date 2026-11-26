# DRC Explain: Evidence-Grounded Design-Rule Explanations

**Status:** Course-report draft. A fresh controlled grid for Qwen3 8B, GPT-4o, and Gemini 3.5 Flash-Lite is available under matching prompt, implementation, and public-input hashes. Earlier Llama/Qwen/GPT grids remain historical and must not be pooled with this comparison.

## Abstract

This project explores a bounded language-model agent for explaining selected SKY130 design-rule checks (DRC). The model interprets a layout question, retrieves supported rule definitions, selects rules, and requests checks from KLayout. A deterministic verifier compares the model's structured claims with the tool evidence and renders the accepted explanation. A 50-layout benchmark and six unsupported-scope probes were evaluated with Qwen3 8B, GPT-4o, and Gemini 3.5 Flash-Lite under three conditions: coordinates only (A), coordinates plus rule retrieval (B), and the complete tool-assisted agent (C). The fresh frozen-grid verdict accuracies were 46%, 58%, and 100% for Qwen; 58%, 54%, and 100% for GPT-4o; and 82%, 86%, and 92% for Gemini. Gemini had 9 execution errors and Qwen had 5; GPT-4o had none. These one-repetition runs are controlled across the three models but still use a small, previously exposed benchmark and an oracle based on the same KLayout engine as the checker.

## 1. Problem and Objective

Physical chip layouts must satisfy manufacturing rules for properties such as minimum metal width, spacing, and via enclosure. A DRC engine can identify geometric violations, but users also need to ask focused questions and understand what was checked. This project tests whether an LLM can select relevant rules and explain checker results while a deterministic tool remains authoritative for geometry.

The agent is deliberately narrow. It supports eight curated rules for ordinary rectangular metal1/metal2 geometry and square 0.15 um vias. It is not a full-chip signoff system, and a PASS applies only to the rules the model selected and the checker returned.

## 2. System and Method

The implementation has three experimental conditions:

| Condition | Model input and tools | Interpretation |
|---|---|---|
| A | Public question and layout coordinates; no retrieval or DRC | Unverified prediction |
| B | Same input plus supported-rule retrieval | Unverified prediction informed by retrieved rules |
| C | Agent can inspect, retrieve rules, request KLayout checks, and submit structured claims | Tool-backed answer accepted only after deterministic verification |

Condition C verifies selected rule IDs, per-rule statuses, limits, available marker measurements, and the overall verdict against evidence for the same layout. Free-form generated prose is not treated as authoritative. The verifier establishes consistency with the selected tool results; rule-selection completeness is measured separately.

The public benchmark contains 50 labeled layouts; six additional probes cover unsupported requests. The main saved grid used Qwen3 8B once for each condition. Verdict accuracy uses the fixed denominator of 50 benchmark cases; ERROR counts as incorrect. Refusal correctness is evaluated separately on the six probes.

## 3. Results

| Condition | Benchmark verdict accuracy | Selection recall (all cases; ERROR counts as missed) | Grounding | Probe refusal correctness | Execution errors |
|---|---:|---:|---:|---:|---:|
| A: coordinates | 20/50 (40.0%) | 0.000 | 0.000 | 5/6 (83.3%) | 1/56 |
| B: + retrieval | 31/50 (62.0%) | 0.591 | 0.120 | 4/6 (66.7%) | 6/56 |
| C: tools + verification | 33/50 (66.0%) | 0.477 | 0.660 | 5/6 (83.3%) | 18/56 |

For C, all 33 non-error benchmark outputs were correct; this conditional count does not replace the fixed-denominator accuracy of 33/50. Fifteen C errors report local Ollama unavailability; the other benchmark errors involved turn-budget exhaustion or a refusal despite missing required geometry. Subsequent log correlation for b026 and b041 found the last `/api/chat` request returned HTTP 500 after exactly 180 seconds while generation was ongoing, suggesting a request cutoff or client cancellation for at least some errors. The original Qwen manifest does not record its timeout, so the cause of all 15 errors is unresolved. A separate b041 C diagnostic with a 1200-second timeout completed in 694.9 seconds and returned the correct overall verdict, but had three irrelevant citations and 40% selection precision. Keep this diagnostic separate from the full-grid score. Pair accuracy for the six pass/fail pairs was 0/6, 4/6, and 6/6 for A/B/C. Numeric grounding on the 21 benchmark cases with scalar measurements was 0/21, 7/21, and 15/21.

The selection-recall values above are end-to-end: errors count as missed selections. Among accepted benchmark outputs only, B selected 52 of 66 required rule instances (78.8% recall, 100% precision), while C selected 42 of 42 (100% recall and precision). This conditional comparison excludes six B and 17 C benchmark errors, so present it alongside—not instead of—the fixed-denominator and execution-error results.

### Fresh controlled full-grid model outcomes

Three fresh grids were run once on the same 50 benchmark layouts plus six unsupported-scope probes. Accuracy uses the fixed 50-case benchmark denominator. Accepted outputs are counted separately over all 56 records.

| Model | A: accuracy; accepted outputs | B: accuracy; accepted outputs | C: accuracy; accepted outputs | ERROR records |
|---|---|---|---|---:|
| Qwen3 8B | 23/50 (46%); 55/56 | 29/50 (58%); 53/56 | 50/50 (100%); 54/56 | 5 |
| GPT-4o | 29/50 (58%); 56/56 | 27/50 (54%); 56/56 | 50/50 (100%); 56/56 | 0 |
| Gemini 3.5 Flash-Lite | 41/50 (82%); 53/56 | 43/50 (86%); 54/56 | 46/50 (92%); 52/56 | 9 |

The three grids share the same prompt, implementation hashes, public inputs, conditions, and repetition. GPT-4o completed every record. Qwen had three B and two C execution errors; C was otherwise correct on all 50 benchmark verdicts. Gemini had three A HTTP 503s, two B turn-budget failures, and four C protocol failures. Gemini's C accuracy is 46/50 on the fixed benchmark denominator, not 92% of only accepted cases.

The earlier Llama and historical Qwen/GPT runs are retained as exploratory evidence, but they are not pooled with this controlled grid. Their different prompt or implementation hashes and, for Llama, protocol failures prevent a clean cross-run ranking.

## 4. Interpretation

In the fresh three-model run, C produced the strongest fixed-denominator benchmark result for all three models: 100% for Qwen and GPT-4o and 92% for Gemini. Gemini led A and B, but Gemini C had both execution errors and a lower C score than the other two. GPT-4o's C result is 100% with no errors. Qwen's C result is also 100%, with two probe-level C errors rather than benchmark verdict errors. Retrieval, verification, and the DRC tool are combined in C, so these results do not isolate the causal effect of KLayout.

The main operational finding is that tool-grounded verification can improve end-to-end verdict accuracy, while inference availability and model/tool protocol reliability remain important. An ERROR is not a geometric FAIL or a domain REFUSE. These comparisons use only one repetition and include no confidence intervals.

## 5. Limitations and Validity

- The 50 curated layouts and six probes are not representative of a production workload.
- The team had prior exposure to several benchmark cases during debugging and demonstrations; the benchmark is not an untouched holdout. See [Debug and Demonstration Case Disclosure](DEBUG_CASE_DISCLOSURE.md).
- This is not an evaluation against an external OpenROAD/Magic/KLayout test suite. The layouts are project-generated synthetic constructions, although the pinned DRC oracle is the upstream KLayout SKY130 deck.
- The archived labels were audited against KLayout's native report reader, but both use the same engine. This is not an independent foundry oracle.
- The supported geometry and rule catalog are intentionally limited; the checker is not a signoff tool.
- The fresh comparison has one repetition, so the reported proportions have no run-to-run uncertainty estimate.
- The fresh Qwen, GPT-4o, and Gemini grids are controlled for prompt, implementation, inputs, conditions, and repetition; historical grids remain non-comparable.
- A/B outputs are predictions without DRC evidence. C verifies only the selected rules.
- Local hardware and electricity costs were not measured.
- GPT-4o was evaluated using the hosted API; its locally estimated full-run cost was $1.346.
- Gemini was evaluated in a Free-tier project; its locally estimated paid-tier cost was $0.294 and Google billing/usage remains the authoritative source.

## 6. Conclusion and Next Steps

This project demonstrates an LLM workflow in which geometry remains checked by KLayout and accepted explanations are constrained by deterministic evidence. The Qwen3 results suggest that retrieval and verification can improve some measured outcomes; accepted C outputs selected all required rules in this benchmark, but end-to-end errors and the single repetition prevent claims of reliable generalization.

The fresh three-model grids are complete under matching prompt, implementation, inputs, and conditions. Preserve the raw runs and report fixed-denominator accuracies alongside accepted-output counts and errors. A separate 24-layout held-out dataset has been generated, labeled, native-RDB-verified with zero construction mismatches, and evaluated in repeated runs. Do not replace existing records with retries. Wider generalization claims require further independent layouts and oracle evidence.

A first one-repetition local Qwen3 C run on the held-out layouts scored 24/24 benchmark verdicts, 3/3 probe refusals, and 0 execution errors. This is held-out evidence for one model, not a repeated stability study or a cross-model ranking.

Three separate repetitions of held-out Qwen3 C then completed 24/24 benchmark verdicts
in each repetition, with 3/3 refusals and 0 execution ERROR records in every run.
The mean accuracy was 100% with a 100-100% range. This measures repeated stability
for one local model and one held-out set, not a cross-model ranking or independent
foundry signoff.

Matching GPT-4o and Gemini held-out condition-C repetitions were completed on
November 25, 2026. GPT-4o scored 24/24 in all three repetitions and had 0 ERROR
records. Gemini's fixed-denominator benchmark accuracies were 20/24, 14/24, and
15/24. Across all 81 Gemini records, there were 23 execution ERROR records:
22 HTTP 503 failures and one protocol failure. All models refused every held-out
probe correctly in each repetition.

The Gemini adapter was then updated to retry HTTP 503 service-unavailable responses.
In a separate 81-record run, fixed-denominator accuracy was 22/24, 21/24, and 19/24;
there were 13 ERROR records. Of 78 records that encountered a 503, 65 later completed
after retries and 13 exhausted retries. Probe refusals were 1/3, 2/3, and 3/3.
The implementation and provider conditions differ from the original run, so the
change in error counts is not a controlled causal estimate.

A subsequent run with up to eight 503 retries scored 18/24, 0/24, and 0/24, with
0/3 probe refusals in each repetition. All 63 ERROR records were HTTP 429 responses
after the free-tier daily request quota was exhausted. This is a separate
quota-limited run, not evidence that the earlier results should be replaced.

## 7. Reproducibility and Demo

The experiment tables and original traces are stored locally under ignored `runs/experiments/` directories and should be preserved separately from source control. The current benchmark integrity and test check is:

```powershell
python run.py check
```

For a reproducible live demonstration, see [Demo Guide](DEMO_GUIDE.md). It uses the local model by default; no hosted model or paid API is required.
