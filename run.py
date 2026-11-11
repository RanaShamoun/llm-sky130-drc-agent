"""Simple project commands. Run `python run.py --help` from any directory."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def python(*arguments):
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description="DRC Explain: start here")
    parser.add_argument(
        "command",
        choices=[
            "check",
            "demo",
            "smoke",
            "doctor",
            "setup-sources",
            "generate",
            "label",
            "format",
            "configure",
            "agent",
            "agent-smoke",
            "serve-local",
            "pull-local",
        ],
        help="See README.md for the normal workflow.",
    )
    args, extra = parser.parse_known_args()
    if extra and args.command != "agent":
        parser.error("Extra arguments are supported only for the agent command.")
    try:
        if args.command == "check":
            python("-m", "pytest", "-q")
            python("scripts/verify_benchmark.py")
        elif args.command == "demo":
            python("examples/use_tools.py")
        elif args.command == "serve-local":
            from drc_explain.local_runtime import ensure_server

            ensure_server()
            print(
                "Local Ollama is running. Cloud features are disabled when started by this project."
            )
        elif args.command == "pull-local":
            from drc_explain.local_runtime import pull_model

            pull_model()
        elif args.command == "configure":
            from drc_explain.provider import configure_api

            configure_api()
        elif args.command == "agent-smoke":
            python("scripts/smoke_agent.py")
        elif args.command == "smoke":
            python("scripts/smoke_handoff.py")
        elif args.command == "setup-sources":
            python("scripts/bootstrap_sources.py")
            python("scripts/build_catalog.py")
        elif args.command == "format":
            python(
                "-m",
                "ruff",
                "check",
                "--select",
                "I",
                "--fix",
                "run.py",
                "src",
                "scripts",
                "tests",
                "examples",
            )
            python(
                "-m",
                "ruff",
                "format",
                "run.py",
                "src",
                "scripts",
                "tests",
                "examples",
            )
        else:
            from drc_explain.cli import main as cli_main

            sys.argv = ["drc-explain", args.command, *extra]
            return cli_main()
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
