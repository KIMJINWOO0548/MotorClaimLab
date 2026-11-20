import json
import math
from pathlib import Path

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning
from test_experiment import _study_frame

from motorclaimlab.__main__ import main
from motorclaimlab.sensitivity import _cap_training, _test_metrics, load_sensitivity_bundle


def test_cap_training_is_independent(frame):
    original = frame.iloc[:2].assign(Exposure=[1.5, 0.25], ClaimNb=[5, 1])
    for name, exposure, claims, affected in (
        ("baseline", 1.75, 6, 0),
        ("exposure_cap", 1.25, 6, 1),
        ("claim_cap", 1.75, 5, 1),
        ("both_caps", 1.25, 5, 1),
    ):
        capped, impact = _cap_training(original, name)
        assert list(capped.IDpol) == list(original.IDpol)
        assert (impact["exposure_before"], impact["claims_before"]) == (1.75, 6)
        assert (impact["exposure_after"], impact["claims_after"], impact["affected_rows"]) == (
            exposure,
            claims,
            affected,
        )
        assert list(original.Exposure) == [1.5, 0.25]
        assert list(original.ClaimNb) == [5, 1]


def test_common_exposure_and_nullable_ratio(frame):
    from motorclaimlab.evaluation import evaluate_predictions

    test = frame.iloc[:2].assign(Exposure=[0.25, 1.0], ClaimNb=[1, 0])
    baseline = evaluate_predictions(test, [0.8, 0.8])
    other = evaluate_predictions(test, [1.0, 1.0])
    assert baseline["predicted_claims"] == 1.0
    assert baseline["mean_poisson_deviance"] == pytest.approx(2 * math.log(5) / 1.25)
    assert other["predicted_claims"] == 1.25
    assert other["mean_poisson_deviance"] == pytest.approx(2 * (math.log(4) + 0.25) / 1.25)
    assert other["observed_predicted_ratio"] == 0.8
    assert _test_metrics(other, baseline)["ratio_delta"] == pytest.approx(-0.2)
    tiny = test.assign(Exposure=0.25, ClaimNb=0)
    underflow = evaluate_predictions(tiny, [5e-324, 5e-324])
    assert underflow["observed_predicted_ratio"] is None
    assert _test_metrics(underflow, baseline)["ratio_delta"] is None


def test_product_baseline_bundle_and_changes(frame, tmp_path, capsys):
    source = tmp_path / "synthetic.csv"
    synthetic = _study_frame(frame)
    synthetic.loc[synthetic.index % 4 == 0, "Exposure"] = 1.5
    synthetic.loc[synthetic.index % 7 == 0, "ClaimNb"] = 6
    synthetic.to_csv(source, index=False)
    baseline = tmp_path / "baseline"
    assert (
        main(
            [
                "run",
                "--input",
                str(source),
                "--output",
                str(baseline),
                "--max-iter",
                "3",
                "--bootstrap-draws",
                "5",
            ]
        )
        == 0
    )
    capsys.readouterr()
    results, selection = baseline / "results.json", baseline / "selection.json"
    args = [
        "sensitivity",
        "--input",
        str(source),
        "--results",
        str(results),
        "--selection",
        str(selection),
        "--output",
    ]
    originals = {path: path.read_bytes() for path in (source, results, selection)}
    first, second = tmp_path / "first", tmp_path / "second"
    assert main([*args, str(first)]) == 0
    assert main([*args, str(second)]) == 0
    for artifact in ("sensitivity.json", "report.html", "report.md", "completion.json"):
        file = first / "artifacts" / artifact
        assert file.read_bytes() == (second / "artifacts" / artifact).read_bytes()
        assert str(tmp_path) not in file.read_text(encoding="utf-8")
        assert "IDpol" not in file.read_text(encoding="utf-8")
    report = load_sensitivity_bundle(first)
    assert report["status"] == "COMPARABLE"
    saved = json.loads(originals[results])
    for actual, expected in (
        ("rows", "rows"),
        ("exposure", "exposure"),
        ("observed_claims", "claims"),
    ):
        assert report["evaluation"][actual] == saved["splits"]["test"][expected]
    assert [row["name"] for row in report["scenarios"]] == [
        "baseline",
        "exposure_cap",
        "claim_cap",
        "both_caps",
    ]
    assert report["scenarios"][0]["test"]["deviance_delta"] == 0
    assert report["scenarios"][3]["impact"]["affected_rows"] > 0
    assert (
        report["scenarios"][3]["impact"]["exposure_after"]
        < report["scenarios"][0]["impact"]["exposure_after"]
    )
    assert (
        report["scenarios"][3]["impact"]["claims_after"]
        < report["scenarios"][0]["impact"]["claims_after"]
    )
    assert main([*args, str(first)]) == 1
    assert {path: path.read_bytes() for path in originals} == originals
    (second / "artifacts" / "report.md").write_text("changed")
    with pytest.raises(ValueError):
        load_sensitivity_bundle(second)
    source.write_bytes(originals[source] + b"\n")
    changed = tmp_path / "changed"
    assert main([*args, str(changed)]) == 1
    assert load_sensitivity_bundle(changed)["reason"] == "SOURCE_MISMATCH"
    assert "<table" not in (changed / "artifacts" / "report.html").read_text(encoding="utf-8")
    source.write_bytes(originals[source])
    selection.write_bytes(b'{"selected_model":"mean","selected_model":"mean"}')
    duplicated = tmp_path / "duplicated"
    assert main([*args, str(duplicated)]) == 1
    assert load_sensitivity_bundle(duplicated)["reason"] == "BASELINE_INVALID"

    schema = json.loads(
        (Path(__file__).parents[1] / "docs/schemas/sensitivity.v1.schema.json").read_bytes()
    )
    for value, spec in [
        (report, schema),
        (report["baseline"], schema["$defs"]["baseline"]),
        (report["evaluation"], schema["$defs"]["evaluation"]),
        (report["scenarios"][0], schema["$defs"]["scenario"]),
    ]:
        assert set(value) == set(spec["required"]) == set(spec["properties"])


