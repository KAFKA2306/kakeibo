from __future__ import annotations

from pathlib import Path

import polars as pl

from src.kakeibo.adapters.parsers.generic_csv import GenericCsvParser


class EnaviCsvParser(GenericCsvParser):
    """Explicit parser profile for Rakuten e-NAVI exports."""


class AplusCsvParser(GenericCsvParser):
    """Explicit parser profile for APLUS statement exports."""


class TransactionHistoryCsvParser(GenericCsvParser):
    """Explicit parser profile for UTF-8 transaction-history exports."""

    def parse(self, file_path: Path, encoding: str) -> pl.DataFrame:
        if encoding.lower().replace("_", "-") not in {"utf-8", "utf-8-sig"}:
            raise ValueError("transaction history requires UTF-8 encoding")
        return super().parse(file_path, encoding)
