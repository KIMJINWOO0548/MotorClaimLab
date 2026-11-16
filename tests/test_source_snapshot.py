import hashlib
import os
from pathlib import Path

import pandas as pd
import pytest

from motorclaimlab import data


def test_parser_uses_captured_bytes_after_source_changes(frame, tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    original = frame.to_csv(index=False).encode()
    source.write_bytes(original)
    read_csv = pd.read_csv

    def change_source_then_parse(stream, **kwargs):
        frame.assign(ClaimNb=0).to_csv(source, index=False)
        return read_csv(stream, **kwargs)

    monkeypatch.setattr(data.pd, "read_csv", change_source_then_parse)
    loaded, fingerprints = data.load_source_snapshot(source)

    assert loaded.ClaimNb.tolist() == frame.ClaimNb.tolist()
    assert fingerprints == {
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_md5": hashlib.md5(original, usedforsecurity=False).hexdigest(),
    }


@pytest.mark.parametrize("change", ["overwrite", "truncate", "replace", "transient_replace"])
def test_snapshot_rejects_source_changes_during_acquisition(change, frame, tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    frame.to_csv(source, index=False)
    original = source.read_bytes()
    initial = source.stat()
    os.utime(source, ns=(initial.st_atime_ns, initial.st_mtime_ns - 10_000_000_000))
    original_open = Path.open

    class ChangingReader:
        def __init__(self, stream):
            self.stream = stream
            self.changed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()
            if change == "replace":
                replacement = source.with_name("replacement.csv")
                replacement.write_bytes(original)
                replacement.replace(source)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            if not self.changed:
                self.changed = True
                first = self.stream.read(12)
                if change == "truncate":
                    with original_open(source, "r+b") as writer:
                        writer.truncate(12)
                elif change == "overwrite":
                    with original_open(source, "r+b") as writer:
                        writer.seek(12)
                        writer.write(b"?")
                return first
            return self.stream.read(size)

    redirected = False

    def open_source(path, *args, **kwargs):
        nonlocal redirected
        if path == source and args == ("rb",):
            if change == "transient_replace" and not redirected:
                redirected = True
                other = source.with_name("other.csv")
                other.write_bytes(original)
                return original_open(other, *args, **kwargs)
            return ChangingReader(original_open(path, *args, **kwargs))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_source)
    with pytest.raises(ValueError, match="changed"):
        data.load_source_snapshot(source)
