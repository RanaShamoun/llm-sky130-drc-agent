from __future__ import annotations

import argparse
import json

from .benchmark import generate, label
from .runner import Checker
from .tools import TOOL_SCHEMAS, Toolset


def main():
    parser = argparse.ArgumentParser(
        description="DRC-Explain tool and benchmark foundation"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("generate")
    sub.add_parser("label")
    sub.add_parser("schemas")
    tool = sub.add_parser("tool")
    tool.add_argument("name", choices=[t["name"] for t in TOOL_SCHEMAS])
    tool.add_argument("arguments", help="JSON object")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = Checker().provenance()
        elif args.command == "generate":
            result = generate()
        elif args.command == "label":
            result = label()
        elif args.command == "schemas":
            result = TOOL_SCHEMAS
        else:
            result = Toolset().call(args.name, json.loads(args.arguments))
            if not result["ok"]:
                print(json.dumps(result, indent=2))
                return 1
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "verdict": None,
                },
                indent=2,
            )
        )
        return 1
