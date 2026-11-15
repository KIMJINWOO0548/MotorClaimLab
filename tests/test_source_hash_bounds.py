from pathlib import Path

import pytest

from motorclaimlab import data, experiment


def test_source_hash_rejects_oversize_before_open(tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    source.write_bytes(b"x" * 33)
    monkeypatch.setattr(data, "MAX_INPUT_BYTES", 32)
    original_open = Path.open

    def checked_open(path, *args, **kwargs):
        if path == source:
            pytest.fail("oversized source was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    with pytest.raises(ValueError, match="size limit"):
        experiment._source_fingerprints(source)


def test_source_hash_enforces_limit_during_read(tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    source.write_bytes(b"x" * 20)
    monkeypatch.setattr(data, "MAX_INPUT_BYTES", 32)
    original_open = Path.open

    def growing_open(path, *args, **kwargs):
        if path == source and args == ("rb",):
            with original_open(path, "ab") as writer:
                writer.write(b"y" * 20)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", growing_open)
    with pytest.raises(ValueError, match="size limit|changed"):
        experiment._source_fingerprints(source)


def test_source_hash_regular_bytes_preserves_both_digests(tmp_path):
    import hashlib

    source = tmp_path / "source.csv"
    raw = b"IDpol,ClaimNb\n1,0\n"
    source.write_bytes(raw)
    assert experiment._source_fingerprints(source) == {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_md5": hashlib.md5(raw, usedforsecurity=False).hexdigest(),
    }


def test_growth_after_open_stops_at_limit_plus_one(tmp_path, monkeypatch):
    source = tmp_path / "growing.csv"
    source.write_bytes(b"x" * 20)
    monkeypatch.setattr(data, "MAX_INPUT_BYTES", 32)
    original_open = Path.open
    reads = []

    class GrowingReader:
        def __init__(self, stream):
            self.stream = stream
            self.grown = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            reads.append(size)
            if not self.grown:
                self.grown = True
                with original_open(source, "ab") as writer:
                    writer.write(b"y" * 100)
            return self.stream.read(size)

    def open_source(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return GrowingReader(stream) if path == source and args == ("rb",) else stream

    monkeypatch.setattr(Path, "open", open_source)
    with pytest.raises(ValueError, match="size limit"):
        experiment._source_fingerprints(source)
    assert reads == [33]


def test_same_size_mutation_during_hash_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "changing.csv"
    source.write_bytes(b"old")
    original_md5 = experiment.hashlib.md5

    class ChangingDigest:
        def __init__(self, inner):
            self.inner = inner

        def update(self, block):
            self.inner.update(block)
            source.write_bytes(b"new")
            import os

            info = source.stat()
            os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(
        experiment.hashlib, "md5", lambda *a, **kw: ChangingDigest(original_md5(*a, **kw))
    )
    with pytest.raises(ValueError, match="changed"):
        experiment._source_fingerprints(source)


def test_stable_path_and_descriptor_metadata_need_not_share_identity(tmp_path, monkeypatch):
    from types import SimpleNamespace

    source = tmp_path / "stable.csv"
    source.write_bytes(b"stable")
    original_fstat = experiment.os.fstat

    def descriptor_stat(fd):
        value = original_fstat(fd)
        return SimpleNamespace(
            st_dev=value.st_dev + 1,
            st_ino=value.st_ino + 1,
            st_size=value.st_size,
            st_mtime_ns=value.st_mtime_ns,
            st_ctime_ns=value.st_ctime_ns,
        )

    monkeypatch.setattr(experiment.os, "fstat", descriptor_stat)
    assert experiment._source_fingerprints(source)["source_sha256"]
