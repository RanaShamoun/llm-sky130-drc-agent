# Ten case inspection record

The coding agent inspected the rendered GDS-derived geometry sheet and the corresponding coordinates and report evidence. This is an agent inspection, not an independent human engineering signoff. Blue is metal1, orange is metal2, gray is via; red lines identify supported edge-pair violation evidence. Polygon corner markers remain in the reports and are not converted to invented distances.

| Case | Check from actual layout coordinates | Oracle and inspection conclusion |
|---|---|---|
| b001 | Metal1 spans x = 0 to 0.135 um | Width 0.135 < 0.140; FAIL, marker distance 0.135 um |
| b002 | Metal1 spans x = 0 to 0.140 um | Exact width boundary; PASS |
| b004 | First right edge x = 0.500, next left edge x = 0.635 um | Gap 0.135 < 0.140; FAIL, opposing edges match marker |
| b005 | First right edge x = 0.500, next left edge x = 0.640 um | Gap 0.140 at boundary; PASS |
| b010 | Metal2 has right/left edges at 0.500 and 0.635 um | Gap 0.135 < 0.140; FAIL |
| b011 | Metal2 has right/left edges at 0.500 and 0.640 um | Gap 0.140 at boundary; PASS |
| b037 | Via left x = 0.300, metal1 left x = 0.250 um; other margins 0.100 | Minimum enclosure 0.050 < 0.055; via.4a FAIL. Single deficient edge leaves via.5a PASS |
| b038 | Via left x = 0.300, metal1 left x = 0.245 um | Minimum enclosure 0.055 at boundary; both requested rules PASS |
| b039 | Metal1 left/bottom = 0.220; via left/bottom = 0.300 um | Two adjacent margins 0.080 < 0.085; via.5a FAIL. Minimum margins remain above 0.055, so via.4a PASS |
| b040 | Metal1 left = 0.215, bottom = 0.220 um | Left margin 0.085, bottom 0.080, right/top 0.100; no corner of two deficient edges, both requested rules PASS |

Passing numeric values above are inspection calculations from saved coordinates. They are not claimed as measurements emitted by a passing KLayout check. Scalar values extracted from violating markers were also cross-checked using KLayout's native edge objects across the complete dataset; see `../validation.json`.

The enclosure interpretation is specific to the pinned deck. The initial five construction discrepancies and their resolution are documented in `../../../docs/ENCLOSURE_AUDIT.md` and `../initial_enclosure_audit.json`.
