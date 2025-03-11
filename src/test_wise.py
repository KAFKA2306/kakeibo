import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import re
from datetime import datetime

def load_transaction_data(file_path):
    """トランザクションデータを読み込む関数"""
    df = pd.read_csv(file_path, encoding='utf-8')
    return df

# 出力ディレクトリの設定
output_dir = r"M:\DB\kakeibo\clean"
os.makedirs(output_dir, exist_ok=True)

# 入力ファイルの設定
input_file = r"M:\DB\kakeibo\input\transaction-history.csv"

# データの読み込み
df = load_transaction_data(input_file)

# 必要な列のみを選択し、列名を変更
df = df[
        ['ID', '送金の種類', '完了日',
        '送金額（手数料差し引き後）', '送金先',
        '受取通貨']
            ].rename(columns={
        '完了日': '日付',
        '送金額（手数料差し引き後）': '金額EUR',
        '送金先': '摘要',
        'ID': 'メモ'
           })

# データ表示
print("=== 元データ ===")
display(df)

# 前処理
# 送金種類に基づいて入出金額を計算
# 条件マスクを作成
eur_mask = df['受取通貨'] == 'EUR'
jpy_mask = df['受取通貨'] == 'JPY'
out_mask = df['送金の種類'] == 'OUT'
in_mask = df['送金の種類'] == 'IN'

# 出金カラムの計算
df['出金'] = 0
df.loc[eur_mask & out_mask, '出金'] = df.loc[eur_mask & out_mask, '金額EUR'] * 165
df.loc[jpy_mask & out_mask, '出金'] = df.loc[jpy_mask & out_mask, '金額EUR'] * 1

# 入金カラムの計算
df['入金'] = 0
df.loc[eur_mask & in_mask, '入金'] = df.loc[eur_mask & in_mask, '金額EUR'] * 165
df.loc[jpy_mask & in_mask, '入金'] = df.loc[jpy_mask & in_mask, '金額EUR'] * 1

df.loc[jpy_mask & in_mask, '入金'] = df.loc[jpy_mask & in_mask, '金額EUR'] * 1


# NEUTRALの行を削除
df = df[df['送金の種類'] != 'NEUTRAL']

# 結果を表示
display(df.sort_values('出金', ascending=False))

# 結果をCSVとして保存
output_file = os.path.join(output_dir, "wise_analysis.csv")
df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\n分析結果を保存しました: {output_file}")
