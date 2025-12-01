import polars as pl
from pathlib import Path
from src.kakeibo.ports.parser import ParserPort

class GenericCsvParser(ParserPort):
    def parse(self, file_path: Path, encoding: str) -> pl.DataFrame:
        """
        一般的なCSVをパースする。
        ヘッダーが含まれていることを前提とし、カラム名マッピングを行う。
        """
        # PolarsでCSV読み込み
        try:
            df = pl.read_csv(file_path, encoding=encoding, has_header=True, infer_schema_length=0)
        except Exception:
            # 失敗時はスキップ行数を変えるなどのリトライが必要かもしれないが、一旦シンプルに
            # 読み込みエラーの場合は空DFを返すかエラーを上げる
            raise

        # カラム名の正規化 (スペース除去など)
        df = df.rename({col: col.strip() for col in df.columns})

        # 必要なカラムが存在するかチェックし、マッピング
        # ここでは一般的なカラム名を想定
        column_mapping = {}

        # 利用日/日付
        for col in ["利用日", "日付", "年月日", "Date"]:
            if col in df.columns:
                column_mapping[col] = "raw_date"
                break

        # 利用店名/摘要
        for col in ["利用店名・商品名", "利用店名", "摘要", "内容", "Description"]:
            if col in df.columns:
                column_mapping[col] = "raw_description"
                break

        # 支払総額/金額
        # 入金・出金が分かれている場合と、符号付きの場合がある

        # 支払金額(出金)
        for col in ["支払総額", "支払金額", "出金", "Amount"]:
            if col in df.columns:
                 # ここは "raw_withdrawal" か "raw_amount" か迷うが、
                 # genericな場合、まずは raw_amount に入れて pipeline で処理分けするか、
                 # ここで分岐する。
                 # とりあえず raw_withdrawal 扱いにしておく (クレジットカード明細は基本出金のみなので)
                 column_mapping[col] = "raw_withdrawal"
                 break

        # もしマッピングできればリネーム、なければ null列を追加
        df = df.rename(column_mapping)

        expected_cols = ["raw_date", "raw_deposit", "raw_withdrawal", "raw_description", "raw_balance", "raw_memo"]

        for col in expected_cols:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))

        return df.select(expected_cols)
