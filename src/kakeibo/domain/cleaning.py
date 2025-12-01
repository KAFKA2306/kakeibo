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

        # 1. 基本的な正規化 (空白除去など)
        df = df.with_columns(
            [pl.col(c).str.strip_chars() for c in df.columns if df.schema[c] == pl.Utf8]
        )

        # 2. 金額のパース
        # 入金と出金を数値に変換し、amount (入金 - 出金) を計算
        df = self._parse_amounts(df)

        # 3. 日付のパース
        df = self._parse_dates(df)

        # 4. バリデーションとフィルタリング
        df = df.filter(pl.col("transaction_date").is_not_null())

        # 5. ソース列の追加
        df = df.with_columns(pl.lit(source).alias("source"))

        # 6. カラムの選択とリネーム
        final_cols = [
            "transaction_date",
            "amount",
            "description",
            "balance",
            "memo",
            "source",
        ]

        # 存在しないカラムがあればnullで埋める
        for col in final_cols:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select(final_cols)

    def _parse_amounts(self, df: pl.DataFrame) -> pl.DataFrame:
        """金額文字列をパースして数値にする"""

        def clean_num_str(col_name):
            # カンマと円マークを除去し、数値に変換できる文字のみ残す（マイナスは保持）
            return (
                pl.col(col_name)
                .str.replace_all(r"[^0-9\-]", "")  # 数字とマイナス以外を削除
                .cast(pl.Int64, strict=False)
                .fill_null(0)
            )

        # raw_deposit, raw_withdrawal がある場合
        if "raw_deposit" in df.columns and "raw_withdrawal" in df.columns:
            df = df.with_columns(
                [
                    clean_num_str("raw_deposit").alias("deposit_val"),
                    clean_num_str("raw_withdrawal").alias("withdrawal_val"),
                    clean_num_str("raw_balance").alias("balance"),
                ]
            )

            # amount = deposit - withdrawal (withdrawalが正の値で入っている前提)
            # もしwithdrawalが既にマイナスで入っているケースがあれば調整が必要だが、
            # 通常、CSVの出金列は正の値で表現されることが多い。
            # ここでは "出金" 列の値を引く形にする。

            df = df.with_columns(
                (pl.col("deposit_val") - pl.col("withdrawal_val")).alias("amount")
            )

        # raw_amount がある場合 (未実装だが将来用)
        elif "raw_amount" in df.columns:
            df = df.with_columns(
                [
                    clean_num_str("raw_amount").alias("amount"),
                    clean_num_str("raw_balance").alias("balance"),
                ]
            )

        # description (摘要) のリネーム
        df = df.with_columns(pl.col("raw_description").alias("description"))
        if "raw_memo" in df.columns:
            df = df.with_columns(pl.col("raw_memo").alias("memo"))
        else:
            df = df.with_columns(pl.lit(None).alias("memo"))

        return df

    def _parse_dates(self, df: pl.DataFrame) -> pl.DataFrame:
        """日付文字列をパースする"""
        # 様々なフォーマットに対応するためのロジック
        # Polarsのstrptimeは1つのフォーマットしか指定できないため、
        # 複数のフォーマットを試すか、正規表現で統一フォーマットに変換してからパースする。

        # ここでは、よくある "YYYY年MM月DD日", "YYYY/MM/DD", "YYYY-MM-DD" を処理する
        # まずは "/" や "-" に統一してしまうのが楽。

        date_col = pl.col("raw_date")

        # "YYYY年MM月DD日" -> "YYYY-MM-DD"
        normalized_date = date_col.str.replace(
            r"(\d{4})年(\d{1,2})月(\d{1,2})日", "$1-$2-$3"
        ).str.replace_all("/", "-")

        # パース実行
        # フォーマットが混在していると厄介だが、1つのファイル内では統一されていると仮定
        # しかし、ファイルによって違うので、try_strptime を使うのが良いが、Polarsにはそのものズバリはない。
        # str.to_date で strict=False にして、失敗したら別のフォーマットを試すcoalesceを使う。

        df = df.with_columns(
            pl.coalesce(
                [
                    normalized_date.str.to_date("%Y-%m-%d", strict=False),
                    normalized_date.str.to_date("%Y/%m/%d", strict=False),
                    # 他のフォーマットがあれば追加
                ]
            ).alias("transaction_date")
        )

        return df
