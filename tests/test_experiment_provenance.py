"""Synthetic regressions for immutable inputs and train/selection boundaries."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from motorclaimlab import experiment
from motorclaimlab.data import split_frame
from motorclaimlab.models import fit_models


def _source(frame, tmp_path):
    records = pd.concat(
        [frame.assign(IDpol=frame.IDpol + 6 * i) for i in range(50)], ignore_index=True
    )
    source = tmp_path / "hand-authored-synthetic.csv"
    records.to_csv(source, index=False)
    return source, records


def test_source_change_during_load_fails_before_creating_output(frame, tmp_path, monkeypatch):
    source, _ = _source(frame, tmp_path)
    original_load = experiment.load_dataset

    def changed_load(path):
        loaded = original_load(path)
        path.write_bytes(path.read_bytes() + b"\n")
        return loaded

    monkeypatch.setattr(experiment, "load_dataset", changed_load)
    output = tmp_path / "unstarted"
    with pytest.raises(ValueError, match="Source bytes changed"):
        experiment.run_experiment(source, output, max_iter=3, bootstrap_draws=3)
    assert not output.exists()


def test_source_change_during_fit_records_failure_without_completed_results(
    frame, tmp_path, monkeypatch
):
    source, _ = _source(frame, tmp_path)
    original_fit = experiment.fit_models

    def changed_fit(*args, **kwargs):
        models = original_fit(*args, **kwargs)
        source.write_bytes(source.read_bytes() + b"\n")
        return models

    monkeypatch.setattr(experiment, "fit_models", changed_fit)
    output = tmp_path / "failed-source"
    with pytest.raises(ValueError, match="Source bytes changed"):
        experiment.run_experiment(source, output, max_iter=3, bootstrap_draws=3)
    execution = json.loads((output / "execution.json").read_text())
    assert execution["status"] == "failed"
    assert execution["exit_code"] == 1
    assert execution["error_type"] == "ValueError"
    assert not (output / "results.json").exists()
    assert not (output / "report.html").exists()
    assert not (output / "predictions.csv").exists()


def test_code_change_during_run_cannot_be_reported_as_completed(frame, tmp_path, monkeypatch):
    source, _ = _source(frame, tmp_path)
    fingerprints = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(experiment, "code_fingerprint", lambda: next(fingerprints))
    output = tmp_path / "failed-code"
    with pytest.raises(ValueError, match="Code bytes changed"):
        experiment.run_experiment(source, output, max_iter=3, bootstrap_draws=3)
    assert json.loads((output / "execution.json").read_text())["status"] == "failed"
    assert not (output / "results.json").exists()
    assert not (output / "report.html").exists()


def test_fit_receives_train_only_once_and_selection_precedes_test_predictions(
    frame, tmp_path, monkeypatch
):
    source, records = _source(frame, tmp_path)
    parts = split_frame(records)
    expected_train = list(parts["train"].IDpol)
    expected_validation = list(parts["validation"].IDpol)
    expected_test = list(parts["test"].IDpol)
    output = tmp_path / "selection-order"
    events = []

    class Predictor:
        def __init__(self, name):
            self.name = name

        def predict(self, subset):
            ids = list(subset.IDpol)
            if ids == expected_test:
                frozen = json.loads((output / "selection.json").read_text())
                assert frozen["selection_split"] == "validation"
                assert frozen["selected_model"] == "mean"
                assert set(frozen["validation"]) == {"mean", "poisson_glm", "poisson_hgb"}
                events.append(("test", self.name))
            else:
                assert ids == expected_validation
                assert not (output / "selection.json").exists()
                events.append(("validation", self.name))
            return np.ones(len(subset))

    def train_only(subset, **kwargs):
        assert list(subset.IDpol) == expected_train
        assert kwargs == {"seed": 20261101, "max_iter": 3}
        events.append(("fit", "train"))
        return {name: Predictor(name) for name in ["mean", "poisson_glm", "poisson_hgb"]}

    monkeypatch.setattr(experiment, "fit_models", train_only)
    result = experiment.run_experiment(source, output, max_iter=3, bootstrap_draws=3)
    assert events == [
        ("fit", "train"),
        ("validation", "mean"),
        ("validation", "poisson_glm"),
        ("validation", "poisson_hgb"),
        ("test", "mean"),
        ("test", "poisson_glm"),
        ("test", "poisson_hgb"),
    ]
    assert result["provenance"]["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["provenance"]["code_sha256"] == experiment.code_fingerprint()


def test_repeated_fits_keep_identical_predictions_and_train_scaling(frame):
    first = fit_models(frame, seed=20261101, max_iter=3)
    second = fit_models(frame, seed=20261101, max_iter=3)
    scaler = first["poisson_glm"].preprocessor.named_transformers_["numeric"]
    np.testing.assert_array_equal(
        scaler.mean_, frame[["VehAge", "DrivAge", "BonusMalus", "Density"]].mean().to_numpy()
    )
    for name in first:
        np.testing.assert_array_equal(first[name].predict(frame), second[name].predict(frame))


def test_synthetic_membership_matches_independent_frozen_sha256_oracle(frame, tmp_path):
    _, records = _source(frame, tmp_path)
    # Independently calculated with hashlib, without importing the split implementation.
    expected = {
        "train": (169, "5b02de24c231947b2f4e8e3c0da454599a2960f5a6b5cfb2b382540f929a9bc8"),
        "validation": (58, "53509a1025ccba79bb10581375fed51e6dbb7d22abc010743eeffd22ce3202b3"),
        "test": (73, "8f178f02d36cbc9288d80c34afb1920d21cc463b36c1fdab9a489726c1c4391d"),
    }
    original = records.copy(deep=True)
    for name, subset in split_frame(records.iloc[::-1].assign(ClaimNb=999)).items():
        ids = "\n".join(str(int(pid)) for pid in subset.IDpol).encode("ascii")
        assert (len(subset), hashlib.sha256(ids).hexdigest()) == expected[name]
    pd.testing.assert_frame_equal(records, original)
