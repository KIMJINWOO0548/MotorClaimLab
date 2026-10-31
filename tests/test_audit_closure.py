"""Core reading-flow regressions use existing aggregates, never new model fits."""

import copy
import re

from test_presentation import _saved

from motorclaimlab.report import render_report, write_figures, write_uncertainty


def test_standalone_paired_figure_names_models_level_and_fixed_conditions(tmp_path):
    svg = write_uncertainty(_saved(), tmp_path).read_text(encoding="utf-8")
    assert "Poisson GLM - Training mean" in svg
    assert "95% paired interval" in svg and "Frozen fits and split" in svg
    assert 'id="zero-reference"' in svg


def test_highest_numeric_bin_support_is_adjacent_and_uses_same_totals_as_curve(tmp_path):
    result = _saved()
    original = copy.deepcopy(result)
    base = result["calibration"]["poisson_glm"][0]
    result["calibration"]["poisson_glm"] = [
        dict(base, bin=10, rows=17, exposure=3, observed_claims=4, predicted_claims=2),
        dict(base, bin=2),
        dict(base, bin=10, rows=3, exposure=1, observed_claims=2, predicted_claims=1),
        dict(base, bin=1),
    ]
    before = copy.deepcopy(result)
    document = render_report(result)
    hero = document.split('<header class="study-hero"', 1)[1].split("</header>", 1)[0]
    write_figures(result, tmp_path)
    svg = (tmp_path / "calibration.svg").read_text(encoding="utf-8")
    for output in (hero, svg):
        assert "Bin 10" in output and "20 rows" in output
        assert "4.00 exposure-years" in output
        assert "Observed 6.00 claims / Predicted 3.00 claims" in output
    assert "Observed 1.500" in svg and "Predicted 0.750" in svg
    assert result == before and original["selected_model"] == result["selected_model"]


def test_incomplete_support_is_explicitly_unavailable(tmp_path):
    result = _saved()
    del result["calibration"]["poisson_glm"][-1]["rows"]
    document = render_report(result)
    write_figures(result, tmp_path)
    svg = (tmp_path / "calibration.svg").read_text(encoding="utf-8")
    assert "Support unavailable (N/A)" in document
    assert "Support unavailable (N/A)" in svg
    assert "0 rows" not in svg


def test_native_dimension_navigation_retains_every_saved_row_and_unknown_dimension():
    result = _saved()
    base = result["segments"][0]
    result["segments"] = [
        dict(base, segment="DrivAge", group="<25"),
        dict(base, segment="VehAge", group="<5"),
        dict(base, segment="Area", group="A"),
        dict(base, segment="Unknown <script>", group="EXTRA_GROUP"),
    ]
    document = render_report(result)
    sections = re.findall(r'<details class="segment-dimension".*?</details>', document, re.S)
    assert len(sections) == 4
    for section, group in zip(sections, ["&lt;25", "&lt;5", "A", "EXTRA_GROUP"], strict=True):
        assert "<summary>" in section and group in section
        assert "Sparse" in section and "Exposure (years)" in section
        assert "Observed claims" in section and "Predicted claims" in section
    assert "운전자 연령" in sections[0] and "차량 연령" in sections[1] and "지역" in sections[2]
    assert "Unknown &lt;script&gt;" in sections[3] and "<script" not in document
