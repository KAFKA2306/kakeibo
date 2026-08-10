from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.kakeibo.commerce_history.adapters import AMAZON_JP_SPEC, RAKUTEN_JP_SPEC
from src.kakeibo.commerce_history.hashing import raw_record_sha256, semantic_sha256
from src.kakeibo.commerce_history.models import (
    CanonicalItem,
    CanonicalOrder,
    CaptureAudit,
    FieldCoverage,
    ParseAudit,
    RenderedEvidence,
)


def _evidence() -> RenderedEvidence:
    html = "<article><span>synthetic order</span></article>"
    text = "synthetic order"
    return RenderedEvidence(
        source="rakuten.co.jp",
        captured_at=datetime(2026, 8, 10, tzinfo=UTC),
        partition="2026",
        page="1",
        record_position=1,
        source_page_url="https://order.my.rakuten.co.jp/",
        rendered_html=html,
        rendered_text=text,
        raw_record_sha256=raw_record_sha256(
            rendered_html=html,
            rendered_text=text,
        ),
    )


def test_rendered_evidence_rejects_tampered_hash() -> None:
    evidence = _evidence()
    assert len(evidence.raw_record_sha256) == 64

    with pytest.raises(ValidationError):
        RenderedEvidence(
            **{
                **evidence.model_dump(),
                "rendered_text": "tampered",
            }
        )


def test_semantic_hash_is_deterministic_for_same_canonical_rows() -> None:
    orders = [
        CanonicalOrder(
            source="rakuten.co.jp",
            account_scope="primary",
            order_id="fixture-order-1",
            order_date=date(2026, 6, 19),
            total_amount=Decimal("10000"),
        )
    ]
    items = [
        CanonicalItem(
            source="rakuten.co.jp",
            order_id="fixture-order-1",
            item_no=1,
            product_name="fixture item",
            product_id="fixture-product",
            product_url=None,
            quantity=Decimal("1"),
            amount=Decimal("10000"),
        )
    ]

    assert semantic_sha256(orders) == semantic_sha256(list(orders))
    assert semantic_sha256(items) == semantic_sha256(list(items))


def test_audits_keep_capture_parse_and_field_coverage_separate() -> None:
    capture = CaptureAudit(
        reported_records=500,
        captured_records=500,
        status="PASS",
    )
    parse = ParseAudit(captured_records=500, parsed_records=500, status="PASS")
    field = FieldCoverage(
        field_name="product_name",
        eligible_records=500,
        populated_records=497,
        status="PARTIAL",
    )

    assert capture.status == "PASS"
    assert parse.status == "PASS"
    assert field.status == "PARTIAL"


def test_adapter_contract_keeps_source_specific_facts_out_of_core() -> None:
    assert AMAZON_JP_SPEC.source == "amazon.co.jp"
    assert AMAZON_JP_SPEC.record_selector == ".order-card.js-order-card"

    assert RAKUTEN_JP_SPEC.source == "rakuten.co.jp"
    assert RAKUTEN_JP_SPEC.parser_version == "rakuten_v02"
    assert 'aria-label="注文詳細"' in (RAKUTEN_JP_SPEC.record_selector or "")
    assert "padding-all-xlarge" in (RAKUTEN_JP_SPEC.item_selector or "")
    assert "?page=N" in RAKUTEN_JP_SPEC.pagination_strategy
    assert 'aria-label="next"' in RAKUTEN_JP_SPEC.pagination_strategy
    assert any("multiple items" in note for note in RAKUTEN_JP_SPEC.notes)
    assert any("127/127" in note for note in RAKUTEN_JP_SPEC.notes)
