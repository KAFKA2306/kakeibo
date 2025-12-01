# parsers/transaction_parser.py

import csv
import datetime
import pandas as pd

def parse_transaction_csv(input_file, encoding='utf-8'):
    """WISEのトランザクション履歴CSVを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        # CSVファイルを読み込む
        df = pd.read_csv(input_file, encoding=encoding)
        
        # 各行を処理
        for _, row in df.iterrows():
            # 日付を変換
            date_str = row['完了日'] if not pd.isna(row['完了日']) else row['作成日']
            formatted_date = format_date(date_str)
            
            # 金額と通貨情報を取得
            amount = row['送金額（手数料差し引き後）'] if not pd.isna(row['送金額（手数料差し引き後）']) else 0
            currency = get_currency(row)
            
            # 入出金情報を設定
            deposit, withdrawal = set_transaction_amounts(row['送金の種類'], amount, currency)
            
            # 摘要と備考
            description = row['備考'] if not pd.isna(row['備考']) else ""
            memo = create_memo(row)
            
            data.append([
                formatted_date,
                deposit,
                withdrawal,
                description,
                "",  # 残高情報なし
                memo
            ])
        
        return headers, data
    
    except Exception as e:
        print(f"WISEトランザクション履歴の処理中にエラーが発生しました: {e}")
        raise

def format_date(date_str):
    """日付文字列を標準形式に変換"""
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return date_obj.strftime('%Y年%m月%d日')
    except:
        return date_str

def get_currency(row):
    """行から通貨情報を取得"""
    if '送金元通貨.1' in row and not pd.isna(row['送金元通貨.1']):
        return row['送金元通貨.1']
    elif not pd.isna(row['送金元通貨']):
        return row['送金元通貨']
    else:
        return 'EUR'  # デフォルト通貨

def set_transaction_amounts(transaction_type, amount, currency):
    """取引タイプに基づいて入金・出金を設定"""
    deposit, withdrawal = "", ""
    
    if transaction_type == 'IN':
        deposit = f"{amount} {currency}"
    elif transaction_type == 'OUT':
        withdrawal = f"{amount} {currency}"
    elif transaction_type == 'NEUTRAL':
        # NEUTRALの場合はIDに基づいて判断するロジックを追加可能
        deposit = f"{amount} {currency}"
    
    return deposit, withdrawal

def create_memo(row):
    """メモ欄の内容を作成"""
    memo = f"WISE {row['送金の種類']}"
    
    if not pd.isna(row['為替レート']):
        memo += f" (レート: {row['為替レート']})"
    
    return memo

def parse_and_save(input_file, output_file, encoding='utf-8'):
    """ファイルを解析してCSVに保存"""
    try:
        # データを解析
        headers, data = parse_transaction_csv(input_file, encoding)
        
        # CSVに書き込む
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        
        return True
    
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        
        # エンコーディングエラーの場合は別のエンコーディングを試行
        if isinstance(e, UnicodeDecodeError) and encoding != 'utf-8-sig':
            print(f"utf-8-sigエンコーディングで再試行します...")
            return parse_and_save(input_file, output_file, 'utf-8-sig')
        
        raise
