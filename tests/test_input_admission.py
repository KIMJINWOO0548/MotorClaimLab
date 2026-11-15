"""Resource admission tests use tiny local synthetic files."""

from unittest.mock import patch

import pytest

from motorclaimlab.data import load_dataset, validate_frame


def test_rejects_oversize_csv_before_parser(tmp_path):
    source = tmp_path / "large.csv"
    source.write_bytes(b"x" * 17)
    with (
        patch("motorclaimlab.data.MAX_INPUT_BYTES", 16),
        patch("motorclaimlab.data.pd.read_csv") as parser,
    ):
        with pytest.raises(ValueError, match="size limit"):
            load_dataset(source)
        parser.assert_not_called()
    assert source.read_bytes() == b"x" * 17


def test_rejects_duplicate_columns_explicitly(frame):
    duplicated = frame.iloc[:, [0, *range(len(frame.columns))]]
    with pytest.raises(ValueError, match="Duplicate column"):
        validate_frame(duplicated)
