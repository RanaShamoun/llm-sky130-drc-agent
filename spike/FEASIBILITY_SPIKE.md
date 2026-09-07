# Feasibility Spike: KLayout + SKY130 as an Independent DRC Oracle

**Date:** September 2026
**Goal:** Confirm that KLayout's DRC engine, run in batch mode against the official SKY130 manufacturing rule deck, can serve as an independent, trustworthy ground-truth labeler for the evaluation set — replacing a self-written geometric checker per instructor feedback.

**Result: Confirmed working end-to-end.**

---

## Environment

- KLayout 0.30.12 (Windows, installed via official installer from klayout.de)
- SKY130 PDK installed via `volare` (version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, 2025.08.09 pre-release build)
- DRC deck used: `sky130A_mr.drc` (SKY130 manufacturing rule deck — the same deck used for real MPW shuttle submission prechecks)
- Test layout generated via the `klayout` Python package (`pip install klayout`)

## Setup Steps (summary)

1. Installed KLayout; added install directory to PATH via a `klayout.bat` wrapper (the Windows installer's binary is named `klayout_app.exe`, not `klayout.exe`).
2. Installed `volare` via pip; added the Python Scripts directory to PATH.
3. Ran `volare enable --pdk sky130 <commit-hash>` (explicit commit hash required — `volare` cannot auto-detect a version outside of a project with a `tool_metadata.yml` file). Listed available versions first via `volare ls-remote --pdk sky130`.
4. Set `PDK_ROOT` and `PDK` (=`sky130A`) as permanent user environment variables.
5. Located the DRC deck on disk directly via:
dir /s /b "%PDK_ROOT%%PDK%\libs.tech\klayout*.drc"
6. Inspected the deck's required input variables via:
findstr /n "source( report( $input $report $topcell CLI" <path-to-deck>.drc

   Found the deck expects `$input`, `$top_cell` (not `$topcell`), and `$report`.

## Confirmed GDS Layer Mapping

Verified against `sky130A.lyp` rather than assumed — **do not trust layer numbers from memory or generic sources**, they vary by PDK build:

- **met1.drawing = GDS layer 68, datatype 20**

## Test Layout

Generated via Python (`make_test_gds.py`, using the `klayout.db` module):

- Two metal1 rectangles, each 0.5µm × 0.5µm
- Placed with a deliberate **5nm gap** between them — far below any realistic minimum-spacing rule, to guarantee an unambiguous violation
- Top cell named `TOP`

## Batch-Mode DRC Command (working, final form)
klayout -b -r "<path-to-sky130A_mr.drc>" ^
-rd input=test_violation.gds ^
-rd top_cell=TOP ^
-rd report=test_violation_report.lyrdb ^
-rd feol=true ^
-rd beol=true


### Critical gotcha discovered

The deck defines `$feol` and `$beol` (front-end-of-line / back-end-of-line rule groups) with a **default value of `"false"`** if not explicitly passed. When left at default, the deck runs with **zero categories checked** — it does not error, it silently produces an empty report (`<categories></categories>`, `<items></items>`).

**This is a silent-failure trap**: a naive invocation using only `input`/`top_cell`/`report` completes successfully and produces a well-formed report file that *looks* valid but contains no checks at all. Every eval label generated this way would be wrong (silently reporting "no violations" regardless of actual layout content). `feol=true` and `beol=true` must always be passed explicitly.

**Action item for the full project:** the Executor tool's KLayout wrapper must hard-code these flags (or explicitly validate that the `<categories>` section of every report is non-empty as a sanity check) so this failure mode can never reoccur silently in the real pipeline.

## Result

Report correctly flagged the violation:

```xml
<item>
  <category>'m1.2'</category>
  <cell>TOP</cell>
  <values>
    <value>edge-pair: (0.505,0;0.505,0.5)/(0.5,0.5;0.5,0)</value>
  </values>
</item>
```

Category `m1.2` corresponds to (per the deck's own category description):
> `m1.2 : min. m1 spacing : 0.14um`

The flagged edge-pair coordinates match exactly the intentional 5nm gap in the test layout (0.5µm to 0.505µm on the x-axis). This confirms:

1. The deck correctly identifies real geometric violations
2. It identifies the *correct* rule for the violation type introduced
3. It reports precise, checkable location data usable downstream (e.g., for the agent's explanation-generation step)

## Conclusion

The KLayout + SKY130 manufacturing rule deck oracle approach is **confirmed feasible** on this timeline and this machine. This replaces the original self-written-checker plan and directly addresses the evaluation-validity concern raised in proposal feedback.

## Open Items for Full Implementation

- [ ] Decide whether to hard-code `feol=true`/`beol=true` always, or expose them as configurable per rule-category scope (spacing/width/enclosure only needs a subset)
- [ ] Build a report-parsing function that extracts `<category>` + `<values>` pairs into a structured label (pass/fail + rule ID + location) for the eval set
- [ ] Add a sanity check that fails loudly if `<categories>` is empty, to catch any future silent-failure invocations
- [ ] Confirm layer numbers for the other 2 in-scope rule categories (width, enclosure) the same way — via `.lyp`, not assumption