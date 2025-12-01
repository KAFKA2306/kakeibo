from abc import ABC, abstractmethod

from src.kakeibo.domain.models import Transaction


class TransactionRepositoryPort(ABC):
    """取引データ保存用リポジトリのインターフェース"""

    @abstractmethod
    def save_bulk(self, transactions: list[Transaction]) -> int:
        """
        複数の取引データを保存する。

        Args:
            transactions: 保存する取引データのリスト

        Returns:
            保存に成功した件数
        """
        pass
