import re
from pathlib import Path

import polars as pl

from src.kakeibo.ports.parser import ParserPort

SonyRow = dict[str, str | None]


class SonyBankParser(ParserPort):
    def parse(self, file_path: Path, encoding: str) -> pl.DataFrame:
        with file_path.open(encoding=encoding) as source:
            text = source.read()

        rows: list[SonyRow] = []
        for raw_line in text.strip().split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if not re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", line):
                continue
            row = self._parse_line(line)
            if row:
                rows.append(row)

        schema = {
            "raw_date": pl.Utf8,
            "raw_deposit": pl.Utf8,
            "raw_withdrawal": pl.Utf8,
            "raw_description": pl.Utf8,
            "raw_balance": pl.Utf8,
            "raw_memo": pl.Utf8,
        }
        if not rows:
            return pl.DataFrame(schema=schema)
        return pl.DataFrame(rows, schema=schema, orient="row")

    def _parse_line(self, line: str) -> SonyRow:
        """1行を解析して正規化前の項目辞書を返す。"""
        remaining = line.strip()
        result: SonyRow = {
            "raw_date": None,
            "raw_deposit": None,
            "raw_withdrawal": None,
            "raw_description": None,
            "raw_balance": None,
            "raw_memo": None,
        }

        date_match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", remaining)
        if date_match:
            result["raw_date"] = date_match.group(1)
            remaining = remaining[date_match.end() :].strip()

        balance_match = re.search(r"([0-9,]+円)\s*$", remaining)
        if balance_match:
            result["raw_balance"] = balance_match.group(1)
            remaining = remaining[: balance_match.start()].strip()

        amount_match = re.search(r"([0-9,]+円)", remaining)
        if amount_match:
            amount = amount_match.group(1)
            result["raw_description"] = remaining[amount_match.end() :].strip()
            prefix = remaining[: amount_match.start()].strip()
            if "入金" in prefix or len(prefix) >= 8:
                result["raw_deposit"] = amount
            else:
                result["raw_withdrawal"] = amount
        else:
            result["raw_description"] = remaining

        return result
