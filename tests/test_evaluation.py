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
            "observed_frequency": 2 / 2.5,
            "predicted_frequency": 4.25 / 2.5,
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
    assert result["selected_minus_baseline"] == pytest.approx(2 / 3)
    assert (result["ci_lower"], result["ci_upper"]) == (-2, 2)
    assert result["draws"] == result["valid_draws"] == 200
    assert result["seed"] == 19
    assert result["invalid_draws"] == 0
    assert result["confidence_level"] == 0.95
    assert result["adequate"] is True
    assert result["abstention_reason"] is None
    assert result == paired_bootstrap(data, [1, 2], [2, 1], seed=19, draws=200)
    short = paired_bootstrap(data, [1, 2], [2, 1], seed=19, draws=3)
    assert short["valid_draws"] == 3
    assert short["degenerate_draws"] == 1
    assert short["adequate"] is False
    assert short["abstention_reason"] == "insufficient_draws"
    assert short["ci_lower"] is short["ci_upper"] is None
    identical = paired_bootstrap(frame, [1] * 6, [1] * 6)
    assert identical["selected_minus_baseline"] == 0
    assert identical["abstention_reason"] == "degenerate_distribution"
    assert identical["ci_lower"] is identical["ci_upper"] is None


def test_bootstrap_percentiles_match_independent_exposure_arithmetic(frame):
    data = frame.iloc[:2].copy()
    data["ClaimNb"] = [1, 2]
    data["Exposure"] = [0.5, 3]
    selected, baseline = (1.0, 2.0), (3.0, 1.0)
    generator = np.random.Generator(np.random.PCG64(13))
    differences = []
    for _ in range(81):
        indices = generator.integers(0, 2, size=2)
        numerator = sum(
            2
            * (
                data["ClaimNb"].iloc[i] * math.log(baseline[i] / selected[i])
                + data["Exposure"].iloc[i] * (selected[i] - baseline[i])
            )
            for i in indices
        )
        differences.append(numerator / sum(data["Exposure"].iloc[i] for i in indices))
    result = paired_bootstrap(data, selected, baseline, seed=13, draws=81)
    ordered = sorted(differences)
    assert result["ci_lower"] == pytest.approx(ordered[2])
    assert result["ci_upper"] == pytest.approx(ordered[-3])
    assert result["degenerate_draws"] == sum(
        difference in (ordered[0], ordered[-1]) for difference in differences
    )


def test_single_policy_bootstrap_abstains(frame):
    result = paired_bootstrap(frame.iloc[[0]], [1], [3], draws=40)
    assert result["abstention_reason"] == "insufficient_policies"
    assert result["degenerate_draws"] == result["valid_draws"] == 40
    assert result["ci_lower"] is result["ci_upper"] is None


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


def test_bootstrap_rejects_nonfinite_replicate_denominator(frame):
    data = frame.iloc[:2].copy()
    data["ClaimNb"] = 0
    data["Exposure"] = [1e308, 0.5]
    result = paired_bootstrap(data, [0.5, 0.5], [0.25, 0.25], seed=19, draws=40)
    assert result["selected_minus_baseline"] == 0.5
    assert 0 < result["invalid_draws"] < result["draws"]
    assert result["valid_draws"] + result["invalid_draws"] == result["draws"]
    assert result["abstention_reason"] == "invalid_draws"
    assert result["ci_lower"] is result["ci_upper"] is None
