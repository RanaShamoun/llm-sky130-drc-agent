"""The three callables Rana can register with any model provider."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT, read_json
from .layouts import inspect_layout
from .runner import Checker

TOOL_SCHEMAS = [
    {
        "name": "retrieve_rules",
        "description": "Search the supported pinned SKY130 rule corpus; returns limits and source citations.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_layout",
        "description": "Read a benchmark-relative GDS and return layer names, polygons, and bounding boxes in um.",
        "parameters": {
            "type": "object",
            "properties": {
                "gds_path": {"type": "string"},
                "top_cell": {"type": "string"},
            },
            "required": ["gds_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_drc",
        "description": "Check explicitly chosen supported rule IDs; results cover only requested rules and are not signoff.",
        "parameters": {
            "type": "object",
            "properties": {
                "gds_path": {"type": "string"},
                "rule_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "top_cell": {"type": "string"},
            },
            "required": ["gds_path", "rule_ids"],
            "additionalProperties": False,
        },
    },
]


def retrieve_rules(query, limit=5):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be nonempty text.")
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("limit must be 1..8.")

    def tokens(text):
        text = (
            text.lower()
            .replace("metal1", "m1")
            .replace("metal2", "m2")
            .replace("met1", "m1")
            .replace("met2", "m2")
        )
        text = (
            text.replace("gap", "spacing")
            .replace("landing", "enclosure")
            .replace("enclose", "enclosure")
        )
        return set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", text)) - {
            "the",
            "of",
            "is",
            "in",
            "a",
            "and",
            "to",
            "for",
            "by",
            "minimum",
            "min",
        }

    query_tokens = tokens(query)
    rules = read_json(ROOT / "data/rules.json")["rules"]
    ranked = []
    for rule in rules:
        corpus = " ".join(
            [
                rule["rule_id"],
                rule["category"],
                rule["description"],
                rule["applicability"],
            ]
        )
        score = len(query_tokens & tokens(corpus))
        if rule["rule_id"].lower() in query.lower():
            score += 10
        if score:
            ranked.append(dict(rule, retrieval_score=score))
    ranked.sort(key=lambda r: (-r["retrieval_score"], r["rule_id"]))
    return {
        "rules": ranked[:limit],
        "scope": "Eight curated rules for ordinary rectangular metal1/metal2 and via geometry. Other rules are unsupported.",
    }


class Toolset:
    def __init__(self, layout_root=None, log_path=None, checker=None):
        # Passing only public/ to this class keeps eval/gold inaccessible via tools.
        self.layout_root = Path(layout_root or ROOT / "eval/public").resolve()
        self.log_path = Path(log_path or ROOT / "runs/tool_calls.jsonl")
        self.checker = checker or Checker()

    def _layout(self, relative):
        if not isinstance(relative, str):
            raise ValueError("gds_path must be text.")
        path = (self.layout_root / relative).resolve()
        if not path.is_relative_to(self.layout_root) or path.suffix.lower() != ".gds":
            raise ValueError(
                "GDS path must stay inside the configured public layout root."
            )
        if not path.is_file():
            raise ValueError("GDS file does not exist.")
        return path

    def call(self, name, arguments):
        start = time.perf_counter()
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object.")
            schemas = {t["name"]: t["parameters"] for t in TOOL_SCHEMAS}
            if name not in schemas:
                raise ValueError("Unknown tool name.")
            schema = schemas[name]
            if set(arguments) - set(schema["properties"]) or set(
                schema["required"]
            ) - set(arguments):
                raise ValueError("Missing required or unexpected tool arguments.")
            if name == "retrieve_rules":
                result = retrieve_rules(**arguments)
            else:
                args = dict(arguments)
                args["gds_path"] = self._layout(args["gds_path"])
                if name == "inspect_layout":
                    result = inspect_layout(**args)
                else:
                    result = self.checker.run_selected(**args)
            response = {"ok": True, "result": result}
        except Exception as exc:
            response = {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "verdict": None,
            }
        entry = {
            "tool": name,
            "arguments": arguments,
            "timestamp": stamp,
            "latency_s": round(time.perf_counter() - start, 6),
            "response": response,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return response
