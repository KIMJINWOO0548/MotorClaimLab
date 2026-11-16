"""Check statistical states in the existing HTML, Markdown and chart exports."""

from test_presentation import _saved

from motorclaimlab.report import render_markdown, render_report, write_uncertainty


def test_insufficient_bootstrap_reports_draw_support_without_plotting_bounds(tmp_path):
    result = _saved()
    result["bootstrap"].update(
        adequate=False,
        abstention_reason="insufficient_draws",
        valid_draws=5,
        draws=5,
        invalid_draws=0,
        degenerate_draws=1,
        minimum_valid_draws=40,
    )
    for report in (render_report(result), render_markdown(result)):
        assert "유효 반복 5 / 5" in report and "최소 40" in report
        assert "-0.20000" not in report
        assert "유효한 재표집 반복이 부족합니다" in report
    svg = write_uncertainty(result, tmp_path).read_text(encoding="utf-8")
    assert "Interval unavailable" in svg and 'id="paired-ci"' not in svg


def test_count_only_report_explains_pure_premium_and_exposure_scopes():
    result = _saved()
    for report in (render_report(result), render_markdown(result)):
        assert "순보험료: N/A" in report and "보험금 액수" in report
        assert "분할 또는 집단의 노출 연수 합계" in report
