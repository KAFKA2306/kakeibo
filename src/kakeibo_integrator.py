# kakeibo_integrator.py
import os
import pandas as pd
import glob
import re
import logging
from datetime import datetime
import unicodedata
import unicodedata

# ロギング設定
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'kakeibo_integrator_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 設定
CLEAN_DIR = r"M:\DB\kakeibo\clean"
OUTPUT_DIR = r"M:\DB\kakeibo\integrated"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "kakeibo_integrated.csv")

# 標準カラム名
STANDARD_COLUMNS = ['日付', '入金', '出金', '摘要', '残高', 'メモ', 'カード', 'カテゴリ']


def standardize_date(date_str):
    """日付を標準形式に変換"""
    if pd.isna(date_str):
        return None
    
    # 既に標準形式（YYYY年MM月DD日）の場合はそのまま返す
    if isinstance(date_str, str) and re.match(r'\d{4}年\d{1,2}月\d{1,2}日', date_str):
        return date_str
    
    try:
        # 数値の場合（例：20240101）
        if isinstance(date_str, (int, float)):
            date_str = str(int(date_str))
            if len(date_str) == 8:
                return f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:8]}日"
        
        # 文字列の場合
        if isinstance(date_str, str):
            # YYYY/MM/DD形式
            match = re.match(r'(\d{4})/(\d{1,2})/(\d{1,2})', date_str)
            if match:
                year, month, day = match.groups()
                return f"{year}年{month}月{day}日"
            
            # YYYY-MM-DD HH:MM:SS形式
            match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+\d{1,2}:\d{1,2}:\d{1,2}', date_str)
            if match:
                year, month, day = match.groups()
                return f"{year}年{month}月{day}日"
        
        # pandas.Timestampに変換できる場合
        return pd.to_datetime(date_str).strftime('%Y年%m月%d日')
    except:
        return date_str

def clean_amount(amount):
    """金額を数値に変換"""
    if pd.isna(amount):
        return None
    
    if isinstance(amount, (int, float)):
        return amount
    
    if isinstance(amount, str):
        # 通貨単位を抽出（例: "10.5 EUR" → "EUR"）
        currency_match = re.search(r'([A-Z]{3}|円)$', amount.strip())
        currency = currency_match.group(1) if currency_match else None
        
        # 通貨記号、カンマ、円記号を削除
        amount_clean = re.sub(r'[¥$€£,円]|\s+[A-Z]{3}$', '', amount)
        try:
            value = float(amount_clean)
            # 通貨単位がある場合は文字列として返す
            if currency:
                return f"{value} {currency}"
            return value
        except:
            return None
    
    return None

def determine_card_type(file_name):
    """ファイル名からカード種類を判定"""
    if 'sony' in file_name.lower():
        return 'ソニー銀行'
    elif 'aplus' in file_name.lower():
        return 'aplus'
    elif 'enavi' in file_name.lower():
        return '楽天カード'
    elif re.search(r'\d{6}\.csv$', file_name.lower()):
        return '三井住友カード'
    elif 'transaction' in file_name.lower():
        return 'Wise'
    elif 'wise' in file_name.lower():
        return 'Wise'

        return '不明'



