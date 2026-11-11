# Command Reference Log — KLayout + SKY130 Setup & Feasibility Spike

This is a straight log of every command that was actually run (and worked) to get
from "nothing installed" to "confirmed working DRC oracle," in order. Use this to
rebuild the environment on a new machine, or as a reference when scripting the
real Executor tool later.

Environment: Windows. Adjust paths for your username if reused elsewhere.

---

## 1. Install KLayout

Downloaded and ran the installer: `klayout-0.30.12-win64-install.exe` from klayout.de.


**Gotcha:** the actual executable is named `klayout_app.exe`, not `klayout.exe`.
Created a wrapper batch file so the `klayout` command works as expected everywhere.

`klayout.bat` (saved inside the KLayout folder above, "Save as type: All Files" in Notepad):
```bat
@echo off
"%~dp0klayout_app.exe" %*
```

Added the KLayout folder to the **User** PATH environment variable

**Verify:**

klayout -v > version.txt 2>&1
type version.txt

Expected output: `KLayout 0.30.12`

---

## 2. Install volare (SKY130 PDK version manager)
pip install volare
Add that folder to PATH the same way as step 1 above.

**Verify:**
volare --help

---

## 3. Download and enable the SKY130 PDK

List available prebuilt versions (volare cannot auto-detect a version outside of
a project with a `tool_metadata.yml` file, so a version must be picked manually):
volare ls-remote --pdk sky130


Enable the chosen version (most recent used here):
volare enable --pdk sky130 c6d73a35f524070e85faff4a6a9eef49553ebc2b


**Gotcha:** on Windows this may throw a `[WinError 32]` permission error during
its own temp-file cleanup step, right after all 7 `.tar.zst` files show 100%
downloaded. This is cosmetic — the install still completes. Confirm with:
volare ls --pdk sky130
---

## 4. Set PDK environment variables

Set as permanent **User** environment variables (same Environment Variables editor as step 1):

| Variable   | Value |
|------------|-------|
| `PDK_ROOT` | `C:\Users\.volare\volare\sky130\versions\c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| `PDK`      | `sky130A` (exact case matters — lowercase `s`, capital `A`) |

**Verify (new terminal window):**
echo %PDK_ROOT%
echo %PDK%

---

## 5. Open KLayout with the SKY130 technology loaded
set KLAYOUT_PATH=%PDK_ROOT%%PDK%\libs.tech\klayout
klayout -e

(Two separate commands/lines — do not merge onto one line.)

In the GUI: **Tools → Manage Technologies** → confirm `sky130A` appears in the list.
If prompted about hierarchy mode when opening a layout, choosing "Yes" (full
hierarchy) is fine — it's a display setting only and doesn't affect DRC batch runs.

---

## 6. Locate the DRC deck and its required variables

Find every `.drc` file inside the installed tech folder:
dir /s /b "%PDK_ROOT%%PDK%\libs.tech\klayout*.drc"

Deck used: `sky130A_mr.drc` (SKY130 manufacturing rule deck — same deck used for
real MPW shuttle submission prechecks).

Inspect how the deck reads its inputs:
findstr /n "source( report( $input $report $topcell CLI" "<full-path-to-sky130A_mr.drc>"

Found: deck expects `$input`, `$top_cell` (underscore, not `$topcell`), `$report`.

Search for other optional/required flags the deck defines:
findstr /n "$" "<full-path-to-sky130A_mr.drc>"

Found: `$feol` and `$beol` both **default to `"false"`** if not passed — and when
false, the corresponding rule categories are skipped entirely with no error or
warning. **Always pass `feol=true` and `beol=true` explicitly**, or the run will
silently produce a well-formed but empty report.

---

## 7. Confirm the metal1 GDS layer number (do this for any new layer/rule you target)

Find the correct `.lyp` file:
dir /s /b "%PDK_ROOT%%PDK%\libs.tech\klayout*.lyp"


Search it for the layer of interest:
findstr /i "met1" "<full-path-to-sky130A.lyp>"

Confirmed: `met1.drawing = GDS layer 68, datatype 20` (this PDK build —
don't assume this number is universal across all SKY130 PDK builds/sources).

---

## 8. Install the KLayout Python bindings and generate a test layout
pip install klayout
(Run inside whichever Python environment/IDE will actually execute the script —
a global `pip install` and an IDE's virtualenv `pip install` are not the same
environment. Use `python -m pip install klayout` from inside the target
environment's terminal to guarantee it lands in the right place.)

`make_test_gds.py`:
```python
import klayout.db as db  # pip install klayout

layout = db.Layout()
top = layout.create_cell("TOP")

# Confirmed from sky130A.lyp: met1.drawing = GDS layer 68, datatype 20
met1_layer = layout.layer(68, 20)

dbu = layout.dbu
def um(v):
    return int(round(v / dbu))

# Two rectangles with only a 5nm gap — deliberately far below any real
# minimum-spacing rule, so this should unambiguously violate DRC.
box1 = db.Box(um(0.0), um(0.0), um(0.5), um(0.5))
box2 = db.Box(um(0.505), um(0.0), um(1.0), um(0.5))

top.shapes(met1_layer).insert(box1)
top.shapes(met1_layer).insert(box2)

layout.write("test_violation.gds")
print("wrote test_violation.gds")
```

Run it:
python make_test_gds.py
Expected output: `wrote test_violation.gds`

---

## 9. Run the DRC batch check (the full, working command)
klayout -b -r "<full-path-to-sky130A_mr.drc>" -rd input=test_violation.gds -rd top_cell=TOP -rd report=test_violation_report.lyrdb -rd feol=true -rd beol=true

---

## 10. Check the report for violations

Quick check for any violations found:
findstr /c:"<item>" test_violation_report.lyrdb


View the full report (categories checked + items found):
type test_violation_report.lyrdb


**Confirmed result:** the deliberate metal1 5nm-gap violation was correctly
flagged under category `m1.2` ("min. m1 spacing : 0.14um"), with violation
coordinates matching the intentional gap exactly:
```xml
<item>
  <category>'m1.2'</category>
  <cell>TOP</cell>
  <values>
    <value>edge-pair: (0.505,0;0.505,0.5)/(0.5,0.5;0.5,0)</value>
  </values>
</item>
```

To view the report visually in the KLayout GUI instead of via text search:
klayout -m test_violation_report.lyrdb test_violation.gds

(`-m` loads a marker database directly on startup, avoiding the need to use
File → Open inside the Marker Browser window manually.)

---

## Summary: the one command that matters most going forward
klayout -b -r "<deck>.drc" -rd input=<layout>.gds -rd top_cell=<cellname> -rd report=<output>.lyrdb -rd feol=true -rd beol=true


This is the template the real Executor tool will wrap programmatically (e.g., via
Python's `subprocess`) to label every generated layout in the eval set. Never
drop the `feol=true`/`beol=true` flags — doing so produces a silently empty,
falsely-valid-looking report.

