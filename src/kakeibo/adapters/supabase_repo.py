import os

from loguru import logger

from src.kakeibo.domain.models import Transaction
from src.kakeibo.ports.repository import TransactionRepositoryPort


class SupabaseRepository(TransactionRepositoryPort):
    def __init__(self, url: str | None = None, key: str | None = None):
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        self.client = None

        if self.url and self.key:
            try:
                from supabase import create_client

                self.client = create_client(self.url, self.key)
            except ImportError:
                logger.warning(
                    "supabase-py not installed. Supabase integration disabled."
                )
        else:
            logger.info("Supabase credentials not found. Skipping connection.")

    def save_bulk(self, transactions: list[Transaction]) -> int:
        if not self.client:
            logger.warning("Supabase client not initialized. Skipping save.")
            return 0

        if not transactions:
            return 0

        data = [tx.model_dump(mode="json") for tx in transactions]

        try:
            # upsert using transaction_date + description + amount as composite key?
            # Or just insert. For now, simple insert.
            response = self.client.table("transactions").upsert(data).execute()
            # response.data contains the inserted rows
            count = len(response.data) if response.data else 0
            logger.info(f"Saved {count} transactions to Supabase.")
            return count
        except Exception as e:
            logger.error(f"Failed to save to Supabase: {e}")
            return 0
