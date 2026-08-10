from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from pydantic import HttpUrl

from ..hashing import raw_record_sha256
from ..models import CanonicalItem, CanonicalOrder, Provenance

RAKUTEN_PARSER_VERSION = "rakuten_v02"
_SOURCE = "rakuten.co.jp"
_ITEM_ROW_CLASSES = {"flex-row-start--1GHo9", "padding-all-xlarge--1DSZs"}
_DATE_RE = re.compile(r"注文日：?\s*(\d{4})/(\d{2})/(\d{2})")
_ORDER_RE = re.compile(r"注文番号：?\s*([0-9-]+)")
_NUMERIC_RE = re.compile(r"[0-9][0-9,]*")
_UNAVAILABLE_ITEM_LABEL = "商品ページがありません"
_ITEM_UI_LABELS = {
    "円",
    "商品レビューを書く",
    "もう一度購入",
    "お気に入りに追加する",
    "リンクをコピー",
    "ROOMに投稿する",
    "おすすめの商品",
}


@dataclass
class _AnchorBuffer:
    href: str | None
    texts: list[str] = field(default_factory=list)


@dataclass
class _ItemBuffer:
    texts: list[str] = field(default_factory=list)
    anchors: list[_AnchorBuffer] = field(default_factory=list)
    amount_texts: list[str] = field(default_factory=list)


class _RakutenOrderHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.item: _ItemBuffer | None = None
        self.item_div_depth = 0
        self.items: list[_ItemBuffer] = []
        self.active_anchor: _AnchorBuffer | None = None
        self.capture_amount = False
        self.amount_div_depth: int | None = None
        self.capture_shop = False
        self.shop_texts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        href = attributes.get("href")

        if tag == "div" and self.item is None and _ITEM_ROW_CLASSES <= classes:
            self.item = _ItemBuffer()
            self.item_div_depth = 1
        elif tag == "div" and self.item is not None:
            self.item_div_depth += 1

        if self.item is not None and tag == "a":
            anchor = _AnchorBuffer(href=href)
            self.item.anchors.append(anchor)
            self.active_anchor = anchor

        if self.item is not None and tag == "div" and "value--21p0x" in classes:
            self.capture_amount = True
            self.amount_div_depth = self.item_div_depth

        if tag == "a" and href and "l-id=ph_pc_shopname" in href:
            self.capture_shop = True
            self.shop_texts = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self.item is not None:
            self.item.texts.append(text)
            if self.active_anchor is not None:
                self.active_anchor.texts.append(text)
            if self.capture_amount:
                self.item.amount_texts.append(text)
        if self.capture_shop:
            self.shop_texts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.active_anchor = None
            self.capture_shop = False

        if tag != "div" or self.item is None:
            return

        if self.capture_amount and self.amount_div_depth == self.item_div_depth:
            self.capture_amount = False
            self.amount_div_depth = None

        self.item_div_depth -= 1
        if self.item_div_depth == 0:
            self.items.append(self.item)
            self.item = None


@dataclass(frozen=True)
class RakutenParsedRecord:
    order: CanonicalOrder
    items: tuple[CanonicalItem, ...]
    provenance: Provenance
    shop_name: str
    visible_item_price_sum: Decimal


def _clean_product_url(value: str) -> str:
    parsed = urlparse(value)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _first_query_value(query: Mapping[str, list[str]], key: str) -> str | None:
    values = query.get(key, [])
    return values[0] if values else None


def _product_id(anchors: list[_AnchorBuffer]) -> str:
    for anchor in anchors:
        if not anchor.href or "my.bookmark.rakuten.co.jp/" not in anchor.href:
            continue
        query = parse_qs(urlparse(anchor.href).query)
        shop_bid = _first_query_value(query, "shop_bid")
        item_id = _first_query_value(query, "iid")
        if shop_bid and item_id:
            return f"{shop_bid}:{item_id}"
    raise ValueError("Rakuten item is missing stable shop_bid:iid evidence")


def _product_name_and_url(buffer: _ItemBuffer) -> tuple[str, str | None]:
    for anchor in buffer.anchors:
        if anchor.href and "s-id=ph_pc_itemname" in anchor.href:
            name = " ".join(anchor.texts).strip()
            if name:
                return name, _clean_product_url(anchor.href)

    if _UNAVAILABLE_ITEM_LABEL not in buffer.texts:
        raise ValueError("Rakuten item name evidence is missing")

    start = buffer.texts.index(_UNAVAILABLE_ITEM_LABEL) + 1
    for text in buffer.texts[start:]:
        if text in _ITEM_UI_LABELS or _NUMERIC_RE.fullmatch(text):
            continue
        return text, None
    raise ValueError("Rakuten unavailable item name could not be recovered")


