from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from src.kakeibo.domain.cleaning import CleaningPipeline
from src.kakeibo.statement_types import (
    STATEMENT_TYPES,
    InvalidStatementSuffix,
    StatementTypeError,
    UnknownStatementType,
    statement_spec,
)

SCHEMA_VERSION = "kakeibo-normalization/v1"
PARSER_VERSION = "statement-registry/v1"
CANONICAL_COLUMNS = (
    "transaction_date",
    "amount",
    "description",
    "balance",
    "memo",
    "source",
)

ReasonCode = Literal[
    "OK",
    "UNKNOWN_STATEMENT_TYPE",
    "SUFFIX_MISMATCH",
    "INPUT_NOT_FOUND",
    "PARSE_FAILED",
    "SCHEMA_MISMATCH",
]


@dataclass(frozen=True)
class AdapterCapability:
    statement_type: str
    suffixes: tuple[str, ...]
    encoding: str
    parser: str


@dataclass(frozen=True)
class NormalizationResult:
    schema_version: str
    parser_version: str
    success: bool
    reason_code: ReasonCode
    statement_type: str | None
    input_sha256: str | None
    encoding: str | None
    record_count: int
    rejected_count: int
    period_start: str | None
    period_end: str | None
    canonical_transactions: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def adapter_manifest() -> tuple[AdapterCapability, ...]:
    """Return the public, versioned adapter capabilities without input data."""
    return tuple(
        AdapterCapability(
            statement_type=name,
            suffixes=spec.allowed_suffixes,
            encoding=spec.encoding,
            parser=spec.parser_factory.__name__,
        )
        for name, spec in sorted(STATEMENT_TYPES.items())
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _failure(
    reason_code: ReasonCode,
    *,
    statement_type: str | None = None,
    input_sha256: str | None = None,
    encoding: str | None = None,
) -> NormalizationResult:
    return NormalizationResult(
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        success=False,
        reason_code=reason_code,
        statement_type=statement_type,
        input_sha256=input_sha256,
        encoding=encoding,
        record_count=0,
        rejected_count=0,
        period_start=None,
        period_end=None,
        canonical_transactions=(),
    )


def normalize_statement(
    file_path: str | Path,
    *,
    statement_type: str,
) -> NormalizationResult:
    """Normalize one local statement without CLI/API startup or external telemetry.

    The return value contains only canonical transaction fields and processing
    metadata. The local path, raw rows, account/card identifiers, and tokens are
    never included in the result.
    """
    path = Path(file_path)
    if not path.is_file():
        return _failure("INPUT_NOT_FOUND", statement_type=statement_type)

    input_sha256 = _sha256(path)
    try:
        spec = statement_spec(statement_type, path.suffix)
    except UnknownStatementType:
        return _failure("UNKNOWN_STATEMENT_TYPE", input_sha256=input_sha256)
    except InvalidStatementSuffix:
        return _failure(
            "SUFFIX_MISMATCH",
            statement_type=statement_type.strip().lower() or None,
            input_sha256=input_sha256,
        )

    try:
        raw = spec.parser_factory().parse(path, encoding=spec.encoding)
        cleaned = CleaningPipeline().process(raw, source=spec.name)
    except StatementTypeError:
        raise
    except Exception:
        return _failure(
            "PARSE_FAILED",
            statement_type=spec.name,
            input_sha256=input_sha256,
            encoding=spec.encoding,
        )

    if tuple(cleaned.columns) != CANONICAL_COLUMNS:
        return _failure(
            "SCHEMA_MISMATCH",
            statement_type=spec.name,
            input_sha256=input_sha256,
            encoding=spec.encoding,
        )

    transactions = tuple(
        {key: _iso(value) for key, value in row.items()}
        for row in cleaned.to_dicts()
    )
    dates = [
        row["transaction_date"]
        for row in transactions
        if row["transaction_date"]
    ]
    rejected_count = max(raw.height - cleaned.height, 0)

    return NormalizationResult(
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        success=True,
        reason_code="OK",
        statement_type=spec.name,
        input_sha256=input_sha256,
        encoding=spec.encoding,
        record_count=len(transactions),
        rejected_count=rejected_count,
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        canonical_transactions=transactions,
    )
