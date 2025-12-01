import re
from pathlib import Path

import polars as pl

from src.kakeibo.ports.parser import ParserPort


class SonyBankParser(ParserPort):
    def parse(self, file_path: Path, encoding: str) -> pl.DataFrame:
        with open(file_path, encoding=encoding) as f:
            text = f.read()

        lines = text.strip().split("\n")
        # ヘッダー行 (1行目) をスキップして処理

        # Sony銀行のCSV/TXTは形式が特殊な場合があるので、既存ロジックを参考に
        # 正規表現ベースで抽出してリスト化し、Polars DataFrameを作るアプローチをとる

        data = []
        # 空行をスキップしつつ、データ行を処理
        # 元のロジックでは lines[1:] としているが、テストデータによっては1行目からデータの場合もある
        # ここでは空行でない行を全て対象にするが、日付が含まれているかチェックする

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 日付が含まれていない行はヘッダーか無効行とみなしてスキップ
            if not re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", line):
                continue

            row = self._parse_line(line)
            if row:
                data.append(row)

        # DataFrame作成
        schema = {
            "raw_date": pl.Utf8,
            "raw_deposit": pl.Utf8,
            "raw_withdrawal": pl.Utf8,
            "raw_description": pl.Utf8,
            "raw_balance": pl.Utf8,
            "raw_memo": pl.Utf8,
        }

        if not data:
            return pl.DataFrame(schema=schema)

        return pl.DataFrame(data, schema=schema, orient="row")

    def _parse_line(self, line: str) -> dict:
        """1行を解析して辞書を返す"""
        line = line.strip()

        # 結果格納用
        result = {
            "raw_date": None,
            "raw_deposit": None,
            "raw_withdrawal": None,
            "raw_description": None,
            "raw_balance": None,
            "raw_memo": None,
        }

        # 日付
        date_match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", line)
        if date_match:
            result["raw_date"] = date_match.group(1)
            line = line[date_match.end() :].strip()

        # 残高 (末尾)
        balance_match = re.search(r"([0-9,]+円)\s*$", line)
        if balance_match:
            result["raw_balance"] = balance_match.group(1)
            line = line[: balance_match.start()].strip()

        # 入出金と摘要
        # "1,000円" のような金額パターンを探す
        amount_match = re.search(r"([0-9,]+円)", line)
        if amount_match:
            amount_str = amount_match.group(1)

            # 金額より後ろは摘要
            result["raw_description"] = line[amount_match.end() :].strip()

            # 金額より前が入金か出金かの判定材料
            prefix = line[: amount_match.start()].strip()

            # "入金"という文字がある、またはprefixが長い場合は入金とみなす(既存ロジック踏襲)
            if "入金" in prefix or len(prefix) >= 8:
                result["raw_deposit"] = amount_str
            else:
                result["raw_withdrawal"] = amount_str
        else:
            # 金額なし＝全額摘要？（通常ありえないが）
            result["raw_description"] = line

        return result
