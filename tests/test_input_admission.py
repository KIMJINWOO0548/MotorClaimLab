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


def test_csv_row_limit_is_enforced_without_silent_truncation(tmp_path, frame):
    source = tmp_path / "input.csv"
    frame.to_csv(source, index=False)
    with patch("motorclaimlab.data.MAX_INPUT_ROWS", 5):
        with pytest.raises(ValueError, match="row limit"):
            load_dataset(source)
    assert len(load_dataset(source)) == 6


def test_frame_at_row_limit_is_accepted(frame):
    with patch("motorclaimlab.data.MAX_INPUT_ROWS", len(frame)):
        assert validate_frame(frame)["rows"] == len(frame)
