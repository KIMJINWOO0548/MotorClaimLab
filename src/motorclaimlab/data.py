"""Pinned public source, strict source audit and target-independent partitions."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import stat
from datetime import UTC, datetime
from io import BytesIO, TextIOWrapper
from itertools import islice
from pathlib import Path
from tempfile import TemporaryFile
from typing import BinaryIO
from urllib.request import Request, urlopen

import arff
import numpy as np
import pandas as pd

SEED = 20261101
DATASET_ID = 41214
SOURCE_URL = "https://www.openml.org/data/v1/download/20649148/freMTPL2freq.arff"
SOURCE_MD5 = "f8875568bf0ca622929105197e2db613"
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024
MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_INPUT_ROWS = 1_000_000
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


def _source_signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _capture_source(path: Path, snapshot: BinaryIO) -> dict[str, str]:
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Source must be a regular file")
    if before.st_size > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds 128 MiB size limit")

    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    total = 0
    try:
        with path.open("rb") as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size != before.st_size:
                raise ValueError("Source changed while opening")
            if not os.path.samestat(before, opened):
                if os.name != "nt":
                    raise ValueError("Source changed while opening")
                # Windows filesystems can report different identities for paths and handles.
                with path.open("rb") as current:
                    if not os.path.samestat(opened, os.fstat(current.fileno())):
                        raise ValueError("Source changed while opening")
            while block := source.read(min(1024 * 1024, MAX_INPUT_BYTES - total + 1)):
                total += len(block)
                if total > MAX_INPUT_BYTES:
                    raise ValueError("Input exceeds 128 MiB size limit")
                snapshot.write(block)
                sha256.update(block)
                md5.update(block)
            if total != opened.st_size or _source_signature(os.fstat(source.fileno())) != (
                _source_signature(opened)
            ):
                raise ValueError("Source changed during snapshot acquisition")
        if _source_signature(path.stat()) != _source_signature(before):
            raise ValueError("Source changed during snapshot acquisition")
    except FileNotFoundError as exc:
        raise ValueError("Source changed during snapshot acquisition") from exc

    return {"source_sha256": sha256.hexdigest(), "source_md5": md5.hexdigest()}


def load_source_snapshot(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    """Acquire a private snapshot, then parse only the bytes hashed during acquisition."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".arff"):
        raise ValueError("Input must be a local .csv or .arff file")
    with TemporaryFile(mode="w+b") as snapshot:
        fingerprints = _capture_source(path, snapshot)
        snapshot.seek(0)
        return _parse_source(snapshot, suffix), fingerprints


def load_dataset(path: Path) -> pd.DataFrame:
    """Read local CSV/ARFF without correcting or rewriting source data."""
    frame, _ = load_source_snapshot(path)
    return frame


def _parse_source(snapshot: BinaryIO, suffix: str) -> pd.DataFrame:
    if suffix == ".csv":
        frame = pd.read_csv(snapshot, nrows=MAX_INPUT_ROWS + 1)
    else:
        with TextIOWrapper(snapshot, encoding="utf-8") as stream:
            contents = arff.load(stream, return_type=arff.DENSE_GEN)
            columns = [name for name, _ in contents["attributes"]]
            if len(columns) != len(set(columns)):
                raise ValueError("Duplicate column names are not allowed")
            if set(columns) != set(COLUMNS):
                raise ValueError("Schema mismatch in ARFF header")
            # Consume the lazy parser while the stream remains open. Never
            # materialize all Python row lists as well as the full DataFrame.
            chunks = []
            count = 0
            rows = iter(contents["data"])
            while True:
                batch = list(islice(rows, min(10_000, MAX_INPUT_ROWS - count + 1)))
                if not batch:
                    break
                count += len(batch)
                if count > MAX_INPUT_ROWS:
                    raise ValueError(
                        "Input exceeds 1,000,000 row limit; no rows are silently dropped"
                    )
                chunks.append(pd.DataFrame(batch, columns=columns))
                del batch
            frame = (
                pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
            )
    validate_frame(frame)
    for name in NUMERIC:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    frame["IDpol"] = frame["IDpol"].astype(np.int64)
    frame["ClaimNb"] = frame["ClaimNb"].astype(np.int64)
    return frame


def validate_frame(frame: pd.DataFrame) -> dict:
    """Reject invalid observations, retaining valid unusual source values."""
    if len(frame) > MAX_INPUT_ROWS:
        raise ValueError("Input exceeds 1,000,000 row limit; no rows are silently dropped")
    if not frame.columns.is_unique:
        raise ValueError("Duplicate column names are not allowed")
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
    # Each count has been checked as an exactly representable integer. Keep
    # their sum out of both binary64 rounding and fixed-width integer overflow.
    claims = sum(int(value) for value in numeric["ClaimNb"])
    try:
        exposure = math.fsum(numeric["Exposure"])
    except OverflowError:
        raise ValueError("Exposure total must be finite") from None
    if not math.isfinite(exposure):
        raise ValueError("Exposure total must be finite")
    return {
        "rows": int(len(frame)),
        "columns": len(frame.columns),
        "claims": claims,
        "exposure": exposure,
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
