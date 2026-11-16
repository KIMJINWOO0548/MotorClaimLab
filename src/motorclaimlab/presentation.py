"""Derive a versioned presentation from saved aggregates without model execution."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

from .report import (
    RENDERER_VERSION,
    render_markdown,
    render_report,
    write_figures,
    write_uncertainty,
)
from .saved_contract import FROZEN_RESULTS, FROZEN_SELECTION, load_saved, sha256, validate_run


def _input_record(path: Path, content: bytes) -> dict:
    try:
        reference = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        reference = path.name
    return {"path": reference, "sha256": sha256(content)}


def renderer_sources() -> dict:
    directory = Path(__file__).parent
    return {
        f"src/motorclaimlab/{name}": sha256((directory / name).read_bytes())
        for name in ("report.py", "presentation.py", "saved_contract.py")
    }


def render_saved(results_path: Path, output_dir: Path, selection_path: Path | None = None) -> dict:
    """Read frozen aggregates and create new files without model imports or execution."""
    results_path, output_dir = Path(results_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Presentation output already exists; choose a fresh directory")
    source = results_path.read_bytes()
    results = load_saved(source)
    inputs = {"results": _input_record(results_path, source)}
    frozen = inputs["results"]["sha256"] == FROZEN_RESULTS
    if selection_path is None:
        sibling = results_path.with_name("selection.json")
        if sibling.exists():
            selection_path = sibling
        elif not frozen:
            raise ValueError("Saved selection is required for this results file")
    if selection_path is not None:
        selection_path = Path(selection_path)
        selection_source = selection_path.read_bytes()
        selection = load_saved(selection_source)
        inputs["selection"] = _input_record(selection_path, selection_source)
    if frozen:
        if selection_path is not None and inputs["selection"]["sha256"] != FROZEN_SELECTION:
            raise ValueError("Saved selection does not match the frozen benchmark")
        identity = None
    else:
        identity = validate_run(results, selection)
    sources = renderer_sources()
    digest = hashlib.sha256()
    for name in sorted(sources):
        digest.update(name.encode("utf-8") + b"\0" + bytes.fromhex(sources[name]))
    output_dir.mkdir(parents=True, exist_ok=False)
    write_figures(results, output_dir / "figures")
    write_uncertainty(results, output_dir / "figures")
    (output_dir / "report.html").write_bytes(render_report(results).encode("utf-8"))
    (output_dir / "report.md").write_bytes(render_markdown(results).encode("utf-8"))
    manifest = {
        "renderer_version": RENDERER_VERSION,
        "renderer_sha256": digest.hexdigest(),
        "renderer_sources": sources,
        "inputs": inputs,
        "saved_contract": "frozen-legacy" if frozen else "matched-run-identity",
        "original_experiment_code_sha256": results["provenance"].get("code_sha256"),
        "original_experiment_git_commit": results["provenance"].get("git_commit"),
        "model_execution": False,
        "values_source": "unchanged saved aggregate results",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "matplotlib": importlib.metadata.version("matplotlib"),
            "numpy": importlib.metadata.version("numpy"),
            "pillow": importlib.metadata.version("Pillow"),
        },
        "artifacts": {
            path.relative_to(output_dir).as_posix(): sha256(path.read_bytes())
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        },
        "browser_validation": (
            "NOT_RUN at generation; browser verification is recorded separately"
        ),
    }
    if identity is not None:
        manifest["run_identity"] = identity
    (output_dir / "presentation.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    )
    # Input identity is checked again after writing; inputs are never opened for writing.
    if results_path.read_bytes() != source:
        raise RuntimeError("Saved results changed during presentation generation")
    if selection_path is not None and selection_path.read_bytes() != selection_source:
        raise RuntimeError("Saved selection changed during presentation generation")
    return manifest
