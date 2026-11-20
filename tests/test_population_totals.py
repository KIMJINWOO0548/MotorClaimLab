"""Independent synthetic checks for exact audit and partition population totals."""

import hashlib
import json
import math
import warnings

import numpy as np
import pandas as pd
import pytest

from motorclaimlab import experiment, report
from motorclaimlab.data import sample_frame, split_frame, validate_frame


@pytest.mark.parametrize(
    "counts,expected",
    [
        ([2**53 - 1, 1, 1, 0, 0, 0], 2**53 + 1),
        ([2**53 - 1] * 6, 6 * (2**53 - 1)),
    ],
)
def test_audit_retains_exact_integer_claim_total(frame, counts, expected):
    records = frame.assign(ClaimNb=counts)
    before = records.copy(deep=True)
    audit = validate_frame(records)
    assert type(audit["claims"]) is int
    assert audit["claims"] == expected
    pd.testing.assert_frame_equal(records, before)


def test_audit_claim_total_can_exceed_int64_without_wrapping(frame):
    records = pd.concat(
        [frame.assign(IDpol=frame.IDpol + 6 * i, ClaimNb=2**53 - 1) for i in range(200)],
        ignore_index=True,
    )
    before = records.copy(deep=True)
    expected = 1200 * (2**53 - 1)
    assert expected > 2**63 - 1
    assert validate_frame(records)["claims"] == expected
    pd.testing.assert_frame_equal(records, before)


@pytest.mark.parametrize("reverse", [False, True])
def test_exposure_total_retains_small_positive_contributions(frame, reverse):
    exposures = [2**53, 1, 1, 1, 1, 1]
    records = frame.assign(Exposure=exposures[::-1] if reverse else exposures)
    before = records.copy(deep=True)
    # The exact sum is 2**53 + 5; its nearest binary64 value is 2**53 + 4.
    assert validate_frame(records)["exposure"] == float(2**53 + 4)
    pd.testing.assert_frame_equal(records, before)


def test_zero_claims_and_large_representable_exposure_remain_valid(frame):
    records = frame.assign(ClaimNb=0, Exposure=1e307)
    before = records.copy(deep=True)
    audit = validate_frame(records)
    assert audit["claims"] == 0
    assert math.isfinite(audit["exposure"])
    assert audit["exposure"] == 6e307
    assert audit["rows"] == 6
    assert audit["source_values_clipped"] is False
    pd.testing.assert_frame_equal(records, before)


def test_finite_exposures_with_overflowing_total_fail_without_numeric_warning(frame):
    records = frame.assign(Exposure=1e308)
    before = records.copy(deep=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match="Exposure total must be finite"):
            validate_frame(records)
    assert not any(issubclass(item.category, RuntimeWarning) for item in caught)
    pd.testing.assert_frame_equal(records, before)


def test_unrepresentable_exposure_stops_experiment_before_output_or_fit(
    frame, tmp_path, monkeypatch
):
    source = tmp_path / "synthetic-overflow.csv"
    frame.assign(Exposure=1e308).to_csv(source, index=False)
    before = source.read_bytes()

    def unexpected_fit(*args, **kwargs):
        raise AssertionError("Invalid population reached model fitting")

    monkeypatch.setattr(experiment, "fit_models", unexpected_fit)
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="Exposure total must be finite"):
        experiment.run_experiment(source, output, max_iter=1, bootstrap_draws=1)
    assert not output.exists()
    assert source.read_bytes() == before


@pytest.mark.parametrize("max_rows", [None, 2200])
def test_experiment_partition_totals_reconcile_without_int64_wrap(
    frame, tmp_path, monkeypatch, max_rows
):
    records = pd.concat(
        [frame.assign(IDpol=frame.IDpol + 6 * i, ClaimNb=2**53 - 1) for i in range(500)],
        ignore_index=True,
    )
    source = tmp_path / "synthetic-count-boundary.csv"
    records.to_csv(source, index=False)
    before = source.read_bytes()
    population = sample_frame(records, max_rows)
    partitions = split_frame(population)

    class Predictor:
        def predict(self, subset):
            return np.ones(len(subset))

    monkeypatch.setattr(experiment, "fit_models", lambda *args, **kwargs: {"mean": Predictor()})
    # Isolate population metadata: SQLite's fixed-width SUM and presentation of
    # arbitrary-size counts are outside this boundary test, not claimed fixed.
    monkeypatch.setattr(experiment, "summarize_sql", lambda records: {})
    monkeypatch.setattr(report, "write_figures", lambda *args: None)
    monkeypatch.setattr(report, "render_report", lambda results: "synthetic aggregate test")
    monkeypatch.setattr(report, "render_markdown", lambda results: "synthetic aggregate test")
    output = tmp_path / "new-run"
    result = experiment.run_experiment(
        source, output, max_rows=max_rows, max_iter=1, bootstrap_draws=1
    )
    expected_rows = 3000 if max_rows is None else 2200
    assert result["study"]["rows"] == expected_rows
    assert result["study"]["sampled"] is (max_rows is not None)
    for name, subset in partitions.items():
        summary = result["splits"][name]
        assert summary["rows"] == len(subset)
        assert summary["claims"] == len(subset) * (2**53 - 1)
        assert summary["exposure"] == math.fsum(subset.Exposure)
        ids = "\n".join(str(int(value)) for value in subset.IDpol).encode("ascii")
        assert summary["membership_sha256"] == hashlib.sha256(ids).hexdigest()
    assert sum(part["rows"] for part in result["splits"].values()) == expected_rows
    assert sum(part["claims"] for part in result["splits"].values()) == expected_rows * (2**53 - 1)
    assert result["audit"]["claims"] == 3000 * (2**53 - 1)
    assert result["audit"]["rows"] == 3000
    assert json.loads((output / "results.json").read_text())["splits"] == result["splits"]
    assert source.read_bytes() == before
