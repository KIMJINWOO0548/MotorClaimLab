import pytest

from motorclaimlab import data


def test_arff_stops_after_row_limit_before_materialization(tmp_path, monkeypatch):
    path = tmp_path / "oversized.arff"
    path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(data, "MAX_INPUT_ROWS", 3)
    seen = []

    def rows():
        for i in range(100):
            seen.append(i)
            if i > 3:
                pytest.fail("consumed rows beyond limit+1")
            yield [i] * 12

    def loader(stream, **kwargs):
        assert kwargs.get("return_type") == data.arff.DENSE_GEN
        return {"attributes": [(n, "NUMERIC") for n in data.COLUMNS], "data": rows()}

    monkeypatch.setattr(data.arff, "load", loader)
    with pytest.raises(ValueError, match="row limit"):
        data.load_dataset(path)
    assert len(seen) == 4


def test_arff_rejects_wrong_schema_before_reading_rows(tmp_path, monkeypatch):
    path = tmp_path / "bad.arff"
    path.write_text("placeholder", encoding="utf-8")

    def rows():
        pytest.fail("invalid schema consumed data")
        yield []

    monkeypatch.setattr(
        data.arff, "load", lambda *a, **kw: {"attributes": [("bad", "STRING")], "data": rows()}
    )
    with pytest.raises(ValueError, match="Schema mismatch"):
        data.load_dataset(path)


def test_real_arff_limit_rejects_before_malformed_trailing_row(frame, tmp_path, monkeypatch):
    declarations = [
        f"@ATTRIBUTE '{name}' {'STRING' if name in data.CATEGORICAL else 'NUMERIC'}"
        for name in frame.columns
    ]
    path = tmp_path / "bounded.arff"
    path.write_text(
        "@RELATION bounded\n"
        + "\n".join(declarations)
        + "\n@DATA\n"
        + frame.to_csv(index=False, header=False)
        + "invalid trailing record\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(data, "MAX_INPUT_ROWS", 3)
    with pytest.raises(ValueError, match="row limit"):
        data.load_dataset(path)


def test_real_arff_exact_limit_and_multiple_chunks(frame, tmp_path, monkeypatch):
    import arff
    import pandas as pd

    many = pd.concat([frame.assign(IDpol=frame.IDpol + 6 * i) for i in range(1700)])
    path = tmp_path / "chunks.arff"
    attributes = [
        (name, "STRING" if name in data.CATEGORICAL else "NUMERIC") for name in many.columns
    ]
    path.write_text(
        arff.dumps({"relation": "chunks", "attributes": attributes, "data": many.values.tolist()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(data, "MAX_INPUT_ROWS", 10200)
    restored = data.load_dataset(path)
    assert len(restored) == 10200
    assert restored.IDpol.tolist() == many.IDpol.tolist()
    assert restored.Area.tolist() == many.Area.tolist()
    assert restored.ClaimNb.sum() == many.ClaimNb.sum()
