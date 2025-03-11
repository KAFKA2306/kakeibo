# parsers/aplus_parser.py
import csv
import datetime
import re
import config

def parse_aplus_data(input_file, encoding):
    """A+のCSVデータを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            # ヘッダー行を読み込む
            original_headers = next(reader, None)
            
            if not original_headers:
                return headers, []
            
            # 列インデックスを特定
            card_idx = -1
            date_idx = -1
            shop_idx = -1
            amount_idx = -1
            memo_idx = -1
            
            for i, header in enumerate(original_headers):
                header_lower = header.lower() if header else ''
                if 'カード番号' in header_lower:
                    card_idx = i
                elif 'ご利用日' in header_lower:
                    date_idx = i
                elif 'ご利用店名' in header_lower:
                    shop_idx = i
                elif 'ご利用金' in header_lower:
                    amount_idx = i
                elif '摘要' in header_lower:
                    memo_idx = i
            
            # 見つからない場合はデフォルト値を設定
            if card_idx == -1 or date_idx == -1 or shop_idx == -1 or amount_idx == -1:
                card_idx = 0 if card_idx == -1 else card_idx
                date_idx = 1 if date_idx == -1 else date_idx
                shop_idx = 2 if shop_idx == -1 else shop_idx
                amount_idx = 3 if amount_idx == -1 else amount_idx
                memo_idx = 8 if memo_idx == -1 else memo_idx
            
            for row in reader:
                if not row or len(row) <= max(card_idx, date_idx, shop_idx, amount_idx):
                    continue
                
                try:
                    card_num = row[card_idx].strip() if card_idx < len(row) else ''
                    date_str = row[date_idx].strip() if date_idx < len(row) else ''
                    shop_name = row[shop_idx].strip() if shop_idx < len(row) else ''
                    amount_str = row[amount_idx].strip() if amount_idx < len(row) else ''
                    memo = row[memo_idx].strip() if memo_idx < len(row) and memo_idx >= 0 else ''
                    
                    # 日付を標準形式に変換
                    try:
                        if len(date_str) == 8 and date_str.isdigit():  # YYYYMMDDの形式
                            date_obj = datetime.datetime.strptime(date_str, '%Y%m%d')
                            formatted_date = date_obj.strftime('%Y年%m月%d日')
                        else:
                            formatted_date = date_str
                    except ValueError:
                        formatted_date = date_str
                    
                    # 金額の処理（負の値は入金として扱う）
                    amount = 0
                    try:
                        amount = float(amount_str.replace(',', ''))
                    except ValueError:
                        pass
                    
                    deposit = abs(amount) if amount < 0 else ''
                    withdrawal = amount if amount > 0 else ''
                    
                    data.append([
                        formatted_date,  # 日付
                        deposit,         # 入金
                        withdrawal,      # 出金
                        shop_name,       # 摘要
                        '',              # 残高
                        memo             # メモ
                    ])
                except Exception as e:
                    print(f"行の解析中にエラーが発生しました: {row}, エラー: {e}")
        
        return headers, data
    except UnicodeDecodeError as e:
        print(f"エンコーディングエラー ({encoding}): {e}")
        raise

def parse_and_save(input_file, output_file, encoding):
    """ファイルを解析してCSVに保存"""
    try:
        # BOMの検出
        with open(input_file, 'rb') as f:
            raw_data = f.read(3)
        
        # UTF-8 BOMが検出された場合はutf-8-sigを使用
        if raw_data.startswith(b'\xef\xbb\xbf'):
            encoding = 'utf-8-sig'
        
        # データを解析
        headers, data = parse_aplus_data(input_file, encoding)
        
        # CSVに書き込む
        with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        raise
