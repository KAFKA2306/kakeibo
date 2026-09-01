from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import Field, HttpUrl

from .models import StrictModel

PurchasePriceBasis = Literal[
    "CONFIRMED_ITEM_PRICE",
    "CONFIRMED_SINGLE_ITEM_ORDER_TOTAL",
    "UNVERIFIED_MULTI_ITEM_ORDER",
]
SalesChannel = Literal["AMAZON", "OFFICIAL", "OTHER_RETAIL"]
IdentityBasis = Literal[
    "ASIN_EXACT",
    "ISBN_EXACT",
    "MODEL_EXACT",
    "JAN_EXACT",
    "SPEC_MATCH",
    "MISMATCH",
    "UNVERIFIED",
]
PriceType = Literal["CURRENT_MARKET_OBSERVATION", "REFERENCE_PRICE"]
PriceAuditConclusion = Literal[
    "PASS_MARKET_COMPARE",
    "REFERENCE_ONLY",
    "RECHECK_IDENTITY",
    "RECHECK_FRESHNESS",
    "REJECT",
]


class PurchasePrice(StrictModel):
    source: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    item_no: int = Field(ge=1)
    product_id: str = Field(min_length=1)
    purchased_at: date
    purchase_price: Decimal = Field(ge=0)
    currency: str = Field(default="JPY", min_length=3, max_length=3)
    purchase_price_basis: PurchasePriceBasis


class PriceObservation(StrictModel):
    product_id: str = Field(min_length=1)
    observed_price: Decimal = Field(ge=0)
    currency: str = Field(default="JPY", min_length=3, max_length=3)
    observed_at: datetime
    source_url: HttpUrl
    sales_channel: SalesChannel
    price_type: PriceType
    identity_basis: IdentityBasis


class PriceAudit(StrictModel):
    identity_status: Literal["PASS", "RECHECK", "FAIL"]
    freshness_status: Literal["PASS", "RECHECK"]
    price_type_status: Literal["PASS", "REFERENCE"]
    sales_channel: SalesChannel
    conclusion: PriceAuditConclusion


class PriceComparison(StrictModel):
    product_id: str = Field(min_length=1)
    purchase_price: Decimal
    current_price: Decimal
    absolute_difference: Decimal
    change_rate_percent: Decimal | None
    purchase_price_basis: PurchasePriceBasis
    sales_channel: SalesChannel
    audit_conclusion: Literal["PASS_MARKET_COMPARE"] = "PASS_MARKET_COMPARE"
    observed_at: datetime


class PriceComparisonResult(StrictModel):
    audit: PriceAudit
    comparison: PriceComparison | None


def audit_price_observation(
    purchase: PurchasePrice,
    observation: PriceObservation,
    *,
    as_of: datetime,
    max_age_days: int = 7,
) -> PriceAudit:
    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    if observation.observed_at > as_of:
        raise ValueError("observation cannot be newer than as_of")

    if purchase.product_id != observation.product_id or observation.identity_basis == "MISMATCH":
        identity_status = "FAIL"
    elif observation.identity_basis in {"ASIN_EXACT", "ISBN_EXACT", "MODEL_EXACT", "JAN_EXACT"}:
        identity_status = "PASS"
    else:
        identity_status = "RECHECK"

    freshness_status = (
        "PASS" if as_of - observation.observed_at <= timedelta(days=max_age_days) else "RECHECK"
    )
    price_type_status = (
        "PASS" if observation.price_type == "CURRENT_MARKET_OBSERVATION" else "REFERENCE"
    )

    if identity_status == "FAIL":
        conclusion = "REJECT"
    elif identity_status == "RECHECK":
        conclusion = "RECHECK_IDENTITY"
    elif freshness_status == "RECHECK":
        conclusion = "RECHECK_FRESHNESS"
    elif price_type_status == "REFERENCE":
        conclusion = "REFERENCE_ONLY"
    else:
        conclusion = "PASS_MARKET_COMPARE"

    return PriceAudit(
        identity_status=identity_status,
        freshness_status=freshness_status,
        price_type_status=price_type_status,
        sales_channel=observation.sales_channel,
        conclusion=conclusion,
    )


def compare_price(
    purchase: PurchasePrice,
    observation: PriceObservation,
    *,
    as_of: datetime,
    max_age_days: int = 7,
) -> PriceComparisonResult:
    if purchase.currency != observation.currency:
        raise ValueError("purchase and observation currencies must match")

    audit = audit_price_observation(purchase, observation, as_of=as_of, max_age_days=max_age_days)
    if audit.conclusion != "PASS_MARKET_COMPARE":
        return PriceComparisonResult(audit=audit, comparison=None)

    absolute_difference = observation.observed_price - purchase.purchase_price
    change_rate_percent = (
        None
        if purchase.purchase_price == 0
        else absolute_difference / purchase.purchase_price * Decimal("100")
    )

    return PriceComparisonResult(
        audit=audit,
        comparison=PriceComparison(
            product_id=purchase.product_id,
            purchase_price=purchase.purchase_price,
            current_price=observation.observed_price,
            absolute_difference=absolute_difference,
            change_rate_percent=change_rate_percent,
            purchase_price_basis=purchase.purchase_price_basis,
            sales_channel=observation.sales_channel,
            observed_at=observation.observed_at,
        ),
    )
