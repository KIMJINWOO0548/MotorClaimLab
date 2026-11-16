"""Boundary oracles for existing aggregate entry points."""

import math

import numpy as np
import pandas as pd
import pytest

from motorclaimlab import evaluation
from motorclaimlab.eda import summarize_sql


def test_nonconstant_draws_can_still_produce_a_degenerate_percentile_interval(frame, monkeypatch):
    class Draws:
        calls = 0

        def integers(self, _low, _high, size):
            self.calls += 1
            index = self.calls == 100
            return np.full(size, int(index), dtype=int)

    monkeypatch.setattr(evaluation.np.random, "Generator", lambda _bitgen: Draws())
    result = evaluation.paired_bootstrap(
        frame.iloc[:2], [1.0, 0.5], [1.0, 1.0], seed=123, draws=100
    )
    assert result["valid_draws"] == 100
    assert result["abstention_reason"] == "degenerate_distribution"
    assert result["adequate"] is False and result["ci_lower"] is result["ci_upper"] is None


def test_sql_group_and_population_denominators_keep_small_exposures(frame):
    result = summarize_sql(frame.assign(Area="A", Exposure=[2**53, 1, 1, 1, 1, 1]))
    # The exact population and single-group exposure is 2**53 + 5,
    # which rounds to 2**53 + 4 in binary64.
    assert result["overall"]["exposure"] == float(2**53 + 4)
    assert result["by_area"][0]["exposure"] == float(2**53 + 4)
    assert result["by_area"][0]["frequency"] == 4 / float(2**53 + 4)


def test_sql_claim_total_is_exact_beyond_a_sqlite_integer(frame):
    records = pd.concat(
        [frame.assign(IDpol=frame.IDpol + 6 * i, Area="A", ClaimNb=2**53 - 1) for i in range(200)],
        ignore_index=True,
    )
    result = summarize_sql(records)
    expected = 1200 * (2**53 - 1)
    assert result["overall"]["claims"] == result["by_area"][0]["claims"] == expected
    assert result["overall"]["exposure"] == 800
    assert result["by_area"][0]["frequency"] == expected / 800


def test_deviance_uses_finite_count_scale_arithmetic_for_unusual_positive_exposure(frame):
    records = frame.iloc[:3].assign(ClaimNb=[1, 0, 0], Exposure=[1e-299, 1, 1])
    result = evaluation.evaluate_predictions(records, [1e-299, 1, 1])
    # Numerator is 2*(log(10**598) - 1 + 1 + 1); the exposure rounds to 2.
    assert result["mean_poisson_deviance"] == pytest.approx(598 * math.log(10) + 1)
    assert result["weighted_mae"] == 1.5
