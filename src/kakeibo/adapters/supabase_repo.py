import os

from loguru import logger

from src.kakeibo.domain.models import Transaction
from src.kakeibo.ports.repository import TransactionRepositoryPort


class SupabaseRepository(TransactionRepositoryPort):
    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        self.client = None

        if self.url and self.key:
            try:
                from supabase import create_client

                self.client = create_client(self.url, self.key)
            except ImportError:
                logger.warning("Supabase integration is unavailable")
        else:
            logger.info("Supabase integration is disabled")

    def save_bulk(self, transactions: list[Transaction]) -> int:
        if not self.client:
            logger.warning("Supabase client is not initialized")
            return 0

        if not transactions:
            return 0

        data = [transaction.model_dump(mode="json") for transaction in transactions]

        try:
            response = self.client.table("transactions").upsert(data).execute()
            count = len(response.data) if response.data else 0
            logger.info("Saved {} transactions to Supabase", count)
            return count
        except Exception as exc:
            logger.error("Supabase write failed error_type={}", type(exc).__name__)
            return 0
