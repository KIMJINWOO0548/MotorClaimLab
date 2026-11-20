"""Verify frozen inputs, renderer sources and derived outputs against Git blobs."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import PurePosixPath

BASE = "docs/evidence/presentation-v3-1/"
SOURCES = {"src/motorclaimlab/report.py", "src/motorclaimlab/presentation.py"}


def _renderer_commit(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("renderer-ref must be an existing full commit SHA")
    command = subprocess.run(
        ["git", "cat-file", "-t", value],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    )
    if command.returncode or command.stdout.strip() != "commit":
        raise argparse.ArgumentTypeError("renderer-ref must be an existing full commit SHA")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Check index before publication")
    parser.add_argument(
        "--renderer-ref",
        type=_renderer_commit,
        help="Existing full commit SHA for historical renderer sources only; never fetches",
    )
    args = parser.parse_args()
    prefix = ":" if args.staged else "HEAD:"

    def blob(path):
        parts = PurePosixPath(path).parts
        if PurePosixPath(path).is_absolute() or ".." in parts or "\\" in path:
            raise ValueError(f"Unexpected presentation path: {path}")
        if not (path.startswith("docs/evidence/") or path in SOURCES):
            raise ValueError(f"Unexpected presentation path: {path}")
        if args.renderer_ref and path in SOURCES:
            return subprocess.check_output(
                ["git", "show", args.renderer_ref + ":" + path],
                env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
            )
        return subprocess.check_output(["git", "show", prefix + path])

    manifest = json.loads(blob(BASE + "presentation.json"))
    if manifest.get("model_execution") is not False or manifest.get("renderer_version") != "3.1":
        raise SystemExit("Unexpected renderer version or model-execution declaration")
    if set(manifest["renderer_sources"]) != SOURCES or set(manifest["inputs"]) != {
        "results",
        "selection",
    }:
        raise SystemExit("Missing frozen inputs or renderer source files")
    failures = []

    def verify(path, expected):
        if hashlib.sha256(blob(path)).hexdigest() != expected:
            failures.append(path)

    for key, entry in manifest["inputs"].items():
        if entry["path"] != f"docs/evidence/benchmark/{key}.json":
            raise SystemExit("Published input must reference the original benchmark " + key)
        verify(entry["path"], entry["sha256"])
    digest = hashlib.sha256()
    for path, expected in sorted(manifest["renderer_sources"].items()):
        verify(path, expected)
        digest.update(path.encode("utf-8") + b"\0" + bytes.fromhex(expected))
    if digest.hexdigest() != manifest["renderer_sha256"]:
        failures.append("combined renderer fingerprint")
    if not manifest["artifacts"]:
        raise SystemExit("Missing derived artifacts")
    for relative, expected in manifest["artifacts"].items():
        if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
            raise SystemExit("Unexpected derived artifact path: " + relative)
        verify(BASE + relative, expected)
    if failures:
        raise SystemExit("Presentation SHA-256 mismatch: " + ", ".join(failures))
    print(
        f"PASS presentation {manifest['renderer_version']}: 2 frozen inputs, "
        f"2 renderer sources, {len(manifest['artifacts'])} derived artifacts"
        + (f"; renderer source commit {args.renderer_ref}" if args.renderer_ref else "")
    )


if __name__ == "__main__":
    main()
