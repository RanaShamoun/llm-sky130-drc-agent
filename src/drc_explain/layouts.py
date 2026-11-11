from __future__ import annotations

from pathlib import Path

import klayout.db as db

from .common import ROOT, read_json


class LayoutError(ValueError):
    pass


def inspect_layout(gds_path, top_cell="TOP", max_shapes=10000):
    layout = db.Layout()
    path = Path(gds_path)
    if not path.is_file():
        raise LayoutError(f"Layout not found: {path}")
    layout.read(str(path))
    cell = layout.cell(top_cell)
    if cell is None:
        raise LayoutError(f"Top cell {top_cell!r} not found.")
    catalog = read_json(ROOT / "data/rules.json")
    known = {(v["layer"], v["datatype"]): k for k, v in catalog["layers"].items()}
    layers = []
    count = 0
    for index in layout.layer_indices():
        info = layout.get_info(index)
        iterator = cell.begin_shapes_rec(index)
        polygons = []
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_text():
                iterator.next()
                continue
            if not (shape.is_box() or shape.is_polygon() or shape.is_path()):
                raise LayoutError("Unsupported GDS shape type.")
            count += 1
            if count > max_shapes:
                raise LayoutError(f"Layout exceeds {max_shapes} geometry shapes.")
            poly = shape.polygon.transformed(iterator.trans())
            if poly.holes():
                raise LayoutError("Polygons with holes are outside v1 input scope.")
            points = [
                [round(p.x * layout.dbu, 9), round(p.y * layout.dbu, 9)]
                for p in poly.each_point_hull()
            ]
            box = poly.bbox()
            polygons.append(
                {
                    "points_um": points,
                    "bbox_um": [
                        round(v * layout.dbu, 9)
                        for v in (box.left, box.bottom, box.right, box.top)
                    ],
                    "is_rectangle": poly.is_box(),
                }
            )
            iterator.next()
        if polygons:
            layers.append(
                {
                    "name": known.get((info.layer, info.datatype), "unknown"),
                    "layer": info.layer,
                    "datatype": info.datatype,
                    "shape_count": len(polygons),
                    "polygons": polygons,
                }
            )
    if not layers:
        raise LayoutError("Layout has no geometry.")
    return {
        "top_cell": top_cell,
        "units": "um",
        "dbu_um": layout.dbu,
        "shape_count": count,
        "layers": layers,
    }
