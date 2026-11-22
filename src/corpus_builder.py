"""
corpus_builder.py

Builds a structured, retrievable rule-text corpus from KLayout's own DRC
report output. This works because a .lyrdb report's <categories> section
lists EVERY rule category defined in the deck (whether or not it was
violated in that particular run) -- not just the ones that fired. So we
can reuse the report from the Week 1 feasibility spike (or any run against
the sky130A_mr.drc deck) as the raw source material for the rule corpus,
rather than hand-transcribing rule text ourselves.

Usage:
    python corpus_builder.py test_violation_report.lyrdb rules_corpus.json

Output: a JSON file, one record per rule category, e.g.:
    {
      "rule_id": "m1.2",
      "raw_description": "m1.2 : min. m1 spacing : 0.14um",
      "layer_hint": "m1",
      "rule_type": "spacing",
      "threshold_value": 0.14,
      "threshold_unit": "um",
      "condition": null
    }

This JSON file is what the retrieval tool will search over -- e.g., loaded
into a simple keyword or embedding-based retriever. Building the retriever
itself is a separate step; this script only produces the corpus.
"""

import sys
import re
import json
import xml.etree.ElementTree as ET

# Known condition phrases that appear in SKY130 rule descriptions and make
# a rule apply only in a specific context. Extend this list if you find
# more while inspecting your own deck's category descriptions.
CONDITION_PHRASES = [
    "for specific cells",
    "in periphery",
    "inside areaid:core",
    "outside areaid:core",
    "inside areaid:ce",
    "across areaid:ce",
    "in areaid:ce",
    "of 2 adjacent edges",
    "should be manually merged if less",
]

# Rough keyword -> rule_type mapping based on the words that show up in
# SKY130's own category descriptions. This is a heuristic, not a guarantee --
# spot-check a sample of the output before trusting it fully.
RULE_TYPE_KEYWORDS = {
    "spacing": "spacing",
    "width": "width",
    "enclosure": "enclosure",
    "enclosed": "enclosure",
    "area": "area",
    "overlap": "overlap",
    "straddle": "straddle",
}


def parse_description(rule_id: str, description: str) -> dict:
    """Pull structured fields out of one rule's free-text description."""
    record = {
        "rule_id": rule_id,
        "raw_description": description,
        "layer_hint": None,
        "rule_type": None,
        "threshold_value": None,
        "threshold_unit": None,
        "condition": None,
    }

    # Threshold value + unit, e.g. "0.14um" or "0.0561um²".
    # Take the LAST match, not the first: descriptions like
    # "m1.3ab : min. 3um.m1 spacing m1 : 0.28um" contain an earlier "3um"
    # (part of a layer name) before the real threshold at the end.
    matches = re.findall(r"([\d.]+)\s*(um|nm)", description)
    if matches:
        value, unit = matches[-1]
        record["threshold_value"] = float(value)
        record["threshold_unit"] = unit

    # Rule type, based on keyword presence (checked in a fixed priority
    # order so e.g. "min. width" doesn't also get flagged as something else)
    desc_lower = description.lower()
    for keyword, rule_type in RULE_TYPE_KEYWORDS.items():
        if keyword in desc_lower:
            record["rule_type"] = rule_type
            break

    # Layer hint: SKY130 category names are usually "<layer>.<number>",
    # e.g. "m1.2" -> layer hint "m1". Falls back to None if the pattern
    # doesn't match (some rule IDs, like MR_lvtn.OVL.2, are irregular).
    m = re.match(r"^([a-zA-Z0-9]+)\.", rule_id)
    if m:
        record["layer_hint"] = m.group(1)

    # Condition: check for any known qualifying phrase
    for phrase in CONDITION_PHRASES:
        if phrase in desc_lower:
            record["condition"] = phrase
            break

    return record


def build_corpus(lyrdb_path: str) -> list:
    tree = ET.parse(lyrdb_path)
    root = tree.getroot()

    records = []
    categories_el = root.find("categories")
    if categories_el is None:
        raise ValueError(
            f"No <categories> section found in {lyrdb_path}. "
            "Make sure this .lyrdb came from a run with feol=true and "
            "beol=true set, or the deck may have skipped all checks "
            "(see the feol/beol gotcha documented in FEASIBILITY_SPIKE.md)."
        )

    for category_el in categories_el.findall("category"):
        name_el = category_el.find("name")
        desc_el = category_el.find("description")
        if name_el is None:
            continue
        rule_id = (name_el.text or "").strip().strip("'\"")
        description = (desc_el.text or "").strip() if desc_el is not None else ""
        if not description:
            continue
        records.append(parse_description(rule_id, description))

    return records


def main():
    if len(sys.argv) != 3:
        print("Usage: python corpus_builder.py <input.lyrdb> <output.json>")
        sys.exit(1)

    lyrdb_path, out_path = sys.argv[1], sys.argv[2]
    records = build_corpus(lyrdb_path)

    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} rule records to {out_path}")

    # Quick sanity check: print a few examples so you can eyeball whether
    # the parsing looks right before trusting it as your retrieval corpus.
    print("\nSample records:")
    for r in records[:5]:
        if r["threshold_value"] is not None:
            threshold = f"{r['threshold_value']}{r['threshold_unit']}"
        else:
            threshold = "none"
        print(f"  {r['rule_id']}: type={r['rule_type']}, "
              f"threshold={threshold}, condition={r['condition']}")


if __name__ == "__main__":
    main()
