"""Check built distributions without installing code or opening policy records."""

import tarfile
import zipfile
from pathlib import Path


def main():
    distributions = sorted(Path("dist").glob("*"))
    if not any(path.suffix == ".whl" for path in distributions):
        raise SystemExit("Missing built wheel")
    if not any(path.name.endswith(".tar.gz") for path in distributions):
        raise SystemExit("Missing source distribution")
    for path in distributions:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        elif path.name.endswith(".tar.gz"):
            with tarfile.open(path) as archive:
                names = archive.getnames()
        else:
            continue
        forbidden = [
            name
            for name in names
            if any(
                part in name.split("/")
                for part in (".venv", "raw", "processed", "runs", ".git", ".env")
            )
            or name.endswith((".arff", ".pkl", ".joblib"))
        ]
        if forbidden:
            raise SystemExit(f"Unexpected local artifacts in {path.name}: {forbidden}")
        print(f"PASS {path.name}: {len(names)} members; local records excluded")


if __name__ == "__main__":
    main()
