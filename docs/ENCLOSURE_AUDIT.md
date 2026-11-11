# Enclosure interpretation audit

The first labeling run caught five disagreements between the initial construction predictions and the actual unchanged upstream deck. The disagreement list is preserved in `eval/gold/initial_enclosure_audit.json`. These predictions were not used as final ground truth.

For `via.5a` and `m2.5`, the pinned deck first finds via edges with less than 0.085 um enclosure, then finds corners formed by adjacent deficient edges. For the isolated square vias in this benchmark, a violation occurs when **two adjacent edges both have insufficient enclosure**. This is not equivalent to simply asking whether there exist two adjacent sufficiently enclosed edges.

For example, left/bottom/right/top margins `[0.080, 0.100, 0.080, 0.100]` pass the deck's corner-based rule: the deficient left/right edges are opposite. Margins `[0.085, 0.085, 0.055, 0.055]` fail: right/top are adjacent deficient edges. The original plain-text construction prediction had these outcomes reversed.

The final enclosure cases include minimum-enclosure boundaries, adjacent deficient corners, and opposing sufficient edges. Construction predictions now encode the reviewed corner operation, and labels are still taken solely from separate full-deck KLayout executions. `via.4a` and `m2.4` independently enforce the 0.055 um minimum.

Rule retrieval preserves the deck's descriptions verbatim and adds an applicability note pointing here. Evaluation measures agreement with this **specific pinned KLayout deck**, not proof of conformance to every interpretation of SKY130 documentation. This distinction should appear in the final report. Do not silently relabel the checker output to match a natural-language expectation.

Source: the pinned `sky130A_mr.drc` implementation, whose immutable revision, file hashes, and exact source lines are recorded in `data/sources.lock.json` and `data/rules.json`.
