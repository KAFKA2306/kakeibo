"""Rendered evidence and canonical commerce-history contracts."""

from .hashing import raw_record_sha256, semantic_sha256
from .models import (
    CanonicalItem,
    CanonicalOrder,
    CaptureAudit,
    FieldCoverage,
    ParseAudit,
    Provenance,
    RenderedEvidence,
)
from .parsers import (
    RAKUTEN_PARSER_VERSION,
    RakutenParsedRecord,
    parse_rakuten_bundle,
    parse_rakuten_record,
)
from .price_comparison import (
    PriceAudit,
    PriceComparison,
    PriceComparisonResult,
    PriceObservation,
    PurchasePrice,
    audit_price_observation,
    compare_price,
)

__all__ = [
    "CanonicalItem",
    "CanonicalOrder",
    "CaptureAudit",
    "FieldCoverage",
    "ParseAudit",
    "PriceAudit",
    "PriceComparison",
    "PriceComparisonResult",
    "PriceObservation",
    "Provenance",
    "PurchasePrice",
    "RAKUTEN_PARSER_VERSION",
    "RakutenParsedRecord",
    "RenderedEvidence",
    "audit_price_observation",
    "compare_price",
    "parse_rakuten_bundle",
    "parse_rakuten_record",
    "raw_record_sha256",
    "semantic_sha256",
]