def categorize_transaction(description, amount):
    """取引内容からカテゴリを判定する簡潔版"""
    desc = unicodedata.normalize('NFKC', str(description or '')).lower()
    
    # 収入判定
    if amount is not None and (isinstance(amount, (int, float)) and amount > 0):
        for kw, cat in [
            (['wise', 'transferwise'], '収入:海外送金'),
            (['給与', '給料'], '収入:給与'),
            (['賞与', 'ボーナス'], '収入:賞与'),
            (['利息', '決算お利息'], '収入:利息'),
            (['refund', '返金', 'cashback', 'キャッシュバック'], '収入:返金'),
            (['balance'], '収入:残高調整'),
            (['振込'], '収入:振込')
        ]:
            if any(w in desc for w in kw): return cat
        return '収入:その他'
    
    # 支出カテゴリのキーワードと対応するカテゴリのマッピング
    categories = [
        (['スーパー', 'ストア', 'aldi', 'rimi', 'spar', 'イオン', 'マツヤ', 'tigre', 'ヨシノヤ', '業務スーパー', 'supermar', 'klaas & kock', 'pick nick', 'tto adv', 'エビス', 'wakaba', 'mini market', '日本食材', 'sakuragiya', 'hamanaga', 'パンアイピ'], '支出:食料品'),
        (['コンビニ', 'セブン', 'ローソン', 'ファミリーマート', '7-eleven', 'narvesen', 'familymart', 'relay', 'yormas', 'クリーニング', 'cleaning', 'sanifair', 'スモークハウス', 'キッチン用品', '事務用品', 'yayoiken', 'marché', 'ahoi', 'sapori', 'mercato', 'don nino', 'vecchio', 'pylsur', 'japan food', 'dae-yang', 'hering', 'scheiners', 'サンフラワ', 'tsumura', 'advanced f', 'カイサ', 'コーラ', 'ウーバ', 'コーヒー', 'coffee', 'クハウス', 'スターバックス', 'starbucks', 'ドトール', 'デリカ', 'りくろー', 'asty京都', '社員食堂', 'aramark', '自動販売機', 'ジドウハンバイキ', '飲料', 'eats'], '支出:外食'),
        (['交通', 'タクシ', '鉄道', 'バス', 'lufthansa', 'klm', 'deutsche bahn', 'train', 'mvg', 'trenitalia', 'hochbahn', 'スマート', 'jr', 'suica', 'rheinbahn', 'tvm-', 'alilaguna', '東海', 'venezia', 'gotogate', 'play', 'airport', '空港', 'flugh', 'rvk', 'excursions', 'umeda', 'さんふらわあ', 'フェリー', 'airo', 'eda', 'fríhöfnin', 'ガソリン', 'jet', 'shell', 'tankstelle', 'ikuy', 'total', '駐車場', 'parking', 'parkraum', 'molenpoort', 'goldbeck'], '支出:交通費'),
        (['hotel', 'inn', '宿', 'agoda', 'ホテル', 'wellton', 'holiday inn', 'h2 htl', 'nidya otel'], '支出:宿泊費'),
        (['amazon', 'アマゾン', 'ｱﾏｿﾞﾝ', 'ユニクロ', 'takko', 'icewear', 'euroshop', 'rossmann', 'parka', 't&e store', 'rose', 'カメラ', 'ビック', 'ﾋﾞﾂｸ', 'ヨドバシ', 'beurer', '電化製品', 'booth', 'limited', 'オンラインショッピング', '衣料品', 'おひさまhouse', '壺焼きいも', 'ジゴクムシコ', 'オカモトヤ', 'お土産'], '支出:ショッピング'),
        (['apotheke', '薬局', '医薬品', 'hairサ', 'ヘア', 'salon', 'treatwell', '美容・健康'], '支出:医療・健康'),
        (['steam', 'play japan', 'game', 'ガクツ', 'ボドゲ', 'ギフトコード', 'universal', 'ユニバーサル', 'museum', 'unsthalle', 'utsches', 'palazzo', 'イマーシブ', 'ﾁｹｯﾄ', 'チケット', 'blue lagoon', 'hauptkirche', 'holocafe', 'icelandia', 'イープラス', 'ウエーブ', '楽天トラベル', 'bezrindas', '展示会', 'messe', 'ama air'], '支出:娯楽・レジャー'),
        (['通信', '携帯', 'モバイル', '通信費', '公共', '電気', 'ガス', '水道', 'stadtwer', 'tadt rhei', '公共料金', '分県国', '行政サービス','audible', 'chrome', 'ｸﾞｰｸﾞﾙ', 'google', 'freenet funk', 'openai', 'freenetfunk', 'サービス利用料'], '支出:サブスクリプション・税'),
        (['振替', '引落', '外貨', '振込 タ', 'カザ', '定期預金', '送金', '積立', '投資', '証券', 'ラクテンシヨウケン'], '支出:資金移動'),
    ]
    
    for keywords, category in categories:
        if any(k in desc for k in keywords):
            return category
    
    return '支出:その他'


