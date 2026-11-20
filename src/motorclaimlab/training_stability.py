"""Replay validation selections with five resampled synthetic training populations."""

import math
import stat
import warnings
from html import escape
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

from .data import sha256_file
from .evaluation import evaluate_predictions
from .experiment import _json, _require_unchanged_source, code_fingerprint
from .models import fit_models
from .saved_contract import (
    FROZEN_RESULTS,
    FROZEN_SELECTION,
    MODELS,
    _digest,
    load_saved,
    sha256,
    validate_run,
)
from .sensitivity import (
    FORMULA_VERSION,
    _check_metric_support,
    _matching_metrics,
    _prepare_replay,
    _require,
    _test_metrics,
    _Unavailable,
)

SCHEMA_VERSION = "motorclaimlab.training-stability.v1"
SEEDS = (20261121, 20261122, 20261123, 20261124, 20261125)
ARTIFACTS = ("training-stability.json", "report.md", "report.html")
PUBLIC_SOURCE_SHA256 = "a45363e056e2ea56408b38eeb9d4d04d7f6c6982eb7a14ed5e807c7c71807cdd"


def _resample(train, seed):
    ordered = train.sort_values("IDpol")
    positions = np.random.Generator(np.random.PCG64(seed)).integers(
        0, len(ordered), size=len(ordered)
    )
    return ordered.iloc[positions].reset_index(drop=True)


def _sample_summary(sample):
    identifiers = [int(value) for value in sample.IDpol]
    return dict(
        rows=len(identifiers),
        unique_policies=len(set(identifiers)),
        exposure=math.fsum(float(value) for value in sample.Exposure),
        observed_claims=sum(int(value) for value in sample.ClaimNb),
        policy_sample_sha256=_digest(identifiers),
    )


def _evaluate(study, partition, models, names):
    study.check_splits()
    frame = study.splits[partition]
    try:
        metrics = {name: evaluate_predictions(frame, models[name].predict(frame)) for name in names}
    except Exception as error:
        raise _Unavailable("EVAL_MISMATCH") from error
    study.check_splits()
    _check_metric_support(metrics, study.signatures[partition][0])
    return metrics


def _fit(sample, study):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            return fit_models(sample, seed=study.seed, max_iter=study.max_iter)
    except Exception as error:
        raise _Unavailable("FIT_FAILED") from error


def _run_repetitions(study, results, baseline, scratch):
    train = study.splits["train"]
    trials = []
    with threadpool_limits(limits=2):
        study.check_splits()
        reference_models = _fit(train.copy(deep=True), study)
        validation = _evaluate(study, "validation", reference_models, MODELS)
        selected_reference = min(MODELS, key=lambda name: validation[name]["mean_poisson_deviance"])
        _require(
            selected_reference == results["selected_model"]
            and _matching_metrics(validation, results["metrics"]["validation"]),
            "REPLAY_MISMATCH",
        )
        for seed in SEEDS:
            sample = _resample(train, seed)
            try:
                stats = _sample_summary(sample)
            except OverflowError as error:
                raise _Unavailable("FIT_FAILED") from error
            _require(stats["observed_claims"] > 0, "FIT_FAILED")
            models = _fit(sample, study)
            validation = _evaluate(study, "validation", models, MODELS)
            scores = {name: validation[name]["mean_poisson_deviance"] for name in MODELS}
            trials.append(
                (
                    models,
                    dict(
                        seed=seed,
                        sample=stats,
                        validation_deviance=scores,
                        selected_model=min(MODELS, key=scores.__getitem__),
                    ),
                )
            )
        _json(
            scratch / "selections.json",
            {
                "reference_model": selected_reference,
                "repetitions": [trial for _, trial in trials],
            },
        )
        replay = _evaluate(study, "test", reference_models, MODELS)
        _require(_matching_metrics(replay, results["metrics"]["test"]), "REPLAY_MISMATCH")
        reference = replay[selected_reference]
        repetitions = []
        for models, trial in trials:
            selected = trial["selected_model"]
            observed = _evaluate(study, "test", models, (selected,))
            repetitions.append(dict(trial, test=_test_metrics(observed[selected], reference)))
    evaluation = {
        name: study.evaluation(name, baseline["source_sha256"]) for name in ("validation", "test")
    }
    counts = dict.fromkeys(MODELS, 0)
    for result in repetitions:
        counts[result["selected_model"]] += 1
    deltas = [result["test"]["deviance_delta"] for result in repetitions]
    summary = dict(
        selection_counts=counts,
        test_deviance_delta=dict(minimum=min(deltas), median=median(deltas), maximum=max(deltas)),
    )
    return evaluation, repetitions, summary


