# File-by-File Guide

Start with the [project walkthrough](PROJECT_WALKTHROUGH.md) for the story of what we did. This guide explains the files in the working project, including existing handoff code and our additions. Repetitive binary GDS files are grouped because they share a format and purpose. Generated environments and logs are explained separately rather than listing thousands of dependency files.

## A Small Glossary

| Term | Plain meaning |
|---|---|
| Module | A Python file containing related code |
| Function | A named operation that receives inputs and returns a result |
| Class | A definition for an object that bundles settings and operations, such as `Agent` or `Checker` |
| JSON | Structured text storing named fields, lists, numbers, and values |
| JSONL | One JSON object per line; useful for appending log events |
| GDS | Binary layout data storing physical shapes, layers, and cells |
| Top cell | The named layout cell being checked; usually `TOP` here |
| um | Micrometers; 0.001 um is one nanometer |
| DBU | Database unit: the coordinate resolution used by a layout |
| DRC deck | Existing checker instructions implementing manufacturing rules |
| Oracle | The trusted source of labels, here the real KLayout deck execution |
| Marker | Coordinates identifying a reported violation |
| Hash/digest | A fingerprint of exact bytes used to detect changes |
| Pin | A recorded exact version or fingerprint, not a moving latest release |
| Fixture | Controlled test data or a fake client used instead of a live model |
| Ablation | A comparison that removes system capabilities to measure their contribution |
| Grounded | Supported by evidence; distinguish live tool evidence from agreement scored afterward |

## The Big Picture

There are three related flows:

```text
Interactive demo:
run.py -> ui.py -> Agent -> OllamaClient
                       -> Toolset -> Checker -> report parser
                       -> verify_answer -> result + explanation

Experiment execution:
run.py -> experiments.py -> A/B baseline OR C Agent -> saved records

Experiment scoring:
experiments.py score_grid -> scoring.py + evaluator-only labels -> tables
```

Gold labels belong only in the evaluation/audit flow. They are not an input to the model's decision-making. Saving public coordinates in a JSON file does not turn them into answers; the gold fields that tell us what should pass/fail are kept separately.

## Root Files

### [README.md](../README.md)

The usual front door: overview, scope, existing status, and basic commands. It is documentation, not executable code. Some inherited counts and handoff wording describe the earlier state. Use the new walkthrough for this session's additions and limitations; do not interpret historical counts as a fresh test run.

### [ProjectProposal.txt](../ProjectProposal.txt)

The course proposal: problem, architecture, metrics, model comparison, benchmark validity, and scope. It is useful for judging whether the deliverable satisfies the original promise. The professor's feedback changes the emphasis toward rule selection and A/B/C grounding; the original three-model requirement still needs agreement if changed.

### [RanaProjectHandoff.txt](../RanaProjectHandoff.txt)

The short transfer-of-work note. It identifies what was built and the evaluation/UI/report tasks remaining. It does not execute or configure anything. Its claims are historical handoff records, not new benchmark results.

### [run.py](../run.py)

The convenient command entry point. `main()` reads the command name, then dispatches to a module, a script, or another Python command. Its `python()` helper uses the same interpreter that launched it, runs from the repository root, and passes the local `src` directory in `PYTHONPATH` to child processes.

This fixes a subtle issue: adding a folder to one Python process's import path does not automatically add it to a new child Python process. Without the environment setting, the UI child could fail to import the package.

| Command | What happens |
|---|---|
| `doctor` | Check KLayout version and pinned source hashes |
| `setup-sources` | Fetch locked sources and build the catalogs |
| `demo` | Run a tool-only example, not a live model evaluation |
| `agent` | Run one live agent question |
| `ui` | Start the local web demo server |
| `experiments run` | Execute the controlled grid and then score records |
| `experiments score` | Score existing records without model inference |
| `check` | Run pytest, then archived benchmark verification if pytest succeeds |
| `smoke` | Run real checker/tool smoke scenarios |
| `agent-smoke` | Run scripted-client integration scenarios against tools |
| `serve-local` / `pull-local` | Manage local Ollama / download weights |
| `generate` / `label` | Recreate layouts / regenerate oracle labels; not everyday evaluation commands |
| `format` | Apply Ruff import cleanup and formatting |
| `configure` | Configure the optional API provider, not needed for local runs |

We changed this file to expose the UI and experiment commands. Keep it stable during recorded evaluation.

### [pyproject.toml](../pyproject.toml)

Package metadata and build rules: project name, minimum Python version, runtime dependencies, installed CLI name, package discovery, and pytest paths. We added the web asset patterns so packaging includes HTML, CSS, and JavaScript.

