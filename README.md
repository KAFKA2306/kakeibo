# Kakeibo — 銀行取引データの整形・分析基盤

**リポジトリ:** https://github.com/KAFKA2306/kakeibo

銀行やカードの取引明細をローカルで正規化する Python プロジェクトです。公開リポジトリにはコードと合成テストデータだけを置き、実明細・生成物・ログ・認証情報は Git の外側に隔離します。

## プライバシー境界

- 実データの既定保存先は Git 管理外の `private/input`、`private/output`、`private/logs`
- CSV、表計算、金融機関エクスポート、DB、画像、PDF、ログ、アーカイブ、秘密鍵、`.env` を `.gitignore` と privacy guard で拒否
- pre-commit と GitHub Actions で、機微ファイル名・既知のトークン形式・高エントロピー認証情報・口座番号・カード番号・個人環境パスを検査
- API は既定で無効。32文字以上のサーバー側トークンを設定した場合だけ処理可能
- API は1リクエスト1ファイル、サイズ・拡張子を制限し、元ファイル名を受け取らず一時ディレクトリ内で処理
- CLI の設定表示とアプリケーションログは秘密値、入力パス、元ファイル名、取引行を出力しない

詳細は [`SECURITY.md`](SECURITY.md) を参照してください。

## セットアップ

```bash
task install
cp .env.example .env
```

`.env` はコミットされません。API を使わない場合は `KAKEIBO_API_ENABLED=false` のままにしてください。

## ローカル処理

```bash
task cli -- process private/input --output-dir private/output
```

入力を上書きせず、匿名化された出力ファイル名で `private/output` に保存します。

## API

API は fail-closed です。明示的に有効化する場合だけ、サーバー環境で次を設定します。

```text
KAKEIBO_API_ENABLED=true
KAKEIBO_API_TOKEN=replace-with-at-least-32-random-characters
```

起動:

```bash
task dev
```

`POST /process` は生のファイル本文を受け取り、`X-API-Key` と `X-File-Suffix: .csv` または `.txt` が必要です。ブラウザへトークンや Supabase Service Role Key を渡してはいけません。

## 検査

```bash
task privacy
task lint
task typecheck
task test
```

全検査:

```bash
task check
```

GitHub Actions の `privacy` ジョブも、push と pull request のたびに同じ検査を実行します。

## 主な構成

```text
src/kakeibo/
├── domain/        # 取引・検証モデル
├── ports/         # Parser・Repositoryインターフェース
├── adapters/      # ファイル・DB実装
├── use_cases/     # アプリケーション処理
├── security.py    # ファイル名匿名化・アップロード検証
├── cli.py
└── api.py
scripts/
└── privacy_guard.py
```

## Supabase

Supabase を使用する場合、接続情報はサーバー環境変数だけに保存してください。RLS、最小権限、データ保持期間、削除手順、バックアップ、監査ログのマスキングを本番公開前に確認してください。

**README最終監査:** 2026-08-02
