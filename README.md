# DRC Explain

**Team:** Giovanni Cascone and Rana Shamoun

An LLM agent that selects SKY130 design rules, checks chip-layout geometry with KLayout, and explains the result using real evidence.

**Current status:** Tools, benchmark, a free local LLM agent, a minimal local UI, and an A/B/C experiment runner with scoring are implemented. Windows setup has produced verified live width FAIL and PASS demonstrations. The saved six-query pilot, full model comparisons, results analysis, and final report remain pending.

## Start here

On the prepared Mac, open a terminal in this folder:

```sh
source .venv/bin/activate
python run.py check
python run.py agent --gds benchmark/b004.gds
```

`check` verifies the code and saved benchmark evidence. `agent` uses the local model to select and check rules; this test layout has an intended spacing failure. The separate tool-only `demo` command shows: width passes and spacing fails with a **0.135 um gap** against a **0.140 um minimum**.

New machine? Follow [Setup](docs/SETUP.md). For the free model, follow [Local setup](docs/LOCAL_MODEL.md) and [Agent details](docs/AGENT.md). For evaluation, read [Rana's handoff](docs/HANDOFF.md) and [the working example](examples/use_tools.py).

Before committing or running experiments, read [Understanding our work](docs/PROJECT_WALKTHROUGH.md) for changes, verified evidence, limitations, and pre-commit findings. Read the [file-by-file guide](docs/FILE_GUIDE.md) for a plain-language explanation of each module, script, data file, and document.

### Windows local UI

After installing dependencies, Ollama with `qwen3:8b`, the pinned sources, and KLayout 0.30.13:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
.\.venv\Scripts\python.exe run.py ui --port 8765
```

Use your actual KLayout executable path if different. Open http://127.0.0.1:8765 and keep the server terminal running. Local inference can take several minutes. Do not submit UI checks while a separate experiment is running.

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
- [x] Implement the local model agent, bounded tool loop, claim verification, and refusal path.
- [x] Verify five scripted agent scenarios with the real checker (not LLM accuracy).
- [x] Verify real local inference: spacing FAIL/PASS, corner-enclosure FAIL, and antenna REFUSE.
- [x] Add evaluator-only scoring and a resumable local-model A/B/C runner.
- [x] Add a local UI with layout geometry, verified verdict, sources, and tool trace.
- [x] Reproduce pinned source setup and live width demonstrations on Windows.

**Evidence status:** On November 11, 2026, the focused tests passed 17/17; the full Windows suite passed 70 tests with two known permission/symlink failures. The archived audit passed for all 56 layouts and cross-checked 41 numeric markers. See [pre-commit validation](docs/PRECOMMIT_VALIDATION.md) for exact commands and remaining coverage limitations. The benchmark has 24 scoped PASS and 26 scoped FAIL cases; these are oracle labels, not model accuracy. The full LLM benchmark has not been evaluated yet. The original handoff's 55 passing tests and four accepted live examples are historical evidence.

## Rana's next steps

1. Review the learning guides and [debug-case disclosure](docs/DEBUG_CASE_DISCLOSURE.md). The encoding fix and known Windows demonstration disclosure are complete; b001 and b002 are previously inspected cases.
2. Review the [completed validation](docs/PRECOMMIT_VALIDATION.md), including its two platform failures, and commit a reproducible implementation checkpoint; then run the six-query smoke pilot below.
3. Run A/B/C across the approved model mix and inspect saved metrics, traces, and failures.
4. Finish results analysis, final report, and demo recording; disclose setup/debug cases.

[The handoff guide](docs/HANDOFF.md) describes the original task list. The [walkthrough](docs/PROJECT_WALKTHROUGH.md) explains the current implementation and remaining work.

### Six-query smoke pilot

From a terminal with `KLAYOUT_BIN` configured and Ollama running:

```powershell
.\.venv\Scripts\python.exe run.py experiments run --models qwen3:8b --conditions A B C --cases b001 b002 --no-probes --output runs/experiments/pilot
```

A predicts from coordinates without retrieval or DRC. B adds rule retrieval. C uses the existing agent with retrieval, KLayout, and deterministic verification. Two cases times three conditions equals six queries. The runner currently accepts benchmark cases and probes, not development cases; this pilot is a smoke test, not development-only prompt tuning or untouched evaluation.

The runner saves records, traces, a manifest, metrics, and a readable results table under the selected output directory. Resume with the identical command and unchanged code/model/options. Existing records, including ERROR records, are skipped. C also adds verification, so this is a system ablation rather than an isolated KLayout-only comparison.

After the pilot is reviewed, the default one-model grid has 50 layouts plus six probes under A/B/C: 168 queries. It does not by itself satisfy the original three-model proposal; agree on any model-mix changes before final evaluation. See the walkthrough for full-run, scoring, and evidence-preservation instructions.

## Where everything lives

```text
run.py                 Simple commands for everyday work
src/drc_explain/       Agent, checker, tools, benchmark, scoring, experiments, and UI
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
| `python run.py pull-local` | Download the free local model once |
| `python run.py agent --gds benchmark/b004.gds` | Run the real local LLM agent; no paid API |
| `python run.py ui --port 8765` | Start the local layout/trace/verdict UI |
| `python run.py experiments run --help` | Show local-model A/B/C grid options |
| `python run.py experiments score --output runs/experiments/pilot` | Score saved pilot records without model inference |
| `python run.py agent-smoke` | Run five explicitly scripted agent integration checks |
| `python run.py demo` | Run a short example using all three tools |
| `python run.py doctor` | Verify the batch executable and pinned sources |
| `python run.py smoke` | Run 16 real-tool checks covering all supported rules |
| `python run.py format` | Sort imports and format the Python code |
| `python run.py generate` | Recreate deterministic benchmark inputs |
| `python run.py label` | Recheck all layouts and rebuild labels/evidence |

After editing code, run `check`. After changing checker behavior, also run `smoke`. After changing benchmark geometry, run `generate`, then `label`, then `check`.

## Scope

V1 supports eight ordinary metal1/metal2 width, spacing, and via-enclosure rules on rectangular geometry. The unchanged full deck executes, then only requested results are returned. A PASS covers those rules only. Passing checks do not provide measured distances; unsupported markers retain their raw evidence. See the [tool contract](docs/TOOL_CONTRACT.md) and [enclosure audit](docs/ENCLOSURE_AUDIT.md) for the details.
