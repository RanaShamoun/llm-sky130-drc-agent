"""Strict parsing of KLayout XML reports, preserving original marker evidence."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
PAIR = re.compile(
    r"^edge-pair:\s*\(("
    + NUMBER
    + r"),("
    + NUMBER
    + r");("
    + NUMBER
    + r"),("
    + NUMBER
    + r")\)[/|]\(("
    + NUMBER
    + r"),("
    + NUMBER
    + r");("
    + NUMBER
    + r"),("
    + NUMBER
    + r")\)$"
)


class ReportError(RuntimeError):
    pass


def marker_measurement(value):
    """Only parallel, axis-aligned, overlapping edge pairs yield a scalar in v1.

    Polygon/corner markers retain their coordinates but never get a guessed value.
    """
    match = PAIR.fullmatch(value.strip())
    if not match:
        return {
            "measured_um": None,
            "measurement_reason": "Marker is not a supported edge pair.",
        }
    v = list(map(float, match.groups()))
    a, b, c, d = [v[i : i + 2] for i in range(0, 8, 2)]
    edges = [a, b, c, d]
    if (
        a[0] == b[0]
        and c[0] == d[0]
        and max(min(a[1], b[1]), min(c[1], d[1]))
        <= min(max(a[1], b[1]), max(c[1], d[1]))
    ):
        distance = abs(a[0] - c[0])
    elif (
        a[1] == b[1]
        and c[1] == d[1]
        and max(min(a[0], b[0]), min(c[0], d[0]))
        <= min(max(a[0], b[0]), max(c[0], d[0]))
    ):
        distance = abs(a[1] - c[1])
    else:
        return {
            "edge_pair_um": edges,
            "measured_um": None,
            "measurement_reason": "Nonparallel or nonoverlapping edge pair; scalar extraction unsupported.",
        }
    return {
        "edge_pair_um": edges,
        "measured_um": round(distance, 9),
        "measurement_source": "Distance between parallel edges in the KLayout violation marker.",
    }


def parse_report(path):
    try:
        root = ET.parse(path if hasattr(path, "read") else Path(path)).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ReportError(f"Missing or invalid KLayout report: {exc}") from exc
    if root.tag != "report-database":
        raise ReportError("Expected a KLayout report-database root.")
    categories = {}

    def walk(parent, prefix=""):
        for c in parent.findall("category"):
            name = c.findtext("name", "").strip("'\"")
            if not name:
                raise ReportError("Unnamed report category.")
            full = f"{prefix}.{name}" if prefix else name
            categories[full] = c.findtext("description", "")
            child = c.find("categories")
            if child is not None:
                walk(child, full)

    container = root.find("categories")
    if container is None:
        raise ReportError("Missing categories section.")
    walk(container)
    if not categories:
        raise ReportError("Zero checked categories; refusing to interpret as PASS.")
    if root.find("items") is None:
        raise ReportError("Missing items section.")
    violations = []
    for item in root.findall("./items/item"):
        rule = item.findtext("category", "").strip("'\"")
        if rule not in categories:
            raise ReportError(f"Unknown marker category {rule!r}")
        values = [v.text or "" for v in item.findall("./values/value")]
        violations.append(
            {
                "rule_id": rule,
                "cell": item.findtext("cell"),
                "markers": [
                    dict(raw=value, **marker_measurement(value)) for value in values
                ],
            }
        )
    return {"categories": categories, "violations": violations}