def _saved_bytes(path, limit):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("Invalid saved study file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Saved study file exceeds its size limit")
    return raw


def _baseline(input_path, results_path, selection_path, report):
    try:
        results_raw = _saved_bytes(results_path, 32 * 1024 * 1024)
        selection_raw = _saved_bytes(selection_path, 1024 * 1024)
        results_hash, selection_hash = sha256(results_raw), sha256(selection_raw)
        _require(
            (results_hash, selection_hash) != (FROZEN_RESULTS, FROZEN_SELECTION),
            "PROTOCOL_MISMATCH",
        )
        results, selection = load_saved(results_raw), load_saved(selection_raw)
        identity = validate_run(results, selection)
    except (OSError, ValueError, OverflowError, RecursionError) as error:
        raise _Unavailable("BASELINE_INVALID") from error
    _require(identity["source_sha256"] != PUBLIC_SOURCE_SHA256, "SOURCE_MISMATCH")
    replay_metadata = {}
    study = _prepare_replay(
        input_path, results, identity, results_hash, selection_hash, replay_metadata
    )
    report["baseline"] = dict(replay_metadata["baseline"], selected_model=results["selected_model"])
    return study, results


def _check_publish(input_path, study, source_hash):
    try:
        _require_unchanged_source(input_path, study.original_source)
        _require(sha256_file(input_path) == source_hash, "SOURCE_MISMATCH")
        _require_unchanged_source(input_path, study.original_source)
    except (OSError, ValueError) as error:
        raise _Unavailable("SOURCE_MISMATCH") from error
    _require(code_fingerprint() == study.code, "PROTOCOL_MISMATCH")


