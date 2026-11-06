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


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _input_record(path: Path, content: bytes) -> dict:
    try:
        reference = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        reference = path.name
    return {"path": reference, "sha256": _sha(content)}


def renderer_sources() -> dict:
    directory = Path(__file__).parent
    return {
        f"src/motorclaimlab/{name}": _sha((directory / name).read_bytes())
        for name in ("report.py", "presentation.py")
    }


def render_saved(results_path: Path, output_dir: Path, selection_path: Path | None = None) -> dict:
    """Read frozen aggregates and create new files without model imports or execution."""
    results_path, output_dir = Path(results_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Presentation output already exists; choose a fresh directory")
    source = results_path.read_bytes()
    results = json.loads(source)
    if not isinstance(results, dict) or any(
        name not in results for name in ("study", "metrics", "provenance", "selected_model")
    ):
        raise ValueError("Saved results must contain study, metrics, provenance and selected_model")
    inputs = {"results": _input_record(results_path, source)}
    if selection_path is not None:
        selection_path = Path(selection_path)
        selection_source = selection_path.read_bytes()
        selection = json.loads(selection_source)
        if (
            not isinstance(selection, dict)
            or selection.get("selected_model") != results["selected_model"]
        ):
            raise ValueError("Saved selection does not match results")
        if "validation" in selection and selection["validation"] != results["metrics"].get(
            "validation"
        ):
            raise ValueError("Saved selection validation metrics do not match results")
        inputs["selection"] = _input_record(selection_path, selection_source)
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
            path.relative_to(output_dir).as_posix(): _sha(path.read_bytes())
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        },
        "browser_validation": (
            "NOT_RUN at generation; browser verification is recorded separately"
        ),
    }
    (output_dir / "presentation.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    )
    # Input identity is checked again after writing; inputs are never opened for writing.
    if results_path.read_bytes() != source:
        raise RuntimeError("Saved results changed during presentation generation")
    if selection_path is not None and selection_path.read_bytes() != selection_source:
        raise RuntimeError("Saved selection changed during presentation generation")
    return manifest
