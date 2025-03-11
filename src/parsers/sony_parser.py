import re
import csv
import config

def parse_bank_statement(text):
    """ソニー銀行の明細データを解析"""
    lines = text.strip().split('\n')
    data = []
    
    # ヘッダー行をスキップ
    for line in lines[1:]:
        if not line.strip():
            continue
            
        fields = [''] * len(config.STANDARD_HEADERS)
        line = line.strip()
        
        # 日付部分の抽出
        date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', line)
        if date_match:
            fields[0] = date_match.group(1)  # 日付フィールド
            line = line[date_match.end():].strip()
        
        # 残高の抽出（末尾から）
        balance_match = re.search(r'([0-9,]+円)\s*$', line)
        if balance_match:
            balance = balance_match.group(1).replace('円', '').replace(',', '')
            fields[4] = balance  # 残高フィールド
            line = line[:balance_match.start()].strip()
        
        # 入金・出金の抽出
        # 最初の数値+円パターンを検出
        amount_match = re.search(r'([0-9,]+円)', line)
        if amount_match:
            amount_str = amount_match.group(1)
            amount_value = amount_str.replace('円', '').replace(',', '')
            
            # 金額の後ろの部分を取得して摘要とする
            description = line[amount_match.end():].strip()
            fields[3] = description  # 摘要フィールド
            
            # 金額の前の部分を確認して入金か出金かを判断
            prefix = line[:amount_match.start()].strip()
            
            # 空白が多いか"入金"という文字があれば入金、それ以外は出金と判断
            if '入金' in prefix or len(prefix) >= 8:  # 8はおおよその目安
                fields[1] = amount_value  # 入金フィールド
            else:
                fields[2] = amount_value  # 出金フィールド
        else:
            # 金額が見つからない場合、残りの部分を摘要とする
            fields[3] = line
        
        data.append(fields)
    
    return config.STANDARD_HEADERS, data

def try_alternative_parsing(text):
    """代替解析方法でデータを解析する"""
    lines = text.strip().split('\n')
    data = []
    
    for line in lines[1:]:
        if not line.strip():
            continue
            
        fields = [''] * len(config.STANDARD_HEADERS)
        parts = line.split('\t')  # タブで分割を試みる
        
        if len(parts) >= 5:
            # タブ区切りの場合の処理
            fields[0] = parts[0].strip()  # 日付
            
            # 入金・出金の判定（空でない方を採用）
            deposit = parts[1].strip().replace('円', '').replace(',', '')
            withdrawal = parts[2].strip().replace('円', '').replace(',', '')
            
            if deposit:
                fields[1] = deposit  # 入金
            if withdrawal:
                fields[2] = withdrawal  # 出金
                
            fields[3] = parts[3].strip()  # 摘要
            
            # 残高
            balance = parts[4].strip().replace('円', '').replace(',', '')
            if balance:
                fields[4] = balance
        
        data.append(fields)
    
    return config.STANDARD_HEADERS, data

def parse_and_save(input_file, output_file, encoding='utf-8-sig'):
    """ファイルを解析してCSVに保存"""
    # 入力ファイルを読み込む
    with open(input_file, 'r', encoding=encoding) as f:
        text = f.read()
    
    # 主要な解析方法でデータを解析
    headers, data = parse_bank_statement(text)
    
    # もし主要な解析方法で入金・出金が正しく分類されていなければ代替方法を試す
    deposit_count = sum(1 for row in data if row[1])
    withdrawal_count = sum(1 for row in data if row[2])
    
    if deposit_count == 0 or withdrawal_count == 0:
        # 全てが入金または全てが出金になっている場合は代替方法を試す
        headers, data = try_alternative_parsing(text)
    
    # CSVに書き込む
    with open(output_file, 'w', newline='', encoding=config.OUTPUT_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    
    return True