It is not the same thing as your environment. Changing a dependency declaration does not install that dependency. Root-command execution uses local source; an installed copy may require reinstalling after changes.

### [requirements.txt](../requirements.txt)

Exact development dependency versions for pip installation. It includes more development/testing packages than the runtime dependencies in the project metadata. KLayout Python bindings are for data inspection; they are not the standalone Ruby-enabled DRC application.

### [.gitignore](../.gitignore)

Rules telling Git which generated/local files not to track by default. Ignored files can still exist and be important locally. In particular, runtime evidence must be backed up even when ignored. Ignore rules are not a security boundary and do not remove secrets already committed.

### [.env.example](../.env.example)

A configuration template, not your credentials. A real local `.env`, if created, can select a provider/model and contain an optional API key. Do not commit secrets. Local Ollama does not require an API key.

### [.vscode/tasks.json](../.vscode/tasks.json)

A VS Code task that launches the UI with the project virtual environment on port 8765. It does not install dependencies or set `KLAYOUT_BIN`. The task needs a suitable inherited environment, just like a terminal command. This task is Windows-oriented; review portability before committing it as team configuration.

## Core Agent Files

### [src/drc_explain/__init__.py](../src/drc_explain/__init__.py)

Marks the directory as a Python package. It has no agent/checker logic. You generally do not need to change it.

### [src/drc_explain/__main__.py](../src/drc_explain/__main__.py)

Allows `python -m drc_explain` to invoke the package CLI. It delegates to the CLI instead of duplicating command logic.

### [src/drc_explain/cli.py](../src/drc_explain/cli.py)

Parses individual agent, doctor, generate, label, schema, and direct tool commands. The agent command chooses local Ollama by default; an optional OpenAI route exists. It prints an explanation or full JSON and distinguishes execution ERROR from normal domain verdicts.

The root dispatcher exposes extra conveniences, so its command list is not identical to this CLI's command list.

### [src/drc_explain/common.py](../src/drc_explain/common.py)

Shared utilities for locating the project root, reading/writing JSON, and computing file SHA256 fingerprints. `ROOT` lets modules find repository data consistently. An environment override can select a project root.

Many modules use these helpers; changing them can affect the entire project. They are infrastructure, not geometry rules.

### [src/drc_explain/agent.py](../src/drc_explain/agent.py)

The existing bounded planner/executor. Its main public entry is `Agent(client).run(question, gds_path, top_cell)`.

`INSTRUCTIONS` is the model's system prompt. It defines supported scope, required evidence use, unavailable measurement handling, and how to submit claims. `FINAL_TOOL` defines the required answer structure. `model_tools()` combines external tools with this submission function.

`run()` creates a new run directory, inspects the layout, calls the model repeatedly, dispatches one requested function per turn, logs events, and invokes the verifier for submitted answers. Invalid claims can be rejected and corrected within the remaining budget. The default budgets are eight model turns and twelve external tool calls.

The agent checks that requested paths/top cells match the input and that the layout did not change. Prose alone is not accepted as a final answer. It saves an ERROR when execution cannot produce an accepted verdict. A model's correct refusal is different from an infrastructure failure.

We preserved this implementation. Changing its prompt affects experiment identity and may invalidate resume. Verified final prose is rendered from accepted evidence; the model's selection justifications are stored but not certified as complete or correct reasoning.

### [src/drc_explain/tools.py](../src/drc_explain/tools.py)

The controlled external-tool interface. `TOOL_SCHEMAS` describes the three functions the model may request. `Toolset.call()` validates the tool name and arguments, dispatches work, catches failures, and logs inputs, outputs, timestamp, and latency.

`retrieve_rules()` searches eight curated rules using normalized word overlap and exact-ID preference. For example, it maps metal1 to m1 and gap to spacing. This is simple ranked retrieval, not an embedding/vector database and not a second LLM.

`inspect_layout` reads public geometry. `run_drc` asks the checker for explicitly selected IDs. `_layout()` enforces a public-root path boundary so a tool cannot traverse into gold files or arbitrary files. The model does not have a shell tool.

The rule retrieval tool returns candidates. The agent must choose which candidates matter; checking every retrieved rule is not automatically good selection.

### [src/drc_explain/layouts.py](../src/drc_explain/layouts.py)

Reads binary GDS with KLayout Python bindings. `inspect_layout()` returns cell name, units, DBU, layers, polygon coordinates, bounding boxes, rectangle flags, and shape counts.

