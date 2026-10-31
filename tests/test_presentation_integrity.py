"""Verify the publication guard against real temporary Git index blobs."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_presentation.py"


def _repository(tmp_path):
    files = {
        "docs/evidence/benchmark/results.json": b'{"fixture":"saved aggregates"}',
        "docs/evidence/benchmark/selection.json": b'{"selected_model":"mean"}',
        "src/motorclaimlab/report.py": b"# test renderer\n",
        "src/motorclaimlab/presentation.py": b"# test writer\n",
        "docs/evidence/presentation-v3/report.html": b"<p>derived fixture</p>\n",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    sources = {name: value for name, value in hashes.items() if name.startswith("src/")}
    digest = hashlib.sha256()
    for name in sorted(sources):
        digest.update(name.encode() + b"\0" + bytes.fromhex(sources[name]))
    manifest = {
        "renderer_version": "3.0",
        "model_execution": False,
        "renderer_sha256": digest.hexdigest(),
        "renderer_sources": sources,
        "inputs": {
            key: {
                "path": f"docs/evidence/benchmark/{key}.json",
                "sha256": hashes[f"docs/evidence/benchmark/{key}.json"],
            }
            for key in ("results", "selection")
        },
        "artifacts": {"report.html": hashes["docs/evidence/presentation-v3/report.html"]},
    }
    (tmp_path / "docs/evidence/presentation-v3/presentation.json").write_text(json.dumps(manifest))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_published_presentation_hashes_use_actual_git_blobs(tmp_path):
    repository = _repository(tmp_path)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged"],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout


@pytest.mark.parametrize(
    "relative",
    [
        "docs/evidence/presentation-v3/report.html",
        "docs/evidence/benchmark/results.json",
        "src/motorclaimlab/report.py",
    ],
)
def test_input_renderer_or_artifact_mutation_is_rejected(relative, tmp_path):
    repository = _repository(tmp_path)
    (repository / relative).write_bytes(b"changed after manifest")
    subprocess.run(["git", "add", relative], cwd=repository, check=True)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged"],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert relative in completed.stdout + completed.stderr
