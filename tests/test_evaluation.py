"""Independent arithmetic checks for exposure-weighted frequency evaluation."""

import math

import numpy as np
import pytest

from motorclaimlab.evaluation import (
    calibration_table,
    evaluate_predictions,
    paired_bootstrap,
    segment_table,
)


def test_frequency_metrics_use_exposure_not_counts(frame):
    data = frame.iloc[:2].copy()
    data["ClaimNb"] = [0, 2]
    data["Exposure"] = [0.5, 2]
    result = evaluate_predictions(data, [0.5, 2])
    # Rates are [0, 1]. Weighted deviance terms: .5*1 and 2*(2-2*log(2)).
    assert result == pytest.approx(
        {
            "rows": 2,
            "exposure": 2.5,
            "mean_poisson_deviance": (0.5 + 4 - 4 * math.log(2)) / 2.5,
            "weighted_mae": (0.25 + 2) / 2.5,
            "observed_claims": 2,
            "predicted_claims": 4.25,
            "observed_predicted_ratio": 2 / 4.25,
        }
    )


def test_zero_observations_have_zero_ratio_and_finite_deviance(frame):
    frame["ClaimNb"] = 0
    result = evaluate_predictions(frame, np.ones(len(frame)))
    assert result["observed_predicted_ratio"] == 0
    assert result["mean_poisson_deviance"] == 2


@pytest.mark.parametrize(
    "predictions",
    [[1], [1] * 7, [0] * 6, [-1] * 6, [float("nan")] * 6, [float("inf")] * 6, [[1]] * 6],
)
def test_invalid_predictions_rejected(frame, predictions):
    with pytest.raises(ValueError):
        evaluate_predictions(frame, predictions)


@pytest.mark.parametrize(
    "column,value",
    [
        ("Exposure", 0),
        ("Exposure", -1),
        ("Exposure", float("inf")),
        ("ClaimNb", -1),
        ("ClaimNb", 0.5),
        ("ClaimNb", float("nan")),
        ("IDpol", 2),
    ],
)
def test_invalid_data_rejected(frame, column, value):
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        evaluate_predictions(frame, np.ones(len(frame)))


def test_empty_data_rejected(frame):
    with pytest.raises(ValueError):
        evaluate_predictions(frame.iloc[:0], [])


def test_calibration_ranks_ties_stably_without_collapsing(frame):
    rows = calibration_table(frame, [2, 1, 1, 1, 3, 2], n_bins=3)
    assert [row["bin"] for row in rows] == [1, 2, 3]
    assert [row["rows"] for row in rows] == [2, 2, 2]
    # Stable rank groups original positions [1,2], [3,0], [5,4].
    assert [row["observed_claims"] for row in rows] == [1, 2, 1]
    assert [row["exposure"] for row in rows] == [1.25, 1.5, 1.25]
    assert sum(row["predicted_claims"] for row in rows) == 6.25
    assert len(calibration_table(frame, [1] * 6, n_bins=10)) == 6


@pytest.mark.parametrize("bins", [0, -1, 1.5, True])
def test_bad_bin_counts_rejected(frame, bins):
    with pytest.raises(ValueError):
        calibration_table(frame, [1] * 6, n_bins=bins)


def test_segments_fixed_boundaries_and_sparse_exposure(frame):
    frame["DrivAge"] = [24, 25, 39, 40, 59, 60]
    frame["VehAge"] = [4, 5, 9, 10, 0, 20]
    rows = segment_table(frame, [1] * 6)
    lookup = {(row["segment"], row["group"]): row for row in rows}
    assert lookup[("DrivAge", "<25")]["rows"] == 1
    assert lookup[("DrivAge", "25-39")]["rows"] == 2
    assert lookup[("DrivAge", "40-59")]["rows"] == 2
    assert lookup[("DrivAge", "60+")]["rows"] == 1
    assert lookup[("VehAge", "<5")]["observed_claims"] == 0
    assert lookup[("VehAge", "5-9")]["observed_claims"] == 1
    assert lookup[("VehAge", "10+")]["observed_claims"] == 3
    assert lookup[("Area", "A")]["exposure"] == 0.75
    assert all(row["sparse"] for row in rows)


def test_sparse_flag_uses_both_rows_and_exposure(frame):
    import pandas as pd

    data = pd.concat([frame.iloc[[0]]] * 50, ignore_index=True)
    data["IDpol"] = range(50)
    data["Exposure"] = 0.2
    assert not any(row["sparse"] for row in segment_table(data, [1] * 50))
    data["Exposure"] = 0.1
    assert all(row["sparse"] for row in segment_table(data, [1] * 50))


def test_bootstrap_same_policy_pairing_and_deterministic_interval(frame):
    data = frame.iloc[:2].copy()
    data["ClaimNb"] = [0, 0]
    data["Exposure"] = [1, 2]
    # Per-policy deviance differences are -2 and +2. Mixed sample gives 2/3.
    result = paired_bootstrap(data, [1, 2], [2, 1], seed=19, draws=200)
    assert result == pytest.approx(
        {"selected_minus_baseline": 2 / 3, "ci_lower": -2, "ci_upper": 2, "seed": 19, "draws": 200}
    )
    assert result == paired_bootstrap(data, [1, 2], [2, 1], seed=19, draws=200)
    # PCG64(19) pairs are [1,0], [0,1], [0,0]. Sorted differences
    # [-2, 2/3, 2/3] give linear percentile endpoints -28/15 and 2/3.
    short = paired_bootstrap(data, [1, 2], [2, 1], seed=19, draws=3)
    assert short["ci_lower"] == pytest.approx(-28 / 15)
    assert short["ci_upper"] == pytest.approx(2 / 3)
    identical = paired_bootstrap(frame, [1] * 6, [1] * 6)
    assert identical["selected_minus_baseline"] == 0
    assert identical["ci_lower"] == identical["ci_upper"] == 0


@pytest.mark.parametrize("draws", [0, -1, 1.5, True])
def test_invalid_bootstrap_draws_rejected(frame, draws):
    with pytest.raises(ValueError):
        paired_bootstrap(frame, [1] * 6, [1] * 6, draws=draws)


def test_bootstrap_validates_both_models(frame):
    with pytest.raises(ValueError):
        paired_bootstrap(frame, [1] * 6, [0] * 6)


def test_short_high_exposure_segments_are_still_sparse(frame):
    frame["Exposure"] = 20
    assert all(row["sparse"] for row in segment_table(frame, [1] * 6))