A bounding box is the smallest rectangle surrounding a shape. It is useful for display and context, but inspection is not a replacement DRC engine. Validation rejects unsupported data such as polygon holes and excessive shape counts.

The UI draws these coordinates, and the agent uses them as engineering context.

### [src/drc_explain/runner.py](../src/drc_explain/runner.py)

Runs the trusted geometric oracle. The `Checker` object chooses the executable and source location, checks pins, launches batch DRC, and translates results into selected-rule checks.

`provenance()` is what makes `doctor` meaningful: it checks exact KLayout version and source hashes. `run_full()` executes the full manufacturing deck, with required front-end/back-end flags, and rejects failed, missing, or incomplete reports. `run_selected()` validates supported geometry and selected IDs, runs the full deck, then filters results.

Geometry restrictions include supported rectangular layers, the benchmark grid, ordinary metal sizes, and square 0.15 um vias. A valid-looking question does not bypass these guards.

This module does not let the LLM modify checker code. A selected-rule PASS is not an all-deck PASS. `KLAYOUT_BIN` is a terminal/process setting, not a permanent change to this file.

### [src/drc_explain/reports.py](../src/drc_explain/reports.py)

Parses KLayout's XML report database into categories and violations. `parse_report()` organizes rule IDs and marker data. `marker_measurement()` extracts distances only for supported parallel, axis-aligned, overlapping edge-pair markers.

For b001, the opposite reported edges are 0.135 um apart. That is a measurement derived from the actual checker marker, not an LLM guess. Passing checks have no violation marker to measure. Corner/polygon markers may contain useful coordinates but no supported scalar distance.

Never use a rule limit as a substitute for missing measurement. Parsing robustness matters because the agent and labels depend on this boundary.

### [src/drc_explain/verification.py](../src/drc_explain/verification.py)

The deterministic evidence gate. `verify_answer()` receives the proposed answer and current-query evidence, not benchmark gold labels.

It checks selected IDs exist in retrieved supported rules; all actually checked rules are included; each selection has a claim; statuses and limits match; claims cite successful DRC evidence; layout hashes match; measurements match available distances; and the overall verdict follows the checks.

For REFUSE it requires no geometric claims and a reason. That structural acceptance does not prove refusal was appropriate for the user's task; the evaluator scores appropriateness afterward.

Accepted claims become a predictable explanation with sources and selected-scope limits. This prevents fabricated factual final prose but does not eliminate wrong/incomplete rule selection. Read this module together with scoring to understand why a verified answer can still lose evaluation points.

### [src/drc_explain/provider.py](../src/drc_explain/provider.py)

The optional OpenAI Responses adapter and configuration helpers. `load_local_config()` reads allowed local configuration without evaluating shell commands. `OpenAIResponses.respond()` sends the shared message/tool format to the API and translates provider failures. `configure_api()` collects a key privately in the terminal.

The local path does not use this API adapter merely because the module exists. Choosing the optional provider can involve paid usage. Never place credentials in experiment notes or commits.

### [src/drc_explain/local_provider.py](../src/drc_explain/local_provider.py)

Adapts the agent's message/tool format to Ollama's local chat API. `OllamaClient` talks to loopback only, rejects remote/cloud model names, records local API cost as zero, and verifies model availability and the default model digest against its lock.

`_check_model()` ensures local weights exist and records metadata. `_messages()` translates tool-call history to Ollama messages. `respond()` sends instructions, inputs, schemas, and options, then returns normalized function calls for the agent.

The options include deterministic temperature zero, disabled thinking, 32768 context, and a prediction limit. Zero temperature does not guarantee identical behavior on every machine/run. A timeout or HTTP 500 gives ERROR, never a manufactured PASS.

The source/model filename lock is not automatically rewritten to accept a mismatched model. Do not change the digest merely to suppress an error.

### [src/drc_explain/local_runtime.py](../src/drc_explain/local_runtime.py)

Finds Ollama, checks whether the loopback server is running, optionally starts it, and pulls configured weights. `runtime_environment()` uses local-only settings and strips cloud API credentials when starting a project-managed process.

If the desktop Ollama server already runs, the project uses it rather than launching another. That server controls its model storage; setting a client environment variable does not relocate an already-running server's weights.

On your Windows install, the terminal initially did not find Ollama through PATH. Calling the installed executable by its full path solved the download step. This is environment setup, not a reason to alter the agent planner.

### [src/drc_explain/benchmark.py](../src/drc_explain/benchmark.py)

