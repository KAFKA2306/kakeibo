from src.kakeibo.commerce_history.adapters.base import BrowserAdapterSpec


AMAZON_JP_SPEC = BrowserAdapterSpec(
    source="amazon.co.jp",
    parser_version="amazon_v02",
    record_selector=".order-card.js-order-card",
    item_selector=".yohtmlc-product-title",
    partition_strategy="discover year-* filters from rendered purchase-history UI",
    pagination_strategy="follow rendered pagination using startIndex",
    render_ready_strategy="wait until order cards and displayed order count stabilize",
    notes=(
        "Amazon-specific selectors and startIndex must never leak into core code.",
        "Capture rendered order-card HTML/text before source-specific parsing.",
    ),
)
