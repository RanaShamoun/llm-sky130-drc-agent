# DRC Explain

**Team:** Giovanni Cascone and Rana Shamoun

An LLM agent that selects SKY130 design rules, checks chip-layout geometry with KLayout, and explains the result using real evidence.

**Current status:** Giovanni's tools and benchmark are complete. Rana's LLM agent and experiments are next.

## Start here

On the prepared Mac, open a terminal in this folder:

```sh
source .venv/bin/activate
python run.py check
python run.py demo
```

`check` verifies the code and saved benchmark evidence. `demo` checks a real layout: width passes and spacing fails with a **0.135 um gap** against a **0.140 um minimum**.

New machine? Follow [Setup](docs/SETUP.md). Ready to build the agent? Read [Rana's handoff](docs/HANDOFF.md) and [the working example](examples/use_tools.py).

## Completed work

- [x] Pin the KLayout version, upstream rule deck, and layer map.
- [x] Build a checker that rejects failed runs and missing checks.
- [x] Implement rule lookup, layout inspection, and selected-rule DRC tools.
- [x] Log tool inputs, outputs, timestamps, and latency.
- [x] Create 50 benchmark layouts, six development layouts, and six refusal probes.
- [x] Label all 56 layouts using separate full-deck KLayout runs.
- [x] Cross-check saved reports and 41 numeric markers with KLayout's native reader.
- [x] Review 10 cases visually and document the enclosure-rule discrepancy.
- [x] Verify passing/failing examples for all eight supported rules.

**Verified result:** 15 regression tests pass. The benchmark has 24 scoped PASS and 26 scoped FAIL cases. These are checker results; LLM accuracy has not been measured yet.

## Rana's next steps

1. Build the planner, tool calls, answer verification, and refusal behavior.
2. Compare coordinates only, retrieval, and full tools across the chosen models.
3. Calculate accuracy, grounding, citation errors, cost, latency, and tool counts.
4. Finish the minimal demo UI, results analysis, and report.

[The handoff guide](docs/HANDOFF.md) explains the inputs, scoring decisions, and files to create.

## Where everything lives

```text
run.py                 Simple commands for everyday work
src/drc_explain/       Checker, tools, parser, and benchmark code
examples/use_tools.py  Small example to copy into the agent
scripts/               Source setup and verification helpers
tests/                 Automated regression tests
data/                  Pinned rules, layer mappings, and source hashes
eval/public/           Questions, coordinates, and GDS layouts for models
eval/gold/             Private labels and archived oracle evidence
docs/                  Setup, handoff, tool details, and original research
```

Give models only `eval/public/`. Keep `eval/gold/` in the evaluator.

## Everyday commands

| Command | What it does |
|---|---|
| `python run.py check` | Run tests and validate all saved benchmark reports |
| `python run.py demo` | Run a short example using all three tools |
| `python run.py doctor` | Verify the batch executable and pinned sources |
| `python run.py smoke` | Run 16 real-tool checks covering all supported rules |
| `python run.py format` | Sort imports and format the Python code |
| `python run.py generate` | Recreate deterministic benchmark inputs |
| `python run.py label` | Recheck all layouts and rebuild labels/evidence |

After editing code, run `check`. After changing checker behavior, also run `smoke`. After changing benchmark geometry, run `generate`, then `label`, then `check`.

## Scope

V1 supports eight ordinary metal1/metal2 width, spacing, and via-enclosure rules on rectangular geometry. The unchanged full deck executes, then only requested results are returned. A PASS covers those rules only. Passing checks do not provide measured distances; unsupported markers retain their raw evidence. See the [tool contract](docs/TOOL_CONTRACT.md) and [enclosure audit](docs/ENCLOSURE_AUDIT.md) for the details.
