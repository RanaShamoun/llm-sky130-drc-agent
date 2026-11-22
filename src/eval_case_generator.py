"""
eval_case_generator.py

Generates the four harder eval case types requested in instructor feedback,
instead of simple random/obvious-violation geometries like the Week 1 spike
used. Each function writes a GDS file and returns a metadata dict describing
the expected ground truth -- but remember: the KLayout DRC oracle run is
still the actual source of truth for labeling (see FEASIBILITY_SPIKE.md).
These "expected" fields are your own prediction, useful for the 10-case
hand-inspection cross-check in Week 3-4, not a substitute for running the
real oracle.

IMPORTANT: layer numbers below are confirmed ONLY for the metal1 drawing
layer (68/20), verified against sky130A.lyp during the Week 1 spike. If you
add cases on other layers (e.g. contacts/vias for enclosure rules), you
MUST verify those layer numbers the same way before trusting the results:

    findstr /i "<layername>" "<path-to-sky130A.lyp>"

Do not assume layer numbers from memory or from other PDK versions.
"""

import json
import klayout.db as db

MET1_LAYER = (68, 20)      # confirmed: met1.drawing, Week 1 spike
MET1_SPACING_UM = 0.14     # rule m1.2
MET1_WIDTH_UM = 0.14       # rule m1.1


def _new_layout(top_cell_name="TOP"):
    layout = db.Layout()
    top = layout.create_cell(top_cell_name)
    dbu = layout.dbu

    def um(v):
        return int(round(v / dbu))

    return layout, top, um


def generate_spacing_case(gap_um, layer=MET1_LAYER, out_path="case.gds",
                           top_cell_name="TOP", rule_id="m1.2",
                           threshold_um=MET1_SPACING_UM):
    """Two rectangles separated by `gap_um`. Writes one GDS file."""
    layout, top, um = _new_layout(top_cell_name)

    box1 = db.Box(um(0.0), um(0.0), um(0.5), um(0.5))
    box2 = db.Box(um(0.5 + gap_um), um(0.0), um(1.0 + gap_um), um(0.5))
    top.shapes(layout.layer(*layer)).insert(box1)
    top.shapes(layout.layer(*layer)).insert(box2)
    layout.write(out_path)

    return {
        "case_type": "spacing",
        "gds_path": out_path,
        "top_cell": top_cell_name,
        "rule_id": rule_id,
        "threshold_um": threshold_um,
        "measured_gap_um": round(gap_um, 4),
        "expected_pass": gap_um >= threshold_um,
    }


def generate_width_case(width_um, layer=MET1_LAYER, out_path="case.gds",
                         top_cell_name="TOP", rule_id="m1.1",
                         threshold_um=MET1_WIDTH_UM):
    """One rectangle of the given width. Writes one GDS file."""
    layout, top, um = _new_layout(top_cell_name)

    box = db.Box(um(0.0), um(0.0), um(width_um), um(0.5))
    top.shapes(layout.layer(*layer)).insert(box)
    layout.write(out_path)

    return {
        "case_type": "width",
        "gds_path": out_path,
        "top_cell": top_cell_name,
        "rule_id": rule_id,
        "threshold_um": threshold_um,
        "measured_width_um": round(width_um, 4),
        "expected_pass": width_um >= threshold_um,
    }


def generate_near_boundary_set(offsets_um, base_name="near_boundary",
                                threshold_um=MET1_SPACING_UM, out_dir="."):
    """
    Generates one spacing case per offset in offsets_um, where each case's
    gap = threshold_um + offset_um. Negative offsets should fail, positive
    (or zero) offsets should pass -- this is the core "near-boundary" idea:
    offsets should be SMALL (e.g. +/-0.002 to +/-0.01 um), not the 5nm-vs-
    140nm gulf used in the Week 1 spike's obvious test violation.
    """
    cases = []
    for i, offset in enumerate(offsets_um):
        gap = threshold_um + offset
        out_path = f"{out_dir}/{base_name}_{i:02d}.gds"
        case = generate_spacing_case(gap, out_path=out_path,
                                      top_cell_name=f"{base_name.upper()}_{i}")
        case["offset_from_threshold_um"] = round(offset, 4)
        cases.append(case)
    return cases


def generate_matched_pair(delta_um=0.002, base_name="matched_pair",
                           threshold_um=MET1_SPACING_UM, out_dir="."):
    """
    Generates exactly two layouts differing only by 2*delta_um in gap size:
    one just under the threshold (fail) and one just over it (pass). This
    directly tests whether the agent's verdict tracks the true boundary
    rather than pattern-matching on "looks tight" vs "looks fine".
    """
    fail_path = f"{out_dir}/{base_name}_fail.gds"
    pass_path = f"{out_dir}/{base_name}_pass.gds"

    fail_case = generate_spacing_case(threshold_um - delta_um, out_path=fail_path,
                                       top_cell_name=f"{base_name.upper()}_FAIL")
    pass_case = generate_spacing_case(threshold_um + delta_um, out_path=pass_path,
                                       top_cell_name=f"{base_name.upper()}_PASS")

    fail_case["pair_id"] = base_name
    pass_case["pair_id"] = base_name
    return [fail_case, pass_case]


