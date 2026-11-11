"""Render a ten-case inspection sheet from the saved GDS-derived coordinates.

Optional dependency: Pillow. This script does not create or change labels.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
cases = {
    r["case_id"]: r for r in json.loads((root / "eval/public/cases.json").read_text())
}
labels = {
    r["case_id"]: r for r in json.loads((root / "eval/gold/labels.json").read_text())
}
ids = ["b001", "b002", "b004", "b005", "b010", "b011", "b037", "b038", "b039", "b040"]
image = Image.new("RGB", (1600, 1900), "white")
draw = ImageDraw.Draw(image)
font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
try:
    font = ImageFont.truetype(font_path, 20)
    small = ImageFont.truetype(font_path, 15)
except OSError:
    font = small = ImageFont.load_default()
colors = {"m1": "#4c78a8", "m2": "#f2a541", "via": "#505050"}
for i, id in enumerate(ids):
    x0 = (i % 2) * 800 + 20
    y0 = (i // 2) * 380 + 15
    case = cases[id]
    gold = labels[id]
    draw.text((x0, y0), id + "  " + str(gold["rule_status"]), fill="black", font=font)
    shapes = [
        (layer["name"], p)
        for layer in case["layout"]["layers"]
        for p in layer["polygons"]
    ]
    allpoints = [xy for _, p in shapes for xy in p["points_um"]]
    xmin = min(p[0] for p in allpoints)
    xmax = max(p[0] for p in allpoints)
    ymin = min(p[1] for p in allpoints)
    ymax = max(p[1] for p in allpoints)
    scale = min(650 / max(xmax - xmin, 0.01), 220 / max(ymax - ymin, 0.01))

    def transform(p):
        return (x0 + 35 + (p[0] - xmin) * scale, y0 + 270 - (p[1] - ymin) * scale)

    for name, p in sorted(
        shapes,
        key=lambda item: -(
            (item[1]["bbox_um"][2] - item[1]["bbox_um"][0])
            * (item[1]["bbox_um"][3] - item[1]["bbox_um"][1])
        ),
    ):
        points = [transform(xy) for xy in p["points_um"]]
        draw.polygon(points, fill=colors.get(name, "#bbbbbb"), outline="black", width=2)
    for v in gold["violations"]:
        for m in v["markers"]:
            if m.get("edge_pair_um"):
                a, b, c, d = map(transform, m["edge_pair_um"])
                draw.line([a, b], fill="#e00000", width=4)
                draw.line([c, d], fill="#e00000", width=4)
    y = y0 + 285
    for name, p in shapes:
        draw.text(
            (x0 + 10, y),
            name + " bbox " + str(p["bbox_um"]) + " um",
            fill=colors.get(name, "black"),
            font=small,
        )
        y += 19
    draw.line((x0, y0 + 365, x0 + 760, y0 + 365), fill="#dddddd")
output = root / "eval/gold/review/ten_case_geometry.png"
output.parent.mkdir(parents=True, exist_ok=True)
image.save(output)
print(output)
