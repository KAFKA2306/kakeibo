# 家計簿データ処理・分析システム

## 概要

このシステムは銀行やクレジットカードの取引データを取り込み、標準形式に変換し、詳細な分析を行うための一連のPythonスクリプトです。複数の金融機関からのデータを統合し、支出パターンを可視化することで家計管理をサポートします。

## 主な機能

- **データ取り込み**: 様々な形式の金融機関データを読み込み
- **データ変換**: 異なるフォーマットを統一された形式に標準化
- **カテゴリ分類**: 取引内容を自動的に支出カテゴリに分類
- **データ分析**: 月別・カテゴリ別・曜日別など多角的な支出分析
- **可視化**: グラフやヒートマップによる支出傾向の視覚化

## システム構成

システムは以下の3つの主要コンポーネントで構成されています：

1. **bank_parser.py**: 銀行/カードデータの取り込みと前処理
2. **kakeibo_integrator.py**: 複数ソースからのデータ統合
3. **kakeibo_analyzer.py**: 統合データの分析と可視化

## 使用方法

### 1. データの準備

金融機関からダウンロードしたCSVファイルを入力ディレクトリに配置します：
```
M:\DB\kakeibo\input\
```

### 2. データの変換と統合

```python
# 1. 各金融機関のデータを標準形式に変換
python bank_parser.py

# 2. 変換されたデータを統合
python kakeibo_integrator.py
```

### 3. データ分析の実行

```python
python kakeibo_analyzer.py
```

## 出力結果

分析結果は「家計簿分析結果」フォルダに保存されます：

- **グラフ**: 月別支出推移、カテゴリ別支出割合、曜日別平均支出など
- **CSV**: 詳細な分析データ（月別カテゴリ別支出、曜日別支出詳細など）
- **サマリー**: 支出の統計情報

## ディレクトリ構造

```
M:\DB\kakeibo\
├── input\        # 入力データ
├── clean\        # 変換済みデータ
├── integrated\   # 統合データ
└── 家計簿分析結果\  # 分析結果
```