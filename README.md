# DRC Explain

**Team:** Giovanni Cascone and Rana Shamoun
**Course:** CMPE 258 Deep Learning

DRC Explain is a bounded LLM agent for explaining SKY130 layout checks. It retrieves supported design rules, requests geometry checks from KLayout, and submits only structured claims that are verified against tool evidence.

This repository is prepared for instructor review. It contains the implementation, benchmark, automated tests, evidence audit, experiment manifests, course-report draft, demo guide, and progress report.

## Repository status

- Core local Qwen3 8B workflow is implemented and usable without an API key.
- Optional Gemini 3.5 Flash-Lite and OpenAI GPT-4o provider adapters are implemented.
- A/B/C experiment runner supports resumable grids and evaluator-only scoring.
- On November 25, 2026, 117 automated tests passed and 1 platform-specific test was skipped.
- A fresh 168-record grid was completed for each of Qwen3 8B, GPT-4o, and Gemini 3.5 Flash-Lite under matching prompt, implementation, and public-input hashes.

The frozen-grid outcomes are summarized below. Accuracy uses the fixed 50-layout benchmark denominator; probe results and `ERROR` records are reported separately.

| Model | A verdict accuracy | B verdict accuracy | C verdict accuracy | ERROR records |
|---|---:|---:|---:|---:|
| Qwen3 8B | 23/50 (46%) | 29/50 (58%) | 50/50 (100%) | 5 |
| GPT-4o | 29/50 (58%) | 27/50 (54%) | 50/50 (100%) | 0 |
| Gemini 3.5 Flash-Lite | 41/50 (82%) | 43/50 (86%) | 46/50 (92%) | 9 |

The comparison has one repetition and uses a small, previously exposed benchmark. It is not a foundry-signoff study or a substitute for independent held-out layouts. Gemini's 9 errors included HTTP 503, turn-budget, and protocol failures; its 429 retry count was zero. GPT-4o and Gemini API cost values are estimates or held usage ledgers, not proof of final provider billing.

See [Experiment Results](docs/EXPERIMENT_RESULTS.md), [Course Report Draft](docs/COURSE_REPORT_DRAFT.md), and [Demo Guide](docs/DEMO_GUIDE.md).

## Independent held-out workflow

A separate 24-layout held-out set has been generated and labeled with zero construction/oracle mismatches. It is kept outside the original 56-case public and gold benchmark:

- Public layouts and questions: `eval/public/heldout/`
- Private labels and oracle archive: `eval/gold/heldout/`
- Dataset documentation: [Held-Out Evaluation](docs/HELDOUT_EVALUATION.md)

Generate and label the held-out set:

```powershell
.\.venv\Scripts\python.exe run.py generate-heldout
.\.venv\Scripts\python.exe run.py label-heldout
.\.venv\Scripts\python.exe scripts\verify_heldout.py
```

Run the held-out grid on one repetition:

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

For stronger evidence, add `--repetitions 3` and run each model in a separate, newly named output directory. Keep all original `ERROR` records, because they are part of end-to-end reliability. `--heldout` also changes the experiment's public/cases/gold manifest paths, and the held-out labels are private to the evaluator.

## Benchmark scope and external suites

The benchmark is not derived from a standard open-source SKY130/OpenROAD DRC suite. It is a project-constructed collection of synthetic rectangular layouts plus unsupported-scope probes. Oracle labels come from the pinned upstream KLayout SKY130 DRC deck in `data/sources.lock.json`, but that deck is not a complete installed fabrication PDK and the project does not claim external tape-out signoff. The 24-layout held-out set is mechanically independent from the original public development cases, but it is generated and labeled with the same geometry builder and same KLayout oracle. It therefore provides stronger generalization evidence than the exposed benchmark, not independent oracle or foundry validation.

## Quick start

### Windows

```powershell
.\.venv\Scripts\python.exe run.py doctor
.\.venv\Scripts\python.exe run.py check
.\.venv\Scripts\python.exe run.py demo
```

For live local inference:

```powershell
.\.venv\Scripts\python.exe run.py pull-local
.\.venv\Scripts\python.exe run.py agent --gds benchmark/b004.gds `
  --question "Check ordinary width and spacing of metal1 routing."
