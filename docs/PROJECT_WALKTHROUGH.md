# Understanding Our Work Before Commit and Evaluation

Read this first, then read the [file-by-file guide](FILE_GUIDE.md). This is a learning and status document, not a claim that the final benchmark is complete.

## 1. What This Project Is Trying to Do

An integrated-circuit layout is a drawing of physical shapes on manufacturing layers. A GDS file stores those shapes. SKY130 is an open semiconductor process with rules that say how wide shapes must be, how far apart they must be, and how much metal must surround a via.

DRC means Design Rule Checking. KLayout is the trusted geometry checker in this project. Qwen is the language model that interprets the engineering question, retrieves rules, chooses what to check, and submits an answer. Qwen does not replace KLayout or generate a new checker.

Our supported categories are width, spacing, and enclosure. The supported catalog contains eight rules for ordinary rectangular metal1/metal2 routing and square 0.15 um vias. It is not a full-chip certification service.

## 2. Why the Professor's Feedback Matters

If the model receives a finished DRC report with the violation ID already supplied, it might only translate the report. The more substantial task is choosing relevant rules from the question and layout before asking for geometric verification.

The existing agent already performs that task. The new evaluator asks whether its selections are complete and relevant, not just whether its explanation sounds correct.

The primary comparison is now:

| Condition | Information and tools | Meaning of the answer |
|---|---|---|
| A | Question, coordinates, and the model's prior rule knowledge; no retrieval or DRC | Unverified prediction |
| B | Same public input, plus rule retrieval; no DRC | Unverified prediction informed by retrieved rules |
| C | Existing agent with inspection, retrieval, KLayout, and deterministic verification | Answer checked against actual tool evidence |

All conditions receive the same base question and coordinate content. A/B use the saved public coordinate dump; C re-inspects the public GDS file. The experiment verifies the public GDS hashes before running.

C also adds answer verification and verified explanation rendering. Therefore this is a system ablation, not a perfectly isolated test of KLayout alone. State that in the report.

One local model across A/B/C does not fulfill the proposal's original three-model comparison by itself. Any change to the open/closed model mix needs agreement and transparent reporting. The current experiment runner supports local Ollama models, not a three-provider grid.

## 3. What Was Already Built Before This Session

The handoff supplied the bounded agent, provider adapters, three logged tools, strict report parsing, evidence verifier, pinned source catalog, 50 benchmark GDS layouts, six development layouts, and six unsupported-scope probes.

It also supplied archived oracle evidence and previous test/acceptance records. We did not rebuild the planner, replace the rule deck, invent gold labels, or redesign the benchmark.

The earlier acceptance records are historical integration evidence. Their reported test counts should not be confused with the current checkout's test counts or new benchmark accuracy.

## 4. What We Added or Changed

