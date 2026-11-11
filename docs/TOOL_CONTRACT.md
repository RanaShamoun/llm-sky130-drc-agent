# Public tool contract

`Toolset.call(name, arguments)` is the only dispatch surface needed by the agent. Schemas are exported as `TOOL_SCHEMAS` in `src/drc_explain/tools.py` (or via the optional installed CLI, `drc-explain schemas`). Distances, bounding boxes, and marker coordinates are in micrometers. `dbu_um` describes the GDS integer database unit; the benchmark uses 0.001 um database units and coordinates on the 0.005 um manufacturing grid.

| Tool | Required input | Result |
|---|---|---|
| `retrieve_rules` | `query` | Ranked supported rules with IDs, descriptions, limits, applicability, immutable source URLs |
| `inspect_layout` | `gds_path` | Top cell, DBU, layers, polygon coordinates, shape counts, bounding boxes |
| `run_drc` | `gds_path`, nonempty `rule_ids` | Scoped PASS/FAIL, per-rule status and limits, original violation evidence, available measurements, provenance |

`top_cell` defaults to `TOP`; rule lookup `limit` defaults to five and is bounded to 1..8. GDS paths resolve within the configured public root. Duplicate rule IDs, unknown rules, missing required layers, missing cells, off-grid layouts, nonrectangular geometry, unsupported layer types, wide-metal geometry, and non-0.15 um vias are rejected by the DRC tool. Input size is capped at 10,000 geometry shapes during inspection. This is a narrow benchmark tool, not support for arbitrary real chip layouts.

A DRC success response includes `execution_mode: "full_deck_then_filter"`, a scope statement, and only requested rule results. The wrapper runs FEOL/BEOL explicitly, rejects nonzero execution or error output, requires a valid nonempty report and all eight expected categories, enforces a timeout, and checks exact source hashes and batch version. No gold file is consulted by tool execution.

Example result fragment for `benchmark/b004.gds` with `m1.2`:

```json
{
  "ok": true,
  "result": {
    "status": "FAIL",
    "execution_mode": "full_deck_then_filter",
    "units": "um",
    "checks": [{
      "rule_id": "m1.2",
      "status": "FAIL",
      "limit_um": 0.14,
      "violations": [{
        "rule_id": "m1.2",
        "cell": "TOP",
        "markers": [{
          "raw": "edge-pair: (0.635,0;0.635,0.5)/(0.5,0.5;0.5,0)",
          "measured_um": 0.135
        }]
      }]
    }]
  }
}
```

This fragment omits descriptive and provenance fields for readability. `docs/examples/tool_session.json` contains complete real tool responses.
