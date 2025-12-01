from abc import ABC, abstractmethod
from pathlib import Path
import polars as pl

class ParserPort(ABC):
    """ファイルパーサーのインターフェース"""

    @abstractmethod
    def parse(self, file_path: Path, encoding: str) -> pl.DataFrame:
        """
        ファイルを読み込み、未加工のDataFrameを返す。

        期待される出力カラム:
        - raw_date: str
        - raw_deposit: str (nullable)
        - raw_withdrawal: str (nullable)
        - raw_description: str
        - raw_balance: str (nullable)
        - raw_memo: str (nullable)
        """
        pass