Builds deterministic synthetic layouts and labels them with KLayout. `designs()` describes intentional constructions, questions, relevant rules, and pairs. `generate()` writes GDS, public coordinate dumps, and separate gold construction specifications. `label()` runs the real deck and preserves evidence.

The construction prediction is a cross-check, not the authoritative oracle label. Near-boundary examples distinguish below/equal/above minimum values; competing-rule layouts test selection; enclosure examples exercise conditional corner behavior.

Do not run generate/label as routine experiment preparation. Regenerating labels or geometry while measuring a model changes the experiment's foundation.

### [src/drc_explain/evidence.py](../src/drc_explain/evidence.py)

Archives original reports/logs/results and reads archived evidence for audit. `archive_reports()` validates ZIP integrity and byte agreement before replacing the archive. `report_bytes()` reads a loose report if available, otherwise its ZIP entry.

The archive is evidence of what the checker returned, not a model input. Preserving it makes parser/label verification possible after loose files are removed.

## New Evaluation Files

### [src/drc_explain/scoring.py](../src/drc_explain/scoring.py)

The evaluator, added in this session. It runs after answers exist. It must not feed gold labels back into prompts.

`score_case(result, gold)` compares the answer with relevant IDs/statuses and available oracle measurements. It calculates selected true positives, false positives, and false negatives; verdict correctness; exact selections; duplicates; citation/limit errors; and measurement agreement.

`_numbers_match()` requires finite numeric values, the same number of distinct reported values, and close numeric agreement. A tiny numeric tolerance is not permission to award a wrong PASS/FAIL verdict near a threshold.

`aggregate()` scores one model, condition, and repetition. It rejects duplicate/unexpected result IDs, includes missing cases in accuracy denominators, scores complete paired groups, separates probes, and computes runtime/cost summaries.

The `case_scores` list in metrics allows you to trace an aggregate number back to individual failures. The metric is structured oracle agreement: it does not independently verify every word of prose, URL, or justification. A/B predictions can match gold but remain unverified at inference time.

### [src/drc_explain/experiments.py](../src/drc_explain/experiments.py)

The resumable experiment controller, added in this session. It uses public inputs for execution and imports scoring only for the evaluator phase.

`model_input()` allowlists question, GDS path, top cell, and layout. It excludes verdicts, case types, pair membership, and even unneeded public bookkeeping fields from the prompt object.

`condition_tools()` gives A only the answer-submission function and B retrieval plus submission. Neither condition can call DRC. `baseline()` runs their bounded prediction loop and saves unverified answers. `_validate_prediction()` checks answer structure and finite numbers, not agreement with the rule tool or oracle.

`run_grid()` selects benchmark cases/probes, checks public GDS hashes and local models, writes/compares the manifest, rotates condition order, runs A/B/C, saves a record per query, and prints progress. C calls the existing `Agent` rather than duplicating it.

`score_grid()` reads evaluator-only labels, groups records, invokes scoring, and writes machine-readable metrics plus a small Markdown table. The table summarizes only some metrics; detailed JSON has additional counts and per-case scores.

Important current boundaries: no development-case CLI support, local Ollama models only, and resume skips saved ERROR records. Manifest disclosure now includes Windows b001/b002 demonstrations and earlier setup errors alongside historical accepted cases. This metadata is not passed to models. The manifest does not automatically contain a Git commit hash. Keep separate experiment notes.

## Web Interface Files

### [src/drc_explain/ui.py](../src/drc_explain/ui.py)

A small standard-library HTTP server restricted to `127.0.0.1`. `public_cases()` returns 56 layout cases plus six probes. `run_request()` accepts only case ID and question, resolves the public path itself, invokes the existing agent, and returns its result and tool log.

The `Handler` serves HTML/CSS/JS, public inputs, and the run endpoint. It checks host/origin and JSON request size. A nonblocking lock prevents two UI requests from invoking the agent concurrently. The lock is released in `finally`, including failure paths.

This is a local research demo, not a deployed authenticated multi-user service. A browser fetch waits for the final result; there is no streaming trace/progress API, cancellation endpoint, or automatic recovery of a run after page reload.

### [src/drc_explain/web/index.html](../src/drc_explain/web/index.html)

The page structure: public-case selector, question field, command button, metadata, geometry canvas, verdict, selected rules, metrics, and trace containers. Element IDs connect the page to JavaScript. HTML is the structure, not the inference engine.

### [src/drc_explain/web/style.css](../src/drc_explain/web/style.css)

Visual presentation: colors, layout spacing, typography, canvas sizing, state styling, and responsive arrangements. CSS affects appearance but cannot change a DRC verdict. Editing this file is how you adjust visual layout without touching agent logic.

