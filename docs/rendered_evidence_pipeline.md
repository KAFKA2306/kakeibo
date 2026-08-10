# Rendered Evidence Pipeline

Issue: https://github.com/KAFKA2306/kakeibo/issues/19

## Purpose

Amazon・楽天などのログイン済みWebサービスで本人が閲覧できる履歴を、サイト固有の一回限りのスクレイピング結果ではなく、**再取得不要・再解析可能・監査可能なデータセット**へ変換する。

```text
Web service
  -> DISCOVER
  -> RENDER
  -> CAPTURE
  -> AUDIT
  -> PARSE
  -> NORMALIZE
  -> VERIFY
  -> PUBLISH
  -> CLASSIFY
```

最重要境界は `CAPTURE` と `CLASSIFY` を混ぜないこと。ふるさと納税候補・書籍・食品・家計などの意味分類は、履歴の事実取得が完了した後段で行う。

## Privacy boundary

このリポジトリはpublicである。実注文履歴はGitHubへ保存しない。

GitHubで管理するもの:

- Core / Adapter / Parserのコード
- schema・型・manifest契約
- 合成fixture
- 決定論的hash・監査ロジック
- テスト
- 運用文書

Git管理外に置くもの:

- rendered HTML / rendered text
- 注文番号
- 商品名・購入金額
- 個人アカウントに紐づくURL
- RAW / canonical / mart の実データ

既定保存先は `private/commerce-history/` とし、既存の `.gitignore` / privacy guard 境界を使用する。

## Core + Adapter

Coreはサイト非依存で、runner / evidence envelope / audit / hashing / canonical schema / manifest / semantic hash を担当する。

Adapterだけが source名 / partition discovery / pagination discovery / render完了判定 / record discovery / field extraction / source固有product id mapping を担当する。

Amazon固有の `.order-card.js-order-card`、`.yohtmlc-product-title`、`startIndex` などをCoreへ入れない。

## Rendered Evidence v01

サイト固有HTMLそのものを共通の封筒に入れる。

```json
{
  "format": "commerce-history-rendered-v01",
  "source": "rakuten.co.jp",
  "capture_method": "browser-rendered-dom",
  "captured_at": "2026-08-10T00:00:00Z",
  "partition": "2026",
  "page": "1",
  "record_position": 1,
  "source_page_url": "https://order.my.rakuten.co.jp/",
  "rendered_html": "<synthetic>...</synthetic>",
  "rendered_text": "synthetic fixture only",
  "raw_record_sha256": "..."
}
```

## Canonical schema

### commerce_order

- source
- account_scope
- order_id
- order_date
- total_amount
- currency
- status

### commerce_item

- source
- order_id
- item_no
- product_name
- product_id
- product_url
- quantity
- amount

### provenance

- captured_at
- partition
- page
- record_position
- source_page_url
- raw_record_sha256
- parser_version

`ASIN` や楽天の商品IDを正準列名にしない。source固有IDはAdapterが `product_id` へ写像する。

## Audit contract

単一のPASSに潰さず、最低3層に分ける。

- `capture_coverage`: reported / captured
- `parse_coverage`: captured / parsed
- `field_coverage`: fieldごとの充足件数

たとえば500注文をcaptureし、500注文をparseできても商品名が497注文にしか無いなら、captureはPASS、field coverageはPARTIALとして保持する。

## Reproducibility contract

同じRAW + parser versionから以下が一致すること。

- canonical order row count
- canonical item row count
- orders semantic SHA-256
- items semantic SHA-256

Google SheetsやData Martは正準データではなく、RAW + parser + manifestから再生成できるviewとする。

## Rakuten JP observations incorporated into the adapter contract

2026-08-10に本人のログイン済み購入履歴画面で確認した構造から、次の条件を契約へ反映する。実注文番号・商品名等はリポジトリへ保存しない。

- 一覧に総件数表示があるため、capture auditの `reported_records` 候補として扱える。
- 年・月・キーワードの絞り込みUIがある。
- 注文には注文日、注文番号、ショップ、注文詳細リンクが表示される。
- 1注文に複数商品が含まれ得るため、order/itemを1対多で扱う。
- 商品ページが消えていても商品名・金額が一覧に残るケースがある。`product_url` はnullableとする。
- 一覧末尾の「もう一度購入」推薦領域は注文履歴recordではないため、capture対象から除外する。
- 注文詳細URLには `order_number` と `shop_id` が含まれる現行表示を確認したが、DOM class名は未確認なので固定selectorを推測しない。

楽天市場公式ヘルプでも、楽天IDで注文した場合は購入履歴一覧から注文内容を確認し、詳細は「注文詳細」から確認する導線が案内されている。また、ショップがキャンセル処理した注文は購入履歴一覧から削除される場合があり、注文直後は一覧反映まで時間差がある。

Primary source:
https://ichiba.faq.rakuten.net/detail/000006428

## Initial adapters

- `amazon_jp`: known Amazon-specific selectors / pagination metadata are isolated here.
- `rakuten_jp`: current facts are isolated here; unverified DOM class selectors must remain unset until rendered DOM is captured.