| File or area | What changed | Why |
|---|---|---|
| [scoring.py](../src/drc_explain/scoring.py) | Added per-case and aggregate evaluation | Compare answers with evaluator-only gold labels |
| [experiments.py](../src/drc_explain/experiments.py) | Added A/B/C runs, evidence saving, model pins, progress, and resume checks | Run a reproducible comparison instead of manually copying UI results |
| [ui.py](../src/drc_explain/ui.py) | Added a loopback web server around the existing agent | Provide a small usable demo without rebuilding agent logic |
| [web files](FILE_GUIDE.md#web-interface-files) | Added question selection, geometry canvas, verdict, sources, metrics, and trace | Make the agent's behavior visible |
| [run.py](../run.py) | Added `experiments` and `ui`; passed local source path to child processes | Make new commands run from the repository |
| [pyproject.toml](../pyproject.toml) | Included web assets in package data | Keep HTML/CSS/JS when packaging |
| [bootstrap_sources.py](../scripts/bootstrap_sources.py) | Preserved LF source bytes in the generated Windows checkout | Make source hashes match the unchanged upstream files |
| [new tests](FILE_GUIDE.md#test-files) | Added experiment restrictions, scoring edge cases, and UI dispatch tests | Catch mistakes without paying for live inference |
| [deck_categories.json](../data/deck_categories.json) | Regenerated during setup | This exposed an encoding issue described below; it is not an intentional rule change |

The proposal and handoff text files were provided as context. An untracked Git status does not mean we authored their content. The VS Code task configuration is a development convenience, not part of the model.

## 5. Windows Setup and the Problems We Solved

### Python

An initial attempt used system Python 3.14 and failed because `pytest` was absent. Dependencies were installed, but later checks showed an existing project Python 3.12 virtual environment was the appropriate working environment. We selected and used that environment.

Use `.\.venv\Scripts\python.exe` for reproducible local commands. Selecting Python in VS Code does not guarantee that a bare `python` in every terminal selects the same interpreter.

### Ollama and Qwen

Installing Ollama installed the runtime, not the model weights. Its account signup was optional; you chose local use. You then downloaded `qwen3:8b`, about 5.2 GB.

We checked the server's installed-model list and confirmed that the weights digest matches the project lock. Model identity is more precise than a name alone: a digest fingerprints the downloaded weights.

The running local server is on `127.0.0.1:11434`. The project does not automatically fall back to a paid cloud model. The optional OpenAI adapter is separate and is not used by the current local experiment runner.

### SKY130 Sources

The first real run could retrieve rules but could not check geometry because the pinned deck files were absent. Fetching the correct revision then failed hash verification: Windows Git converted LF line endings to CRLF.

The bootstrap now checks that its generated source checkout has no edits, disables automatic line-ending conversion there, recreates the locked files from the Git index, and verifies their SHA256 hashes. It does not lower the hash requirements or edit the deck's logic.

### Standalone KLayout

The Python `klayout` wheel can inspect GDS and reports. The standalone application with Ruby support is needed to execute the manufacturing deck. Those are two different installations, with different pinned versions.

You installed KLayout 0.30.13 and set:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
```

Your `doctor` output confirmed the application version, source revision, deck hash, and layer-map hash. Start the UI or experiments from a terminal with this setting; a different terminal does not inherit it automatically.

### UI States

`Pending` means no answer has been accepted yet. `Busy` means another UI request owns the one-run-at-a-time lock. `ERROR` means execution failed; it is not a geometric FAIL or a domain REFUSE.

The UI now shows elapsed seconds while waiting and does not call a busy response a geometric error. Refreshing the browser does not cancel the server's in-progress request. The UI lock protects that UI server only; it does not coordinate separately launched experiments. Avoid simultaneous UI checks and experiments.

## 6. A Successful Query, Step by Step

For your width demonstration:

1. The browser submits the selected public case ID and your question.
2. The server maps that ID to an allowed public GDS path.
3. The agent inspects the GDS and sends the coordinates and question to Qwen.
4. Qwen asks for relevant SKY130 rule text.
5. Qwen chooses `m1.1` and calls `run_drc` for that rule.
6. KLayout executes the full unchanged deck. The wrapper filters the report to the chosen rules.
7. Qwen submits structured claims using `finalize_answer`.
8. The verifier checks rule IDs, status, limits, evidence call ID, measurements, and layout hash against the current run's evidence.
9. Accepted facts are rendered into the final explanation and saved with traces.

The full deck runs internally, but its complete report is not simply handed to Qwen before selection. A PASS only covers selected rules. Unselected rules may still fail.

`finalize_answer` is a submission function, not a fourth external geometry/retrieval tool. Your three counted tool calls were inspection, retrieval, and DRC. Multiple retrievals or DRC calls can increase that count on other queries.

## 7. What We Have Actually Verified

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Source setup succeeded | Pinned deck and layer-map bytes match | Agent benchmark accuracy |
| Your `doctor` succeeded | Standalone KLayout version and pins match | Every live checker scenario works |
| Archived benchmark verification reported 56 valid layouts | Saved labels/reports and public geometry passed the audit checks | New-model performance on those layouts |
| Focused tests passed during development | The tested code paths behave as asserted | Every untested path or all platform behavior |
| Browser simulated-busy check passed | Overlapping-request state displays Busy/Pending | A real new inference result |
| Your b001 FAIL, 345.576846 s | Verified `m1.1` FAIL; 0.135 um measured versus 0.14 um minimum | Accuracy over 50 cases |
| Your b002 PASS, 313.488256 s | Saved result confirms b002; accepted PASS with no invented passing measurement | Accuracy over 50 cases |

These live demonstrations cost $0 in API charges. Hardware, electricity, and time are not free and have not been priced.

Pre-commit validation on November 11, 2026, confirmed 17 focused tests passing and 70 full-suite tests passing with the same two Windows permission/symlink failures. The archived audit passed all 56 layouts and 41 numeric marker cross-checks. The failures were not silently corrected or declared passing; see [the validation record](PRECOMMIT_VALIDATION.md) for their exact scope and unverified security coverage.

No six-query experiment or 168-query experiment has been established as complete in this walkthrough. There are no final comparative accuracy tables yet.

## 8. Important Pre-Commit Findings

### Category-index encoding issue (resolved)

Reviewing the actual Git diff showed that some area-unit strings in [deck_categories.json](../data/deck_categories.json) changed from JSON `\u00b2` to `\u00c2\u00b2`. That was text decoding corruption, not a new manufacturing rule.

On November 11, 2026, we changed the catalog builder to `deck.read_text(encoding="utf-8")` and regenerated both catalogs. Executable checks confirmed 11 repaired descriptions, all 262 category IDs unchanged, the supported rule catalog unchanged byte for byte, model/source pins unchanged, and upstream source hashes still valid. The regenerated category data equals the committed reference; its unintended diff is gone.

### Debug and pilot disclosure

The saved second PASS result identifies `b002`. Future experiment manifests now record the accepted Windows `b001` FAIL and `b002` PASS, four earlier b001 ERROR attempts, and the historical accepted examples `b004`, `b005`, `b039`, and `o002`. The [debug-case disclosure](DEBUG_CASE_DISCLOSURE.md) records evidence references, fingerprints, and report wording. These fields are output metadata, not model inputs or new experiment observations. The list is not an exhaustive audit of historical test exposure.

The current runner accepts benchmark cases and probes, but not the six development cases. Therefore the proposed `b001`/`b002` pilot is a pipeline smoke test, not a development-only prompt-tuning exercise. Do not tune on those gold labels or present the later benchmark as wholly untouched.

### Metric interpretation

The aggregate `grounding_rate` means structured claims agree with oracle labels and available measurements. A/B can score well by prediction, but they still have no live DRC evidence. It is not an audit of every sentence of free-form reasoning, every URL, or model selection justification.

The C verifier establishes fidelity to chosen tool results. It does not prove that the model selected every relevant rule. That is why selection recall is separately scored.

The manifest fingerprints selected implementation files, prompts, public inputs, and model metadata. It does not currently embed the Git commit hash or fingerprint every dependency, scoring file, and source configuration. Record the commit hash and environment separately. Keep the working tree fixed during inference.

## 9. How to Read the Scores

| Metric | Easy meaning |
|---|---|
| Verdict accuracy | How often PASS/FAIL matches the relevant-rule oracle verdict |
| Pair accuracy | Whether all members of each expected paired group get the correct verdict |
| Selection precision | Of the selected rules, how many were relevant? |
| Selection recall | Of all relevant rules, how many did the model select? |
| Exact selection accuracy | Did it select exactly the relevant set without duplicate selections? |
| Grounding rate | Do verdict, complete selections, per-rule status, limits, and available numeric values agree? |
| Numeric grounding rate | On cases with scalar oracle distances, did the predicted/reported distances match? |
| Refusal correctness | Did unsupported probes receive REFUSE without geometric claims and with a reason? |
| Citation error counts | Invented, unsupported, irrelevant rule IDs, wrong limits, duplicates, or unavailable measurement claims |
| Mean latency / p95 | Average duration / the slower-end 95th-percentile duration |
| Tool calls | Number of external tool calls; not identical workloads across A/B/C |

For example, selecting one correct rule out of two required rules gives perfect precision but only half recall. A seemingly correct PASS could still miss the rule that actually fails.

Passing checks and some corner/polygon markers have no scalar DRC distance. Their numeric-grounding metric is not applicable. `None` in Python becomes `null` in JSON and `N/A` in the table; it does not mean zero accuracy.

Missing results remain in accuracy denominators. Saved ERROR records count as completed execution records but not correct domain verdicts. Runtime statistics use recorded results, not missing runs.

## 10. Commit and Run Checklist

The catalog encoding issue is fixed. Before commit, complete the debug-case disclosure, understand the changed files, and run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py tests/test_scoring.py tests/test_ui.py -q
git diff --stat
git diff --check
```

Also run the full check and distinguish known platform failures from newly introduced failures. `run.py check` stops at failed pytest execution, so verify archived reports separately if needed:

```powershell
.\.venv\Scripts\python.exe run.py check
.\.venv\Scripts\python.exe scripts/verify_benchmark.py
```

Review/stage files intentionally. Do not blindly stage credentials, weights, local environment files, or all runtime outputs. The new guides can be included with the implementation commit. We have not committed on your behalf.

After committing, record `git rev-parse HEAD`. Keep the same code/model/options throughout a run and resume.

### Six-query smoke pilot

In a new terminal at the repository root, while Ollama is running:

```powershell
$env:KLAYOUT_BIN = "$env:APPDATA\KLayout\klayout_app.exe"
.\.venv\Scripts\python.exe run.py doctor
.\.venv\Scripts\python.exe run.py experiments run --models qwen3:8b --conditions A B C --cases b001 b002 --no-probes --output runs/experiments/pilot
```

Two cases times three conditions times one model times one repetition equals six queries. `--no-probes` excludes refusal probes. The runner rotates condition order by case; it does not always run all A cases first.

Progress prints after each completed or skipped record. A quiet terminal during a query does not by itself mean a hang. Baseline traces are written when that query finishes; C logs model/tool events as it proceeds.

Read the generated `results.md` and inspect any ERROR record before launching the full grid. A pilot is useful even if A/B answers are wrong: its first purpose is verifying execution, storage, scoring, and restrictions.

### Full one-model experiment

```powershell
.\.venv\Scripts\python.exe run.py experiments run --models qwen3:8b --conditions A B C --output runs/experiments/qwen3-main
```

Fifty layouts plus six probes, times three conditions, equals 168 queries. This is one model, not the proposal's three-model comparison. Runtime may be many hours; the two UI demos are not enough to accurately predict all conditions and case types.

### Resume and score

Ctrl+C interrupts execution; it is not a graceful geometric refusal. Rerun the identical command to resume. Existing `record.json` files are skipped, including ERROR records. An unfinished query without a record can run again. Preserve evidence rather than deleting inconvenient failures to improve scores.

To score already saved results without making model calls:

```powershell
.\.venv\Scripts\python.exe run.py experiments score --output runs/experiments/pilot
```

Resume refuses a changed manifest. For intentional changes, use a new output directory and document the new experiment version. Do not regenerate/relabel the benchmark casually during evaluation.

## 11. What Remains for Final Completion

Resolve the pre-commit findings, validate the pilot, run the approved model/condition grid, preserve raw evidence, inspect failures, and write results with limitations. Obtain agreement on any reduced model mix. Finish the report and demo recording. A functioning UI and two good examples are integration milestones, not the final semester evaluation.