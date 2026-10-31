"""Catch corrupt source values and target/order-dependent partitions."""

import gzip
import hashlib
import io

import numpy as np
import pandas as pd
import pytest

from motorclaimlab import data
from motorclaimlab.data import load_dataset, sample_frame, split_frame, validate_frame


@pytest.mark.parametrize(
    "column,value",
    [
        ("Exposure", 0),
        ("Exposure", -1),
        ("Exposure", np.inf),
        ("ClaimNb", -1),
        ("ClaimNb", 0.5),
        ("ClaimNb", np.nan),
        ("Density", 0),
        ("DrivAge", -1),
        ("IDpol", 1.5),
        ("VehBrand", ""),
        ("Area", None),
    ],
)
def test_invalid_source_values_are_rejected(frame, column, value):
    bad = frame.copy()
    bad[column] = bad[column].astype(object)
    bad.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        validate_frame(bad)


def test_duplicate_policies_and_missing_fields_stop_audit(frame):
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="IDpol"):
        validate_frame(duplicate)
    with pytest.raises(ValueError, match="Exposure"):
        validate_frame(frame.drop(columns="Exposure"))


def test_valid_extremes_are_audited_without_clipping(frame):
    frame.loc[0, "Exposure"] = 2
    frame.loc[0, "ClaimNb"] = 7
    audit = validate_frame(frame)
    assert audit["rows"] == 6
    assert audit["exposure_gt_one"] == 1
    assert audit["claims_gt_four"] == 1
    assert frame.loc[0, "Exposure"] == 2
    assert frame.loc[0, "ClaimNb"] == 7


def test_split_membership_is_independent_of_order_and_targets(frame):
    many = pd.concat([frame.assign(IDpol=frame.IDpol + 6 * i) for i in range(50)])
    parts = split_frame(many)
    altered = many.sample(frac=1, random_state=7).assign(ClaimNb=100)
    again = split_frame(altered)
    memberships = {k: set(v.IDpol) for k, v in parts.items()}
    assert set(memberships) == {"train", "validation", "test"}
    assert set.union(*memberships.values()) == set(range(1, 301))
    assert memberships["train"].isdisjoint(memberships["validation"])
    assert memberships["train"].isdisjoint(memberships["test"])
    assert memberships["validation"].isdisjoint(memberships["test"])
    assert all(memberships[k] == set(again[k].IDpol) for k in memberships)
    assert all(len(v) > 25 for v in parts.values())


def test_sampling_is_bounded_seeded_and_target_independent(frame):
    chosen = sample_frame(frame, 3, seed=17)
    other = sample_frame(frame.iloc[::-1].assign(ClaimNb=99), 3, seed=17)
    assert len(chosen) == 3
    assert list(chosen.IDpol) == list(other.IDpol)
    with pytest.raises(ValueError):
        sample_frame(frame, 0)


def test_csv_and_arff_are_loaded_without_mutating_source(frame, tmp_path):
    csv = tmp_path / "synthetic.csv"
    frame.to_csv(csv, index=False)
    before = hashlib.sha256(csv.read_bytes()).hexdigest()
    loaded = load_dataset(csv)
    assert loaded.ClaimNb.sum() == 4
    assert loaded.Exposure.sum() == 4
    assert hashlib.sha256(csv.read_bytes()).hexdigest() == before
    declarations = []
    for name in frame.columns:
        choices = ",".join(sorted(set(frame[name].astype(str))))
        kind = (
            "NUMERIC"
            if name not in {"Area", "VehBrand", "VehGas", "Region"}
            else "{" + choices + "}"
        )
        declarations.append(f"@ATTRIBUTE {name} {kind}")
    arff = tmp_path / "synthetic.arff"
    arff.write_text(
        "@RELATION synthetic\n"
        + "\n".join(declarations)
        + "\n@DATA\n"
        + frame.to_csv(index=False, header=False),
        encoding="utf-8",
    )
    restored = load_dataset(arff)
    assert restored.Area.tolist() == ["A", "B", "A", "C", "B", "C"]
    assert restored.ClaimNb.sum() == 4


def test_arff_string_attributes_are_supported(frame, tmp_path):
    declarations = [
        f"@ATTRIBUTE '{name}' {'STRING' if name in data.CATEGORICAL else 'NUMERIC'}"
        for name in frame.columns
    ]
    path = tmp_path / "strings.arff"
    path.write_text(
        "@RELATION strings\n"
        + "\n".join(declarations)
        + "\n@DATA\n"
        + frame.to_csv(index=False, header=False),
        encoding="utf-8",
    )
    result = load_dataset(path)
    assert result.Area.tolist() == ["A", "B", "A", "C", "B", "C"]
    assert result.ClaimNb.sum() == 4


def test_empty_data_is_rejected(frame):
    with pytest.raises(ValueError, match="empty"):
        validate_frame(frame.iloc[:0])


def test_fetch_rejects_corrupt_bytes_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: io.BytesIO(b"corrupt"))
    target = tmp_path / "raw"
    with pytest.raises(ValueError, match="MD5"):
        data.fetch_dataset(target)
    assert not target.exists()


def test_fetch_checks_identity_records_hash_and_refuses_overwrite(tmp_path, monkeypatch):
    content = b"synthetic unit test download, not insurance records"
    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: io.BytesIO(content))
    monkeypatch.setattr(data, "SOURCE_MD5", hashlib.md5(content).hexdigest())
    path = data.fetch_dataset(tmp_path / "raw")
    assert path.read_bytes() == content


def test_fetch_verifies_decoded_gzip_source_bytes(tmp_path, monkeypatch):
    content = b"synthetic gzip transport; not insurance records"

    class Response(io.BytesIO):
        headers = {"Content-Encoding": "gzip"}

    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: Response(gzip.compress(content)))
    monkeypatch.setattr(data, "SOURCE_MD5", hashlib.md5(content).hexdigest())
    path = data.fetch_dataset(tmp_path / "raw")
    assert path.read_bytes() == content
    import json

    descriptor = json.loads((path.parent / "source.json").read_text())
    assert descriptor["sha256"] == hashlib.sha256(content).hexdigest()
    with pytest.raises(FileExistsError):
        data.fetch_dataset(path.parent)
    assert path.read_bytes() == content
