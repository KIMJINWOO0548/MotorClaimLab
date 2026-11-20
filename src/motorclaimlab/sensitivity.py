"""Compare train-only caps against a replayed synthetic baseline."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, TypedDict

import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

from .data import SOURCE_MD5, load_source_snapshot, sample_frame, split_frame, validate_frame
from .evaluation import evaluate_predictions
from .experiment import (
    _json,
    _require_unchanged_source,
    _source_metadata,
    _split_summary,
    _study_environment,
    _study_settings,
    code_fingerprint,
)
from .models import fit_models
from .saved_contract import (
    FROZEN_RESULTS,
    FROZEN_SELECTION,
    MODELS,
    _digest,
    _hex,
    _integer,
    _number,
    load_saved,
    sha256,
    validate_run,
)

SCHEMA_VERSION = "motorclaimlab.sensitivity.v1"
FORMULA_VERSION = "frequency-poisson.v1"
SCENARIOS = ("baseline", "exposure_cap", "claim_cap", "both_caps")
REASONS = (
    "BASELINE_INVALID",
    "SOURCE_MISMATCH",
    "SPLIT_MISMATCH",
    "PROTOCOL_MISMATCH",
    "REPLAY_MISMATCH",
    "FIT_FAILED",
    "EVAL_MISMATCH",
)
ARTIFACTS = ("sensitivity.json", "report.md", "report.html")


class Baseline(TypedDict):
    results_sha256: str
    selection_sha256: str
    seed: int
    code_sha256: str
    environment_sha256: str
    config_sha256: str
    split_sha256: str
    source_sha256: str
    data_kind: Literal["local_unverified"]
    protocol_version: int


class Evaluation(TypedDict):
    identity_sha256: str
    membership_sha256: str
    outcomes_sha256: str
    formula_version: str
    rows: int
    exposure: float
    observed_claims: int


class TrainingImpact(TypedDict):
    rows: int
    exposure_affected: int
    claim_affected: int
    both_affected: int
    affected_rows: int
    exposure_before: float
    exposure_after: float
    claims_before: int
    claims_after: int


class TestMetrics(TypedDict):
    predicted_claims: float
    observed_frequency: float
    predicted_frequency: float
    mean_poisson_deviance: float
    observed_predicted_ratio: float | None
    deviance_delta: float
    ratio_delta: float | None


class Scenario(TypedDict):
    name: str
    impact: TrainingImpact
    selected_model: str
    validation_deviance: dict[str, float]
    test: TestMetrics


class SensitivityReport(TypedDict):
    schema_version: str
    status: Literal["COMPARABLE", "UNAVAILABLE"]
    reason: str | None
    baseline: Baseline | None
    evaluation: Evaluation | None
    scenarios: list[Scenario]


class _Unavailable(Exception):
    pass


def _require(condition, reason):
    if not condition:
        raise _Unavailable(reason)


def _outcomes(frame):
    return _digest(
        [
            [int(claim), float(exposure).hex()]
            for claim, exposure in zip(frame.ClaimNb, frame.Exposure, strict=True)
        ]
    )


def _signature(frame):
    return _split_summary(frame), _outcomes(frame)


def _cap_training(train: pd.DataFrame, scenario: str) -> tuple[pd.DataFrame, TrainingImpact]:
    capped = train.copy(deep=True)
    cap_exposure = scenario in ("exposure_cap", "both_caps")
    cap_claims = scenario in ("claim_cap", "both_caps")
    exposure_affected = (train.Exposure > 1.0) & cap_exposure
    claim_affected = (train.ClaimNb > 4) & cap_claims
    if cap_exposure:
        capped["Exposure"] = train.Exposure.clip(upper=1.0)
    if cap_claims:
        capped["ClaimNb"] = train.ClaimNb.clip(upper=4)
    before = validate_frame(train)
    after = validate_frame(capped)
    common = train.drop(columns=["Exposure", "ClaimNb"])
    expected_exposure = math.fsum(
        min(float(x), 1.0) if cap_exposure else float(x) for x in train.Exposure
    )
    expected_claims = sum(min(int(x), 4) if cap_claims else int(x) for x in train.ClaimNb)
    _require(
        common.equals(capped[common.columns])
        and before["rows"] == after["rows"]
        and after["claims"] == expected_claims
        and math.isclose(after["exposure"], expected_exposure, rel_tol=1e-15),
        "FIT_FAILED",
    )
    return capped, {
        "rows": before["rows"],
        "exposure_affected": int(exposure_affected.sum()),
        "claim_affected": int(claim_affected.sum()),
        "both_affected": int((exposure_affected & claim_affected).sum()),
        "affected_rows": int((exposure_affected | claim_affected).sum()),
        "exposure_before": before["exposure"],
        "exposure_after": after["exposure"],
        "claims_before": before["claims"],
        "claims_after": after["claims"],
    }


def _close(a, b):
    if type(a) is float or type(b) is float:
        return _number(a) and _number(b) and math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-10)
    return type(a) is type(b) and a == b


def _matching_metrics(actual, saved):
    return all(
        actual[name].keys() == saved[name].keys()
        and all(_close(value, saved[name][key]) for key, value in actual[name].items())
        for name in MODELS
    )


def _test_metrics(metrics, baseline) -> TestMetrics:
    ratio, reference = metrics["observed_predicted_ratio"], baseline["observed_predicted_ratio"]
    return {
        "predicted_claims": metrics["predicted_claims"],
        "observed_frequency": metrics["observed_frequency"],
        "predicted_frequency": metrics["predicted_frequency"],
        "mean_poisson_deviance": metrics["mean_poisson_deviance"],
        "observed_predicted_ratio": ratio,
        "deviance_delta": metrics["mean_poisson_deviance"] - baseline["mean_poisson_deviance"],
        "ratio_delta": ratio - reference if ratio is not None and reference is not None else None,
    }


def _check_metric_support(metrics, summary):
    _require(
        all(
            value["rows"] == summary["rows"]
            and value["exposure"] == summary["exposure"]
            and value["observed_claims"] == summary["claims"]
            for value in metrics.values()
        ),
        "EVAL_MISMATCH",
    )


@dataclass
class _ReplayStudy:
    seed: int
    max_iter: int
    original_source: tuple[int, ...]
    code: str
    splits: dict
    signatures: dict

    def check_splits(self):
        try:
            current = {name: _signature(frame) for name, frame in self.splits.items()}
        except (ValueError, OverflowError) as error:
            raise _Unavailable("EVAL_MISMATCH") from error
        _require(current == self.signatures, "EVAL_MISMATCH")

    def evaluation(self, name, source_hash):
        summary, outcomes = self.signatures[name]
        identity = dict(
            source_sha256=source_hash,
            membership_sha256=summary["membership_sha256"],
            outcomes_sha256=outcomes,
            formula_version=FORMULA_VERSION,
        )
        return Evaluation(
            membership_sha256=summary["membership_sha256"],
            outcomes_sha256=outcomes,
            formula_version=FORMULA_VERSION,
            rows=summary["rows"],
            exposure=summary["exposure"],
            observed_claims=summary["claims"],
            identity_sha256=_digest(identity),
        )


def _prepare_replay(input_path, results, identity, results_hash, selection_hash, report):
    settings = results["study"]["settings"]
    environment = _study_environment()
    code = code_fingerprint()
    _require(
        code == identity["code_sha256"]
        and results.get("environment") == environment
        and _digest(settings)
        == _digest(
            _study_settings(
                settings["seed"],
                settings["max_rows"],
                settings["max_iter"],
                settings["bootstrap_draws"],
            )
        ),
        "PROTOCOL_MISMATCH",
    )
    _require(
        results["study"]["data_kind"] == "local_unverified"
        and identity["source_md5"] != SOURCE_MD5,
        "SOURCE_MISMATCH",
    )
    report["baseline"] = Baseline(
        results_sha256=results_hash,
        selection_sha256=selection_hash,
        seed=settings["seed"],
        code_sha256=code,
        environment_sha256=_digest(environment),
        config_sha256=identity["config_sha256"],
        split_sha256=identity["split_sha256"],
        source_sha256=identity["source_sha256"],
        data_kind="local_unverified",
        protocol_version=identity["version"],
    )
    try:
        original_source = _source_metadata(input_path)
        full, source = load_source_snapshot(input_path)
        _require_unchanged_source(input_path, original_source)
    except (OSError, ValueError, OverflowError) as error:
        raise _Unavailable("SOURCE_MISMATCH") from error
    _require(
        source["source_sha256"] == identity["source_sha256"]
        and source["source_md5"] == identity["source_md5"],
        "SOURCE_MISMATCH",
    )
    _require(code_fingerprint() == code, "PROTOCOL_MISMATCH")

    try:
        splits = split_frame(
            sample_frame(full, settings["max_rows"], settings["seed"]), settings["seed"]
        )
        _require(all(not frame.empty for frame in splits.values()), "SPLIT_MISMATCH")
        signatures = {name: _signature(frame) for name, frame in splits.items()}
    except (ValueError, OverflowError) as error:
        raise _Unavailable("SPLIT_MISMATCH") from error
    _require(
        {name: value[0] for name, value in signatures.items()} == results["splits"],
        "SPLIT_MISMATCH",
    )
    return _ReplayStudy(
        seed=settings["seed"],
        max_iter=settings["max_iter"],
        original_source=original_source,
        code=code,
        splits=splits,
        signatures=signatures,
    )


def _compare(input_path, results, identity, results_hash, selection_hash, report, scratch):
    study = _prepare_replay(input_path, results, identity, results_hash, selection_hash, report)
    splits, signatures = study.splits, study.signatures
    test_summary = signatures["test"][0]
    evaluation = study.evaluation("test", identity["source_sha256"])

    fitted = {}
    with threadpool_limits(limits=2):
        for name in SCENARIOS:
            study.check_splits()
            try:
                capped, impact = _cap_training(splits["train"], name)
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    models = fit_models(capped, seed=study.seed, max_iter=study.max_iter)
            except Exception as error:
                raise _Unavailable("FIT_FAILED") from error
            study.check_splits()
            try:
                validation = {
                    model: evaluate_predictions(
                        splits["validation"], models[model].predict(splits["validation"])
                    )
                    for model in MODELS
                }
            except Exception as error:
                raise _Unavailable("EVAL_MISMATCH") from error
            study.check_splits()
            _check_metric_support(validation, signatures["validation"][0])
            scores = {model: validation[model]["mean_poisson_deviance"] for model in MODELS}
            selected = min(MODELS, key=scores.__getitem__)
            if name == "baseline":
                _require(
                    selected == results["selected_model"]
                    and _matching_metrics(validation, results["metrics"]["validation"]),
                    "REPLAY_MISMATCH",
                )
            fitted[name] = (models, impact, scores, selected)
        _json(
            scratch / "selections.json",
            {
                name: {"validation_deviance": scores, "selected_model": selected}
                for name, (_, _, scores, selected) in fitted.items()
            },
        )

        scenarios = []
        for name, (models, impact, scores, selected) in fitted.items():
            study.check_splits()
            try:
                test = {
                    model: evaluate_predictions(
                        splits["test"], models[model].predict(splits["test"])
                    )
                    for model in (MODELS if name == "baseline" else (selected,))
                }
            except Exception as error:
                raise _Unavailable("EVAL_MISMATCH") from error
            study.check_splits()
            _check_metric_support(test, test_summary)
            if name == "baseline":
                _require(_matching_metrics(test, results["metrics"]["test"]), "REPLAY_MISMATCH")
                reference = test[selected]
            metrics = _test_metrics(test[selected], reference)
            scenarios.append(
                Scenario(
                    name=name,
                    impact=impact,
                    selected_model=selected,
                    validation_deviance=scores,
                    test=metrics,
                )
            )

    report.update(status="COMPARABLE", reason=None, evaluation=evaluation, scenarios=scenarios)
    return study.original_source, study.code


def run_sensitivity(
    input_path: Path, results_path: Path, selection_path: Path, output_dir: Path
) -> SensitivityReport:
    """Publish an aggregate bundle or a redacted diagnostic to a new directory."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError("Output must be a new directory")
    with TemporaryDirectory(prefix=".sensitivity-", dir=output_dir.parent) as temporary:
        scratch = Path(temporary)
        report = SensitivityReport(
            schema_version=SCHEMA_VERSION,
            status="UNAVAILABLE",
            reason="BASELINE_INVALID",
            baseline=None,
            evaluation=None,
            scenarios=[],
        )
        provenance = None
        try:
            results_bytes, selection_bytes = results_path.read_bytes(), selection_path.read_bytes()
            results, selection = load_saved(results_bytes), load_saved(selection_bytes)
            results_hash, selection_hash = sha256(results_bytes), sha256(selection_bytes)
            if (results_hash, selection_hash) == (FROZEN_RESULTS, FROZEN_SELECTION):
                raise _Unavailable("PROTOCOL_MISMATCH")
            identity = validate_run(results, selection)
            provenance = _compare(
                input_path, results, identity, results_hash, selection_hash, report, scratch
            )
        except _Unavailable as error:
            report["reason"] = error.args[0]
        except (ValueError, OSError, OverflowError, RecursionError):
            pass
        _validate_report(report)
        bundle = scratch / "bundle"
        bundle.mkdir()
        _write_bundle(report, bundle)
        if provenance is not None:
            original_source, code = provenance
            reason = None
            try:
                _require_unchanged_source(input_path, original_source)
            except (OSError, ValueError):
                reason = "SOURCE_MISMATCH"
            if code_fingerprint() != code:
                reason = "PROTOCOL_MISMATCH"
            if reason:
                report.update(status="UNAVAILABLE", reason=reason, evaluation=None, scenarios=[])
                _write_bundle(report, bundle)
        output_dir.mkdir(exist_ok=False)
        bundle.rename(output_dir / "artifacts")
        return report


