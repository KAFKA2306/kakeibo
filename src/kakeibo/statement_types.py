from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.kakeibo.adapters.parsers.generic_csv import GenericCsvParser
from src.kakeibo.adapters.parsers.profiled_csv import (
    AplusCsvParser,
    EnaviCsvParser,
    TransactionHistoryCsvParser,
)
from src.kakeibo.adapters.parsers.sony import SonyBankParser
from src.kakeibo.ports.parser import ParserPort


class StatementTypeError(ValueError):
    """Base class for statement contract violations."""


class UnknownStatementType(StatementTypeError):
    """Raised when a caller names a source type outside the public registry."""


class InvalidStatementSuffix(StatementTypeError):
    """Raised when a source type and file suffix are incompatible."""


@dataclass(frozen=True)
class StatementTypeSpec:
    name: str
    allowed_suffixes: tuple[str, ...]
    encoding: str
    filename_pattern: re.Pattern[str] | None
    parser_factory: Callable[[], ParserPort]


STATEMENT_TYPES: dict[str, StatementTypeSpec] = {
    "sony": StatementTypeSpec(
        name="sony",
        allowed_suffixes=(".txt",),
        encoding="utf-8-sig",
        filename_pattern=re.compile(r"sony_.*\.txt$", re.IGNORECASE),
        parser_factory=SonyBankParser,
    ),
    "enavi": StatementTypeSpec(
        name="enavi",
        allowed_suffixes=(".csv",),
        encoding="utf-8-sig",
        filename_pattern=re.compile(r"enavi\d{6}\(\d+\)\.csv$", re.IGNORECASE),
        parser_factory=EnaviCsvParser,
    ),
    "aplus": StatementTypeSpec(
        name="aplus",
        allowed_suffixes=(".csv",),
        encoding="utf-8-sig",
        filename_pattern=re.compile(r"aplus_meisai_\d+_\d{6}\.csv$", re.IGNORECASE),
        parser_factory=AplusCsvParser,
    ),
    "transaction": StatementTypeSpec(
        name="transaction",
        allowed_suffixes=(".csv",),
        encoding="utf-8",
        filename_pattern=re.compile(r"transaction-history\.csv$", re.IGNORECASE),
        parser_factory=TransactionHistoryCsvParser,
    ),
    "generic": StatementTypeSpec(
        name="generic",
        allowed_suffixes=(".csv",),
        encoding="shift_jis",
        filename_pattern=re.compile(r"\d{6}\.csv$", re.IGNORECASE),
        parser_factory=GenericCsvParser,
    ),
}


def normalize_statement_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in STATEMENT_TYPES:
        raise UnknownStatementType("unsupported statement type")
    return normalized


def normalize_suffix(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", normalized):
        raise InvalidStatementSuffix("unsupported statement suffix")
    return normalized


def statement_spec(statement_type: str | None, suffix: str | None) -> StatementTypeSpec:
    normalized_type = normalize_statement_type(statement_type)
    normalized_suffix = normalize_suffix(suffix)
    spec = STATEMENT_TYPES[normalized_type]
    if normalized_suffix not in spec.allowed_suffixes:
        raise InvalidStatementSuffix("statement type and suffix are incompatible")
    return spec


def infer_statement_type(filename: str) -> str | None:
    """Infer a local CLI source type without exposing the filename externally."""
    basename = Path(filename).name
    for name, spec in STATEMENT_TYPES.items():
        if spec.filename_pattern and spec.filename_pattern.search(basename):
            return name
    if Path(basename).suffix.lower() == ".csv":
        return "generic"
    return None


def build_parser_registry() -> dict[str, ParserPort]:
    return {name: spec.parser_factory() for name, spec in STATEMENT_TYPES.items()}
