# Setup

Run commands from the repository root. Python 3.11 or newer is required; this Mac was verified with Python 3.14.

## 1. Install Python dependencies

macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If activation is blocked, invoke `.venv\Scripts\python.exe` directly. The root `run.py` command loads the local source code, so changes take effect immediately and no editable package installation is needed.

## 2. Verify the saved benchmark

```sh
python run.py check
```

Expected: 15 tests pass and all 56 saved reports validate. This step uses the Python bindings and archived evidence; the standalone KLayout app is not needed yet.

## 3. Fetch the pinned rule sources

```sh
python run.py setup-sources
```

This retrieves the pinned upstream revision, verifies the deck/layer-map hashes, and builds the catalog. It keeps only the required source files in the working checkout. A full volare PDK installation is not needed for this self-contained deck. The source pin is distinct from the older Windows spike environment.

Source revision, file hashes, and required versions are in `data/sources.lock.json`. `SKY130_KLAYOUT_SOURCE` can point the checker to another checkout containing the exact pinned files. The setup/catalog scripts use the default `.tools/sky130_klayout_pdk` location.

## 4. Configure KLayout

Install **KLayout 0.30.13** from [the official downloads](https://www.klayout.de/build.html). It must be the application with Ruby DRC support; the Python wheel alone cannot run the manufacturing deck.

The prepared Mac already has a working copy at `.tools/klayout.app`. Otherwise, the checker uses `KLAYOUT_BIN` or searches PATH.

macOS example:

```sh
export KLAYOUT_BIN='/Applications/klayout.app/Contents/MacOS/klayout'
```

Windows example:

```powershell
$env:KLAYOUT_BIN = 'C:\Users\YOUR_NAME\AppData\Roaming\KLayout\klayout_app.exe'
```

Then verify:

```sh
python run.py doctor
python run.py demo
python run.py smoke
```

The demo reports a 0.135 um metal1-spacing violation. Smoke verification checks 16 layouts with passing/failing examples for all eight supported rules.

## 5. Normal development

Edit files in `src/drc_explain/`. Run `python run.py format`, then `python run.py check`. Use `python run.py smoke` after changes to checker behavior. Model tool calls go through `Toolset.call`; copy [the working example](../examples/use_tools.py) to get started.

To recreate the benchmark deliberately:

```sh
python run.py generate
python run.py label
python run.py check
```

GDS output is deterministic. Labeling runs the full deck, fails on construction/oracle disagreement, and saves original reports, logs, and parsed results in `eval/gold/oracle_reports.zip`. Archive members are verified byte for byte before loose reports are removed. If labeling fails, loose evidence remains under `eval/gold/reports/` for diagnosis.

## Troubleshooting and optional CLI

- Missing/mismatched sources: rerun `setup-sources`. Do not change hashes to suppress an error.
- Wrong executable version: install the pinned version. Upgrading the checker requires regenerating and reviewing the evidence.
- Failed run, empty report, missing categories, timeout, unsupported layout, or unsupported rule: no verdict is issued. Never treat a tool error as PASS.
- Python cannot import `klayout`: activate the correct virtual environment and install `requirements.txt` there.
- Optional installed CLI: `python -m pip install .` provides `drc-explain`. Reinstall after source changes. The recommended `python run.py ...` workflow always uses local source directly.

The official Mac disk image used for verification was `arm64ST-klayout-0.30.13-macOS-GoldenGate-C32-1-qt5MP-RsysPsys.dmg`, SHA256 `18853b8445675c90e58f99b3391d8c4504a5ddb7cb45cdef04dd81c58ad8bef1`. The installed app is ignored by Git; the redundant downloaded image has been removed. Other platforms use their own official 0.30.13 build and rerun verification.
