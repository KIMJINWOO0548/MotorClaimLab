"""Explicit local CLI; importing the package never downloads data or runs models."""

import argparse
import json
import sys
from pathlib import Path

from .data import SEED, fetch_dataset
from .experiment import run_experiment


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Historical insurance claim frequency research")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Download pinned OpenML ARFF into a new target")
    fetch.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run", help="Run frozen study and create a standalone report")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--seed", type=int, default=SEED)
    run.add_argument("--max-rows", type=int)
    run.add_argument("--max-iter", type=int, default=100)
    run.add_argument("--bootstrap-draws", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            print(fetch_dataset(args.output))
        else:
            result = run_experiment(
                args.input,
                args.output,
                args.seed,
                args.max_rows,
                args.max_iter,
                args.bootstrap_draws,
            )
            print(
                json.dumps(
                    {
                        "selected_model": result["selected_model"],
                        "rows": result["study"]["rows"],
                        "test_metrics": result["metrics"]["test"],
                        "report": str(args.output / "report.html"),
                    },
                    indent=2,
                )
            )
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"MotorClaimLab: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
