"""Fetch exactly the locked upstream deck revision, never a moving branch."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "data/sources.lock.json").read_text())
dest = root / ".tools/sky130_klayout_pdk"
if not dest.exists():
    dest.mkdir(parents=True)
    subprocess.run(["git", "init", str(dest)], check=True)
    subprocess.run(
        ["git", "-C", str(dest), "remote", "add", "origin", lock["repository"]],
        check=True,
    )
if subprocess.run(
    ["git", "-C", str(dest), "cat-file", "-e", lock["revision"] + "^{commit}"],
    capture_output=True,
).returncode:
    subprocess.run(
        ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", lock["revision"]],
        check=True,
    )
# Do not replace edited source files silently.
changes = subprocess.check_output(
    ["git", "-C", str(dest), "status", "--porcelain"], text=True
)
if changes:
    sys.exit("Source checkout has edits; restore or use a separate clean checkout.")
subprocess.run(
    [
        "git",
        "-C",
        str(dest),
        "sparse-checkout",
        "set",
        "--no-cone",
        "/LICENSE",
        *["/" + path for path in lock["files"]],
    ],
    check=True,
)
subprocess.run(
    ["git", "-C", str(dest), "checkout", "--detach", lock["revision"]], check=True
)
for relative, expected in lock["files"].items():
    actual = hashlib.sha256((dest / relative).read_bytes()).hexdigest()
    if actual != expected:
        sys.exit(f"Hash mismatch: {relative}")
print("Pinned deck and layer map verified.")
