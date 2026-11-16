"""Saved aggregate JSON must not silently discard conflicting declarations."""

import hashlib
import json
from pathlib import Path

import pytest
from test_experiment import _study_frame

from motorclaimlab.presentation import render_saved

ARCHIVE = Path(__file__).resolve().parents[1] / "docs/evidence/benchmark"


def current_saved():
    results = json.loads((ARCHIVE / "results.json").read_bytes())
    selection = json.loads((ARCHIVE / "selection.json").read_bytes())
    results["provenance"]["source_capture"] = "bounded_snapshot"
    for group in (
        *results["metrics"].values(),
        *results["calibration"].values(),
        results["segments"],
    ):
        for metric in group.values() if isinstance(group, dict) else group:
            metric["observed_claims"] = int(metric["observed_claims"])
            for prefix in ("observed", "predicted"):
                metric[f"{prefix}_frequency"] = metric[f"{prefix}_claims"] / metric["exposure"]
            if "bin" in metric or "segment" in metric:
                reasons = []
                if metric["rows"] < 50:
                    reasons.append("rows_below_50")
                if metric["exposure"] < 10:
                    reasons.append("exposure_below_10")
                metric.update(sparse=bool(reasons), sparse_reasons=reasons)
    results["bootstrap"].update(
        valid_draws=200,
        invalid_draws=0,
        degenerate_draws=0,
        minimum_valid_draws=40,
        minimum_policies=2,
        confidence_level=0.95,
        adequate=True,
        abstention_reason=None,
    )
    identity = {"version": 1}
    for field in ("source_sha256", "source_md5", "code_sha256"):
        identity[field] = results["provenance"][field]
    for field, value in (
        ("config_sha256", results["study"]["settings"]),
        ("split_sha256", results["splits"]),
    ):
        identity[field] = hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    results["run_identity"] = identity.copy()
    selection["run_identity"] = identity.copy()
    selection["validation"] = json.loads(json.dumps(results["metrics"]["validation"]))
    return results, selection


@pytest.mark.parametrize("table", ["calibration", "segments"])
def test_current_run_rejects_prediction_totals_from_another_scope(tmp_path, table):
    results, selection = current_saved()
    rows = results[table] if table == "segments" else results[table]["poisson_hgb"]
    row = rows[0]
    row["predicted_claims"] += 1
    row["predicted_frequency"] = row["predicted_claims"] / row["exposure"]
    row["observed_predicted_ratio"] = row["observed_claims"] / row["predicted_claims"]
    for name, value in (("results", results), ("selection", selection)):
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    out = tmp_path / "invalid"
    with pytest.raises(ValueError, match="predicted claims"):
        render_saved(tmp_path / "results.json", out)
    assert not out.exists()


@pytest.mark.parametrize(
    ("target", "fields", "replacement", "error"),
    [
        ("results", ("audit", "exposure"), -1, "exposure"),
        ("results", ("segments",), [], "segments"),
        ("results", ("eda", "overall", "frequency"), 0, "EDA frequency"),
        ("results", ("metrics", "test", "mean", "observed_frequency"), None, "frequency"),
        ("results", ("selected_model",), "mean", "selected model"),
        ("results", ("splits", "test", "membership_sha256"), "a" * 64, "fingerprints"),
        ("results", ("study", "settings", "max_iter"), 101, "fingerprints"),
        ("results", ("provenance", "source_sha256"), "a" * 64, "fingerprints"),
        ("results", ("provenance", "source_md5"), "a" * 32, "fingerprints"),
        ("results", ("run_identity", "version"), True, "fingerprints"),
        ("results", ("run_identity",), None, "run identity"),
        ("selection", ("selection_split",), "test", "selection"),
        ("selection", ("selected_model",), "mean", "selection"),
        ("selection", ("metric",), "weighted_mae", "selection"),
        ("selection", ("run_identity", "split_sha256"), "a" * 64, "selection"),
        ("selection", ("run_identity", "source_sha256"), "a" * 64, "selection"),
        ("selection", ("validation", "mean", "weighted_mae"), 0, "selection"),
        ("selection", ("settings", "seed"), 2, "selection"),
        ("selection", ("settings",), None, "selection"),
    ],
)
def test_current_run_rejects_invalid_domain_and_identity(
    tmp_path, target, fields, replacement, error
):
    saved = dict(zip(("results", "selection"), current_saved(), strict=True))
    value = saved[target]
    for field in fields[:-1]:
        value = value[field]
    if replacement is None:
        del value[fields[-1]]
    else:
        value[fields[-1]] = replacement
    for name, value in saved.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match=error):
        render_saved(tmp_path / "results.json", output)
    assert not output.exists()


