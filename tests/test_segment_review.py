"""Hand-calculated segment investigation; no model or policy-level data."""

import copy
import math

import pytest
from test_presentation import _saved

from motorclaimlab.report import render_markdown, render_report, segment_review


def balanced_partition():
    result = _saved()
    total = {"rows": 100, "exposure": 50.0, "observed_claims": 20.0, "predicted_claims": 20.0}
    result["metrics"]["test"][result["selected_model"]].update(total)
    result["segments"] = [
        dict(
            total,
            segment="Area",
            group="A",
            rows=60,
            exposure=30.0,
            observed_claims=18.0,
            predicted_claims=10.0,
            sparse=False,
        ),
        dict(
            total,
            segment="Area",
            group="B",
            rows=40,
            exposure=20.0,
            observed_claims=2.0,
            predicted_claims=10.0,
            sparse=True,
        ),
    ]
    return result


def test_zero_total_gap_does_not_hide_offsetting_errors_and_support():
    result = balanced_partition()
    before = copy.deepcopy(result)
    review = segment_review(result)
    assert len(review) == 1
    dimension = review[0]
    assert dimension["dimension"] == "Area"
    assert dimension["reconciled"] is True
    assert dimension["net_gap"] == 0
    assert dimension["absolute_gap"] == 16
    assert dimension["under"]["group"] == "A"
    assert dimension["under"]["gap"] == 8
    assert dimension["under"]["exposure_share"] == 0.6
    assert dimension["over"]["group"] == "B"
    assert dimension["over"]["gap"] == -8
    assert dimension["over"]["sparse"] is True
    document = render_report(result)
    assert 'id="segment-review"' in document
    assert 'href="#segment-dimension-0"' in document
    assert 'id="segment-dimension-0"' in document
    assert "16.00" in document and "60.0%" in document
    assert "Absolute group gap" in render_markdown(result)
    assert "16.00" in render_markdown(result)
    assert result == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("rows", 39),
        ("exposure", 19),
        ("observed_claims", 1),
        ("predicted_claims", 9),
        ("exposure", None),
        ("observed_claims", True),
        ("predicted_claims", math.inf),
        ("rows", 40.5),
        ("exposure", -2),
    ],
)
def test_incomplete_or_invalid_partition_suppresses_combined_claim_and_denominators(field, value):
    result = balanced_partition()
    result["segments"][1][field] = value
    dimension = segment_review(result)[0]
    assert dimension["reconciled"] is False
    assert dimension["net_gap"] is None
    assert dimension["absolute_gap"] is None
    assert dimension["under"] is None and dimension["over"] is None
    assert "N/A" in render_markdown(result)


def test_duplicate_group_and_missing_test_population_are_not_complete():
    result = balanced_partition()
    result["segments"][1]["group"] = "A"
    assert segment_review(result)[0]["reconciled"] is False
    result = balanced_partition()
    del result["metrics"]["test"][result["selected_model"]]["exposure"]
    assert segment_review(result)[0]["reconciled"] is False


def test_each_dimension_has_own_denominator_and_does_not_add_overlapping_groups():
    result = balanced_partition()
    result["segments"] += [dict(row, segment="DrivAge") for row in result["segments"]]
    review = segment_review(result)
    assert [dimension["absolute_gap"] for dimension in review] == [16, 16]
    assert [dimension["under"]["exposure_share"] for dimension in review] == [0.6, 0.6]
    assert segment_review(dict(result, segments=[])) == []


def test_equal_gaps_have_deterministic_saved_order_and_escape_untrusted_labels():
    result = balanced_partition()
    result["segments"][0]["group"] = '<img src=x onerror="alert(1)">|A'
    result["segments"][1]["segment"] = result["segments"][0]["segment"] = "<script>bad()</script>"
    document = render_report(result)
    assert "<script>bad()</script>" not in document
    assert '<img src=x onerror="alert(1)">' not in document
    assert "&lt;script&gt;bad()&lt;/script&gt;" in document
    assert "&#124;A" in render_markdown(result)


def test_exact_ties_keep_saved_order_and_absence_of_direction_is_explicit():
    result = balanced_partition()
    template = result["segments"][0]
    result["segments"] = [
        dict(template, group="first", rows=20, exposure=10, observed_claims=9, predicted_claims=5),
        dict(template, group="second", rows=40, exposure=20, observed_claims=9, predicted_claims=5),
        dict(template, group="over", rows=40, exposure=20, observed_claims=2, predicted_claims=10),
    ]
    assert segment_review(result)[0]["under"]["group"] == "first"
    for row in result["segments"]:
        row["observed_claims"] = row["predicted_claims"]
    review = segment_review(result)[0]
    assert review["reconciled"] is True
    assert review["absolute_gap"] == 0
    assert review["under"] is None and review["over"] is None


def test_overflowing_saved_aggregates_make_partition_summary_unavailable():
    result = balanced_partition()
    result["metrics"]["test"][result["selected_model"]]["observed_claims"] = 10**1000
    assert segment_review(result)[0]["reconciled"] is False
    result = balanced_partition()
    for row in result["segments"]:
        row["observed_claims"] = 1e308
    assert segment_review(result)[0]["reconciled"] is False
