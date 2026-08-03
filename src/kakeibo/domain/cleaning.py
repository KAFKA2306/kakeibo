import polars as pl


class CleaningPipeline:
    """データクリーニングパイプライン"""

    def process(self, df: pl.DataFrame, source: str) -> pl.DataFrame:
        """
        生のDataFrameを受け取り、クリーンなDataFrameに変換する。

        Args:
            df: 生データ (ParserPort.parseの出力)
            source: データソース名

        Returns:
            クリーンなデータ (Transactionモデルに対応するカラムを持つ)
        """
        df = df.with_columns(
            [pl.col(column).str.strip_chars() for column in df.columns if df.schema[column] == pl.Utf8]
        )
        df = self._parse_amounts(df)
        df = self._parse_dates(df)
        df = df.filter(pl.col("transaction_date").is_not_null())
        df = df.with_columns(pl.lit(source).alias("source"))

        final_columns = [
            "transaction_date",
            "amount",
            "description",
            "balance",
            "memo",
            "source",
        ]
        for column in final_columns:
            if column not in df.columns:
                df = df.with_columns(pl.lit(None).alias(column))
        return df.select(final_columns)

    def _parse_amounts(self, df: pl.DataFrame) -> pl.DataFrame:
        """金額文字列をパースして数値にする。"""

        def clean_num_str(column_name: str) -> pl.Expr:
            return (
                pl.col(column_name)
                .str.replace_all(r"[^0-9\-]", "")
                .cast(pl.Int64, strict=False)
                .fill_null(0)
            )

        if "raw_deposit" in df.columns and "raw_withdrawal" in df.columns:
            expressions = [
                clean_num_str("raw_deposit").alias("deposit_val"),
                clean_num_str("raw_withdrawal").alias("withdrawal_val"),
            ]
            if "raw_balance" in df.columns:
                expressions.append(clean_num_str("raw_balance").alias("balance"))
            df = df.with_columns(expressions)
            df = df.with_columns(
                (pl.col("deposit_val") - pl.col("withdrawal_val")).alias("amount")
            )
        elif "raw_amount" in df.columns:
            expressions = [clean_num_str("raw_amount").alias("amount")]
            if "raw_balance" in df.columns:
                expressions.append(clean_num_str("raw_balance").alias("balance"))
            df = df.with_columns(expressions)

        df = df.with_columns(pl.col("raw_description").alias("description"))
        if "raw_memo" in df.columns:
            df = df.with_columns(pl.col("raw_memo").alias("memo"))
        else:
            df = df.with_columns(pl.lit(None).alias("memo"))
        return df

    def _parse_dates(self, df: pl.DataFrame) -> pl.DataFrame:
        """日付文字列を複数の既知形式からパースする。"""
        date_column = pl.col("raw_date")
        normalized_date = date_column.str.replace(
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            "$1-$2-$3",
        ).str.replace_all("/", "-")

        return df.with_columns(
            pl.coalesce(
                [
                    normalized_date.str.to_date("%Y-%m-%d", strict=False),
                    normalized_date.str.to_date("%Y/%m/%d", strict=False),
                ]
            ).alias("transaction_date")
        )