def _write_bundle(report, bundle):
    markdown = ["# Training-cap sensitivity", "", f"**{report['status']}**"]
    heading = (
        "Scenario",
        "Selected model",
        "Affected train rows",
        "Test deviance",
        "Deviance change",
        "Observed / predicted",
        "Ratio change",
    )
    rows = []
    impacts = []
    if report["status"] == "COMPARABLE":
        evaluation = report["evaluation"]
        support = (
            "Common test support · "
            f"{evaluation['rows']} rows · {evaluation['exposure']:.12g} years of exposure · "
            f"{evaluation['observed_claims']} observed claims"
        )
        for scenario in report["scenarios"]:
            metric = scenario["test"]
            impact = scenario["impact"]
            impacts.append(
                (
                    scenario["name"],
                    str(impact["exposure_affected"]),
                    str(impact["claim_affected"]),
                    str(impact["both_affected"]),
                    f"{impact['exposure_before']:.12g} → {impact['exposure_after']:.12g}",
                    f"{impact['claims_before']} → {impact['claims_after']}",
                )
            )
            rows.append(
                (
                    scenario["name"],
                    scenario["selected_model"],
                    str(scenario["impact"]["affected_rows"]),
                    f"{metric['mean_poisson_deviance']:.8f}",
                    f"{metric['deviance_delta']:+.8f}",
                    "Unavailable"
                    if metric["observed_predicted_ratio"] is None
                    else f"{metric['observed_predicted_ratio']:.8f}",
                    "Unavailable"
                    if metric["ratio_delta"] is None
                    else f"{metric['ratio_delta']:+.8f}",
                )
            )
    else:
        support = report["reason"]
        if support == "PROTOCOL_MISMATCH":
            support += (
                " · Use render for archived results or create a baseline with the current build."
            )
    note = "Synthetic study. Caps affect training only. Models are selected using validation."
    markdown.extend(("", support, "", note, ""))

    def table(title, columns, entries):
        markdown.extend((f"## {title}", ""))
        markdown.extend(
            ("| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |")
        )
        markdown.extend("| " + " | ".join(row) + " |" for row in entries)
        markdown.append("")
        headers = "".join(f'<th scope="col">{escape(value)}</th>' for value in columns)
        body = "".join(
            "<tr>"
            + f'<th scope="row">{escape(row[0])}</th>'
            + "".join(f"<td>{escape(value)}</td>" for value in row[1:])
            + "</tr>"
            for row in entries
        )
        return (
            f'<div class="comparison" role="region" tabindex="0" aria-label="{escape(title)}">'
            f"<table><caption>{escape(title)}</caption>"
            f"<thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></div>"
        )

    content = ""
    if rows:
        evidence = (
            f"{SCHEMA_VERSION} · {FORMULA_VERSION} · Replayed baseline · "
            f"Evaluation identity {evaluation['identity_sha256']}"
        )
        content = (
            '<nav aria-label="Report sections"><a href="#comparison">Scenario comparison</a> · '
            '<a href="#training">Training impact</a> · <a href="#evidence">Evidence</a></nav>'
            '<h2 id="comparison" tabindex="-1">Scenario comparison</h2>'
            + table("Test results with common exposure and claims", heading, rows)
            + '<h2 id="training" tabindex="-1">Training impact</h2>'
            + table(
                "Training-only caps",
                (
                    "Scenario",
                    "Exposure affected",
                    "Claims affected",
                    "Both affected",
                    "Exposure years before → after",
                    "Claims before → after",
                ),
                impacts,
            )
            + f'<h2 id="evidence" tabindex="-1">Evidence</h2><p>{escape(evidence)}</p>'
            + '<a href="#summary">Back to summary</a>'
        )
        markdown.extend(("## Evidence", "", evidence))
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Training-cap sensitivity · MotorClaimLab</title><style>"
        "body{margin:0;background:#f5f7fa;color:#223146;font:1rem/1.55 system-ui,sans-serif}"
        "main{max-width:1120px;margin:auto;padding:clamp(1rem,4vw,3rem)}"
        "header{border-bottom:2px solid #ccd6e0;margin-bottom:1rem}"
        "p{overflow-wrap:anywhere}"
        "h1{font-size:clamp(1.6rem,4vw,2.5rem);margin:.2em 0}"
        "a{color:#245384;display:inline-flex;align-items:center;min-height:44px}"
        ":focus-visible,:target{outline:3px solid #28618e;outline-offset:2px}"
        ".comparison{overflow:auto;background:white;margin-bottom:1rem}"
        "table{border-collapse:collapse;width:100%}caption{text-align:left;color:#405775;padding:.5rem}"
        "td,th{text-align:left;padding:.6rem;border-bottom:1px solid #dbe2e9;"
        "font-variant-numeric:tabular-nums}"
        "</style></head><body><main><header>"
        '<h1 id="summary" tabindex="-1">Training-cap sensitivity</h1>'
        f"<p><strong>{escape(report['status'])}</strong></p><p>{escape(support)}</p></header>"
        f"<p>{escape(note)}</p>{content}</main></body></html>"
    )
    _json(bundle / "sensitivity.json", report)
    (bundle / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8", newline="\n")
    (bundle / "report.html").write_text(html, encoding="utf-8", newline="\n")
    _json(
        bundle / "completion.json",
        {
            "status": report["status"],
            "artifacts": {name: sha256((bundle / name).read_bytes()) for name in ARTIFACTS},
        },
    )


def _closed(obj, fields):
    if type(obj) is not dict or set(obj) != set(fields):
        raise ValueError("Invalid sensitivity bundle fields")


def _valid(condition):
    if not condition:
        raise ValueError("Invalid sensitivity bundle values")


def _validate_baseline(baseline):
    _closed(baseline, Baseline.__annotations__)
    _valid(all(_hex(value, 64) for key, value in baseline.items() if key.endswith("_sha256")))
    _valid(
        _integer(baseline["seed"])
        and baseline["seed"] < 2**32
        and _integer(baseline["protocol_version"], 1)
        and baseline["protocol_version"] == 1
        and baseline["data_kind"] == "local_unverified"
    )


def _validate_report(report) -> SensitivityReport:
    _closed(report, SensitivityReport.__annotations__)
    _valid(report["schema_version"] == SCHEMA_VERSION)
    baseline, evaluation, scenarios = report["baseline"], report["evaluation"], report["scenarios"]
    if baseline is not None:
        _validate_baseline(baseline)
    if report["status"] == "UNAVAILABLE":
        _valid(report["reason"] in REASONS and evaluation is None and scenarios == [])
        return report

    _valid(report["status"] == "COMPARABLE" and report["reason"] is None and baseline is not None)
    _closed(evaluation, Evaluation.__annotations__)
    _valid(
        all(
            _hex(evaluation[key], 64)
            for key in ("identity_sha256", "membership_sha256", "outcomes_sha256")
        )
    )
    _valid(
        evaluation["formula_version"] == FORMULA_VERSION
        and _integer(evaluation["rows"], 1)
        and _integer(evaluation["observed_claims"])
        and _number(evaluation["exposure"])
        and evaluation["exposure"] > 0
    )
    _valid(
        evaluation["identity_sha256"]
        == _digest(
            {
                "source_sha256": baseline["source_sha256"],
                "membership_sha256": evaluation["membership_sha256"],
                "outcomes_sha256": evaluation["outcomes_sha256"],
                "formula_version": FORMULA_VERSION,
            }
        )
    )
    _valid(type(scenarios) is list and len(scenarios) == len(SCENARIOS))
    for expected, scenario in zip(SCENARIOS, scenarios, strict=True):
        _closed(scenario, Scenario.__annotations__)
        _valid(scenario["name"] == expected)
        scores = scenario["validation_deviance"]
        _closed(scores, MODELS)
        _valid(all(_number(score) and score >= 0 for score in scores.values()))
        _valid(scenario["selected_model"] == min(MODELS, key=scores.__getitem__))
        impact = scenario["impact"]
        _closed(impact, TrainingImpact.__annotations__)
        ints = (
            "rows",
            "exposure_affected",
            "claim_affected",
            "both_affected",
            "affected_rows",
            "claims_before",
            "claims_after",
        )
        _valid(all(_integer(impact[key]) for key in ints))
        _valid(
            impact["rows"] > 0
            and 0
            <= impact["both_affected"]
            <= min(impact["exposure_affected"], impact["claim_affected"])
            and impact["affected_rows"]
            == impact["exposure_affected"] + impact["claim_affected"] - impact["both_affected"]
            and impact["affected_rows"] <= impact["rows"]
            and impact["claims_after"] <= impact["claims_before"]
        )
        _valid(
            all(_number(impact[key]) for key in ("exposure_before", "exposure_after"))
            and 0 < impact["exposure_after"] <= impact["exposure_before"]
        )
        _valid(
            (bool(impact["claim_affected"]) == (impact["claims_after"] < impact["claims_before"]))
            and (expected in ("claim_cap", "both_caps") or impact["claim_affected"] == 0)
            and (expected in ("exposure_cap", "both_caps") or impact["exposure_affected"] == 0)
            and (
                impact["exposure_affected"] or impact["exposure_before"] == impact["exposure_after"]
            )
        )
        test = scenario["test"]
        _closed(test, TestMetrics.__annotations__)
        nullable = ("observed_predicted_ratio", "ratio_delta")
        _valid(
            all(
                _number(value) or (key in nullable and value is None) for key, value in test.items()
            )
        )
        _valid(
            all(
                test[key] >= 0
                for key in (
                    "predicted_claims",
                    "observed_frequency",
                    "predicted_frequency",
                    "mean_poisson_deviance",
                )
            )
        )
        _valid(
            _close(
                test["observed_frequency"], evaluation["observed_claims"] / evaluation["exposure"]
            )
            and _close(
                test["predicted_frequency"], test["predicted_claims"] / evaluation["exposure"]
            )
        )
        ratio = (
            evaluation["observed_claims"] / test["predicted_claims"]
            if test["predicted_claims"]
            else None
        )
        ratio = ratio if ratio is None or math.isfinite(ratio) else None
        _valid(_close(test["observed_predicted_ratio"], ratio))
    reference = scenarios[0]["test"]
    initial = scenarios[0]["impact"]
    for scenario in scenarios:
        impact, test = scenario["impact"], scenario["test"]
        _valid(
            all(impact[key] == initial[key] for key in ("rows", "exposure_before", "claims_before"))
        )
        delta = _test_metrics(test, reference)
        _valid(
            _close(test["deviance_delta"], delta["deviance_delta"])
            and _close(test["ratio_delta"], delta["ratio_delta"])
        )
    return report


def load_sensitivity_bundle(output_dir: Path) -> SensitivityReport:
    bundle = output_dir / "artifacts"
    if bundle.is_symlink():
        raise ValueError("Invalid sensitivity bundle directory")
    completion = load_saved((bundle / "completion.json").read_bytes())
    _closed(completion, ("status", "artifacts"))
    _closed(completion["artifacts"], ARTIFACTS)
    content = {}
    for name in ARTIFACTS:
        path = bundle / name
        _valid(not path.is_symlink())
        content[name] = path.read_bytes()
        _valid(completion["artifacts"][name] == sha256(content[name]))
    report = _validate_report(load_saved(content["sensitivity.json"]))
    _valid(report["status"] == completion["status"])
    return report
