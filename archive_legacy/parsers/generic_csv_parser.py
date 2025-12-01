# parsers/generic_csv_parser.py
import csv
import datetime
import re
import config

def parse_generic_csv(input_file, encoding):
    """一般的なCSVファイルを解析"""
    data = []
    
    with open(input_file, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        # 最初の行をヘッダーとして読み込む
        original_headers = next(reader, None)
        
        if not original_headers:
            return config.STANDARD_HEADERS, []
        
        # ヘッダーのマッピングを推測
        header_mapping = {}
        for i, header in enumerate(original_headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['日付', 'date', '年月日']):
                header_mapping['date'] = i
            elif any(keyword in header_lower for keyword in ['入金', 'deposit', '収入']):
                header_mapping['deposit'] = i
            elif any(keyword in header_lower for keyword in ['出金', 'withdrawal', '支出']):
                header_mapping['withdrawal'] = i
            elif any(keyword in header_lower for keyword in ['摘要', 'description', '内容']):
                header_mapping['description'] = i
            elif any(keyword in header_lower for keyword in ['残高', 'balance']):
                header_mapping['balance'] = i
            elif any(keyword in header_lower for keyword in ['メモ', 'memo', '備考']):
                header_mapping['memo'] = i
        
        # 各行を処理
        for row in reader:
            if not row or len(row) < 2:  # 空行または短すぎる行はスキップ
                continue
            
            # 標準フォーマットの行を作成
            new_row = [''] * 6  # [日付, 入金, 出金, 摘要, 残高, メモ]
            
            # マッピングに従ってデータを配置
            for field, index in header_mapping.items():
                if index < len(row):
                    value = row[index].strip()
                    
                    # 日付フィールドの場合、フォーマットを変換
                    if field == 'date' and value:
                        try:
                            # 様々な日付形式に対応
                            date_formats = ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日', '%m/%d/%Y']
                            for fmt in date_formats:
                                try:
                                    date_obj = datetime.datetime.strptime(value, fmt)
                                    value = date_obj.strftime('%Y年%m月%d日')
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass  # 変換できない場合は元の値を使用
                    
                    # 金額フィールドの場合、カンマと通貨記号を削除
                    if field in ['deposit', 'withdrawal', 'balance'] and value:
                        value = re.sub(r'[¥$€£,円]', '', value)
                    
                    # 対応するインデックスに値を設定
                    if field == 'date':
                        new_row[0] = value
                    elif field == 'deposit':
                        new_row[1] = value
                    elif field == 'withdrawal':
                        new_row[2] = value
                    elif field == 'description':
                        new_row[3] = value
                    elif field == 'balance':
                        new_row[4] = value
                    elif field == 'memo':
                        new_row[5] = value
            
            data.append(new_row)
    
    return config.STANDARD_HEADERS, data

def parse_and_save(input_file, output_file, encoding='utf-8'):
    """ファイルを解析してCSVに保存"""
    # データを解析
    headers, data = parse_generic_csv(input_file, encoding)
    
    # CSVに書き込む
    with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    
    return True





def parse_generic_csv(input_file, encoding='utf-8-sig'):
    """WISEのCSVファイルを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            # タブ区切りCSVとして読み込み
            reader = csv.reader(f, delimiter='\t')
            original_headers = next(reader, None)
            
            if not original_headers:
                return headers, []
            
            # ヘッダーのマッピングを作成
            header_mapping = {
                '完了日': 'date',
                '送金額（手数料差し引き後）': 'amount',
                '送金元通貨': 'currency',
                '送金の種類': 'type',
                '備考': 'description'
            }
            
            # インデックスを取得
            indices = {key: original_headers.index(key) for key in header_mapping.keys() if key in original_headers}
            
            for row in reader:
                if len(row) < len(original_headers):
                    continue
                
                date = row[indices['完了日']]
                amount = row[indices['送金額（手数料差し引き後）']]
                currency = row[indices['送金元通貨']]
                transaction_type = row[indices['送金の種類']]
                description = row[indices['備考']]
                
                # 日付フォーマットの変換
                date_obj = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%Y年%m月%d日')
                
                # 入金/出金の判定
                if transaction_type == 'IN':
                    deposit = amount
                    withdrawal = ''
                elif transaction_type == 'OUT':
                    deposit = ''
                    withdrawal = amount
                else:
                    deposit = ''
                    withdrawal = ''
                
                data.append([
                    formatted_date,
                    deposit,
                    withdrawal,
                    description,
                    '',  # 残高情報がない場合は空欄
                    f'WISE {transaction_type}'  # メモ欄にWISEと取引種類を記載
                ])
        
        return headers, data
    except Exception as e:
        print(f"WISEファイル処理中にエラーが発生しました: {e}")
        raise