def generate_competing_rule_case(out_path="competing.gds", top_cell_name="COMPETING",
                                  spacing_gap_um=0.14 - 0.01,
                                  width_val_um=0.14 - 0.01,
                                  focus="spacing"):
    """
    Places TWO separate violations in the same layout: a spacing violation
    in one region and a width violation in a different region. `focus`
    indicates which one the eval scenario's natural-language question is
    actually about -- e.g., if focus="spacing", the scenario text should
    ask specifically about the spacing region, and the width violation
    elsewhere is a distractor the agent should NOT report on unless asked.

    This tests whether the agent's rule-retrieval and scope-decision steps
    correctly narrow to the relevant rule/region rather than reporting
    every violation KLayout happens to find.
    """
    layout, top, um = _new_layout(top_cell_name)

    # Spacing violation region (near x=0 to x=1)
    box1 = db.Box(um(0.0), um(0.0), um(0.5), um(0.5))
    box2 = db.Box(um(0.5 + spacing_gap_um), um(0.0), um(1.0 + spacing_gap_um), um(0.5))
    top.shapes(layout.layer(*MET1_LAYER)).insert(box1)
    top.shapes(layout.layer(*MET1_LAYER)).insert(box2)

    # Width violation region, placed far away (near x=5) so it's spatially
    # distinct and could plausibly be excluded by a scope decision
    box3 = db.Box(um(5.0), um(0.0), um(5.0 + width_val_um), um(0.5))
    top.shapes(layout.layer(*MET1_LAYER)).insert(box3)

    layout.write(out_path)

    return {
        "case_type": "competing_rules",
        "gds_path": out_path,
        "top_cell": top_cell_name,
        "focus_region": "spacing" if focus == "spacing" else "width",
        "distractor_region": "width" if focus == "spacing" else "spacing",
        "spacing_rule_id": "m1.2",
        "width_rule_id": "m1.1",
        "spacing_expected_pass": spacing_gap_um >= MET1_SPACING_UM,
        "width_expected_pass": width_val_um >= MET1_WIDTH_UM,
        "note": ("The eval scenario text paired with this case should ask "
                 "specifically about the `focus_region`. Correct agent "
                 "behavior is to retrieve/report on that region's rule, "
                 "not the distractor's."),
    }


def generate_conditional_case_STUB(**kwargs):
    """
    STUB -- not yet implemented.

    Conditional/enclosure cases (e.g., a general enclosure rule vs. a
    "for specific cells" variant, like m1.4 vs m1.4a) require a second
    layer -- typically a contact/via layer (e.g. mcon) plus, for the
    conditional variant, a marker layer indicating the special condition
    (e.g. an areaid marker layer).

    Before implementing this function for real:
      1. Find the mcon (or relevant via) GDS layer/datatype the same way
         met1 was confirmed in the Week 1 spike:
             findstr /i "mcon" "<path-to-sky130A.lyp>"
      2. Find the areaid/marker layer referenced in the conditional rule's
         description (e.g. search the .lyrdb category list for the exact
         condition text, then findstr for that marker name in the .lyp).
      3. Only then write geometry using VERIFIED layer numbers -- do not
         guess, per the lesson learned with the met1 layer number mismatch
         in the original spike (67/20 assumed vs. 68/20 confirmed).
    """
    raise NotImplementedError(
        "Verify mcon and marker layer numbers against sky130A.lyp before "
        "implementing this case type. See docstring for the exact steps."
    )


def main():
    """Generates a full example eval batch and writes a manifest JSON."""
    all_cases = []

    # Near-boundary: small offsets around the m1.2 spacing threshold
    all_cases += generate_near_boundary_set(
        offsets_um=[-0.01, -0.005, -0.002, 0.0, 0.002, 0.005, 0.01],
        base_name="near_boundary_spacing",
    )

    # Matched pass/fail pair
    all_cases += generate_matched_pair(delta_um=0.002, base_name="matched_pair_1")

    # Competing candidate rules (one case, focus on spacing)
    all_cases.append(generate_competing_rule_case(
        out_path="competing_1.gds", focus="spacing"
    ))

    with open("eval_manifest.json", "w") as f:
        json.dump(all_cases, f, indent=2)

    print(f"Generated {len(all_cases)} cases. Manifest written to eval_manifest.json")
    print("NOTE: 'expected_pass' fields are your own prediction based on the "
          "geometry you generated -- run every case through the KLayout DRC "
          "oracle (drc_runner, not yet built) to get the real ground-truth "
          "label before trusting these for evaluation.")


if __name__ == "__main__":
    main()
