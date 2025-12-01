# parsers/transaction_history_parser.py
import csv
import datetime
import re
import config

def parse_transaction_history(input_file, encoding):
    """transaction-history.csvファイルを解析"""
    data = []
    
    with open(input_file, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        # ヘッダー行を読み込む
        headers = next(reader, None)
        
        if not headers:
            return config.STANDARD_HEADERS, []
        
        # ヘッダーのインデックスを特定
        date_idx = -1
        description_idx = -1
        amount_idx = -1
        balance_idx = -1
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['date', 'transaction date']):
                date_idx = i
            elif any(keyword in header_lower for keyword in ['description', 'details', 'transaction']):
                description_idx = i
            elif any(keyword in header_lower for keyword in ['amount', 'transaction amount']):
                amount_idx = i
            elif any(keyword in header_lower for keyword in ['balance', 'running balance']):
                balance_idx = i
        
        # 必要なインデックスが見つからない場合
        if date_idx == -1 or description_idx == -1 or amount_idx == -1:
            print(f"警告: 必要なヘッダーが見つかりません: {headers}")
            return config.STANDARD_HEADERS, []
        
        # 各行を処理
        for row in reader:
            if not row or len(row) <= max(date_idx, description_idx, amount_idx):
                continue
            
            try:
                date_str = row[date_idx].strip()
                description = row[description_idx].strip()
                amount_str = row[amount_idx].strip()
                balance = row[balance_idx].strip() if balance_idx != -1 and balance_idx < len(row) else ''
                
                # 日付を標準形式に変換
                try:
                    # 様々な日付形式に対応
                    date_formats = ['%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
                    for fmt in date_formats:
                        try:
                            date_obj = datetime.datetime.strptime(date_str, fmt)
                            formatted_date = date_obj.strftime('%Y年%m月%d日')
                            break
                        except ValueError:
                            formatted_date = date_str
                except Exception:
                    formatted_date = date_str
                
                # 金額の正負を判断して入金/出金に振り分け
                amount_str = re.sub(r'[¥$€£,円]', '', amount_str)
                deposit = ''
                withdrawal = ''
                
                # 金額が負の場合は出金、正の場合は入金
                if amount_str.startswith('-'):
                    withdrawal = amount_str.lstrip('-')
                else:
                    deposit = amount_str
                
                # 残高からカンマと通貨記号を削除
                if balance:
                    balance = re.sub(r'[¥$€£,円]', '', balance)
                
                # 標準フォーマットに変換
                new_row = [
                    formatted_date,  # 日付
                    deposit,         # 入金
                    withdrawal,      # 出金
                    description,     # 摘要
                    balance,         # 残高
                    ''               # メモ
                ]
                
                data.append(new_row)
            except Exception as e:
                print(f"行の解析中にエラーが発生しました: {row}, エラー: {e}")
    
    return config.STANDARD_HEADERS, data

def parse_and_save(input_file, output_file, encoding='utf-8'):
    """ファイルを解析してCSVに保存"""
    # データを解析
    headers, data = parse_transaction_history(input_file, encoding)
    
    # CSVに書き込む
    with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    
    return True