def test_selection_lock_and_failed_evaluation(frame, tmp_path, monkeypatch):
    from motorclaimlab import experiment, sensitivity
    from motorclaimlab.data import split_frame

    source = tmp_path / "synthetic.csv"
    samples = _study_frame(frame).assign(ClaimNb=1, Exposure=1.0)
    samples.to_csv(source, index=False)
    partitions = split_frame(samples)
    holdout_ids = {tuple(part.IDpol) for part in (partitions["validation"], partitions["test"])}
    test_ids = tuple(partitions["test"].IDpol)
    events = []

    class Predictor:
        def predict(self, subset):
            identifiers = tuple(subset.IDpol)
            assert identifiers in holdout_ids
            events.append("test" if identifiers == test_ids else "validation")
            return np.ones(len(subset))

    def fit(*args, **kwargs):
        events.append("fit")
        return {model: Predictor() for model in sensitivity.MODELS}

    monkeypatch.setattr(experiment, "fit_models", fit)
    monkeypatch.setattr(sensitivity, "fit_models", fit)
    baseline = tmp_path / "baseline"
    experiment.run_experiment(source, baseline, bootstrap_draws=5)
    results, selection = baseline / "results.json", baseline / "selection.json"
    real_json = sensitivity._json

    def record(path, value):
        if path.name == "selections.json":
            assert all(item["selected_model"] == "mean" for item in value.values())
            events.append("locked")
        return real_json(path, value)

    monkeypatch.setattr(sensitivity, "_json", record)
    events.clear()
    run = sensitivity.run_sensitivity
    report = run(source, results, selection, tmp_path / "tie")
    assert report["status"] == "COMPARABLE"
    assert events == [
        item for _ in range(4) for item in ("fit", "validation", "validation", "validation")
    ] + ["locked", *["test"] * 6]

    original_predict = Predictor.predict
    for name, column in (("claims", "ClaimNb"), ("exposure", "Exposure"), ("membership", "IDpol")):

        def mutate(self, subset, field=column):
            result = original_predict(self, subset)
            if events[-1] == "test":
                subset.loc[subset.index[0], field] += 1
            return result

        monkeypatch.setattr(Predictor, "predict", mutate)
        report = run(source, results, selection, tmp_path / name)
        assert report["reason"] == "EVAL_MISMATCH"
        assert report["evaluation"] is None
        assert report["scenarios"] == []

    monkeypatch.setattr(Predictor, "predict", original_predict)

    def does_not_converge(*args, **kwargs):
        raise ConvergenceWarning("synthetic local path")

    monkeypatch.setattr(sensitivity, "fit_models", does_not_converge)
    assert run(source, results, selection, tmp_path / "convergence")["reason"] == "FIT_FAILED"

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(sensitivity, "fit_models", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run(source, results, selection, tmp_path / "interrupted")
    assert not (tmp_path / "interrupted").exists()

    monkeypatch.setattr(sensitivity, "fit_models", fit)
    mismatch = tmp_path / "environment.json"
    changed = json.loads(results.read_bytes())
    changed["environment"]["python"] = "0.0"
    mismatch.write_text(json.dumps(changed), encoding="utf-8")
    assert (
        run(source, mismatch, selection, tmp_path / "environment")["reason"] == "PROTOCOL_MISMATCH"
    )

    original_evaluate = sensitivity.evaluate_predictions

    def changed_metric(subset, predictions):
        metrics = original_evaluate(subset, predictions)
        metrics["mean_poisson_deviance"] += 0.1
        return metrics

    with monkeypatch.context() as change:
        change.setattr(sensitivity, "evaluate_predictions", changed_metric)
        assert run(source, results, selection, tmp_path / "replay")["reason"] == "REPLAY_MISMATCH"

    def empty_split(*args, **kwargs):
        return dict(partitions, test=partitions["test"].iloc[:0])

    with monkeypatch.context() as change:
        change.setattr(sensitivity, "split_frame", empty_split)
        assert run(source, results, selection, tmp_path / "empty")["reason"] == "SPLIT_MISMATCH"

    write_text = Path.write_text

    def fail_on_html(path, *args, **kwargs):
        if path.name == "report.html":
            raise OSError("PRIVATE_WRITE_MARKER")
        return write_text(path, *args, **kwargs)

    with monkeypatch.context() as change:
        change.setattr(Path, "write_text", fail_on_html)
        output = tmp_path / "writer-failure"
        assert (
            main(
                [
                    "sensitivity",
                    "--input",
                    str(source),
                    "--results",
                    str(results),
                    "--selection",
                    str(selection),
                    "--output",
                    str(output),
                ]
            )
            == 1
        )
        assert not output.exists()