def _item_amount(buffer: _ItemBuffer) -> Decimal:
    raw = "".join(buffer.amount_texts).replace(",", "")
    if not raw.isdigit():
        raise ValueError("Rakuten item price evidence is missing")
    return Decimal(raw)


def _parse_item(buffer: _ItemBuffer, *, order_id: str, item_no: int) -> CanonicalItem:
    product_name, product_url = _product_name_and_url(buffer)
    return CanonicalItem(
        source=_SOURCE,
        order_id=order_id,
        item_no=item_no,
        product_name=product_name,
        product_id=_product_id(buffer.anchors),
        product_url=HttpUrl(product_url) if product_url is not None else None,
        quantity=None,
        amount=_item_amount(buffer),
    )


def _parse_order_date(rendered_text: str) -> date:
    match = _DATE_RE.search(rendered_text)
    if match is None:
        raise ValueError("Rakuten order date evidence is missing")
    year, month, day = (int(value) for value in match.groups())
    return date(year, month, day)


def _parse_order_id(record: Mapping[str, Any], rendered_text: str) -> str:
    explicit = record.get("order_number")
    if explicit:
        return str(explicit)
    match = _ORDER_RE.search(rendered_text)
    if match is None:
        raise ValueError("Rakuten order number evidence is missing")
    return match.group(1)


def _parse_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def parse_rakuten_record(
    record: Mapping[str, Any],
    *,
    account_scope: str = "primary",
) -> RakutenParsedRecord:
    if record.get("source") not in (None, _SOURCE):
        raise ValueError("record source is not rakuten.co.jp")

    rendered_html = str(record["rendered_html"])
    rendered_text = str(record["rendered_text"])
    raw_hash = str(record["raw_record_sha256"])
    expected_hash = raw_record_sha256(
        rendered_html=rendered_html,
        rendered_text=rendered_text,
    )
    if raw_hash != expected_hash:
        raise ValueError("Rakuten rendered evidence SHA-256 mismatch")

    order_id = _parse_order_id(record, rendered_text)
    parser = _RakutenOrderHTMLParser()
    parser.feed(rendered_html)
    shop_name = " ".join(parser.shop_texts).strip()
    if not shop_name:
        raise ValueError("Rakuten shop-name evidence is missing")
    if not parser.items:
        raise ValueError("Rakuten order has no captured item rows")

    items = tuple(
        _parse_item(buffer, order_id=order_id, item_no=index)
        for index, buffer in enumerate(parser.items, start=1)
    )
    order = CanonicalOrder(
        source=_SOURCE,
        account_scope=account_scope,
        order_id=order_id,
        order_date=_parse_order_date(rendered_text),
        total_amount=None,
        currency="JPY",
        status=None,
    )
    provenance = Provenance(
        source=_SOURCE,
        order_id=order_id,
        captured_at=_parse_datetime(record["captured_at"]),
        partition=str(record["partition"]),
        page=str(record["page"]),
        record_position=int(record["record_position"]),
        source_page_url=HttpUrl(str(record["source_page_url"])),
        raw_record_sha256=raw_hash,
        parser_version=RAKUTEN_PARSER_VERSION,
    )
    visible_item_price_sum = sum(
        (item.amount or Decimal("0") for item in items),
        Decimal("0"),
    )
    return RakutenParsedRecord(
        order=order,
        items=items,
        provenance=provenance,
        shop_name=shop_name,
        visible_item_price_sum=visible_item_price_sum,
    )


def parse_rakuten_bundle(
    bundle: Mapping[str, Any],
    *,
    account_scope: str = "primary",
) -> tuple[RakutenParsedRecord, ...]:
    if bundle.get("source") not in (None, _SOURCE):
        raise ValueError("bundle source is not rakuten.co.jp")
    if bundle.get("capture_status") != "PASS":
        raise ValueError("Rakuten capture_status must be PASS before parsing")
    if bundle.get("field_coverage_status") not in (None, "PASS"):
        raise ValueError("Rakuten field_coverage_status must be PASS before parsing")

    raw_records = bundle.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("Rakuten bundle records must be a list")

    parsed: list[RakutenParsedRecord] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping):
            raise ValueError("Rakuten bundle contains a non-object record")
        parsed.append(parse_rakuten_record(raw_record, account_scope=account_scope))

    reported = bundle.get("reported_records")
    if reported is not None and len(parsed) != int(reported):
        raise ValueError("Rakuten parsed order count does not match reported_records")

    order_ids = [record.order.order_id for record in parsed]
    if len(order_ids) != len(set(order_ids)):
        raise ValueError("Rakuten bundle contains duplicate order IDs")

    return tuple(parsed)