def test_current_run_requires_matching_sibling_or_explicit_selection(tmp_path):
    results, selection = current_saved()
    source = tmp_path / "results.json"
    source.write_text(json.dumps(results), encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match="selection is required"):
        render_saved(source, output)
    assert not output.exists()
    (tmp_path / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    manifest = render_saved(source, output)
    assert manifest["saved_contract"] == "matched-run-identity"
    assert manifest["run_identity"] == results["run_identity"]
    assert set(manifest["inputs"]) == {"results", "selection"}


def test_fresh_experiment_artifacts_satisfy_saved_contract(frame, tmp_path):
    from motorclaimlab.experiment import run_experiment

    source = tmp_path / "synthetic.csv"
    _study_frame(frame).to_csv(source, index=False)
    experiment = tmp_path / "run"
    result = run_experiment(source, experiment, max_iter=1, bootstrap_draws=2)
    manifest = render_saved(experiment / "results.json", tmp_path / "presentation")
    assert manifest["run_identity"] == result["run_identity"]
    assert (
        manifest["run_identity"]["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert manifest["saved_contract"] == "matched-run-identity"


@pytest.mark.parametrize("target", ["results", "selection"])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_json_is_rejected_even_in_unused_nested_fields(tmp_path, target, literal):
    paths = {name: tmp_path / f"{name}.json" for name in ("results", "selection")}
    for name, path in paths.items():
        original = (ARCHIVE / path.name).read_bytes()
        if name == target:
            original = ('{"extra":[{"value":' + literal + "}],").encode() + original[1:]
        path.write_bytes(original)
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match="Non-finite"):
        render_saved(paths["results"], output, paths["selection"])
    assert not output.exists()


def test_modified_old_results_cannot_use_frozen_legacy_exception(tmp_path):
    results = tmp_path / "results.json"
    saved = json.loads((ARCHIVE / results.name).read_bytes())
    saved["splits"]["test"]["exposure"] = -1
    results.write_text(json.dumps(saved), encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError):
        render_saved(results, output, ARCHIVE / "selection.json")
    assert not output.exists()


def test_old_selection_with_removed_declarations_cannot_match_archive(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text('{"selected_model":"poisson_hgb"}', encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match="selection"):
        render_saved(ARCHIVE / "results.json", output, selection)
    assert not output.exists()


@pytest.mark.parametrize("target", ["results", "selection"])
def test_duplicate_json_keys_rejected_before_output(tmp_path, target):
    results = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    results.write_bytes((ARCHIVE / results.name).read_bytes())
    selection.write_text(json.dumps({"selected_model": "poisson_glm"}), encoding="utf-8")
    path = results if target == "results" else selection
    raw = path.read_text(encoding="utf-8")
    path.write_text('{"selected_model":"conflicting_model",' + raw[1:], encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match="Duplicate"):
        render_saved(results, output, selection)
    assert not output.exists()


@pytest.mark.parametrize("target", ["results", "selection"])
def test_nested_duplicate_json_keys_rejected_without_leaking_key(tmp_path, target):
    results = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    results.write_bytes((ARCHIVE / results.name).read_bytes())
    selection.write_text(json.dumps({"selected_model": "poisson_glm"}), encoding="utf-8")
    path = results if target == "results" else selection
    raw = path.read_text(encoding="utf-8")
    path.write_text('{"extra":{"PRIVATE_KEY":1,"PRIVATE_KEY":2},' + raw[1:], encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError) as error:
        render_saved(results, output, selection)
    assert "PRIVATE_KEY" not in str(error.value)
    assert not output.exists()
