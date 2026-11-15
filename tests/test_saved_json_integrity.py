"""Saved aggregate JSON must not silently discard conflicting declarations."""

import json

import pytest
from test_presentation import _saved

from motorclaimlab.presentation import render_saved


@pytest.mark.parametrize("target", ["results", "selection"])
def test_duplicate_json_keys_rejected_before_output(tmp_path, target):
    results = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    results.write_text(json.dumps(_saved()), encoding="utf-8")
    selection.write_text(json.dumps({"selected_model": "poisson_glm"}), encoding="utf-8")
    path = results if target == "results" else selection
    raw = path.read_text(encoding="utf-8")
    path.write_text('{"selected_model":"conflicting_model",' + raw[1:], encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError, match="Duplicate"):
        render_saved(results, output, selection)
    assert not output.exists()


@pytest.mark.parametrize("target", ["results", "selection"])
def test_nested_duplicate_json_keys_rejected_without_leaking_key(tmp_path, target):
    results = tmp_path / "results.json"
    selection = tmp_path / "selection.json"
    results.write_text(json.dumps(_saved()), encoding="utf-8")
    selection.write_text(json.dumps({"selected_model": "poisson_glm"}), encoding="utf-8")
    path = results if target == "results" else selection
    raw = path.read_text(encoding="utf-8")
    path.write_text('{"extra":{"PRIVATE_KEY":1,"PRIVATE_KEY":2},' + raw[1:], encoding="utf-8")
    output = tmp_path / "presentation"
    with pytest.raises(ValueError) as error:
        render_saved(results, output, selection)
    assert "PRIVATE_KEY" not in str(error.value)
    assert not output.exists()
