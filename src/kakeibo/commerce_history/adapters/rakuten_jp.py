from src.kakeibo.commerce_history.adapters.base import BrowserAdapterSpec  # noqa: I001


RAKUTEN_JP_SPEC = BrowserAdapterSpec(
    source="rakuten.co.jp",
    parser_version="rakuten_v01",
    record_selector=(
        'a[aria-label="注文詳細"][href*="purchase-history"]'
        '[href*="order_number="][href*="shop_id="]'
    ),
    item_selector='a[rel="noreferrer"][href*="item.rakuten.co.jp"]',
    partition_strategy="discover year/month filters from rendered purchase-history UI",
    pagination_strategy=(
        "verified rendered pagination: page query parameter (?page=N), "
        'BUTTON aria-label="next" / text "次へ"; 25 records per full page'
    ),
    render_ready_strategy=(
        "wait until purchase-history count, order-detail links, and visible order records "
        "stabilize"
    ),
    notes=(
        (
            "Verified 2026-08-10 rendered capture: 127/127 records across six pages "
            "(25+25+25+25+25+2), PASS."
        ),
        (
            "Verified rendered page exposes order date, order number, shop, "
            "order-detail link, items and amounts."
        ),
        (
            "Use the semantic order-detail anchor as the record locator, then climb to "
            "the smallest ancestor containing exactly one order link plus 注文日/注文番号; "
            "hashed CSS-module class names are not a contract."
        ),
        (
            "One order may contain multiple items; normalize as one commerce_order to "
            "many commerce_item rows."
        ),
        (
            "A product page may be unavailable while product name and amount remain "
            "visible; product_url is nullable."
        ),
        (
            "Exclude the page-level buy-again recommendation section from captured "
            "order records."
        ),
        "Verified order-detail links expose order_number and shop_id.",
        (
            "Verified pagination controls are buttons; the final page has disabled "
            "next navigation."
        ),
        "Official help: https://ichiba.faq.rakuten.net/detail/000006428",
    ),
)
