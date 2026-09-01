from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.kakeibo.commerce_history.price_comparison import (
    PriceObservation,
    PurchasePrice,
    audit_price_observation,
    compare_price,
)


def _purchase() -> PurchasePrice:
    return PurchasePrice(
        source="amazon.co.jp",
        order_id="fixture-order-1",
        item_no=1,
        product_id="B09YY3DM1Z",
        purchased_at=date(2026, 7, 28),
        purchase_price=Decimal("5144"),
        currency="JPY",
        purchase_price_basis="CONFIRMED_SINGLE_ITEM_ORDER_TOTAL",
    )


def _observation(**overrides: object) -> PriceObservation:
    values: dict[str, object] = {
        "product_id": "B09YY3DM1Z",
        "observed_price": Decimal("6800"),
        "currency": "JPY",
        "observed_at": datetime(2026, 9, 1, tzinfo=UTC),
        "source_url": "https://www.amazon.co.jp/dp/B09YY3DM1Z",
        "sales_channel": "AMAZON",
        "price_type": "CURRENT_MARKET_OBSERVATION",
        "identity_basis": "ASIN_EXACT",
    }
    values.update(overrides)
    return PriceObservation(**values)


def test_exact_fresh_market_price_produces_deterministic_comparison() -> None:
    result = compare_price(
        _purchase(),
        _observation(),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert result.audit.conclusion == "PASS_MARKET_COMPARE"
    assert result.comparison is not None
    assert result.comparison.absolute_difference == Decimal("1656")
    assert result.comparison.change_rate_percent == Decimal("1656") / Decimal("5144") * Decimal("100")
    assert result.comparison.sales_channel == "AMAZON"


def test_spec_match_requires_identity_recheck_and_hides_delta() -> None:
    result = compare_price(
        _purchase(),
        _observation(identity_basis="SPEC_MATCH"),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert result.audit.conclusion == "RECHECK_IDENTITY"
    assert result.comparison is None


def test_stale_observation_requires_refresh_and_hides_delta() -> None:
    result = compare_price(
        _purchase(),
        _observation(observed_at=datetime(2026, 8, 20, tzinfo=UTC)),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
        max_age_days=7,
    )

    assert result.audit.conclusion == "RECHECK_FRESHNESS"
    assert result.comparison is None


def test_reference_price_is_not_used_as_market_delta() -> None:
    result = compare_price(
        _purchase(),
        _observation(price_type="REFERENCE_PRICE", sales_channel="OFFICIAL"),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert result.audit.conclusion == "REFERENCE_ONLY"
    assert result.comparison is None


def test_mismatched_product_is_rejected() -> None:
    audit = audit_price_observation(
        _purchase(),
        _observation(product_id="OTHER-ASIN"),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert audit.identity_status == "FAIL"
    assert audit.conclusion == "REJECT"


def test_currency_mismatch_fails_loudly() -> None:
    with pytest.raises(ValueError, match="currencies must match"):
        compare_price(
            _purchase(),
            _observation(currency="USD"),
            as_of=datetime(2026, 9, 2, tzinfo=UTC),
        )


def test_future_observation_fails_loudly() -> None:
    with pytest.raises(ValueError, match="newer than as_of"):
        audit_price_observation(
            _purchase(),
            _observation(observed_at=datetime(2026, 9, 3, tzinfo=UTC)),
            as_of=datetime(2026, 9, 2, tzinfo=UTC),
        )


def test_zero_purchase_price_does_not_invent_percent_change() -> None:
    purchase = _purchase().model_copy(update={"purchase_price": Decimal("0")})
    result = compare_price(
        purchase,
        _observation(observed_price=Decimal("100")),
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert result.comparison is not None
    assert result.comparison.absolute_difference == Decimal("100")
    assert result.comparison.change_rate_percent is None


def test_freshness_boundary_is_inclusive() -> None:
    as_of = datetime(2026, 9, 2, tzinfo=UTC)
    result = compare_price(
        _purchase(),
        _observation(observed_at=as_of - timedelta(days=7)),
        as_of=as_of,
        max_age_days=7,
    )

    assert result.audit.conclusion == "PASS_MARKET_COMPARE"
