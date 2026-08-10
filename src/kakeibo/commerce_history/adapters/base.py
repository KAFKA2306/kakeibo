from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import CanonicalItem, CanonicalOrder, Provenance, RenderedEvidence


@dataclass(frozen=True)
class BrowserAdapterSpec:
    source: str
    parser_version: str
    record_selector: str | None
    item_selector: str | None
    partition_strategy: str
    pagination_strategy: str
    render_ready_strategy: str
    notes: tuple[str, ...] = ()


class CommerceHistoryAdapter(Protocol):
    spec: BrowserAdapterSpec

    def parse_record(
        self,
        evidence: RenderedEvidence,
        *,
        account_scope: str,
    ) -> tuple[CanonicalOrder, list[CanonicalItem], Provenance]:
        """Parse one rendered order record into source-independent models."""
        ...
