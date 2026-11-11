# Rana's handoff

The tools, benchmark, and LLM agent code are implemented. Your part is evaluation/scoring, model comparisons, the minimal UI, and report. The default provider is now a free local model; follow [Local setup](LOCAL_MODEL.md) and [Agent details](AGENT.md). No paid API credits are required. Start with `python run.py demo`, then open [examples/use_tools.py](../examples/use_tools.py).

## 1. Reproduce the agent

Follow [Agent setup](AGENT.md), set up the local model, then run:

```sh
python run.py agent --gds benchmark/b004.gds --question "Check ordinary width and spacing of metal1 routing."
```

The implementation is in `src/drc_explain/agent.py`, `local_provider.py`, and `verification.py`. Use `Agent(OllamaClient()).run(question, gds_path)` from your experiment runner. Do not rebuild the planner or tool dispatch. Each run saves its result, token usage, model IDs, response IDs, prompt hash, latency, and traces under `runs/agent/`.

The final explanation is rendered from evidence-verified structured model claims. It does not freely paraphrase arbitrary model prose. Rule-selection completeness, selection justifications, and refusal correctness still require evaluation. Read the limitations in `AGENT.md` before writing the report.

The DRC tool executes the unchanged full deck and filters results afterward. Report this accurately. Keep ERROR separate from REFUSE and domain PASS/FAIL.

## 2. Keep inputs and answers separate

| File | How to use it |
|---|---|
| `eval/public/cases.json` | Questions, GDS paths, and coordinate dumps. Score only `split == "benchmark"` |
| `eval/public/benchmark/` | 50 test layouts |
| `eval/public/development/` | Six separate examples for prompt development |
| `eval/public/probes.json` | Six unsupported-scope questions; score separately |
| `eval/gold/labels.json` | Evaluator-only relevant rules, statuses, pair IDs, and evidence |
| `eval/gold/oracle_reports.zip` | Original full-deck reports/logs/results for audit |

Give models the same base question and coordinates in all conditions. Never pass gold labels, construction notes, case types, or pair membership into the model. The tool path boundary restricts GDS access to the public root; do not expose arbitrary file or shell access that can bypass it.

## 3. Run the experiments

Suggested new files: `src/drc_explain/experiments.py` and `src/drc_explain/scoring.py`.

Compare A: coordinates only; B: coordinates plus retrieval; C: full tools. Pin the model IDs and prompts. The original proposal compares one open-weights and two closed models. This local demo provides the open-weights route; agree on free access or an approved change for the other models. The full initial grid is 450 queries; three total C runs per model gives 750 before refusal probes. Budget fallback: A/B/C on one model and C on the other two.

Collect verdict and pair accuracy, rule-selection precision/recall, citation errors, grounding, refusal correctness, API cost, latency, and tool-call count. Keep raw outputs and traces in `runs/`, which is ignored by Git. Save the final aggregate results separately for the report.

Scoring details:

- Use the relevant-rule `verdict`, not `full_deck_verdict`. Unrelated violations are retained for audit.
- Compare selections to `relevant_rule_ids`, including applicable passing rules. Pair accuracy uses the six `pair_id` groups.
- Numeric measurements exist only for supported edge-pair violation markers. Passing checks and polygon/corner markers do not provide scalar distances. Report measurement availability and numeric grounding on eligible cases, plus evidence/verdict correctness on every case. Never invent a passing measurement or let tolerance excuse a wrong threshold verdict.
- The supported eight rules are in `data/rules.json`. `data/deck_categories.json` indexes 262 static deck IDs for citation auditing. An existing but unsupported ID is not automatically fabricated; numeric limits also need the correct applicability.
- Read [the enclosure audit](ENCLOSURE_AUDIT.md). The benchmark measures agreement with the pinned deck, not every possible interpretation of foundry text.

## 4. Finish and verify

Build the minimal input/trace/verdict UI, compare the model results and failure cases, and complete the report and course deliverables. The original research and Windows spike are under `docs/research/`.

Run `python run.py check` after code changes and `python run.py smoke` after checker changes. The current baseline has 55 passing tests, 56 validated layouts, 41 cross-checked numeric markers, and 16 real-tool smoke checks. Five scripted agent scenarios also pass against the real engine. Separately, four real Qwen3 local-model acceptance examples pass; see `eval/gold/local_agent_acceptance.json` and `local_agent_traces.zip`. Rejected integration attempts are preserved. Those demonstration cases were used for debugging, so do not present them as untouched evaluation data. Ten layouts were visually inspected by the coding agent; do not describe that as independent human signoff.
