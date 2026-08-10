from src.kakeibo.commerce_history.adapters.base import BrowserAdapterSpec  # noqa: I001


RAKUTEN_JP_SPEC = BrowserAdapterSpec(
    source="rakuten.co.jp",
    parser_version="rakuten_v02",
    record_selector=(
        'a[aria-label="注文詳細"][href*="purchase-history"]'
        '[href*="order_number="][href*="shop_id="]'
    ),
    item_selector='div[class*="padding-all-xlarge"]',
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
            "Verified 2026-08-10 v04 capture: 127/127 records across six pages "
            "(25+25+25+25+25+2), capture PASS and field-coverage PASS."
        ),
        (
            "Verified all 127 raw SHA-256 values replay exactly; parser v02 normalizes "
            "127 orders into 131 item rows."
        ),
        (
            "Stable Rakuten product_id is shop_bid:iid from the rendered bookmark link; "
            "this remains available when the product page itself is unavailable."
        ),
        (
            "The purchase-history item price is normalized to commerce_item.amount. "
            "commerce_order.total_amount stays null because shipping, coupons and other "
            "order-level adjustments are not proven by this list view."
        ),
        (
            "One order may contain multiple items; normalize as one commerce_order to "
            "many commerce_item rows."
        ),
        (
            "A product page may be unavailable while product name, stable product ID and "
            "item price remain visible; product_url is nullable."
        ),
        (
            "Use semantic attributes and evidence content as the contract; CSS-module "
            "class names are implementation details used only inside the verified parser."
        ),
        "Verified order-detail links expose order_number and shop_id.",
        (
            "Verified pagination controls are buttons; the final page has disabled "
            "next navigation."
        ),
        "Official help: https://ichiba.faq.rakuten.net/detail/000006428",
    ),
)