def process_file(file_path):
    """CSVファイルを読み込み、標準形式に変換"""
    try:
        logger.info(f"処理開始: {file_path}")
        
        # ファイル名からカード種類を判定
        card_type = determine_card_type(os.path.basename(file_path))
        logger.info(f"カード種類: {card_type}")
        
        # CSVファイルを読み込む
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        logger.info(f"列名: {df.columns.tolist()}")
        logger.info(f"行数: {len(df)}")
        
        # 標準形式のDataFrameを作成
        standard_df = pd.DataFrame(columns=STANDARD_COLUMNS)
        
        # 列のマッピング
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if '日付' in col_lower or 'date' in col_lower:
                column_mapping['日付'] = col
            elif '入金' in col_lower or 'deposit' in col_lower or 'income' in col_lower:
                column_mapping['入金'] = col
            elif '出金' in col_lower or 'withdrawal' in col_lower or 'expense' in col_lower or 'payment' in col_lower:
                column_mapping['出金'] = col
            elif '摘要' in col_lower or '店名' in col_lower or '内容' in col_lower or 'description' in col_lower:
                column_mapping['摘要'] = col
            elif '残高' in col_lower or 'balance' in col_lower:
                column_mapping['残高'] = col
            elif 'メモ' in col_lower or '備考' in col_lower or 'memo' in col_lower or 'note' in col_lower:
                column_mapping['メモ'] = col
        
        # データをマッピング
        for std_col, file_col in column_mapping.items():
            if std_col == '日付':
                standard_df[std_col] = df[file_col].apply(standardize_date)
            elif std_col in ['入金', '出金', '残高']:
                standard_df[std_col] = df[file_col].apply(clean_amount)
            else:
                standard_df[std_col] = df[file_col]
        
        # 未設定の列を空文字で初期化
        for col in STANDARD_COLUMNS:
            if col not in standard_df.columns and col not in ['カード', 'カテゴリ']:
                standard_df[col] = ''
        
        # カード種類を設定
        standard_df['カード'] = card_type
        
        # カテゴリを判定
        standard_df['カテゴリ'] = standard_df.apply(
            lambda row: categorize_transaction(
                row['摘要'], 
                row['入金'] if pd.notna(row['入金']) and row['入金'] != '' else 
                -row['出金'] if pd.notna(row['出金']) and row['出金'] != '' else None
            ), 
            axis=1
        )
        
        # 欠損値を処理
        standard_df = standard_df.fillna('')
        
        logger.info(f"標準化後の行数: {len(standard_df)}")
        return standard_df
    
    except Exception as e:
        logger.error(f"ファイル処理中にエラーが発生: {e}")
        logger.error(f"エラー詳細: {str(e)}")
        return pd.DataFrame(columns=STANDARD_COLUMNS)

def main():
    """メイン処理"""
    logger.info("=== 家計簿データ統合処理を開始します ===")
    
    # 出力ディレクトリの作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # クリーンディレクトリ内のCSVファイルを取得
    csv_files = glob.glob(os.path.join(CLEAN_DIR, "*.csv"))
    logger.info(f"処理対象ファイル数: {len(csv_files)}")
    
    # 全データを格納するDataFrame
    all_data = pd.DataFrame(columns=STANDARD_COLUMNS)
    
    # 各ファイルを処理
    success_count = 0
    error_count = 0
    for file_path in csv_files:
        try:
            df = process_file(file_path)
            if not df.empty:
                all_data = pd.concat([all_data, df], ignore_index=True)
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"ファイル {file_path} の処理中にエラー: {e}")
            error_count += 1
    
    logger.info(f"処理結果: 成功={success_count}, 失敗={error_count}")
    
    # 日付でソート
    try:
        # 日付列が空の行を除外
        all_data = all_data[all_data['日付'] != '']
        
        # 日付を一時的にdatetime型に変換してソート
        all_data['日付_temp'] = pd.to_datetime(all_data['日付'], format='%Y年%m月%d日', errors='coerce')
        all_data = all_data.sort_values('日付_temp')
        
        # 元の形式に戻す
        all_data['日付'] = all_data['日付_temp'].dt.strftime('%Y年%m月%d日')
        all_data = all_data.drop('日付_temp', axis=1)
    except Exception as e:
        logger.error(f"日付ソート中にエラーが発生: {e}")
    
    # 結果を保存
    all_data.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    logger.info(f"統合データを保存しました: {OUTPUT_FILE}")
    logger.info(f"総行数: {len(all_data)}")
    
    # カテゴリごとの集計
    try:
        category_summary = all_data.groupby('カテゴリ').size().reset_index(name='件数')
        logger.info(f"カテゴリ別集計:\n{category_summary.to_string()}")
        
        # カード別の集計
        card_summary = all_data.groupby('カード').size().reset_index(name='件数')
        logger.info(f"カード別集計:\n{card_summary.to_string()}")
        
        # 月別の集計
        try:
            all_data['月'] = pd.to_datetime(all_data['日付'], format='%Y年%m月%d日').dt.strftime('%Y年%m月')
            month_summary = all_data.groupby('月').size().reset_index(name='件数')
            logger.info(f"月別集計:\n{month_summary.to_string()}")
        except Exception as e:
            logger.error(f"月別集計中にエラーが発生: {e}")
    except Exception as e:
        logger.error(f"集計処理中にエラーが発生: {e}")
    
    logger.info("=== 家計簿データ統合処理を終了します ===")

if __name__ == "__main__":
    main()
