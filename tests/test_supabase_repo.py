from datetime import date
from types import SimpleNamespace

from src.kakeibo.adapters.supabase_repo import (
    SupabaseRepository,
    transaction_fingerprint,
)
from src.kakeibo.domain.models import Transaction


def make_transaction(description: str = "coffee") -> Transaction:
    return Transaction(
        transaction_date=date(2026, 8, 6),
        amount=-500,
        description=description,
        balance=10000,
        memo=None,
        source="test",
        category="food",
        sub_category=None,
    )


class FakeQuery:
    def __init__(self, calls: list[list[dict[str, object]]]) -> None:
        self.calls = calls
        self.payload: list[dict[str, object]] = []

    def upsert(self, payload: list[dict[str, object]]) -> "FakeQuery":
        self.payload = payload
        self.calls.append(payload)
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.payload)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def table(self, name: str) -> FakeQuery:
        assert name == "transactions"
        return FakeQuery(self.calls)


def test_fingerprint_is_stable_and_content_sensitive() -> None:
    first = make_transaction()
    same = make_transaction()
    different = make_transaction("lunch")

    assert transaction_fingerprint(first) == transaction_fingerprint(same)
    assert transaction_fingerprint(first) != transaction_fingerprint(different)


def test_save_bulk_deduplicates_and_batches() -> None:
    repository = SupabaseRepository(batch_size=1)
    client = FakeClient()
    repository.client = client

    saved = repository.save_bulk(
        [make_transaction(), make_transaction(), make_transaction("lunch")]
    )

    assert saved == 2
    assert len(client.calls) == 2
    assert sum(len(batch) for batch in client.calls) == 2


def test_batch_size_must_be_positive() -> None:
    try:
        SupabaseRepository(batch_size=0)
    except ValueError as exc:
        assert str(exc) == "batch_size must be at least 1"
    else:
        raise AssertionError("ValueError was not raised")
