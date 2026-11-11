# Rana's handoff

Giovanni's tools and benchmark are complete. Your part is the LLM agent, experiments, minimal UI, and report. Start with `python run.py demo`, then open [examples/use_tools.py](../examples/use_tools.py).

## 1. Connect the agent to the tools

Suggested new file: `src/drc_explain/agent.py`.

```python
from drc_explain.tools import Toolset, TOOL_SCHEMAS

tools = Toolset(log_path="runs/model_case_tool_calls.jsonl")
answer = tools.call("run_drc", {
    "gds_path": "benchmark/b004.gds",
    "rule_ids": ["m1.1", "m1.2"],
})
```

Register `TOOL_SCHEMAS` using the selected model provider's function-calling format. The three tools are `retrieve_rules`, `inspect_layout`, and `run_drc`. Every response has `ok: true` and a result, or `ok: false`, an error, and no verdict. Use a separate trace log for each query/run.

Build a planner to choose relevant rules, dispatch calls through `Toolset.call`, and verify the final answer against the returned evidence. Refuse unsupported questions and failed checks. A passing result must state which rules were checked.

The DRC tool executes the unchanged full deck and filters results afterward. It does not selectively execute checks or read cached labels. Report this behavior accurately.

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

Compare A: coordinates only; B: coordinates plus retrieval; C: full tools. Pin the model IDs and prompts. The full initial grid is 450 queries; three total C runs per model gives 750 before refusal probes. Budget fallback: A/B/C on one model and C on the other two.

Collect verdict and pair accuracy, rule-selection precision/recall, citation errors, grounding, refusal correctness, API cost, latency, and tool-call count. Keep raw outputs and traces in `runs/`, which is ignored by Git. Save the final aggregate results separately for the report.

Scoring details:

- Use the relevant-rule `verdict`, not `full_deck_verdict`. Unrelated violations are retained for audit.
- Compare selections to `relevant_rule_ids`, including applicable passing rules. Pair accuracy uses the six `pair_id` groups.
- Numeric measurements exist only for supported edge-pair violation markers. Passing checks and polygon/corner markers do not provide scalar distances. Report measurement availability and numeric grounding on eligible cases, plus evidence/verdict correctness on every case. Never invent a passing measurement or let tolerance excuse a wrong threshold verdict.
- The supported eight rules are in `data/rules.json`. `data/deck_categories.json` indexes 262 static deck IDs for citation auditing. An existing but unsupported ID is not automatically fabricated; numeric limits also need the correct applicability.
- Read [the enclosure audit](ENCLOSURE_AUDIT.md). The benchmark measures agreement with the pinned deck, not every possible interpretation of foundry text.

## 4. Finish and verify

Build the minimal input/trace/verdict UI, compare the model results and failure cases, and complete the report and course deliverables. The original research and Windows spike are under `docs/research/`.

Run `python run.py check` after code changes and `python run.py smoke` after checker changes. The current baseline has 15 passing tests, 56 validated layouts, 41 cross-checked numeric markers, and 16 real-tool smoke checks. Ten layouts were visually inspected by the coding agent; do not describe that as independent human signoff.
