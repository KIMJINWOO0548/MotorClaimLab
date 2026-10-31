"""Pinned public source, strict source audit and target-independent partitions."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import arff
import numpy as np
import pandas as pd

SEED = 20261101
DATASET_ID = 41214
SOURCE_URL = "https://www.openml.org/data/v1/download/20649148/freMTPL2freq.arff"
SOURCE_MD5 = "f8875568bf0ca622929105197e2db613"
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024
COLUMNS = (
    "IDpol",
    "ClaimNb",
    "Exposure",
    "Area",
    "VehPower",
    "VehAge",
    "DrivAge",
    "BonusMalus",
    "VehBrand",
    "VehGas",
    "Density",
    "Region",
)
CATEGORICAL = ("Area", "VehBrand", "VehGas", "Region")
NUMERIC = tuple(name for name in COLUMNS if name not in CATEGORICAL)


def sha256_file(path: Path) -> str:
    """Fingerprint bytes without persisting source records in public artifacts."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_dataset(directory: Path) -> Path:
    """Download the pinned ARFF once, rejecting checksum mismatch and overwrite."""
    directory = Path(directory)
    target = directory / "freMTPL2freq.arff"
    manifest = directory / "source.json"
    if target.exists() or manifest.exists():
        raise FileExistsError("Source target already exists; choose a new output directory")
    request = Request(
        SOURCE_URL, headers={"User-Agent": "MotorClaimLab/0.1.0", "Accept-Encoding": "gzip"}
    )
    with urlopen(request, timeout=60) as response:
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
        encoding = getattr(response, "headers", {}).get("Content-Encoding", "")
    if encoding.lower() == "gzip":
        with gzip.GzipFile(fileobj=BytesIO(payload)) as compressed:
            payload = compressed.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Source download exceeds 128 MiB limit")
    if hashlib.md5(payload, usedforsecurity=False).hexdigest() != SOURCE_MD5:
        raise ValueError("Source MD5 mismatch; refusing unverified download")
    directory.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(payload)
    descriptor = {
        "dataset_id": DATASET_ID,
        "version": 1,
        "source_url": SOURCE_URL,
        "license_asserted_by_openml": "CC0",
        "published_md5": SOURCE_MD5,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "original_insurer_permission_independently_verified": False,
    }
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(descriptor, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return target


def load_dataset(path: Path) -> pd.DataFrame:
    """Read local CSV/ARFF without correcting or rewriting source data."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() == ".arff":
        with path.open(encoding="utf-8") as stream:
            contents = arff.load(stream)
        frame = pd.DataFrame(contents["data"], columns=[name for name, _ in contents["attributes"]])
    else:
        raise ValueError("Input must be a local .csv or .arff file")
    validate_frame(frame)
    for name in NUMERIC:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    frame["IDpol"] = frame["IDpol"].astype(np.int64)
    frame["ClaimNb"] = frame["ClaimNb"].astype(np.int64)
    return frame


def validate_frame(frame: pd.DataFrame) -> dict:
    """Reject invalid observations, retaining valid unusual source values."""
    missing = sorted(set(COLUMNS) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(COLUMNS))
    if missing or extra:
        raise ValueError(f"Schema mismatch: missing={missing}, unexpected={extra}")
    if frame.empty:
        raise ValueError("Source dataset is empty")
    numeric = {}
    for name in NUMERIC:
        if frame[name].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError(f"{name} must contain measurements, not boolean values")
        try:
            values = pd.to_numeric(frame[name], errors="raise").to_numpy(dtype=float)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{name} must contain finite numeric values") from exc
        if not np.isfinite(values).all():
            raise ValueError(f"{name} must contain finite numeric values")
        numeric[name] = values
    for name in ("IDpol", "ClaimNb"):
        values = numeric[name]
        if (values < 0).any() or (values != np.floor(values)).any():
            raise ValueError(f"{name} must contain nonnegative integers")
        if (values > 2**53 - 1).any():
            raise ValueError(f"{name} exceeds exact integer range")
    if pd.Series(numeric["IDpol"]).duplicated().any():
        raise ValueError("IDpol must be unique; duplicate policy identifiers are not deduplicated")
    for name in ("Exposure", "Density", "BonusMalus"):
        if (numeric[name] <= 0).any():
            raise ValueError(f"{name} must be strictly positive")
    for name in ("VehPower", "VehAge", "DrivAge"):
        if (numeric[name] < 0).any():
            raise ValueError(f"{name} must be nonnegative")
    for name in CATEGORICAL:
        values = frame[name]
        if (
            values.isna().any()
            or values.map(lambda value: not isinstance(value, str) or not value.strip()).any()
        ):
            raise ValueError(f"{name} must contain nonempty text categories")
    return {
        "rows": int(len(frame)),
        "columns": len(frame.columns),
        "claims": int(numeric["ClaimNb"].sum()),
        "exposure": float(numeric["Exposure"].sum()),
        "exposure_gt_one": int((numeric["Exposure"] > 1).sum()),
        "claims_gt_four": int((numeric["ClaimNb"] > 4).sum()),
        "zero_claim_rows": int((numeric["ClaimNb"] == 0).sum()),
        "source_values_clipped": False,
    }


def _policy_hash(policy_id: int, seed: int, purpose: str) -> int:
    encoded = f"{seed}:{purpose}:{int(policy_id)}".encode("ascii")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def split_frame(frame: pd.DataFrame, seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Assign immutable policy IDs, independently of labels and input row order."""
    validate_frame(frame)
    ordered = frame.sort_values("IDpol").reset_index(drop=True)
    hashes = np.array([_policy_hash(pid, seed, "split") for pid in ordered.IDpol], dtype="uint64")
    train_boundary = (2**64 * 60) // 100
    validation_boundary = (2**64 * 80) // 100
    return {
        "train": ordered.loc[hashes < train_boundary].copy(),
        "validation": ordered.loc[
            (hashes >= train_boundary) & (hashes < validation_boundary)
        ].copy(),
        "test": ordered.loc[hashes >= validation_boundary].copy(),
    }


def sample_frame(frame: pd.DataFrame, max_rows: int | None, seed: int = SEED) -> pd.DataFrame:
    """Target-blind hash sample; never take a favorable head slice or claim subset."""
    if max_rows is None:
        return frame.sort_values("IDpol").reset_index(drop=True)
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError("max_rows must be a positive integer")
    hashes = [_policy_hash(pid, seed, "sample") for pid in frame.IDpol]
    ranked = frame.assign(_sample_hash=hashes).sort_values(["_sample_hash", "IDpol"])
    return (
        ranked.head(max_rows)
        .drop(columns="_sample_hash")
        .sort_values("IDpol")
        .reset_index(drop=True)
    )
