"""Explicit local CLI; importing the package never downloads data or runs models."""

import argparse
import json
import sys
from pathlib import Path

from .data import SEED, fetch_dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Historical insurance claim frequency research")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Download pinned OpenML ARFF into a new target")
    fetch.add_argument("--output", type=Path, required=True)
    render = commands.add_parser(
        "render", help="Derive a presentation from frozen aggregate results"
    )
    render.add_argument("--results", type=Path, required=True)
    render.add_argument("--selection", type=Path)
    render.add_argument("--output", type=Path, required=True)
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
        elif args.command == "render":
            from .presentation import render_saved

            manifest = render_saved(args.results, args.output, args.selection)
            print(
                json.dumps(
                    {
                        "renderer_version": manifest["renderer_version"],
                        "renderer_sha256": manifest["renderer_sha256"],
                        "model_execution": False,
                        "artifacts": len(manifest["artifacts"]),
                    },
                    indent=2,
                )
            )
        else:
            from .experiment import run_experiment

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
