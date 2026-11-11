# Pre-Commit Validation

Validation performed November 11, 2026, in the Windows project virtual environment using Python 3.12.0. This records step 3 of the pre-commit workflow after the catalog encoding fix and debug-case disclosure.

## Summary

| Check | Result |
|---|---|
| Focused experiment/scoring/UI tests | 17 passed, 0 failed |
| Full regression suite | 70 passed, 2 failed; 72 tests total |
| Archived benchmark audit | Passed for all 56 layouts |
| Numeric marker cross-check | 41 markers matched KLayout's native reader |
| Tracked reference data after audit | No diff in checked labels, public cases, catalogs, source/model locks, or validation summary |

The focused tests are a subset of the full suite, not 17 additional independent successes. The full suite is **not all green**. Both failures match the previously observed Windows limitations; no additional test failures were observed in this run.

## Commands Executed

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py tests/test_scoring.py tests/test_ui.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_benchmark.py
```

The focused command completed with 17 passes in 0.20 seconds. The full suite completed with 70 passes and two failures in 2.01 seconds. These short test times come from fixtures and saved data, not hundreds of live model queries.

The benchmark audit was run separately because [run.py](../run.py) `check` stops when pytest exits unsuccessfully and would not proceed to the audit.

## Failure 1: Unix Permission Assertion on Windows

Test: `test_hidden_key_configuration_preserves_other_settings` in [tests/test_agent.py](../tests/test_agent.py#L385).

The test uses a fake, non-secret key and a temporary file. Its checks for preserved settings, exactly one key entry, and no key printed to output passed. Its final assertion requires Unix permission bits `0600`:

```python
assert path.stat().st_mode & 0o777 == 0o600
```

Windows returned `0666` through this mode-bit interface. Windows uses ACLs rather than the same permission model as Unix; the assertion is not a portable way to establish owner-only access on Windows.

This does **not** establish that a real Windows secret file has adequate access controls. The optional API configuration code requests `0600`, but owner-only Windows ACL behavior has not been validated. Current Ollama evaluation does not need an API key. Do not treat this as approval to store paid-provider secrets without reviewing Windows access permissions.

We did not alter the provider, weaken the assertion, or silently skip the test in this step.

## Failure 2: Symlink Test Requires Windows Privilege

Test: `test_tool_path_boundary_and_no_gold_exposure` in [tests/test_foundation.py](../tests/test_foundation.py#L81).

The test first checks traversal, an outside absolute path, and a missing layout. Those rejection assertions passed. It then tries to create a test symlink pointing outside the public root. Windows stopped creation with:

```text
OSError: [WinError 1314] A required privilege is not held by the client
```

Consequently, the symlink-escape rejection assertion later in that test did not execute on this machine. This run does not demonstrate either a successful or failed symlink escape; it demonstrates an unavailable test prerequisite.

Possible follow-up: run this test in an environment with symlink creation available, such as Windows Developer Mode where permitted by local policy, or Linux/macOS. Do not weaken the public-root guard just to make a test pass, and do not describe this coverage as already verified on Windows. No elevation or system-setting change was attempted in this step.

## Archived Benchmark Audit

[scripts/verify_benchmark.py](../scripts/verify_benchmark.py) validated saved report parsing, public GDS hashes/coordinates, relevant-rule labels, construction expectations, category counts, and per-rule statuses. It cross-checked the project's parser against KLayout's native report-database reader.

| Dataset fact | Verified count |
|---|---|
| Layouts audited | 56: 50 benchmark plus 6 development |
| Benchmark scoped FAIL | 26 |
| Benchmark scoped PASS | 24 |
| Near-boundary cases | 12 |
| Pass/fail-pair cases | 12 |
| Competing-rule cases | 12 |
| Conditional-enclosure cases | 14 |
| Numeric markers cross-checked | 41 |

All 56 native-reader comparison entries were true. The summary in [eval/gold/validation.json](../eval/gold/validation.json) remained unchanged relative to Git after the audit.

This is parser/data verification against the same KLayout engine, not a second independent physical signoff oracle. No standalone DRC deck was rerun and no benchmark labels were regenerated. It does not measure new LLM accuracy or certify current live runtime availability.

## Scope and Remaining Work

No live Ollama queries were launched, no model weights or source pins were changed, and no Git commit was made during step 3. Existing model demonstrations remain disclosed separately in [Debug Case Disclosure](DEBUG_CASE_DISCLOSURE.md).

Validation is complete with the two explicitly recorded platform failures. This supports proceeding to a deliberate code/documentation review and commit, but not describing the suite as fully passing. Running the same suite again on this unchanged Windows setup is expected to reproduce those failures until their prerequisites/assertions are addressed.

Step 4 should review what is staged, keep secrets/environments/weights/raw runtime folders out of the commit, and record the resulting commit hash. Step 5 remains the six-query smoke pilot; it has not been run by this validation step. Keep its observations separate from historical setup demonstrations.