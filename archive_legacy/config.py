import os

# 基本設定
INPUT_DIR = r"M:\DB\kakeibo\input"
OUTPUT_DIR = r"M:\DB\kakeibo\clean"

# ファイルタイプの識別パターン
FILE_PATTERNS = {
    'sony': r'sony_.*\.txt$',
    'enavi': r'enavi\d{6}\(\d+\)\.csv$',
    'aplus': r'aplus_meisai_\d+_\d{6}\.csv$',
    'generic': r'\d{6}\.csv$',
    'transaction': r'transaction-history\.csv$'
}

# 各ファイルタイプのデフォルトエンコーディング
DEFAULT_ENCODINGS = {
    'sony': 'utf-8-sig',
    'enavi': 'utf-8-sig',  # 更新: shift_jisからutf-8-sigに変更
    'aplus': 'utf-8-sig',  # 更新: shift_jisからutf-8-sigに変更
    'generic': 'shift_jis', # 更新: utf-8からshift_jisに変更（SMBCカード対応）
    'transaction': 'utf-8'  # WISEトランザクション履歴用
}

# 出力ファイルの設定
OUTPUT_ENCODING = 'utf-8-sig'

# ヘッダー定義（標準化したフィールド名）
STANDARD_HEADERS = ['日付', '入金', '出金', '摘要', '残高', 'メモ']

# フォールバックエンコーディング（自動検出が失敗した場合に試行するエンコーディング）
FALLBACK_ENCODINGS = ['utf-8-sig', 'utf-8', 'shift_jis', 'cp932', 'euc-jp', 'iso-2022-jp']

# 日付フォーマット設定
DATE_FORMAT = '%Y年%m月%d日'  # 標準出力フォーマット
DATE_INPUT_FORMATS = [
    '%Y/%m/%d',
    '%Y-%m-%d',
    '%Y年%m月%d日',
    '%m/%d/%Y',
    '%d/%m/%Y',
    '%Y-%m-%d %H:%M:%S'  # WISEトランザクション履歴用
]

# 通貨単位設定
CURRENCY_SYMBOLS = ['¥', '$', '€', '£', '円']

# ファイル処理設定
MAX_PREVIEW_ROWS = 5  # プレビュー表示する最大行数
MIN_CONFIDENCE_THRESHOLD = 0.7  # エンコーディング検出の最小確信度

# ログ設定
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