def run_training_stability(
    input_path: Path, results_path: Path, selection_path: Path, output_dir: Path
) -> dict:
    """Write checked aggregate results to a new directory after operator confirmation."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError("Output must be a new directory")
    protocol = dict(
        seeds=list(SEEDS),
        sampler="PCG64",
        sort="policy-id-ascending",
        draw="with-replacement-original-training-size",
        formula_version=FORMULA_VERSION,
    )
    report = dict(
        schema_version=SCHEMA_VERSION,
        status="UNAVAILABLE",
        reason=None,
        protocol=protocol,
        baseline=None,
        evaluation=None,
        repetitions=[],
        summary=None,
    )
    with TemporaryDirectory(prefix=".training-stability-", dir=output_dir.parent) as temporary:
        scratch = Path(temporary)
        bundle = scratch / "bundle"
        bundle.mkdir()
        try:
            study, results = _baseline(input_path, results_path, selection_path, report)
            evaluation, repetitions, summary = _run_repetitions(
                study, results, report["baseline"], scratch
            )
            report.update(
                status="COMPARABLE", evaluation=evaluation, repetitions=repetitions, summary=summary
            )
            _write_bundle(report, bundle)
            _check_publish(input_path, study, report["baseline"]["source_sha256"])
        except _Unavailable as error:
            report.update(
                status="UNAVAILABLE",
                reason=error.args[0],
                evaluation=None,
                repetitions=[],
                summary=None,
            )
            _write_bundle(report, bundle)
        output_dir.mkdir(exist_ok=False)
        bundle.rename(output_dir / "artifacts")
    return report


def _write_bundle(report, bundle):
    title = "Training sample stability · MotorClaimLab"
    note = (
        "Synthetic training samples and fixed validation/test populations. "
        "Validation determines model choice. Test changes are conditional descriptive statistics."
    )
    paragraphs = [report["status"], note]
    columns = (
        "Seed",
        "Train policies drawn",
        "Unique policies",
        "Train exposure (years)",
        "Selected model",
        "Test deviance",
        "Change vs baseline",
        "Observed / predicted",
    )
    rows = []
    if report["status"] == "COMPARABLE":
        paragraphs.append(f"Replayed reference model: {report['baseline']['selected_model']}.")
        for label, heldout in report["evaluation"].items():
            paragraphs.append(
                f"Fixed {label}: {heldout['rows']} policies, "
                f"{heldout['exposure']:.12g} exposure years, {heldout['observed_claims']} claims. "
                f"Identity {heldout['identity_sha256']}."
            )
        counts = report["summary"]["selection_counts"]
        deltas = report["summary"]["test_deviance_delta"]
        paragraphs.append(
            "Validation selections: " + ", ".join(f"{key} {value}" for key, value in counts.items())
        )
        paragraphs.append(
            "Fixed-test deviance change (min / median / max): "
            + " / ".join(f"{deltas[key]:+.8f}" for key in ("minimum", "median", "maximum"))
        )
        for trial in report["repetitions"]:
            sample, metrics = trial["sample"], trial["test"]
            ratio = metrics["observed_predicted_ratio"]
            rows.append(
                (
                    str(trial["seed"]),
                    str(sample["rows"]),
                    str(sample["unique_policies"]),
                    f"{sample['exposure']:.12g}",
                    trial["selected_model"],
                    f"{metrics['mean_poisson_deviance']:.8f}",
                    f"{metrics['deviance_delta']:+.8f}",
                    "Unavailable" if ratio is None else f"{ratio:.8f}",
                )
            )
    else:
        paragraphs.append(report["reason"])

    markdown = [f"# {title}", "", "\n\n".join(paragraphs)]
    table = ""
    if rows:
        markdown.extend(
            (
                "",
                "| " + " | ".join(columns) + " |",
                "| " + " | ".join(["---"] * len(columns)) + " |",
            )
        )
        markdown.extend("| " + " | ".join(row) + " |" for row in rows)
        header = "".join(f'<th scope="col">{escape(value)}</th>' for value in columns)
        body = "".join(
            f'<tr><th scope="row">{escape(row[0])}</th>'
            + "".join(f"<td>{escape(value)}</td>" for value in row[1:])
            + "</tr>"
            for row in rows
        )
        table = (
            '<div role="region" tabindex="0" aria-label="Training samples" style="overflow:auto">'
            f"<table><caption>Five training draws with the same test support</caption>"
            f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
        )
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        f"<title>{title}</title><style>"
        "main{max-width:72rem;margin:auto;padding:1rem;font:1rem/1.5 system-ui}"
        "p{overflow-wrap:anywhere}table{border-collapse:collapse}caption{text-align:left}"
        "th,td{padding:.5rem;border-bottom:1px solid #bac3cf;text-align:left}"
        "</style></head><body><main>"
        f"<h1>{title}</h1>"
        + "".join(f"<p>{escape(value)}</p>" for value in paragraphs)
        + table
        + "</main></body></html>"
    )
    _json(bundle / "training-stability.json", report)
    (bundle / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8", newline="\n")
    (bundle / "report.html").write_text(html, encoding="utf-8", newline="\n")
    _json(
        bundle / "completion.json",
        dict(
            status=report["status"],
            artifacts={name: sha256((bundle / name).read_bytes()) for name in ARTIFACTS},
        ),
    )
