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
        "docs/evidence/presentation-v3-1/report.html": b"<p>derived fixture</p>\n",
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
        "renderer_version": "3.1",
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
        "artifacts": {"report.html": hashes["docs/evidence/presentation-v3-1/report.html"]},
    }
    (tmp_path / "docs/evidence/presentation-v3-1/presentation.json").write_text(
        json.dumps(manifest)
    )
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
        "docs/evidence/presentation-v3-1/report.html",
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


def _commit(repository):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Synthetic fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Freeze fixture",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()


def test_explicit_historical_commit_preserves_original_renderer_hash_validation(tmp_path):
    repository = _repository(tmp_path)
    historical = _commit(repository)
    (repository / "src/motorclaimlab/report.py").write_bytes(b"# later renderer version\n")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--renderer-ref", historical],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert historical in completed.stdout


@pytest.mark.parametrize(
    "relative",
    ["docs/evidence/benchmark/results.json", "docs/evidence/presentation-v3-1/report.html"],
)
def test_historical_sources_do_not_bypass_current_input_or_artifact_checks(relative, tmp_path):
    repository = _repository(tmp_path)
    historical = _commit(repository)
    (repository / relative).write_bytes(b"changed after original publication")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--renderer-ref", historical],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert relative in completed.stdout + completed.stderr


def test_wrong_historical_renderer_commit_is_rejected(tmp_path):
    repository = _repository(tmp_path)
    _commit(repository)
    (repository / "src/motorclaimlab/report.py").write_bytes(b"# unrelated historical renderer\n")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    wrong = _commit(repository)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--renderer-ref", wrong],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "src/motorclaimlab/report.py" in completed.stdout + completed.stderr


@pytest.mark.parametrize("reference", ["HEAD", "1235c1f", "0" * 40])
def test_renderer_reference_requires_an_existing_full_commit_sha(reference, tmp_path):
    repository = _repository(tmp_path)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--renderer-ref", reference],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "existing full commit SHA" in completed.stderr


def test_renderer_reference_rejects_an_existing_noncommit_object(tmp_path):
    repository = _repository(tmp_path)
    blob = subprocess.check_output(
        ["git", "rev-parse", ":src/motorclaimlab/report.py"], cwd=repository, text=True
    ).strip()
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--renderer-ref", blob],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "existing full commit SHA" in completed.stderr
