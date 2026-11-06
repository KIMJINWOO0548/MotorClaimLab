"""Renderer regressions use frozen aggregate fixtures; fitting is forbidden."""

import copy
import hashlib
import json
import re

import pytest
from test_report import _results

from motorclaimlab.presentation import render_saved
from motorclaimlab.report import render_markdown, render_report, write_uncertainty


def _saved():
    result = _results()
    old = result["selected_model"]
    result["selected_model"] = "poisson_glm"
    result["calibration"]["poisson_glm"] = result["calibration"].pop(old)
    result["metrics"]["validation"]["poisson_glm"]["mean_poisson_deviance"] = 0.123456
    result["metrics"]["test"]["poisson_glm"]["mean_poisson_deviance"] = 0.234567
    result["study"]["settings"] = {"split_method": "sha256-policy-id-60-20-20"}
    return result


def test_comparison_keeps_three_models_and_validation_selection_together():
    document = render_report(_saved())
    table = re.search(r'<table id="model-comparison".*?</table>', document, flags=re.S).group()
    assert table.count("<tbody>") == 1 and table.count("<tr") == 4
    assert all(label in table for label in ["Training mean", "Poisson GLM", "Poisson HGB"])
    assert "0.123456" in table and "0.234567" in table
    assert "검증 분할에서 선택" in table
    assert "Validation" in table and "Test results" in table
    assert 'class="cards"' not in document and 'class="card"' not in document


def test_native_provenance_contains_full_saved_source_context_and_is_escaped():
    result = _saved()
    result["study"]["settings"]["note"] = '</pre><script>alert("x")</script>'
    document = render_report(result)
    details = re.search(r'<details id="provenance".*?</details>', document, re.S).group()
    assert "<summary>" in details
    assert "b" * 64 in details and "d" * 64 in details and "e" * 40 in details
    assert "20261101" in details and "membership_sha256" in details
    assert "sha256-policy-id-60-20-20" in details
    assert "&lt;script&gt;" in details and "<script" not in document
    ids = re.findall(r'\bid="([^"]+)"', document)
    assert len(ids) == len(set(ids)), "Inline charts must not duplicate SVG/HTML IDs"


def test_markdown_retains_comparison_precision_interval_and_source_fingerprint():
    document = render_markdown(_saved())
    assert "0.123456" in document and "0.234567" in document
    assert "-0.20000" in document and "0.01000" in document
    assert "d" * 64 in document and "20261101" in document


def test_paired_interval_uses_stored_bounds_and_zero_reference(tmp_path):
    path = write_uncertainty(_saved(), tmp_path)
    svg = path.read_text(encoding="utf-8")
    assert 'id="zero-reference"' in svg and 'id="paired-ci"' in svg
    assert "-0.20000" in svg and "0.01000" in svg and "-0.10000" in svg
    assert "negative favors selected" in svg and "Frozen fits" in svg
    assert (tmp_path / "paired-difference.png").read_bytes().startswith(b"\x89PNG")


@pytest.mark.parametrize(
    "bootstrap",
    [
        {},
        {"ci_lower": float("nan")},
        {"selected_minus_baseline": 0.2, "ci_lower": 0.3, "ci_upper": 0.1},
    ],
)
def test_missing_or_invalid_interval_is_unavailable_instead_of_zero_success(bootstrap, tmp_path):
    result = _saved()
    result["bootstrap"] = bootstrap
    document = render_report(result)
    assert "계산되지 않음" in document
    svg = write_uncertainty(result, tmp_path).read_text(encoding="utf-8")
    assert 'id="paired-ci"' not in svg and "Interval unavailable" in svg


def test_baseline_selection_is_labeled_as_identical_comparison():
    result = _saved()
    result["selected_model"] = "mean"
    result["bootstrap"].update(selected_minus_baseline=0, ci_lower=0, ci_upper=0)
    assert "기준 모델과 동일한 비교" in render_report(result)


def test_missing_calibration_counts_are_not_drawn_as_zero_observations(tmp_path):
    import xml.etree.ElementTree as ET

    from motorclaimlab.report import write_figures

    result = _saved()
    result["calibration"]["poisson_glm"] = [
        {"bin": 1, "rows": 10, "exposure": 10, "predicted_claims": 2}
    ]
    paths = write_figures(result, tmp_path)
    svg = paths[1].read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    labels = [node.text for node in root.iter() if node.tag.endswith("}text")]
    assert "0.000" not in labels
    assert "Incomplete calibration bins: 1" in svg


def test_nonboolean_source_match_is_not_presented_as_verified_identity():
    result = _saved()
    result["provenance"]["source_matches_pinned"] = 1
    document = render_report(result)
    condition = document.split("<dt>입력 식별</dt>", 1)[1].split("</dd>", 1)[0]
    assert "기록 없음" in condition and "원본 바이트 일치" not in condition


def test_saved_render_preserves_inputs_and_records_separate_renderer(tmp_path, monkeypatch):
    from motorclaimlab import experiment, models

    def forbidden(*args, **kwargs):
        raise AssertionError("Presentation must never train or reevaluate models")

    monkeypatch.setattr(models, "fit_models", forbidden)
    monkeypatch.setattr(experiment, "run_experiment", forbidden)
    result = _saved()
    original = copy.deepcopy(result)
    source = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    source.write_text(json.dumps(result), encoding="utf-8")
    selection.write_text(
        json.dumps(
            {"selected_model": "poisson_glm", "validation": result["metrics"]["validation"]}
        ),
        encoding="utf-8",
    )
    before = {p: p.read_bytes() for p in [source, selection]}
    output = tmp_path / "presentation-v3-1"
    manifest = render_saved(source, output, selection)
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert json.loads(source.read_text()) == original
    assert manifest["model_execution"] is False and manifest["renderer_version"] == "3.3"
    assert manifest["inputs"]["results"]["sha256"] == hashlib.sha256(before[source]).hexdigest()
    assert (
        manifest["inputs"]["selection"]["sha256"] == hashlib.sha256(before[selection]).hexdigest()
    )
    assert manifest["original_experiment_code_sha256"] == "d" * 64
    assert len(manifest["renderer_sha256"]) == 64
    assert set(manifest["renderer_sources"]) == {
        "src/motorclaimlab/report.py",
        "src/motorclaimlab/presentation.py",
    }
    for relative, expected in manifest["artifacts"].items():
        assert hashlib.sha256((output / relative).read_bytes()).hexdigest() == expected
    assert {
        "report.html",
        "report.md",
        "figures/paired-difference.svg",
        "figures/paired-difference.png",
    } <= set(manifest["artifacts"])
    with pytest.raises(FileExistsError):
        render_saved(source, output, selection)


def test_mismatched_selection_does_not_create_a_presentation(tmp_path):
    source = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    source.write_text(json.dumps(_saved()))
    selection.write_text(json.dumps({"selected_model": "mean"}))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="selection"):
        render_saved(source, output, selection)
    assert not output.exists()
