# parsers/generic_parser.py
import csv
import datetime
import re
import config

def parse_generic_csv(input_file, encoding):
    """一般的なCSVファイルを解析"""
    data = []
    
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            # 最初の行をヘッダーとして読み込む
            original_headers = next(reader, None)
            
            if not original_headers:
                return config.STANDARD_HEADERS, []
            
            # SMBCカードCSVファイルの特別処理
            if len(original_headers) >= 3 and '三井住友カードＶＩＳＡ' in original_headers[2]:
                return parse_smbc_card_csv(input_file, encoding)
            
            # ヘッダーのマッピングを推測
            header_mapping = {}
            for i, header in enumerate(original_headers):
                header_lower = header.lower()
                if any(keyword in header_lower for keyword in ['日付', 'date', '年月日', '利用日']):
                    header_mapping['date'] = i
                elif any(keyword in header_lower for keyword in ['入金', 'deposit', '収入']):
                    header_mapping['deposit'] = i
                elif any(keyword in header_lower for keyword in ['出金', 'withdrawal', '支出', '利用金額', 'ご利用金']):
                    header_mapping['withdrawal'] = i
                elif any(keyword in header_lower for keyword in ['摘要', 'description', '内容', '利用店名', 'ご利用店名']):
                    header_mapping['description'] = i
                elif any(keyword in header_lower for keyword in ['残高', 'balance']):
                    header_mapping['balance'] = i
                elif any(keyword in header_lower for keyword in ['メモ', 'memo', '備考', '支払方法']):
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
                                date_formats = ['%Y/%m/%d', '%Y-%m-%d', '%Y年%m月%d日', '%m/%d/%Y', '%d/%m/%Y']
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
    except UnicodeDecodeError as e:
        print(f"エンコーディングエラー ({encoding}): {e}")
        raise

