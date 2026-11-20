"""Hand-derived insurance calculations with synthetic exposures and losses."""

import numpy as np
import pytest

from motorclaimlab import evaluation
from motorclaimlab.eda import summarize_sql
from motorclaimlab.evaluation import calibration_table, evaluate_predictions, segment_table


def test_risk_aggregates_share_the_actual_exposure_denominator(frame):
    data = frame.iloc[:4].copy()
    data["ClaimNb"] = [0, 1, 3, 0]
    data["Exposure"] = [0.25, 0.75, 2.5, 0.5]
    data["Area"] = ["A", "A", "B", "B"]
    rates = [0.25, 0.75, 0.5, 1.0]

    metrics = evaluate_predictions(data, rates)
    assert metrics["observed_frequency"] == 4 / 4
    assert metrics["predicted_frequency"] == 2.375 / 4
    assert evaluation.pure_premium(data, [0, 80, 600, 0]) == 680 / 4
    assert evaluation.pure_premium(data, [0, 0, 0, 0]) == 0

    areas = [row for row in segment_table(data, rates) if row["segment"] == "Area"]
    assert [row["observed_frequency"] for row in areas] == [1, 1]
    assert [row["predicted_frequency"] for row in areas] == [0.625, 1.75 / 3]
    assert [row["frequency"] for row in summarize_sql(data)["by_area"]] == [1, 1]

    bins = calibration_table(data, rates, n_bins=2)
    assert [row["observed_frequency"] for row in bins] == pytest.approx([3 / 2.75, 1 / 1.25])
    assert [row["predicted_frequency"] for row in bins] == pytest.approx(
        [1.3125 / 2.75, 1.0625 / 1.25]
    )
    assert len(calibration_table(data.iloc[[0]], [1], n_bins=5)) == 1
    assert bins[0]["sparse_reasons"] == ["rows_below_50", "exposure_below_10"]


@pytest.mark.parametrize("exposure", [0, -1, np.nan, np.inf])
def test_invalid_exposure_rejected_at_each_metric_entry(frame, exposure):
    data = frame.iloc[:2].copy()
    data["Exposure"] = [exposure, 1.5]
    for calculate in (
        lambda: evaluate_predictions(data, [1, 1]),
        lambda: calibration_table(data, [1, 1]),
        lambda: segment_table(data, [1, 1]),
        lambda: summarize_sql(data),
        lambda: evaluation.pure_premium(data, [0, 10]),
    ):
        with pytest.raises(ValueError, match="Exposure"):
            calculate()


@pytest.mark.parametrize("losses", [[1], [-1, 1], [np.nan, 1], [np.inf, 1], [True, 1]])
def test_pure_premium_requires_explicit_valid_loss_amounts(frame, losses):
    with pytest.raises(ValueError, match="Loss amounts"):
        evaluation.pure_premium(frame.iloc[:2], losses)


def test_empty_source_has_no_denominator(frame):
    data = frame.iloc[:0]
    with pytest.raises(ValueError, match="empty"):
        summarize_sql(data)
    with pytest.raises(ValueError, match="empty"):
        evaluation.pure_premium(data, [])


def test_zero_over_zero_claim_ratio_is_unavailable(frame):
    data = frame.iloc[[0]].copy()
    data["ClaimNb"] = 0
    data["Exposure"] = 1e-200
    result = evaluate_predictions(data, [1e-200])
    assert result["observed_claims"] == result["predicted_claims"] == 0
    assert result["observed_predicted_ratio"] is None