### [src/drc_explain/web/app.js](../src/drc_explain/web/app.js)

Browser behavior. It fetches public cases, updates selected question/context, draws polygons on a 2D canvas, submits JSON to the server, and renders results with source links and expandable tool logs.

`draw()` scales layout coordinates to the canvas; it is a visualization, not geometric checking. `selectCase()` resets old results. `run()` disables controls during its request, shows elapsed seconds, displays Busy for HTTP 409, and distinguishes returned results from request/setup errors.

The elapsed counter is browser time, not a live model-turn report. Trace entries appear once the request completes. Display text is inserted using text content rather than treating model content as HTML.

## Script Files

### [scripts/bootstrap_sources.py](../scripts/bootstrap_sources.py)

Fetches only the pinned upstream revision and required files into a generated tools checkout. It checks for edits before refreshing sources and verifies hashes afterward. We added Windows LF-preservation handling here after observing CRLF checkout bytes.

Only the generated, guarded source checkout is refreshed. This is not a command to discard unrelated project changes.

### [scripts/build_catalog.py](../scripts/build_catalog.py)

Checks source hashes, extracts static deck output IDs/descriptions, constructs the curated eight-rule catalog with applicability and citations, verifies layer mappings from XML, and writes both data catalogs.

It does not generate DRC algorithms. The eight-rule selection/applicability metadata is curated; descriptions and source locations come from the pinned deck. It now reads the deck explicitly as UTF-8, fixing the Windows category-description corruption. Regeneration was verified to preserve all IDs, supported rules, limits, and source pins.

### [scripts/verify_benchmark.py](../scripts/verify_benchmark.py)

Audits saved public geometry, labels, report categories/statuses, and numeric markers. It cross-checks the project's parser with KLayout's native report reader and writes a validation summary.

This checks the evidence interpretation without new LLM calls. The native reader is an independent parser cross-check, not a second independent manufacturing oracle.

### [scripts/smoke_handoff.py](../scripts/smoke_handoff.py)

Runs real tool/checker integration examples covering supported rules and selected-rule isolation. It verifies retrieval/inspection/check results and saves a summary. These are tool tests, not new live LLM accuracy measurements.

### [scripts/smoke_agent.py](../scripts/smoke_agent.py)

Runs the agent with scripted model actions and real tools for a small set of scenarios. This checks planner protocol, dispatch, verification, refusal structure, and saved output. A scripted client is not a real Qwen inference result.

### [scripts/render_review.py](../scripts/render_review.py)

Produces a visual sheet of selected layouts and violation markers for inspection. It is an optional review aid, not a checker or label oracle. Review notes should distinguish automated/coding-agent inspection from independent human signoff.

### [examples/use_tools.py](../examples/use_tools.py)

Small runnable example of retrieving rules, inspecting a public GDS, and checking selected IDs. `run.py demo` launches it. It helps understand `Toolset.call()` without waiting for a live model.

## Test Files

Tests are assertions, not benchmark questions. Most use fixtures/mocks to avoid expensive model calls. A green unit suite does not mean the 168-query experiment ran.

### [tests/test_foundation.py](../tests/test_foundation.py)

Checks core parsing, measurement semantics, deterministic benchmark generation, public/gold separation, retrieval ranking, path guards, selected-rule filtering, and checker failures. Platform-specific permission/symlink assumptions previously failed on Windows and should be reported honestly.

### [tests/test_agent.py](../tests/test_agent.py)

Checks the existing agent/verifier with controlled clients/evidence: acceptable claims, fabricated/contradictory measurements, sources, refusal/error behavior, and logging. It targets evidence safety, not comparative model accuracy.

### [tests/test_local_provider.py](../tests/test_local_provider.py)

Checks local-provider message translation, local-only restrictions, model metadata/digest handling, and errors using controlled responses. Useful when changing Ollama adapter behavior without downloading/running another model.

### [tests/test_scoring.py](../tests/test_scoring.py)

New scoring tests: relevant rather than full-deck verdicts; missing pair members; ERROR versus REFUSE; invented passing distances; numeric agreement; missing applicable passing rules; unsupported versus fabricated citations; duplicate claims.

These examples demonstrate why scoring needs more than matching the single word PASS or FAIL.

### [tests/test_experiments.py](../tests/test_experiments.py)

New tests for allowlisted model inputs, A/B tool restrictions, saved forbidden-action errors, and unverified baseline refusal. Current tests are focused; they do not constitute exhaustive testing of long-run resume or all real-model baseline behaviors.

