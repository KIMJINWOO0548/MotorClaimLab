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
    render.add_argument(
        "--selection", type=Path, help="Selection record (defaults to sibling selection.json)"
    )
    render.add_argument("--output", type=Path, required=True)
    sensitivity = commands.add_parser(
        "sensitivity", help="Compare training caps on operator-confirmed synthetic input"
    )
    stability = commands.add_parser(
        "training-stability", help="Resample synthetic training with fixed validation and test data"
    )
    stability.add_argument(
        "--synthetic",
        action="store_true",
        required=True,
        help="Confirm that the local input was independently generated as synthetic",
    )
    for command in (sensitivity, stability):
        for field in ("input", "results", "selection", "output"):
            command.add_argument(f"--{field}", type=Path, required=True)
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
        elif args.command == "sensitivity":
            from .sensitivity import run_sensitivity

            report = run_sensitivity(args.input, args.results, args.selection, args.output)
            print(report["status"], report["reason"] or "")
            return 0 if report["status"] == "COMPARABLE" else 1
        elif args.command == "training-stability":
            from .training_stability import run_training_stability

            report = run_training_stability(args.input, args.results, args.selection, args.output)
            print(report["status"], report["reason"] or "")
            return 0 if report["status"] == "COMPARABLE" else 1
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
        messages = {
            "sensitivity": "Sensitivity could not write or complete the local report.",
            "training-stability": "Could not complete the local training-stability report.",
        }
        message = messages.get(args.command, f"MotorClaimLab: {error}")
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
