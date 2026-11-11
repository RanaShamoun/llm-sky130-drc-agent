from __future__ import annotations

import argparse
import json
import os

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
    agent = sub.add_parser("agent", help="Run the live OpenAI tool-grounded agent")
    agent.add_argument(
        "--question", default="Check ordinary width and spacing of metal1 routing."
    )
    agent.add_argument(
        "--gds",
        default=None,
        help="GDS path relative to eval/public; omitted for unsupported probes",
    )
    agent.add_argument("--top-cell", default="TOP")
    agent.add_argument("--model", default=None)
    agent.add_argument("--provider", choices=["ollama", "openai"], default=None)
    agent.add_argument("--max-turns", type=int, default=8)
    agent.add_argument(
        "--json", action="store_true", help="Print the full structured result"
    )
    tool = sub.add_parser("tool")
    tool.add_argument("name", choices=[t["name"] for t in TOOL_SCHEMAS])
    tool.add_argument("arguments", help="JSON object")
    args = parser.parse_args()
    try:
        if args.command == "agent":
            from .agent import Agent
            from .local_provider import OllamaClient
            from .provider import OpenAIResponses, load_local_config

            load_local_config()
            provider = args.provider or os.environ.get("DRC_PROVIDER", "ollama")
            if provider == "ollama":
                client = OllamaClient(model=args.model)
            elif provider == "openai":
                client = OpenAIResponses(model=args.model)
            else:
                raise ValueError("Unknown provider. Choose ollama or openai.")
            result = Agent(client, max_turns=args.max_turns).run(
                args.question, args.gds, args.top_cell
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result["explanation"])
                print(f"Model: {result['model']}")
                print(f"Verified: {result['verification']['accepted']}")
                print(f"Saved result: {result['result_path']}")
                for check in result["checks"]:
                    print(f"Source for {check['rule_id']}: {check['source_url']}")
            return 1 if result["verdict"] == "ERROR" else 0
        elif args.command == "doctor":
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