### [tests/test_ui.py](../tests/test_ui.py)

New tests verifying public-only case listing, rejected bad inputs, and dispatch to the existing agent. They do not launch a real model. We separately exercised the browser Busy path with a simulated HTTP response.

## Rule and Model Data

### [data/sources.lock.json](../data/sources.lock.json)

Records upstream repository/revision, required source file hashes, and pinned KLayout versions. The bootstrap and checker use it to refuse changed evidence foundations. Altering it is a deliberate oracle upgrade requiring review, not a setup shortcut.

### [data/rules.json](../data/rules.json)

The model-accessible eight-rule corpus plus layer mapping metadata. A rule record contains ID, category, numeric limit, layers, description, applicability, and pinned source URL/line.

Supported IDs: `m1.1`, `m1.2`, `m2.1`, `m2.2`, `via.4a`, `via.5a`, `m2.4`, `m2.5`. Width/spacing limits are 0.14 um; basic via enclosure is 0.055 um; corner-based enclosure uses 0.085 um with audited operational behavior.

Retrieval, checker selection validation, final verification, and scoring all use this catalog for different purposes. Do not confuse a layer being listed in metadata with its entire rule family being supported.

### [data/deck_categories.json](../data/deck_categories.json)

Static index of 262 extracted deck IDs/descriptions, including unsupported or conditional rules. Scoring uses the keys to distinguish a real-but-unsupported citation from an invented ID.

It is not the supported retrieval corpus, not a list of what every run enabled, and not a full-deck report. The Windows encoding corruption in 11 descriptions was repaired; the regenerated category data matches the committed reference.

### [data/local_model.lock.json](../data/local_model.lock.json)

Recorded Qwen weights digest, size, options, local cost policy, and historical Ollama/runtime download provenance. The default model's digest is checked against it. It is a supplied pin, not a file the adapter automatically creates or updates.

The historical runtime archive URL is for the earlier Mac environment; your Windows Ollama installation is different. Actual runtime metadata is recorded in each result. Matching model weights does not require that Mac application archive on Windows.

## Public Evaluation Inputs

### [eval/public/cases.json](../eval/public/cases.json)

Fifty benchmark layout records plus six development layout records: 56 total, not 62. Each has an engineering question, GDS path/hash, split, and coordinate inspection. The UI adds six probes from the separate probe file to reach 62 options.

`model_input()` uses only the allowed input fields. Keep the split, answers, case construction type, and pair membership out of prompts unless explicitly part of a different approved task.

### Benchmark GDS Files

[b001](../eval/public/benchmark/b001.gds) through [b050](../eval/public/benchmark/b050.gds) are the 50 binary benchmark layouts. They are stored drawings, not programs. Every numbered file's exact question, geometry, and hash is in the public manifest.

They cover near-boundary widths/spacings, pass/fail pairs, competing candidate rules, and conditional/enclosure layouts. Do not infer a label from the filename. Models receive geometry/questions, while hidden expected results live in gold.

### Development GDS Files

[d001](../eval/public/development/d001.gds) through [d006](../eval/public/development/d006.gds) are the six separate layouts intended for development/prompt tuning, not headline benchmark scoring. The UI can display them; the current experiment CLI filters them out.

### [eval/public/probes.json](../eval/public/probes.json)

Six unsupported-scope questions with no GDS: density, antenna, tape-out certification, latch-up, wide-metal spacing, and special core-region enclosure. They test whether the model refuses appropriately, not geometric PASS/FAIL.

## Gold Labels and Audit Files

Never expose these as model prompts or tool-accessible inputs. They are the answer key and evidence used after inference or for explicit audits.

### [eval/gold/labels.json](../eval/gold/labels.json)

Authoritative saved layout labels: relevant-rule verdict, relevant IDs, per-rule status, violation markers, full-deck verdict, unrelated failures, hashes, source/tool provenance, case types, and pair IDs. Headline scoring uses the relevant-rule verdict, not the all-deck result.

### [eval/gold/designs.json](../eval/gold/designs.json)

Hidden construction specifications: how layouts were made, intended behavior, rule selection, pairing, and notes. Useful for auditing labels and explaining benchmark design, but leaking these would make rule interpretation trivial.

### [eval/gold/probe_labels.json](../eval/gold/probe_labels.json)

Expected unsupported-probe refusal labels. The current scorer constructs probe REFUSE labels from the public probe IDs rather than reading this file. The saved file remains part of the benchmark's design record.

### [eval/gold/validation.json](../eval/gold/validation.json)

