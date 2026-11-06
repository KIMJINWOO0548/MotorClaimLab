"""Direction labels are descriptive views of saved aggregate claim counts."""

import copy
import re

import pytest
from test_presentation import _saved

from motorclaimlab.report import render_markdown, render_report


@pytest.mark.parametrize(
    ("observed", "predicted", "expected"),
    [(9, 6, "과소예측 · +3.00"), (1, 5, "과대예측 · -4.00"), (0, 0, "일치 · 0.00")],
)
def test_segment_direction_comes_from_counts_not_saved_ratio(observed, predicted, expected):
    result = _saved()
    result["segments"][0].update(
        observed_claims=observed, predicted_claims=predicted, observed_predicted_ratio=999
    )
    before = copy.deepcopy(result)
    document = render_report(result)
    segment = re.search(r'<details class="segment-dimension".*?</details>', document, re.S).group()
    assert "Observed − predicted (claims)" in segment
    assert expected in segment
    assert expected in render_markdown(result)
    assert "Exposure (years)" in segment and "Rows" in segment
    assert "청구 건수의 기술적 차이" in document
    assert result == before


@pytest.mark.parametrize("invalid", [None, True, "3", -1, float("inf"), float("nan")])
def test_missing_or_invalid_counts_never_look_balanced(invalid):
    result = _saved()
    result["segments"] = [dict(result["segments"][0], observed_claims=invalid, predicted_claims=2)]
    segment = re.search(
        r'<details class="segment-dimension".*?</details>', render_report(result), re.S
    ).group()
    assert "판정 불가 · N/A" in segment
    assert "일치 · 0.00" not in segment
