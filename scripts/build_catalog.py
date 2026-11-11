"""Extract supported rule descriptions verbatim from the pinned upstream deck."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drc_explain.common import ROOT, read_json, sha256, write_json

source = ROOT / ".tools/sky130_klayout_pdk"
lock = read_json(ROOT / "data/sources.lock.json")
for file, expected in lock["files"].items():
    if sha256(source / file) != expected:
        raise RuntimeError(f"Pinned source mismatch: {file}")
deck = source / "tech/sky130/drc/sky130A_mr.drc"
text = deck.read_text()
outputs = {
    m[1]: (m[2], text[: m.start()].count("\n") + 1)
    for m in re.finditer(r'\.output\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', text)
}
specs = [
    ("m1.1", "width", 0.14, ["m1"], "Width of ordinary metal1 geometry."),
    (
        "m1.2",
        "spacing",
        0.14,
        ["m1"],
        "Spacing of ordinary metal1 geometry; wide-metal variants are outside v1.",
    ),
    ("m2.1", "width", 0.14, ["m2"], "Width of ordinary metal2 geometry."),
    (
        "m2.2",
        "spacing",
        0.14,
        ["m2"],
        "Spacing of ordinary metal2 geometry; wide-metal variants are outside v1.",
    ),
    (
        "via.4a",
        "enclosure",
        0.055,
        ["m1", "via"],
        "Minimum enclosure of rectangular 0.15um via by metal1, outside special regions.",
    ),
    (
        "via.5a",
        "enclosure",
        0.085,
        ["m1", "via"],
        "Metal1 corner-based via enclosure check; see docs/ENCLOSURE_AUDIT.md for operational semantics.",
    ),
    (
        "m2.4",
        "enclosure",
        0.055,
        ["m2", "via"],
        "Metal2 enclosure of via outside areaid:core; core-region variant is outside v1.",
    ),
    (
        "m2.5",
        "enclosure",
        0.085,
        ["m2", "via"],
        "Metal2 corner-based via enclosure check, outside areaid:core; see docs/ENCLOSURE_AUDIT.md.",
    ),
]
rules = []
for id, kind, limit, layers, applicability in specs:
    description, line = outputs[id]
    if str(limit) not in description:
        raise RuntimeError(f"Limit mismatch: {id}")
    rules.append(
        dict(
            rule_id=id,
            category=kind,
            limit_um=limit,
            layers=layers,
            description=description,
            applicability=applicability,
            source_url=f"https://github.com/efabless/sky130_klayout_pdk/blob/{lock['revision']}/tech/sky130/drc/sky130A_mr.drc#L{line}",
            source_line=line,
            source_revision=lock["revision"],
        )
    )
root = ET.parse(source / "tech/sky130/sky130.lyp").getroot()
layer_specs = {
    "m1": ("met1.drawing", 68, 20),
    "m2": ("met2.drawing", 69, 20),
    "via": ("via.drawing", 68, 44),
    "li": ("li1.drawing", 67, 20),
}
layers = {}
for key, (label, layer, datatype) in layer_specs.items():
    matches = [
        p
        for p in root.iter("properties")
        if p.findtext("source", "").split("@")[0] == f"{layer}/{datatype}"
    ]
    if not matches:
        raise RuntimeError(f"Layer absent from layer map: {key}")
    layers[key] = {
        "layer": layer,
        "datatype": datatype,
        "map_name": matches[0].findtext("name"),
        "source": "tech/sky130/sky130.lyp",
    }
write_json(
    ROOT / "data/rules.json",
    {
        "rules": rules,
        "layers": layers,
        "scope": "Ordinary rectangular metal1/metal2 and 0.15um via enclosure only; no signoff claim.",
    },
)
write_json(
    ROOT / "data/deck_categories.json",
    {
        "source_revision": lock["revision"],
        "extraction": "Static .output ID/description pairs; includes conditional outputs not enabled in every run.",
        "categories": {k: v[0] for k, v in sorted(outputs.items())},
    },
)
print(f"Extracted {len(rules)} rules; verified {len(layers)} layer mappings")
