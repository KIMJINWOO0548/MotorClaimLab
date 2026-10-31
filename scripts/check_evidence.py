"""Verify evidence hashes against actual Git blobs, independent of checkout EOLs."""

import argparse
import hashlib
import json
import subprocess
from pathlib import PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Check index before commit")
    args = parser.parse_args()
    prefix = ":" if args.staged else "HEAD:"

    def blob(path):
        parts = PurePosixPath(path).parts
        if parts[:2] != ("docs", "evidence") or ".." in parts:
            raise ValueError(f"Unexpected evidence path: {path}")
        return subprocess.check_output(["git", "show", prefix + path])

    manifest = json.loads(blob("docs/evidence/verification.json"))
    mismatches = [
        path
        for path, expected in manifest["artifact_sha256"].items()
        if hashlib.sha256(blob(path)).hexdigest() != expected
    ]
    if mismatches:
        raise SystemExit("Evidence SHA-256 mismatch: " + ", ".join(mismatches))
    print(f"PASS {len(manifest['artifact_sha256'])} published evidence Git blobs")


if __name__ == "__main__":
    main()
