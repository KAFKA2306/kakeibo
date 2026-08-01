from pathlib import Path

import pytest

from src.kakeibo.security import (
    UnsafeUploadName,
    classify_input_name,
    opaque_file_id,
    private_output_name,
    validate_upload_suffix,
)


def test_upload_suffix_accepts_supported_type() -> None:
    assert validate_upload_suffix(".CSV", (".csv", ".txt")) == ".csv"


@pytest.mark.parametrize("suffix", ["csv", ".exe", "../.csv", None])
def test_upload_suffix_rejects_unsafe_type(suffix: str | None) -> None:
    with pytest.raises(UnsafeUploadName):
        validate_upload_suffix(suffix, (".csv", ".txt"))


def test_private_names_do_not_expose_input_name() -> None:
    source = Path("my-bank-account-1234.csv")
    assert "my-bank" not in private_output_name()
    assert opaque_file_id(source) != source.name


def test_anonymous_upload_names_still_select_a_parser() -> None:
    patterns = {"transaction": r"transaction-history\.csv$"}
    assert classify_input_name("upload.csv", patterns) == "generic"
    assert classify_input_name("upload.txt", patterns) == "sony"
    assert classify_input_name("upload.exe", patterns) is None
