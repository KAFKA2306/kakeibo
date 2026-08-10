from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .hashing import raw_record_sha256


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RenderedEvidence(StrictModel):
    format: Literal["commerce-history-rendered-v01"] = (
        "commerce-history-rendered-v01"
    )
    source: str = Field(min_length=1)
    capture_method: Literal["browser-rendered-dom"] = "browser-rendered-dom"
    captured_at: datetime
    partition: str = Field(min_length=1)
    page: str = Field(min_length=1)
    record_position: int = Field(ge=1)
    source_page_url: HttpUrl
    rendered_html: str
    rendered_text: str
    raw_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_raw_hash(self) -> "RenderedEvidence":
        expected = raw_record_sha256(
            rendered_html=self.rendered_html,
            rendered_text=self.rendered_text,
        )
        if self.raw_record_sha256 != expected:
            raise ValueError("raw_record_sha256 does not match rendered evidence")
        return self


class CanonicalOrder(StrictModel):
    source: str = Field(min_length=1)
    account_scope: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    order_date: date
    total_amount: Decimal | None = None
    currency: str = Field(default="JPY", min_length=3, max_length=3)
    status: str | None = None


class CanonicalItem(StrictModel):
    source: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    item_no: int = Field(ge=1)
    product_name: str | None = None
    product_id: str | None = None
    product_url: HttpUrl | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = None


class Provenance(StrictModel):
    source: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    captured_at: datetime
    partition: str = Field(min_length=1)
    page: str = Field(min_length=1)
    record_position: int = Field(ge=1)
    source_page_url: HttpUrl
    raw_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_version: str = Field(min_length=1)


class CaptureAudit(StrictModel):
    reported_records: int | None = Field(default=None, ge=0)
    captured_records: int = Field(ge=0)
    status: Literal["PASS", "PARTIAL", "FAIL"]

    @model_validator(mode="after")
    def validate_status(self) -> "CaptureAudit":
        if self.reported_records is None:
            return self
        if self.captured_records == self.reported_records and self.status != "PASS":
            raise ValueError("matching reported/captured counts require PASS")
        if self.captured_records != self.reported_records and self.status == "PASS":
            raise ValueError("mismatched reported/captured counts cannot PASS")
        return self


class ParseAudit(StrictModel):
    captured_records: int = Field(ge=0)
    parsed_records: int = Field(ge=0)
    status: Literal["PASS", "PARTIAL", "FAIL"]

    @model_validator(mode="after")
    def validate_status(self) -> "ParseAudit":
        if self.parsed_records > self.captured_records:
            raise ValueError("parsed_records cannot exceed captured_records")
        if self.parsed_records == self.captured_records and self.status != "PASS":
            raise ValueError("full parse coverage requires PASS")
        if self.parsed_records != self.captured_records and self.status == "PASS":
            raise ValueError("partial parse coverage cannot PASS")
        return self


class FieldCoverage(StrictModel):
    field_name: str = Field(min_length=1)
    eligible_records: int = Field(ge=0)
    populated_records: int = Field(ge=0)
    status: Literal["PASS", "PARTIAL", "FAIL"]

    @model_validator(mode="after")
    def validate_status(self) -> "FieldCoverage":
        if self.populated_records > self.eligible_records:
            raise ValueError("populated_records cannot exceed eligible_records")
        if self.populated_records == self.eligible_records and self.status != "PASS":
            raise ValueError("full field coverage requires PASS")
        if self.populated_records != self.eligible_records and self.status == "PASS":
            raise ValueError("partial field coverage cannot PASS")
        return self
