from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.kakeibo.sdk import (
    SCHEMA_VERSION,
    adapter_manifest,
    normalize_statement,
)


def _write_statement(path: Path, encoding: str) -> bytes:
    content = (
        "利用日,利用店名,支払総額\n"
        "2026/08/01,fixture-shop-a,1200\n"
        "2026/08/03,fixture-shop-b,800\n"
    )
    payload = content.encode(encoding)
    path.write_bytes(payload)
    return payload


@pytest.mark.parametrize(
    ("statement_type", "filename", "encoding"),
    [
        ("enavi", "enavi202608(1).csv", "utf-8-sig"),
        ("aplus", "aplus_meisai_1_202608.csv", "utf-8-sig"),
        ("transaction", "transaction-history.csv", "utf-8"),
    ],
)
def test_sdk_normalizes_three_registered_adapters(
    tmp_path: Path,
    statement_type: str,
    filename: str,
    encoding: str,
) -> None:
    path = tmp_path / filename
    payload = _write_statement(path, encoding)

    result = normalize_statement(path, statement_type=statement_type)

    assert result.success is True
    assert result.schema_version == SCHEMA_VERSION
    assert result.reason_code == "OK"
    assert result.statement_type == statement_type
    assert result.input_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.encoding == encoding
    assert result.record_count == 2
    assert result.rejected_count == 0
    assert result.period_start == "2026-08-01"
    assert result.period_end == "2026-08-03"
    assert result.canonical_transactions[0]["description"] == "fixture-shop-a"
    assert set(result.canonical_transactions[0]) == {
        "transaction_date",
        "amount",
        "description",
        "balance",
        "memo",
        "source",
    }


def test_sdk_manifest_reuses_statement_registry() -> None:
    manifest = {entry.statement_type: entry for entry in adapter_manifest()}

    assert {"sony", "enavi", "aplus", "transaction", "generic"} <= set(
        manifest
    )
    assert manifest["transaction"].suffixes == (".csv",)
    assert manifest["sony"].encoding == "utf-8-sig"


def test_sdk_returns_structured_contract_errors(tmp_path: Path) -> None:
    csv_path = tmp_path / "statement.csv"
    _write_statement(csv_path, "utf-8")

    unknown = normalize_statement(csv_path, statement_type="not-a-bank")
    assert unknown.success is False
    assert unknown.reason_code == "UNKNOWN_STATEMENT_TYPE"

    wrong_suffix = tmp_path / "statement.txt"
    wrong_suffix.write_text("fixture", encoding="utf-8")
    mismatch = normalize_statement(wrong_suffix, statement_type="transaction")
    assert mismatch.success is False
    assert mismatch.reason_code == "SUFFIX_MISMATCH"

    malformed = tmp_path / "transaction-history.csv"
    malformed.write_bytes(b"\xff\xfe\x00\x00")
    parse_failure = normalize_statement(malformed, statement_type="transaction")
    assert parse_failure.success is False
    assert parse_failure.reason_code == "PARSE_FAILED"


def test_sdk_missing_input_does_not_echo_local_path(tmp_path: Path) -> None:
    missing = tmp_path / "account-1234-secret.csv"

    result = normalize_statement(missing, statement_type="transaction")
    serialized = str(result.to_dict())

    assert result.reason_code == "INPUT_NOT_FOUND"
    assert str(missing) not in serialized
    assert "account-1234-secret" not in serialized
