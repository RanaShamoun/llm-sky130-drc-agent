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
        ],
        help="See README.md for the normal workflow.",
    )
    args = parser.parse_args()
    try:
        if args.command == "check":
            python("-m", "pytest", "-q")
            python("scripts/verify_benchmark.py")
        elif args.command == "demo":
            python("examples/use_tools.py")
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
                "-m", "ruff", "format", "run.py", "src", "scripts", "tests", "examples"
            )
        else:
            from drc_explain.cli import main as cli_main

            sys.argv = ["drc-explain", args.command]
            return cli_main()
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
