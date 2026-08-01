# Kakeibo — 銀行取引データの整形・分析基盤

**リポジトリ:** https://github.com/KAFKA2306/kakeibo

銀行やカードの取引明細を読み込み、形式を正規化し、支出分析やAPI提供へつなげるPythonプロジェクトです。

Polarsによる表データ処理、Pydanticによる入力検証、Typer CLI、FastAPI、Supabase接続用の構造を、Clean Architectureの層へ分けています。

## できること

- 取引明細ファイルの読込
- 列名、日付、金額、摘要の正規化
- データ検証
- 出力ディレクトリへの変換結果保存
- CLIからのバッチ処理
- FastAPIによる処理入口
- Supabase Repository実装の差し替え

実際に対応している銀行・ファイル形式は、`adapters/`配下の現在のParserを正としてください。

## セットアップ

```bash
task install
```

このタスクは`uv`を使って依存関係を同期します。

## CLIで処理する

```bash
task cli -- process /path/to/input_dir --output-dir /path/to/output_dir
```

入力ファイルを元の場所で上書きせず、出力先を別ディレクトリへ指定してください。

現在の設定を確認する場合:

```bash
task cli -- config
```

## APIを起動する

```bash
task dev
```

APIのURL、ポート、認証有無は現在のTaskfileと`src/kakeibo/api.py`を確認してください。

## 環境変数

アプリ設定は`pydantic-settings`から読み込みます。アプリ固有の設定には`KAKEIBO_`接頭辞を使用します。

Supabase接続例:

```text
SUPABASE_URL=...
SUPABASE_KEY=...
```

- 秘密鍵をコミットしない
- ブラウザへService Role Keyを渡さない
- 本番と開発でプロジェクトを分ける
- Row Level Securityを確認する

## 主な構成

```text
src/kakeibo/
├── domain/        # 取引・設定などのドメインモデル
├── ports/         # Parser・Repositoryなどのインターフェース
├── adapters/      # ファイル、DB、外部サービスの実装
├── use_cases/     # アプリケーション処理
├── cli.py         # Typer CLI
└── api.py         # FastAPI
```

## アーキテクチャの考え方

```text
入力ファイル・API・DB
  → Adapter
  → Port
  → Use Case
  → Domain Model
  → 検証済み出力
```

銀行固有のCSV形式をドメイン処理へ直接埋め込まず、Parser Adapterへ閉じ込めます。

## 開発コマンド

```bash
task test
task lint
task format
task typecheck
```

すべての検査が成功しても、実際の銀行明細に含まれる全例外へ対応できるとは限りません。匿名化した実データのサンプルで確認してください。

## 取引データの注意

- 明細には氏名、口座番号、カード番号、店舗、生活履歴が含まれます
- 元データ、ログ、テスト失敗時のダンプを公開しないでください
- 金額の正負が銀行ごとに異なる場合があります
- 返金、振替、立替、分割払い、外貨決済を区別してください
- 同じ摘要でも別の取引先である可能性があります
- 文字コードとタイムゾーンを保存してください

## Supabase・Vercel

リポジトリにはクラウド接続を想定した構造がありますが、「Cloud Ready」はデプロイ完了やセキュリティ確認済みを意味しません。

本番公開前に次を確認してください。

- 認証
- RLS
- 秘密情報
- データ保持期間
- バックアップ
- 削除機能
- ログの個人情報
- アップロードサイズ制限

## ライセンス・利用範囲

ライセンスファイルが存在する場合はその内容を正としてください。個人金融データの処理は、利用者本人の許可されたデータに限定してください。

**README最終監査:** 2026-08-01