def parse_smbc_card_csv(input_file, encoding):
    """三井住友カードのCSVファイルを解析"""
    data = []
    
    with open(input_file, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        # ヘッダー行をスキップ
        for _ in range(4):  # 通常、最初の4行はヘッダー情報
            next(reader, None)
        
        # データ行を処理
        for row in reader:
            if not row or len(row) < 4:
                continue
            
            # SMBCカードのCSV形式に合わせて解析
            try:
                date_str = row[0].strip()
                shop_name = row[1].strip()
                amount = row[3].strip().replace(',', '')
                
                # 日付を標準形式に変換
                try:
                    date_parts = date_str.split('/')
                    if len(date_parts) == 2:
                        # 年が省略されている場合、ファイル名から年を取得
                        month, day = date_parts
                        # ファイル名から年を取得（例: 202501.csv）
                        file_year = re.search(r'(\d{4})\d{2}', input_file)
                        if file_year:
                            year = file_year.group(1)
                            date_obj = datetime.datetime(int(year), int(month), int(day))
                        else:
                            # 年が取得できない場合は現在の年を使用
                            current_year = datetime.datetime.now().year
                            date_obj = datetime.datetime(current_year, int(month), int(day))
                    else:
                        date_obj = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                    
                    formatted_date = date_obj.strftime('%Y年%m月%d日')
                except ValueError:
                    formatted_date = date_str
                
                # 標準フォーマットに変換
                new_row = [
                    formatted_date,  # 日付
                    '',              # 入金
                    amount,          # 出金
                    shop_name,       # 摘要
                    '',              # 残高
                    ''               # メモ
                ]
                
                data.append(new_row)
            except Exception as e:
                print(f"行の解析中にエラーが発生しました: {row}, エラー: {e}")
    
    return config.STANDARD_HEADERS, data

def parse_and_save(input_file, output_file, encoding):
    """ファイルを解析してCSVに保存"""
    try:
        # データを解析
        headers, data = parse_generic_csv(input_file, encoding)
        
        # CSVに書き込む
        with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        raise


# parsers/generic_parser.py の更新部分

def parse_generic_csv(input_file, encoding):
    """一般的なCSVファイルを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        # ファイル名が202501.csvなどの形式かチェック
        is_smbc = False
        if re.search(r'\d{6}\.csv$', input_file):
            is_smbc = True
        
        with open(input_file, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            # 最初の行をヘッダーとして読み込む
            original_headers = next(reader, None)
            
            # SMBCカードのCSVかどうかを確認
            if is_smbc or (original_headers and any('三井住友カード' in str(h) for h in original_headers)):
                # SMBCカードCSVの特殊処理
                return parse_smbc_card(input_file, encoding)
            
            # その他の一般的なCSVファイル処理...（既存コード）
    except UnicodeDecodeError as e:
        # エンコーディングエラーの場合、shift_jisで再試行
        if encoding != 'shift_jis':
            return parse_generic_csv(input_file, 'shift_jis')
        else:
            raise e
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        raise

def parse_smbc_card(input_file, encoding='shift_jis'):
    """三井住友カードのCSVを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        # ファイル名から年月を抽出（例: 202501.csv → 2025年01月）
        match = re.search(r'(\d{4})(\d{2})\.csv$', input_file)
        year = match.group(1) if match else str(datetime.datetime.now().year)
        month = match.group(2) if match else '01'
        
        with open(input_file, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            
            # ヘッダー行をスキップ（通常、最初の4行はヘッダー情報）
            for _ in range(4):
                try:
                    next(reader)
                except StopIteration:
                    break
            
            for row in reader:
                if not row or len(row) < 4:
                    continue
                
                # 日付、店名、金額を取得
                date_str = row[0].strip() if len(row) > 0 else ''
                shop_name = row[1].strip() if len(row) > 1 else ''
                amount_str = row[3].strip() if len(row) > 3 else ''
                
                # 日付が数値のみの場合や空の場合はスキップ
                if not date_str or date_str.isdigit() or date_str == 'nan':
                    continue
                
                # 日付形式を変換
                formatted_date = ''
                try:
                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts) == 2:  # MM/DD形式
                            date_obj = datetime.datetime.strptime(f"{year}/{date_str}", '%Y/%m/%d')
                            formatted_date = date_obj.strftime('%Y年%m月%d日')
                        else:
                            date_obj = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                            formatted_date = date_obj.strftime('%Y年%m月%d日')
                    else:
                        formatted_date = date_str
                except ValueError:
                    formatted_date = date_str
                
                # 金額を数値に変換
                amount = 0
                try:
                    amount = float(amount_str.replace(',', ''))
                except ValueError:
                    continue
                
                data.append([
                    formatted_date,  # 日付
                    '',              # 入金
                    str(amount),     # 出金
                    shop_name,       # 摘要
                    '',              # 残高
                    'クレジットカード(SMBC)'  # メモ
                ])
    except Exception as e:
        print(f"三井住友カードファイル処理中にエラーが発生しました: {e}")
        raise
    
    return headers, data

def parse_and_save(input_file, output_file, encoding):
    """ファイルを解析してCSVに保存"""
    try:
        # ファイル名が202501.csvなどの形式かチェック
        if re.search(r'\d{6}\.csv$', input_file):
            # 三井住友カードファイルはshift_jisを強制
            encoding = 'shift_jis'
        
        # データを解析
        headers, data = parse_generic_csv(input_file, encoding)
        
        # CSVに書き込む
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"ファイル処理中にエラーが発生しました: {e}")
        raise


import pandas as pd
import re

def parse_smbc_visa(file_path):
    # ファイル読み込み
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # ヘッダー行をスキップし、データ行のみを抽出
    data_lines = []
    for line in lines:
        if re.match(r'\d{4}/\d{2}/\d{2}', line):  # 日付形式で始まる行を抽出
            data_lines.append(line)
    
    # 一時ファイルに保存
    temp_file = 'temp_data.csv'
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('日付,店舗名,金額,不明1,不明2,金額再掲,備考\n')  # ヘッダー追加
        for line in data_lines:
            f.write(line)
    
    # pandas で読み込み
    df = pd.read_csv(temp_file)
    
    # 必要なカラムのみ抽出
    result_df = df[['日付', '店舗名', '金額']]
    
    return result_df

