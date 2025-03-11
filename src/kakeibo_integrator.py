# kakeibo_integrator.py
import os
import pandas as pd
import glob
import re
import logging
from datetime import datetime
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
    """取引内容からカテゴリを判定する充実版"""

    description = unicodedata.normalize('NFKC', str(description).lower()) if description else ''

    # 金額が正の場合（収入）
    if amount is not None and (isinstance(amount, (int, float)) and amount > 0):
        if '給与' in description or '給料' in description:
            return '収入:給与'
        elif '賞与' in description or 'ボーナス' in description:
            return '収入:賞与'
        elif '利息' in description or '決算お利息' in description:
            return '収入:利息'
        elif 'refund' in description or '返金' in description or 'cashback' in description:
            return '収入:返金'
        elif 'balance' in description:
            return '収入:残高調整'
        elif 'キャッシュバック' in description:
            return '収入:キャッシュバック'
        elif '振込' in description:
            if 'wise' in description or 'transferwise' in description:
                return '収入:海外送金'
            return '収入:振込'
        else:
            return '収入:その他'

    # 以下は支出カテゴリ
    # 食費関連
    if ('スーパー' in description or 'ストア' in description or
        'aldi' in description or 'rimi' in description or 'spar' in description or
        'イオン' in description or 'マツヤ' in description or 'tigre' in description or
        'ヨシノヤ' in description or '業務スーパー' in description or 'hanaro supermarkt' in description or'ニツパン' in description or
        'bonus' in description or 'klaas & kock' in description or 'pick nick' in description or
        'tto advance' in description or
        'エビス' in description or
        'wakaba japan shop' in description or 'mini market' in description):
        return '支出:食料品'
    elif ('コンビニ' in description or 'セブン' in description or 'ローソン' in description or
          'ファミリーマート' in description or '7-eleven' in description or 'narvesen' in description or
          'familymart' in description or 'relay' in description or 'yormas' in description):
        return '支出:コンビニ'
    elif ('飲食' in description or 'レストラン' in description or '食堂' in description or
          'mcdonald' in description or 'burger king' in description or 'sbarro' in description or
          'ヤヨイケン' in description or '松屋' in description or "domino's" in description or
          'リンクス' in description or 'カフェ' in description or 'venchi' in description or
          'mannucci' in description or 'umami' in description or 'mexicana' in description or
          '東洋軒' in description or 'レッドペッパー' in description or 'red pepper' in description or
          'yayoiken' in description or 'marché' in description or 'ahoi steffen henssler' in description or
          'sapori & dintorni' in description or 'il mercato centrale' in description or
          'don nino' in description or 'vecchio carlino' in description or 'bæjarins beztu pylsur' in description or
          'japan food express' in description or 'dae-yang' in description or 'hering' in description or
          'scheiners am dom' in description or 'サンフラワ' in description or 'tsumura' in description or 'advanced f' in description or
          'カイサ' in description or
          'コーラ' in description or
          'ウーバ' in description or
          'コーヒー' in description or 'coffee' in description or 'クハウス' in description or
          'スターバックス' in description or 'starbucks' in description or 'ドトール' in description or
          'デリカ' in description or 'りくろーおじさん' in description or 'asty京都' in description):
        return '支出:外食'

    # 交通関連
    elif ('交通' in description or 'タクシ-' in description or
          '鉄道' in description or 'バス' in description or 'lufthansa' in description or
          'klm' in description or 'deutsche bahn' in description or 'train' in description or
          'mvg' in description or 'trenitalia' in description or 'hochbahn' in description or
          'スマート' in description or 'jr' in description or 'suica' in description or
          'rheinbahn' in description or 'tvm-' in description or 'alilaguna' in description or '東海' in description or
          'venezia unica' in description or 'gotogate' in description or 'play' in description or
          'airport' in description or '空港' in description or 'flugh' in description or
          'rvk bilast' in description or 'excursions' in description or 'umeda' in description or
          'さんふらわあ' in description or 'フェリー' in description or 'airo catering' in description or
          'eda' in description or
          'fríhöfnin' in description ):

        return '支出:交通費'
    elif ('jet' in description or 'shell' in description or 'tankstelle' in description or'ikuy' in description or
          'total' in description):
        return '支出:ガソリン代'
    elif ('parking' in description or 'parkraum' in description or 'molenpoortparking' in description or
          'goldbeck parking' in description):
        return '支出:駐車場'

    # 宿泊・旅行関連
    elif ('hotel' in description or 'inn' in description or '宿' in description or
          'agoda' in description or 'ホテル' in description or
          'wellton' in description or 'holiday inn' in description or 'h2 htl' in description or
          'nidya otel' in description or 'yokohama air cabin' in description):
        return '支出:宿泊費'

    # ショッピング関連
    elif ('amazon' in description or 'アマゾン' in description or
          'ｱﾏｿﾞﾝ' in description):
        return '支出:ネット通販'
    elif ('ユニクロ' in description or 'takko' in description or 'icewear' in description or
          'euroshop' in description or 'rossmann' in description or 'parka' in description or
          't&e store' in description or 'rose' in description):
        return '支出:衣料品・雑貨'
    elif ('カメラ' in description or 'ビック' in description or 'ﾋﾞﾂｸ' in description or
          'ヨドバシカメラ' in description or 'beurer' in description):
        return '支出:電化製品'
    elif ('booth' in description or 'limitedsecond' in description):
        return '支出:オンラインショッピング'
    elif ('marien apotheke' in description or '薬局' in description):
        return '支出:医薬品'

    # エンタメ・レジャー関連
    elif ('steam' in description or 'play japan' in description or 'game' in description or
          'ナガクツ店' in description or 'ボドゲ' in description or 'ギフトコード' in description or
          'universal' in description or 'ユニバーサル' in description or 'museum' in description or
          'kunsthalle' in description or 'deutsches' in description or 'palazzo' in description or
          'イマーシブ' in description or 'ﾁｹｯﾄ' in description or 'チケット' in description or
          'blue lagoon' in description or 'hauptkirche st. michaelis' in description or
          'holocafe' in description or 'icelandia' in description or 'イープラスショップ' in description or
          'ウエーブ' in description or '楽天トラベル観光体験' in description or
          'bezrindas' in description):
        return '支出:娯楽・レジャー'
    elif ('audible' in description or 'chrome' in description or 'ｸﾞｰｸﾞﾙ' in description or
          'google' in description or 'freenet funk' in description):
        return '支出:サブスクリプション'

    # 金融関連
    elif ('積立' in description or '投資' in description or '証券' in description or
          'ラクテンシヨウケン' in description):
        return '支出:投資'
    elif ('振替' in description or '引落' in description or '外貨' in description or'振込 タ' in description or 'カザ' in description or
          '定期預金' in description):
        return '支出:資金移動'
    elif ('fee' in description or '手数料' in description or 'atm' in description):
        return '支出:手数料'

    # 電子マネー・決済関連
    elif ('チャージ' in description or 'ペイ' in description or 'pay' in description or
          'paypal' in description or 'モバイル決済' in description or
          'visa provisioning service' in description or 'pppl eu ce eur' in description or
          'ウーバーイーツ' in description or 'uber eats' in description):
        return '支出:電子マネー'

    # その他の分類
    elif ('通信' in description or '携帯' in description or 'モバイル' in description
          ):
        return '支出:通信費'
    elif ('公共' in description or '電気' in description or 'ガス' in description or
          '水道' in description or 'stadtwerke' in description or 'stadt rheine' in description):
        return '支出:公共料金'
    elif ('hairサロン' in description or 'ヘア－スタジオ' in description or 'salon' in description or
          'treatwell' in description):
        return '支出:美容・健康'
    elif ('openai' in description or 'freenetfunk' in description):
        return '支出:サービス利用料'
    elif ('messe' in description):
        return '支出:展示会'
    elif ('スモークハウス' in description):
        return '支出:キッチン用品'
    elif ('コーラ' in description or '自動販売機' in description or 'ジドウハンバイキ' in description):
        return '支出:飲料'
    elif ('パンアイピーエス' in description):
        return '支出:事務用品'
    elif ('おひさまhouse' in description or '壺焼きいも' in description or 'ジゴクムシコ' in description or
          'オカモトヤ' in description):
        return '支出:お土産'
    elif ('大分県国東市' in description):
        return '支出:行政サービス'
    elif ('cleaning' in description or 'sanifair' in description):
        return '支出:クリーニング'
    elif ('aramark' in description):
        return '支出:社員食堂'
    elif ('transferwise' in description):
        return '支出:送金'
    elif ('sakuragiya' in description or 'hamanaga' in description):
        return '支出:日本食材'
    elif ('b.v. algemene amsterdamse' in description or 'hermann baveld' in description or
          'hza muenster' in description or 'izbraukumu tirdzniecib' in description or
          'northb' in description or 'centrale m3' in description or 'jolly86' in description or
          'sas hsp' in description or 'nsc enschede' in description or 'tmc p-enschede' in description):
        return '支出:海外サービス'

    # 上記のカテゴリに当てはまらない場合
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
