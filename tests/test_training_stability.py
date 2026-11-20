import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning
from test_experiment import _study_frame

from motorclaimlab import experiment, training_stability
from motorclaimlab.__main__ import main
from motorclaimlab.data import split_frame
from motorclaimlab.saved_contract import MODELS


def test_sampling_is_seeded_on_policy_id(frame):
    ordered = _study_frame(frame)
    shuffled = ordered.sample(frac=1, random_state=15)
    first = training_stability._resample(shuffled, 20261121)
    second = training_stability._resample(ordered, 20261121)
    third = training_stability._resample(ordered, 20261122)
    assert first.equals(second)
    assert len(first) == len(ordered)
    assert first.IDpol.nunique() < len(first)
    assert not first.equals(third)
    assert first.set_index("IDpol").equals(ordered.set_index("IDpol").loc[list(first.IDpol)])


def test_cli_replays_and_preserves_exposure_contract(frame, tmp_path, capsys):
    source = tmp_path / "synthetic.csv"
    synthetic = _study_frame(frame)
    synthetic["Exposure"] = 0.25 * (synthetic.IDpol % 3 + 1)
    synthetic["ClaimNb"] = synthetic.IDpol % 3
    synthetic.loc[synthetic.IDpol % 4 == 0, "Exposure"] = 1.5
    synthetic.loc[synthetic.IDpol % 7 == 0, "ClaimNb"] = 6
    synthetic.to_csv(source, index=False)
    baseline = tmp_path / "baseline"
    experiment.run_experiment(source, baseline, max_iter=3, bootstrap_draws=5)
    results, selection = baseline / "results.json", baseline / "selection.json"
    args = [
        "training-stability",
        "--input",
        str(source),
        "--results",
        str(results),
        "--selection",
        str(selection),
        "--output",
    ]
    omitted = tmp_path / "omitted"
    with pytest.raises(SystemExit, match="2"):
        main([*args, str(omitted)])
    assert not omitted.exists()
    args.insert(1, "--synthetic")
    originals = {path: path.read_bytes() for path in (source, results, selection)}
    first, second = tmp_path / "first", tmp_path / "second"
    assert main([*args, str(first)]) == main([*args, str(second)]) == 0
    assert main([*args, str(first)]) == 1
    bundle = first / "artifacts"
    completion = json.loads((bundle / "completion.json").read_bytes())
    assert set(completion["artifacts"]) == {"training-stability.json", "report.html", "report.md"}
    for name, digest in completion["artifacts"].items():
        content = (bundle / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        assert content == (second / "artifacts" / name).read_bytes()
        assert b"IDpol" not in content
        assert str(tmp_path) not in content.decode("utf-8")
    report = json.loads((bundle / "training-stability.json").read_bytes())
    assert report["status"] == completion["status"] == "COMPARABLE"
    test = report["evaluation"]["test"]
    assert (test["rows"], test["exposure"], test["observed_claims"]) == (73, 53.5, 98)
    for repetition in report["repetitions"]:
        assert repetition["test"]["observed_frequency"] == pytest.approx(98 / 53.5)
    assert len({row["sample"]["policy_sample_sha256"] for row in report["repetitions"]}) == 5
    assert len({row["test"]["predicted_claims"] for row in report["repetitions"]}) > 1
    assert sum(report["summary"]["selection_counts"].values()) == 5
    assert {path: path.read_bytes() for path in originals} == originals
    source.write_bytes(originals[source] + b"\n")
    output = tmp_path / "changed"
    assert main([*args, str(output)]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "UNAVAILABLE SOURCE_MISMATCH"
    unavailable = json.loads((output / "artifacts" / "training-stability.json").read_bytes())
    assert unavailable["repetitions"] == [] and unavailable["summary"] is None
    assert "<table" not in (output / "artifacts" / "report.html").read_text(encoding="utf-8")
    source.write_bytes(originals[source])
    selection.write_bytes(b'{"duplicate": 1, "duplicate": 2}')
    assert (
        training_stability.run_training_stability(source, results, selection, tmp_path / "invalid")[
            "reason"
        ]
        == "BASELINE_INVALID"
    )

    schema = json.loads(
        (Path(__file__).parents[1] / "docs/schemas/training-stability.v1.schema.json").read_bytes()
    )
    assert set(report) == set(schema["required"]) == set(schema["properties"])


def test_all_choices_are_locked_before_holdout_predictions(frame, tmp_path, monkeypatch):
    source = tmp_path / "synthetic.csv"
    samples = _study_frame(frame).assign(ClaimNb=1, Exposure=1.0)
    samples.to_csv(source, index=False)
    holdouts = split_frame(samples)
    heldout_ids = tuple(holdouts["test"].IDpol)
    validation_ids = tuple(holdouts["validation"].IDpol)
    events = []

    class Predictor:
        def __init__(self, model):
            self.model = model

        def predict(self, subset):
            identifiers = tuple(subset.IDpol)
            assert identifiers in (heldout_ids, validation_ids)
            is_test = identifiers == heldout_ids
            events.append(("test" if is_test else "validation", self.model))
            rates = [1.0, 1.45, 0.55] if is_test else [0.55, 1.0, 1.45]
            return np.full(len(subset), rates[MODELS.index(self.model)])

    def fit(train, seed, max_iter):
        events.append(("fit", seed))
        assert max_iter == 3
        assert not set(train.IDpol) & (set(heldout_ids) | set(validation_ids))
        return {model: Predictor(model) for model in MODELS}

    monkeypatch.setattr(experiment, "fit_models", fit)
    monkeypatch.setattr(training_stability, "fit_models", fit)
    baseline = tmp_path / "baseline"
    experiment.run_experiment(source, baseline, max_iter=3, bootstrap_draws=5)
    files = (source, baseline / "results.json", baseline / "selection.json")
    events.clear()
    report = training_stability.run_training_stability(*files, tmp_path / "report")
    assert report["status"] == "COMPARABLE"
    assert events == [
        event
        for _ in range(6)
        for event in [("fit", 20261101), *(("validation", model) for model in MODELS)]
    ] + [*(("test", model) for model in MODELS), *[("test", "poisson_glm")] * 5]
    assert report["summary"]["selection_counts"] == dict.fromkeys(MODELS, 0) | {"poisson_glm": 5}
    assert report["repetitions"][0]["test"]["mean_poisson_deviance"] > 0

    def fails(*args, **kwargs):
        raise ConvergenceWarning("PRIVATE_FIT_ERROR")

    monkeypatch.setattr(training_stability, "fit_models", fails)
    failure = training_stability.run_training_stability(*files, tmp_path / "fit-failed")
    assert failure["status"] == "UNAVAILABLE"
    assert failure["reason"] == "FIT_FAILED"
    assert failure["repetitions"] == [] and failure["summary"] is None