def parse_smbc_card(input_file, encoding='shift_jis'):
    """三井住友カードのCSVを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        # ファイル名から年月を抽出（例: 202501.csv → 2025年01月）
        match = re.search(r'(\d{4})(\d{2})\.csv$', input_file)
        year = match.group(1) if match else str(datetime.datetime.now().year)
        
        with open(input_file, 'r', encoding=encoding) as f:
            content = f.read()
            lines = content.splitlines()
            
            # ヘッダー行を確認
            header_line_idx = -1
            for i, line in enumerate(lines):
                if '様,' in line and '三井住友カード' in line:
                    header_line_idx = i
                    break
            
            # データ行を処理
            data_lines = []
            for line in lines[header_line_idx+1:]:
                if re.match(r'\d{4}/\d{2}/\d{2}', line):  # 日付形式で始まる行を抽出
                    data_lines.append(line)
            
            # CSVとして解析
            for line in data_lines:
                row = line.split(',')
                if len(row) < 3:
                    continue
                
                date_str = row[0].strip()
                shop_name = row[1].strip()
                amount_str = row[2].strip()  # 金額は3列目に変更
                
                # 日付形式を変換
                try:
                    date_obj = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                    formatted_date = date_obj.strftime('%Y年%m月%d日')
                except ValueError:
                    formatted_date = date_str
                
                # 金額を数値に変換
                amount = 0
                try:
                    amount = float(amount_str.replace(',', ''))
                except ValueError:
                    continue
                
                data.append([
                    formatted_date,  # 日付
                    '',              # 入金
                    str(amount),     # 出金
                    shop_name,       # 摘要
                    '',              # 残高
                    'クレジットカード(SMBC)'  # メモ
                ])
    except Exception as e:
        print(f"三井住友カードファイル処理中にエラーが発生しました: {e}")
        raise
    
    return headers, data
def parse_smbc_card(input_file, encoding='shift_jis'):
    """三井住友カードのCSVを解析"""
    data = []
    headers = ['日付', '入金', '出金', '摘要', '残高', 'メモ']
    
    try:
        # ファイル名から年月を抽出
        match = re.search(r'(\d{4})(\d{2})\.csv$', input_file)
        year = match.group(1) if match else str(datetime.datetime.now().year)
        
        with open(input_file, 'r', encoding=encoding) as f:
            content = f.read()
            lines = content.splitlines()
            
            # ヘッダー行を確認
            header_line_idx = -1
            for i, line in enumerate(lines):
                if '様,' in line and '三井住友カード' in line:
                    header_line_idx = i
                    break
            
            # データ行を処理
            data_lines = []
            for line in lines[header_line_idx+1:]:
                if re.match(r'\d{4}/\d{2}/\d{2}', line):  # 日付形式で始まる行を抽出
                    data_lines.append(line)
            
            # CSVとして解析
            for line in data_lines:
                row = line.split(',')
                if len(row) < 3:
                    continue
                
                date_str = row[0].strip()
                shop_name = row[1].strip()
                amount_str = row[2].strip()  # 金額は3列目
                
                # 日付形式を変換
                try:
                    date_obj = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                    formatted_date = date_obj.strftime('%Y年%m月%d日')
                except ValueError:
                    formatted_date = date_str
                
                # 金額を数値に変換
                amount = 0
                try:
                    amount = float(amount_str.replace(',', ''))
                except ValueError:
                    continue
                
                data.append([
                    formatted_date,  # 日付
                    '',              # 入金
                    str(amount),     # 出金
                    shop_name,       # 摘要
                    '',              # 残高
                    'クレジットカード(SMBC)'  # メモ
                ])
    except Exception as e:
        print(f"三井住友カードファイル処理中にエラーが発生しました: {e}")
        raise
    
    return headers, data



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