Saved benchmark-validation summary from the report/geometry audit. Read it for counts, cross-checks, and scope; do not use it as evidence that a new model answered correctly.

### [eval/gold/construction_crosscheck.json](../eval/gold/construction_crosscheck.json)

Record comparing intentional construction expectations with oracle behavior. It helps expose mistaken assumptions in benchmark design, but the KLayout result remains the label source.

### [eval/gold/initial_enclosure_audit.json](../eval/gold/initial_enclosure_audit.json)

Preserved enclosure investigation record, including early expectation/oracle disagreement. It documents why the corner interpretation needed correction rather than hiding an inconvenient result.

### [eval/gold/handoff_smoke.json](../eval/gold/handoff_smoke.json)

Saved tool-smoke summary: which real-tool checks passed and whether selected-rule isolation worked. It is historical integration evidence, not a live LLM comparison table.

### [eval/gold/local_agent_acceptance.json](../eval/gold/local_agent_acceptance.json)

Historical four-example local Qwen acceptance summary with evidence references. These examples were used for debugging. They do not provide a 50-case accuracy estimate and do not list every manual run in our session.

### [eval/gold/oracle_reports.zip](../eval/gold/oracle_reports.zip)

ZIP archive of original full-deck reports, logs, and parsed results used to substantiate labels. It is read for audits without making it available to the model. Keep it preserved even if loose report directories are absent.

### [eval/gold/local_agent_traces.zip](../eval/gold/local_agent_traces.zip)

Archived historical agent attempts/traces used for local integration acceptance and debugging. This is separate from newly generated UI/experiment runs. Accepted examples and rejected attempts must not be confused with a clean evaluation set.

### [eval/gold/review/inspection_notes.md](../eval/gold/review/inspection_notes.md)

Notes for the ten-case visual geometry/marker review. Inspection aids parser sanity checking; it should not be described as independent human approval when performed by a coding agent.

### [eval/gold/review/ten_case_geometry.png](../eval/gold/review/ten_case_geometry.png)

Rendered visual review sheet for those cases. It is a picture for inspection, not a gold-label generator or an input image used by the current model.

## Existing Documentation

### [docs/SETUP.md](SETUP.md)

Dependency, source, standalone KLayout, and normal-command setup. Includes Windows instructions and troubleshooting. Earlier expected test counts describe historical verification and may change as tests are added.

### [docs/LOCAL_MODEL.md](LOCAL_MODEL.md)

Local Ollama/Qwen setup and local-budget policy. Explains download versus inference and why local demonstrations do not replace the proposed evaluation.

### [docs/AGENT.md](AGENT.md)

Agent workflow, command examples, saved evidence, programmatic use, and verifier limits. Read before interpreting an accepted answer as complete rule selection.

### [docs/HANDOFF.md](HANDOFF.md)

Detailed task ownership and evaluator guidance: public/gold separation, A/B/C, metrics, enclosure caveats, and completion criteria. The newly implemented runner/scorer/UI fill part of that task list, not the final analysis/report.

### [docs/ENCLOSURE_AUDIT.md](ENCLOSURE_AUDIT.md)

Explains the pinned deck's corner-based via-enclosure behavior and why a casual interpretation of "two adjacent edges" can disagree with actual markers. Read before modifying enclosure benchmark expectations or claiming geometric generality.

### [docs/TOOL_CONTRACT.md](TOOL_CONTRACT.md)

Tool schemas, response structures, units, path/scope boundaries, and full-deck-then-filter behavior. This is the interface agreement between model actions and trustworthy execution.

### [docs/examples/tool_session.json](examples/tool_session.json)

Saved example tool interaction for learning the input/output contract. It is not the latest run and should not be treated as new evaluation evidence.

### [docs/research/LITERATURE_SURVEY.md](research/LITERATURE_SURVEY.md)

Research background and related work. Explains how interpreting/explaining with a trusted checker differs from projects generating DRC scripts. Literature claims need their own source checking for the final report.

### [docs/research/AI_NOVELTY_FEASIBILITY.md](research/AI_NOVELTY_FEASIBILITY.md)

Assessment of project novelty, scope, feasibility, and evaluation risks. It motivates the research direction, not executable behavior or measured final results.

### [docs/research/spike/FEASIBILITY_SPIKE.md](research/spike/FEASIBILITY_SPIKE.md)

Historical proof that a deliberately invalid layout can run through the real checker. Contains environment and operational lessons, including required deck flags. Its historical environment differs from the current pin/setup.

### [docs/research/spike/COMMAND_LOG.md](research/spike/COMMAND_LOG.md)

