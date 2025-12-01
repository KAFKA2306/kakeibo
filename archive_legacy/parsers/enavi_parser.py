# parsers/enavi_parser.py
import csv
import datetime
import re
import config

def parse_enavi_data(input_file, encoding):
    """e-naviのCSVデータを解析"""
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
            date_idx = -1
            shop_idx = -1
            amount_idx = -1
            payment_method_idx = -1
            user_idx = -1
            
            for i, header in enumerate(original_headers):
                header_lower = header.lower() if header else ''
                if '利用日' in header_lower:
                    date_idx = i
                elif '利用店名' in header_lower or '商品名' in header_lower:
                    shop_idx = i
                elif '利用金額' in header_lower:
                    amount_idx = i
                elif '支払方法' in header_lower:
                    payment_method_idx = i
                elif '利用者' in header_lower:
                    user_idx = i
            
            if date_idx == -1 or shop_idx == -1 or amount_idx == -1:
                date_idx = 0 if date_idx == -1 else date_idx
                shop_idx = 1 if shop_idx == -1 else shop_idx
                amount_idx = 4 if amount_idx == -1 else amount_idx
                payment_method_idx = 3 if payment_method_idx == -1 else payment_method_idx
                user_idx = 2 if user_idx == -1 else user_idx
            
            # ファイル名から年月を抽出
            match = re.search(r'enavi(\d{6})', input_file)
            year_month = match.group(1) if match else None
            
            for row in reader:
                if not row or len(row) <= max(date_idx, shop_idx, amount_idx):
                    continue
                
                try:
                    date_str = row[date_idx].strip()
                    shop_name = row[shop_idx].strip()
                    amount = row[amount_idx].strip().replace(',', '')
                    payment_method = row[payment_method_idx].strip() if payment_method_idx < len(row) else ''
                    user = row[user_idx].strip() if user_idx < len(row) and user_idx >= 0 else ''
                    
                    # 日付を標準形式に変換
                    try:
                        if '/' in date_str:
                            parts = date_str.split('/')
                            if len(parts) == 2:  # MM/DD形式
                                if year_month:
                                    year = year_month[:4]
                                    date_obj = datetime.datetime.strptime(f"{year}/{date_str}", '%Y/%m/%d')
                                else:
                                    # 年が不明な場合は現在の年を使用
                                    current_year = datetime.datetime.now().year
                                    date_obj = datetime.datetime.strptime(f"{current_year}/{date_str}", '%Y/%m/%d')
                            else:
                                date_obj = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                            formatted_date = date_obj.strftime('%Y年%m月%d日')
                        else:
                            formatted_date = date_str
                    except ValueError:
                        formatted_date = date_str
                    
                    # 摘要にユーザー情報を含める
                    description = shop_name
                    if user:
                        description = f"{description} ({user})"
                    
                    data.append([
                        formatted_date,  # 日付
                        '',              # 入金
                        amount,          # 出金
                        description,     # 摘要
                        '',              # 残高
                        payment_method   # メモ
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
        headers, data = parse_enavi_data(input_file, encoding)
        
        # CSVに書き込む
        with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        raise
