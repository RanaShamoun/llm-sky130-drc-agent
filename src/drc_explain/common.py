from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def project_root():
    explicit = os.environ.get("DRC_EXPLAIN_ROOT")
    candidates = (
        [Path(explicit)]
        if explicit
        else [Path(__file__).resolve().parents[2], Path.cwd(), *Path.cwd().parents]
    )
    for candidate in candidates:
        if (candidate / "data/sources.lock.json").is_file():
            return candidate.resolve()
    raise RuntimeError("Run from the repository root or set DRC_EXPLAIN_ROOT to it.")


ROOT = project_root()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
