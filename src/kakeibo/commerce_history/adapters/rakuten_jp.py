from .base import BrowserAdapterSpec


RAKUTEN_JP_SPEC = BrowserAdapterSpec(
    source="rakuten.co.jp",
    parser_version="rakuten_v01",
    record_selector=None,
    item_selector=None,
    partition_strategy="discover year/month filters from rendered purchase-history UI",
    pagination_strategy="discover current rendered pagination; do not assume URL shape",
    render_ready_strategy=(
        "wait until purchase-history count, order-detail links, and visible order records "
        "stabilize"
    ),
    notes=(
        "Verified rendered page exposes order date, order number, shop, order-detail link, items and amounts.",
        "One order may contain multiple items; normalize as one commerce_order to many commerce_item rows.",
        "A product page may be unavailable while product name and amount remain visible; product_url is nullable.",
        "Exclude the page-level buy-again recommendation section from captured order records.",
        "Current order-detail links expose order_number and shop_id, but DOM class selectors are not yet verified.",
        "Do not invent or freeze DOM selectors until rendered HTML is captured and audited.",
        "Official help: https://ichiba.faq.rakuten.net/detail/000006428",
    ),
)