```

### macOS/Linux

```sh
source .venv/bin/activate
python run.py doctor
python run.py check
python run.py demo
python run.py pull-local
python run.py agent --gds benchmark/b004.gds
```

`b004` is a known demonstration layout. It has a 0.135 um metal1 spacing result against a 0.140 um limit.

## Project structure

```text
run.py                 Everyday commands
src/drc_explain/       Agent, provider adapters, KLayout tools, verifier, UI, and scoring
scripts/               Setup and benchmark verification helpers
tests/                 Automated unit and integration tests
data/                  Pinned sources, rules, layers, and deck hashes
eval/public/           Layouts and public questions
eval/gold/             Private labels and oracle evidence
docs/                  Setup, handoff, report, validation, and demo documents
runs/                  Generated agent and experiment records, ignored by Git
```

Give models only `eval/public/`. Keep `eval/gold/` in the evaluator.

## Web demo

```powershell
.\.venv\Scripts\python.exe run.py ui --port 8765
```

Open `http://127.0.0.1:8765`. The UI shows layout geometry, the selected layout, model response, deterministic verdict, sources, and tool trace. Local inference can take several minutes.

Do not run UI demonstrations while a cloud or local experiment is active.

## Evaluation commands

```powershell
# Run tests and verify saved benchmark evidence
.\.venv\Scripts\python.exe run.py check

# Run scripted agent integration checks
.\.venv\Scripts\python.exe run.py agent-smoke

# Run tool coverage across supported rules
.\.venv\Scripts\python.exe run.py smoke

# Score an existing experiment without model inference
.\.venv\Scripts\python.exe run.py experiments score `
  --output runs\experiments\final-comparison-gpt4o-20261121
```

Full grids are expensive and should only be rerun intentionally. The current fresh results are preserved under:

- `runs/experiments/final-comparison-qwen3-20261121/`
- `runs/experiments/final-comparison-gpt4o-20261121/`
- `runs/experiments/final-comparison-gemini35-20261121/`

These directories are ignored by Git. Preserve or archive them separately when submitting or sharing the repository.

## Progress report

The submission-ready progress report can be regenerated from the project script:

```powershell
.\.venv\Scripts\python.exe scripts\generate_progress_report.py
```

This produces:

- `DRC_Explain_Progress_Report.docx`
- `DRC_Explain_Progress_Report.pdf`

The report summarizes completed work, the three-model frozen-grid results, limitations, and specific questions for professor feedback.

## Hosted-provider setup

Hosted providers are opt-in:

```powershell
.\.venv\Scripts\python.exe run.py configure openai
.\.venv\Scripts\python.exe run.py configure gemini
```

Configure keys interactively. Credentials remain in the ignored `.env` file and should never be pasted into chat, traces, source control, or submission documents.

Gemini uses `gemini-3.5-flash-lite` in the implementation default. Existing `.env` values are preserved. GPT-4o and Gemini experiment runs require explicit application estimate caps:

```powershell
--api-budget-usd 5
--api-budget-usd 2
```

These are runner-side estimate guards, not guaranteed billing caps. Provider account dashboards and billing settings are authoritative.

## Scope and limitations

The implementation currently supports eight curated ordinary metal1/metal2 width, spacing, and via-enclosure rules. It supports limited rectangular geometry and does not provide full-chip signoff.

Important limitations:

- The benchmark is small and contains previously exposed team-development cases.
- The oracle and implementation use the same KLayout engine.
- A/B outputs are unverified coordinate/retrieval predictions.
- C outputs are constrained by deterministic verification but cover only selected rules.
- One repetition was used, so run-to-run uncertainty is not estimated.
- `ERROR` is separate from PASS/FAIL/REFUSE and remains visible in all accuracy denominators.

See [Tool Contract](docs/TOOL_CONTRACT.md), [Enclosure Audit](docs/ENCLOSURE_AUDIT.md), and [Debug Case Disclosure](docs/DEBUG_CASE_DISCLOSURE.md).

## Development commands

```powershell
.\.venv\Scripts\python.exe run.py format
.\.venv\Scripts\python.exe run.py generate
.\.venv\Scripts\python.exe run.py label
.\.venv\Scripts\python.exe run.py check
```

After editing code, run `check`. After changing checker behavior, run `smoke` too. After changing benchmark geometry, run `generate`, `label`, and `check`.
