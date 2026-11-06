"""A report must not pair sampled rows with full-input exposure years."""

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest
from test_presentation import _saved

from motorclaimlab.presentation import render_saved
from motorclaimlab.report import render_markdown, render_report


def _sampled():
    results = _saved()
    results["study"].update(rows=120, sampled=True)
    results["audit"].update(rows=300, exposure=200.0)
    for name, rows, exposure in [
        ("train", 72, 50.0),
        ("validation", 24, 17.0),
        ("test", 24, 17.75),
    ]:
        results["splits"][name].update(rows=rows, exposure=exposure)
    return results


def _study_context(document):
    return re.search(r'<div class="study-context">(.*?)</div>', document, re.S).group(1)


def test_sampled_rows_and_exposure_describe_same_population_without_mutating_results():
    results = _sampled()
    original = copy.deepcopy(results)
    document = render_report(results)
    context = _study_context(document)
    assert "120" in context and "84.75" in context and "200.00" not in context
    assert "분석 노출" in context and "표본 실행" in context
    assert "전체 입력 감사" in document and "300" in document and "200.00" in document
    markdown = render_markdown(results)
    assert "Study exposure: 84.75 years" in markdown
    assert "Full-input audit: 300 rows; exposure 200.00 years" in markdown
    assert results == original


def test_full_run_uses_same_complete_split_population():
    results = _sampled()
    results["study"]["sampled"] = False
    results["audit"].update(rows=120, exposure=84.75)
    context = _study_context(render_report(results))
    assert "120" in context and "84.75" in context and "전체 자료 실행" in context


@pytest.mark.parametrize("exposure", [None, True, "17.75", float("nan"), float("inf"), -1, 0])
def test_invalid_split_exposure_is_unavailable_never_replaced_by_full_input(exposure):
    results = _sampled()
    results["splits"]["test"]["exposure"] = exposure
    context = _study_context(render_report(results))
    assert "N/A" in context and "200.00" not in context
    assert "Study exposure: N/A years" in render_markdown(results)


@pytest.mark.parametrize("defect", ["missing_split", "missing_exposure", "wrong_rows", "bool_rows"])
def test_incomplete_or_mismatched_split_population_is_unavailable(defect):
    results = _sampled()
    if defect == "missing_split":
        del results["splits"]["train"]
    elif defect == "missing_exposure":
        del results["splits"]["test"]["exposure"]
    elif defect == "wrong_rows":
        results["splits"]["test"]["rows"] = 23
    else:
        results["splits"]["test"]["rows"] = True
    context = _study_context(render_report(results))
    assert "N/A" in context and "200.00" not in context


@pytest.mark.parametrize("defect", ["sum_overflow", "integer_overflow"])
def test_aggregate_overflow_is_unavailable_without_crashing_the_report(defect):
    results = _sampled()
    if defect == "sum_overflow":
        for split in results["splits"].values():
            split["exposure"] = 1e308
    else:
        results["splits"]["test"]["exposure"] = 10**1000
    assert "N/A" in _study_context(render_report(results))
    assert "Study exposure: N/A years" in render_markdown(results)


def test_integer_precision_loss_cannot_make_mismatched_populations_appear_equal():
    results = _sampled()
    results["study"]["rows"] = 9007199254740994
    for name, count in [("train", 9007199254740993), ("validation", 1), ("test", 1)]:
        results["splits"][name].update(rows=count, exposure=1.0)
    # Exact saved count is 9007199254740995, not the declared study population.
    assert sum(part["rows"] for part in results["splits"].values()) != results["study"]["rows"]
    assert "N/A" in _study_context(render_report(results))
    assert "Study exposure: N/A years" in render_markdown(results)


def test_new_renderer_manifest_tracks_current_source_and_outputs_on_fresh_saved_aggregates(
    tmp_path, monkeypatch
):
    from motorclaimlab import experiment, models

    def forbidden(*args, **kwargs):
        raise AssertionError("Saved rendering must not fit models or run an experiment")

    monkeypatch.setattr(experiment, "run_experiment", forbidden)
    monkeypatch.setattr(models, "fit_models", forbidden)
    source = tmp_path / "synthetic-aggregates.json"
    selection = tmp_path / "synthetic-selection.json"
    results = _sampled()
    source.write_text(json.dumps(results), encoding="utf-8")
    selection.write_text(
        json.dumps(
            {
                "selected_model": results["selected_model"],
                "validation": results["metrics"]["validation"],
            }
        ),
        encoding="utf-8",
    )
    original = {path: path.read_bytes() for path in (source, selection)}
    output = tmp_path / "renderer-3-2"
    manifest = render_saved(source, output, selection)
    assert manifest["renderer_version"] == "3.3" and manifest["model_execution"] is False
    root = Path(__file__).resolve().parents[1]
    for name, expected in manifest["renderer_sources"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    for name, expected in manifest["artifacts"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    assert len(manifest["artifacts"]) == 8
    assert "84.75" in _study_context((output / "report.html").read_text(encoding="utf-8"))
    assert "Study exposure: 84.75 years" in (output / "report.md").read_text(encoding="utf-8")
    assert all(path.read_bytes() == value for path, value in original.items())
