"""Verify frozen inputs, renderer sources and derived outputs against Git blobs."""

import argparse
import hashlib
import json
import subprocess
from pathlib import PurePosixPath

BASE = "docs/evidence/presentation-v3/"
SOURCES = {"src/motorclaimlab/report.py", "src/motorclaimlab/presentation.py"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Check index before publication")
    args = parser.parse_args()
    prefix = ":" if args.staged else "HEAD:"

    def blob(path):
        parts = PurePosixPath(path).parts
        if PurePosixPath(path).is_absolute() or ".." in parts or "\\" in path:
            raise ValueError(f"Unexpected presentation path: {path}")
        if not (path.startswith("docs/evidence/") or path in SOURCES):
            raise ValueError(f"Unexpected presentation path: {path}")
        return subprocess.check_output(["git", "show", prefix + path])

    manifest = json.loads(blob(BASE + "presentation.json"))
    if manifest.get("model_execution") is not False or manifest.get("renderer_version") != "3.0":
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
    )


if __name__ == "__main__":
    main()
