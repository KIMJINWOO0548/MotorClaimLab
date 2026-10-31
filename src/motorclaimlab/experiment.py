"""Frozen study orchestration; no fitting or model selection on the test split."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from threadpoolctl import threadpool_limits

from .data import (
    SEED,
    SOURCE_MD5,
    load_dataset,
    sample_frame,
    sha256_file,
    split_frame,
    validate_frame,
)
from .eda import summarize_sql
from .evaluation import calibration_table, evaluate_predictions, paired_bootstrap, segment_table
from .models import fit_models

LIMITATIONS = [
    "No observation-date field: policy holdout is not a temporal validation.",
    "OpenML asserts CC0; original-insurer permission/provenance is not independently verified.",
    "No clipping of unusual valid exposures/counts; source anomalies may affect the comparison.",
    "Model selected on validation; test segments are exploratory, not threshold optimization.",
    "Bootstrap interval is conditional on this split and frozen fits; not retraining uncertainty.",
    "No causal, fairness, pricing, underwriting, claim-decision or measured business-impact claim.",
    "Internal AI-assisted review is not external human or actuarial review.",
]


def _json(path: Path, value: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def code_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _git_commit() -> str | None:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists():
        return None
    command = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return command.stdout.strip() if command.returncode == 0 else None


def _positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def run_experiment(
    input_path: Path,
    output_dir: Path,
    seed: int = SEED,
    max_rows: int | None = None,
    max_iter: int = 100,
    bootstrap_draws: int = 200,
) -> dict:
    """Run one frozen protocol into a fresh directory, preserving failed runs."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Output directory already exists; choose a fresh run path")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer from 0 to 2**32 - 1")
    _positive_integer(max_iter, "max_iter")
    _positive_integer(bootstrap_draws, "bootstrap_draws")
    started = time.perf_counter()
    full = load_dataset(input_path)
    audit = validate_frame(full)
    records = sample_frame(full, max_rows, seed)
    partitions = split_frame(records, seed)
    if any(part.empty for part in partitions.values()):
        raise ValueError("Hash split produced an empty partition; use more source observations")
    output_dir.mkdir(parents=True, exist_ok=False)
    settings = {
        "seed": seed,
        "max_rows": max_rows,
        "max_iter": max_iter,
        "bootstrap_draws": bootstrap_draws,
        "thread_limit": 2,
        "split_method": "sha256-policy-id-60-20-20",
        "test_used_for_selection": False,
        "glm": {"alpha": 1e-4, "max_iter": 300, "tol": 1e-6},
        "hgb": {
            "max_iter": max_iter,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 100,
            "learning_rate": 0.05,
            "early_stopping": False,
            "loss": "poisson",
        },
    }
    _json(
        output_dir / "execution.json",
        {
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
            "settings": settings,
        },
    )
    try:
        split_summaries = {}
        memberships = []
        for name, subset in partitions.items():
            ids = "\n".join(str(int(pid)) for pid in subset.IDpol).encode("ascii")
            split_summaries[name] = {
                "rows": len(subset),
                "claims": int(subset.ClaimNb.sum()),
                "exposure": float(subset.Exposure.sum()),
                "membership_sha256": hashlib.sha256(ids).hexdigest(),
            }
            memberships.append(subset[["IDpol"]].assign(split=name))
        pd.concat(memberships).to_csv(output_dir / "split-membership.csv", index=False)
        fit_started = time.perf_counter()
        with threadpool_limits(limits=2):
            models = fit_models(partitions["train"], seed=seed, max_iter=max_iter)
            fit_seconds = time.perf_counter() - fit_started
            validation_predictions = {
                name: model.predict(partitions["validation"]) for name, model in models.items()
            }
            validation = {
                name: evaluate_predictions(partitions["validation"], prediction)
                for name, prediction in validation_predictions.items()
            }
            # Dict order is complexity order; min() retains first on exact ties.
            selected = min(validation, key=lambda name: validation[name]["mean_poisson_deviance"])
            # Freeze choice BEFORE test predictions, scores, calibration or segments exist.
            _json(
                output_dir / "selection.json",
                {
                    "selected_model": selected,
                    "selection_split": "validation",
                    "metric": "exposure_weighted_mean_poisson_deviance",
                    "settings": settings,
                    "validation": validation,
                },
            )
            test_predictions = {
                name: model.predict(partitions["test"]) for name, model in models.items()
            }
            test = {
                name: evaluate_predictions(partitions["test"], prediction)
                for name, prediction in test_predictions.items()
            }
            calibration = {
                name: calibration_table(partitions["test"], prediction)
                for name, prediction in test_predictions.items()
            }
            segments = segment_table(partitions["test"], test_predictions[selected])
            bootstrap = paired_bootstrap(
                partitions["test"],
                test_predictions[selected],
                test_predictions["mean"],
                seed,
                bootstrap_draws,
            )
        local_predictions = partitions["test"][["IDpol", "ClaimNb", "Exposure"]].copy()
        for name, prediction in test_predictions.items():
            local_predictions[name] = prediction
        local_predictions.to_csv(output_dir / "predictions.csv", index=False)
        source_md5 = hashlib.md5(input_path.read_bytes(), usedforsecurity=False).hexdigest()
        pinned = source_md5 == SOURCE_MD5
        results = {
            "study": {
                "name": "MotorClaimLab",
                "seed": seed,
                "sampled": len(records) < len(full),
                "rows": len(records),
                "selection_split": "validation",
                "data_kind": "openml_pinned" if pinned else "local_unverified",
                "settings": settings,
            },
            "audit": audit,
            "selected_model": selected,
            "splits": split_summaries,
            "metrics": {"validation": validation, "test": test},
            "calibration": calibration,
            "segments": segments,
            "bootstrap": bootstrap,
            "eda": summarize_sql(records),
            "provenance": {
                "source_sha256": sha256_file(input_path),
                "source_md5": source_md5,
                "source_matches_pinned": pinned,
                "code_sha256": code_fingerprint(),
                "git_commit": _git_commit(),
                "policy_records_redistributed": False,
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.system(),
                "packages": {
                    name: importlib.metadata.version(name)
                    for name in [
                        "numpy",
                        "pandas",
                        "scipy",
                        "scikit-learn",
                        "matplotlib",
                        "threadpoolctl",
                    ]
                },
            },
            "timing": {"fit_seconds": fit_seconds, "total_seconds": time.perf_counter() - started},
            "limitations": LIMITATIONS
            + [
                "Historical French benchmark; current Korean or KB insurance validity is untested."
                if pinned
                else "Local input does not match pinned OpenML bytes; "
                "origin and real/synthetic status are unverified."
            ],
        }
        from .report import render_markdown, render_report, write_figures

        write_figures(results, output_dir / "figures")
        (output_dir / "report.html").write_text(render_report(results), encoding="utf-8")
        (output_dir / "report.md").write_text(render_markdown(results), encoding="utf-8")
        _json(output_dir / "results.json", results)
        _json(
            output_dir / "execution.json",
            {
                "status": "completed",
                "exit_code": 0,
                "completed_at": datetime.now(UTC).isoformat(),
                "settings": settings,
            },
        )
        return results
    except Exception as error:
        _json(
            output_dir / "execution.json",
            {
                "status": "failed",
                "exit_code": 1,
                "error_type": type(error).__name__,
                "error": str(error),
                "settings": settings,
            },
        )
        raise
