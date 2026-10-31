"""Exercise the real offline workflow and its file/selection boundaries."""

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from motorclaimlab.eda import summarize_sql
from motorclaimlab.experiment import run_experiment


def _study_frame(frame):
    return pd.concat(
        [frame.assign(IDpol=frame.IDpol + 6 * i) for i in range(50)], ignore_index=True
    )


def test_sql_eda_uses_exposure_totals_instead_of_mean_row_frequency(frame):
    result = summarize_sql(frame)
    assert result["overall"]["claims"] == 4
    assert result["overall"]["exposure"] == 4
    assert result["overall"]["frequency"] == 1
    area_a = next(row for row in result["by_area"] if row["area"] == "A")
    assert area_a["exposure"] == 0.75
    assert area_a["claims"] == 0


def test_sql_eda_does_not_truncate_whole_year_exposure_rates(frame):
    frame["Exposure"] = 1
    result = summarize_sql(frame)
    assert result["overall"]["frequency"] == pytest.approx(2 / 3)
    areas = {row["area"]: row for row in result["by_area"]}
    assert areas["B"]["frequency"] == 0.5
    assert areas["C"]["frequency"] == 1.5


def test_end_to_end_writes_aggregates_and_preserves_source(frame, tmp_path):
    source = tmp_path / "synthetic.csv"
    _study_frame(frame).to_csv(source, index=False)
    original = source.read_bytes()
    output = tmp_path / "new-run"
    result = run_experiment(source, output, max_iter=3, bootstrap_draws=5)
    assert source.read_bytes() == original
    assert result["study"]["data_kind"] == "local_unverified"
    assert sum(part["rows"] for part in result["splits"].values()) == 300
    assert set(result["metrics"]["test"]) == {"mean", "poisson_glm", "poisson_hgb"}
    assert result["selected_model"] == min(
        result["metrics"]["validation"],
        key=lambda name: result["metrics"]["validation"][name]["mean_poisson_deviance"],
    )
    assert result["bootstrap"]["draws"] == 5
    assert json.loads((output / "results.json").read_text()) == result
    for name in [
        "report.html",
        "report.md",
        "split-membership.csv",
        "predictions.csv",
        "figures/model-comparison.svg",
        "figures/calibration.svg",
    ]:
        assert (output / name).is_file()
    with pytest.raises(FileExistsError):
        run_experiment(source, output, max_iter=3, bootstrap_draws=5)
    assert source.read_bytes() == original


def test_selection_uses_validation_even_when_test_favors_another_model(
    frame, tmp_path, monkeypatch
):
    from motorclaimlab import experiment
    from motorclaimlab.data import split_frame

    records = _study_frame(frame).assign(ClaimNb=1, Exposure=1.0)
    validation_ids = set(split_frame(records)["validation"].IDpol)

    class Predictor:
        def __init__(self, name):
            self.name = name

        def predict(self, subset):
            is_validation = subset.IDpol.isin(validation_ids).to_numpy()
            if self.name == "mean":
                return np.where(is_validation, 1.1, 2.0)
            if self.name == "poisson_glm":
                return np.where(is_validation, 2.0, 1.0)
            return np.full(len(subset), 3.0)

    monkeypatch.setattr(
        experiment,
        "fit_models",
        lambda *args, **kwargs: {
            name: Predictor(name) for name in ["mean", "poisson_glm", "poisson_hgb"]
        },
    )
    source = tmp_path / "synthetic.csv"
    records.to_csv(source, index=False)
    result = run_experiment(source, tmp_path / "selection", bootstrap_draws=3)
    assert result["selected_model"] == "mean"
    assert result["metrics"]["test"]["poisson_glm"]["mean_poisson_deviance"] == 0
    assert result["metrics"]["test"]["mean"]["mean_poisson_deviance"] > 0


def test_cli_returns_failure_without_overwriting_existing_output(frame, tmp_path):
    source = tmp_path / "synthetic.csv"
    frame.to_csv(source, index=False)
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "preserve.txt"
    marker.write_text("preserve me")
    command = [
        sys.executable,
        "-m",
        "motorclaimlab",
        "run",
        "--input",
        str(source),
        "--output",
        str(existing),
        "--max-iter",
        "2",
        "--bootstrap-draws",
        "3",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert completed.returncode != 0
    assert "exists" in completed.stderr.lower()
    assert marker.read_text() == "preserve me"
