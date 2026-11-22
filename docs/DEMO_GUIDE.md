# Demo Guide

This guide prepares a short demonstration of the DRC Explain workflow. The deterministic demo does not depend on the model-comparison runs and makes no hosted API calls.

## Before the presentation

From PowerShell at the repository root, confirm that the pinned checker sources and standalone KLayout executable are available:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
```

For a deterministic tool demonstration, run:

```powershell
.\.venv\Scripts\python.exe run.py demo
```

This example retrieves metal1 rules, inspects `b004`, and requests width and spacing checks. It does not call an LLM. Confirm Ollama and its local `qwen3:8b` model are available only if demonstrating live inference; no paid-provider fallback is used.

## Suggested five-minute flow

1. **Frame the problem (30 seconds).** Explain that DRC checks layout geometry against manufacturing constraints and that the model does not replace the checker.
2. **State the boundary (30 seconds).** The prototype supports eight curated width, spacing, and via-enclosure rules on limited rectangular metal/via geometry. It is not full-chip signoff.
3. **Show rule retrieval (45 seconds).** Point out that a question such as metal1 spacing retrieves a supported rule ID, its numeric limit, and a source.
4. **Show geometry and DRC evidence (90 seconds).** In the deterministic demo, show that `b004` has a 0.135 um spacing violation against a 0.140 um minimum. The tool output is scoped to the requested rules.
5. **Explain verification (60 seconds).** The agent's final answer must match the DRC status, threshold, and available measurements. Passing checks do not have measured passing distances; unavailable scalar markers are not guessed.
6. **Summarize evaluation honestly (60 seconds).** The fresh frozen-grid comparison used 56 inputs per model and one repetition. A/B/C verdict accuracies were Qwen 46%/58%/100%, GPT-4o 58%/54%/100%, and Gemini 82%/86%/92%. Report the 5 Qwen and 9 Gemini execution errors, GPT-4o's zero errors, the prior-case exposure, and the same-engine oracle limitation. These results are not evidence of independent foundry signoff or run-to-run uncertainty. See [Experiment Results](EXPERIMENT_RESULTS.md).
7. **Close on next evidence (30 seconds).** The full grids are complete. The next useful validation is a repeated run on independent layouts or a separate held-out test set, not another retry over the same benchmark.

## Optional live-agent demonstration

If there is enough time and the local model is already responsive, run:

```powershell
.\.venv\Scripts\python.exe run.py agent --gds benchmark/b004.gds --question "Check ordinary width and spacing of metal1 routing."
```

Local model inference can take several minutes, especially on cold start. Treat the response as a live illustration, not additional benchmark evidence. If it returns ERROR, explain that an execution error is not a geometric FAIL; use the deterministic `run.py demo` instead of retrying repeatedly.

The local UI can also be shown with:

```powershell
.\.venv\Scripts\python.exe run.py ui --port 8765
```

Open `http://127.0.0.1:8765` in a browser. Keep the server running in its terminal and do not submit UI checks while another experiment is active.

## Presentation checklist

- [ ] Run `doctor` and the deterministic demo before recording.
- [ ] Keep evaluator-only `eval/gold/` out of model-facing material.
- [ ] Describe `b004` as a known demonstration case, not an untouched test.
- [ ] Distinguish tool-backed C results from unverified A/B predictions.
- [ ] Say that a PASS covers selected rules only, not the whole layout or tape-out.
- [ ] Present the fresh model grids with fixed denominators and accepted/error counts; keep earlier historical grids separate.
- [ ] Do not show credentials, local environment files, or secret values.