Reproduction commands and outputs from that early feasibility work. A historical log, not commands to blindly execute over the current benchmark.

### [docs/research/spike/make_test_gds.py](research/spike/make_test_gds.py)

Creates the small intentional spacing-violation layout for the spike. It is an early demonstration generator, not the main 56-layout benchmark generator.

### [docs/research/spike/test_violation.gds](research/spike/test_violation.gds)

Binary geometry for that early deliberate violation, separate from benchmark/development cases.

### [docs/research/spike/test_violation_report.lyrdb](research/spike/test_violation_report.lyrdb)

KLayout report database from the spike. Contains violation coordinates for feasibility evidence, not labels for the current 50-case evaluation.

### [docs/PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md)

Our new session summary: what existed, what changed, Windows fixes, successful demos, metric semantics, known issues before commit, and exact pilot/full-run commands.

### [docs/FILE_GUIDE.md](FILE_GUIDE.md)

This companion guide. Its purpose is understanding, not configuration. Both guides can be committed as documentation once reviewed.

### [docs/DEBUG_CASE_DISCLOSURE.md](DEBUG_CASE_DISCLOSURE.md)

Records known prior live-model demonstrations and Windows setup errors, identifies the second PASS as b002 from its saved result, and preserves run IDs/result fingerprints. Explains what future manifests disclose, what stays out of model inputs, and how to honestly report prior case exposure. It is integration history, not new benchmark accuracy evidence.

### [docs/PRECOMMIT_VALIDATION.md](PRECOMMIT_VALIDATION.md)

Records the November 11 pre-commit checks: 17 focused passes, 70 full-suite passes with two Windows failures, and successful archived verification of 56 layouts and 41 numeric markers. Explains the permission and symlink test limitations without treating them as passing or as proof of a tool-boundary escape. This is regression/audit evidence, not live LLM benchmark results.

## Generated Local Files

These paths may be ignored or machine-specific. They are not a request to commit them.

| Area | What it contains | How to handle it |
|---|---|---|
| `.venv/` | Python interpreter/environment packages | Recreate from dependencies; do not commit |
| `.tools/sky130_klayout_pdk/` | Generated pinned source checkout | Keep exact pins; do not edit deck logic |
| `.tools/ollama-models/` | Weights when a project-managed server uses this location | Large binary data; do not commit |
| Desktop Ollama model storage | Weights managed by the running Windows Ollama app | May be outside the repository; leave managed by Ollama |
| `.git/` | Git history/index/configuration | Managed by Git, not application code |
| Python/pytest caches | Compiled modules and test cache data | Generated, not evaluation evidence |

### Saved UI/Agent Runs

Each `runs/agent/<run_id>/` contains a `result.json`, a model/event `trace.jsonl`, and a `tool_calls.jsonl`. Results contain verdict, explanation, checks, selections, model/runtime identity, token usage, latency, cost, verification status, and saved path. Traces make it possible to see which rule was actually requested.

`runs/tool_calls.jsonl` can hold tool-only calls. `runs/ollama-server.log` is a project-started server log; the already-running desktop application may keep its own logs elsewhere.

### Saved Experiment Runs

```text
runs/experiments/pilot/
  manifest.json
  metrics.json
  results.md
  model0/
    A/1/b001/record.json
    B/1/b001/record.json
    C/1/b001/record.json
```

This is a schematic, not a claim these outputs already exist. Each case directory also stores its baseline result/trace or a nested C agent run with JSONL logs.

`manifest.json` states cases, models, conditions, repetitions, public input/prompt/selected-code fingerprints, and model pins. `record.json` wraps a result with its case/condition/repetition. `metrics.json` contains aggregate and per-case scores. `results.md` is a compact readable table.

The files are complementary: a table alone cannot prove the model used the allowed tools. Preserve raw records/traces as well as aggregates. Git-ignored does not mean disposable; back up evidence separately and publish an intentional compact results artifact for the report.

## A Suggested Reading Order

1. Read the walkthrough and its pre-commit findings.
2. Read the new evaluator/experiment/UI sections in this guide.
3. Follow the real query through agent, tools, checker, report parser, and verifier.
4. Read the public/gold distinction and enclosure audit.
5. Review the focused tests and saved example result/trace.
6. Resolve the documented findings, then commit and run the smoke pilot.

Before proceeding, you should be able to explain why Qwen is not the geometric oracle, why PASS does not certify the full layout, why A/B answers remain predictions, why a verified C answer can miss relevant rules, and why two successful demos do not establish benchmark accuracy.