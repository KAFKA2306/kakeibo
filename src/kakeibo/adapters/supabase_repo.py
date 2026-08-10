import hashlib
import json
import os
from collections.abc import Iterable

from loguru import logger

from src.kakeibo.domain.models import Transaction
from src.kakeibo.ports.repository import TransactionRepositoryPort

DEFAULT_BATCH_SIZE = 500


def transaction_fingerprint(transaction: Transaction) -> str:
    """Return a stable content fingerprint used to suppress duplicate writes."""
    payload = transaction.model_dump(mode="json")
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _deduplicate(transactions: Iterable[Transaction]) -> list[Transaction]:
    unique: dict[str, Transaction] = {}
    for transaction in transactions:
        unique.setdefault(transaction_fingerprint(transaction), transaction)
    return list(unique.values())


class SupabaseRepository(TransactionRepositoryPort):
    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        self.batch_size = batch_size
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

        unique_transactions = _deduplicate(transactions)
        duplicate_count = len(transactions) - len(unique_transactions)
        saved_count = 0

        logger.info(
            "Starting Supabase write input_count={} unique_count={} duplicate_count={} batch_size={}",
            len(transactions),
            len(unique_transactions),
            duplicate_count,
            self.batch_size,
        )

        try:
            for offset in range(0, len(unique_transactions), self.batch_size):
                batch = unique_transactions[offset : offset + self.batch_size]
                data = [transaction.model_dump(mode="json") for transaction in batch]
                response = self.client.table("transactions").upsert(data).execute()
                saved_count += len(response.data) if response.data else 0

            logger.info(
                "Completed Supabase write saved_count={} unique_count={} duplicate_count={}",
                saved_count,
                len(unique_transactions),
                duplicate_count,
            )
            return saved_count
        except Exception as exc:
            logger.error(
                "Supabase write failed error_type={} saved_count={} unique_count={}",
                type(exc).__name__,
                saved_count,
                len(unique_transactions),
            )
            return saved_count
