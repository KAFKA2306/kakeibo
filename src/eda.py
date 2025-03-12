import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
from collections import Counter
import japanize_matplotlib

# 設定
plt.rcParams['font.family'] = 'Meiryo'
output_folder = "家計簿分析結果"
os.makedirs(output_folder, exist_ok=True)

def load_and_preprocess_data(file_path):
    """データの読み込みと前処理を行う関数"""
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    df['日付'] = pd.to_datetime(df['日付'], format='%Y年%m月%d日', errors='coerce')
    df['年月'] = df['日付'].dt.strftime('%Y-%m')
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
    df['日'] = df['日付'].dt.day
    
    for col in ['入金', '出金', '残高']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['金額'] = df['入金'].fillna(0) - df['出金'].fillna(0)
    
    # 投資と資金移動を除外した支出データ
    filtered_df = df[(df['金額'] < 0) & ~df['カテゴリ'].isin(['支出:投資', '支出:資金移動'])]
    
    return df, filtered_df

def create_pivot_tables(filtered_df):
    """各種ピボットテーブルを作成する関数"""
    # 月別カテゴリ別支出
    monthly_category = filtered_df.groupby(['年月', 'カテゴリ'])['金額'].sum() * -1
    monthly_category = monthly_category.reset_index()
    
    pivot = pd.pivot_table(monthly_category, values='金額', index='年月', 
                          columns='カテゴリ').fillna(0)
    pivot = pivot[pivot.sum().sort_values(ascending=False).index].astype(int)
    
    # 年別カテゴリ支出
    yearly_category = filtered_df.groupby(['年', 'カテゴリ'])['金額'].sum() * -1
    yearly_category = yearly_category.reset_index()
    
    pivot_yearly = pd.pivot_table(yearly_category, values='金額', 
                                index='年', columns='カテゴリ').fillna(0)
    
    # 年月別支出
    monthly_total = filtered_df.groupby(['年', '月'])['金額'].sum() * -1
    monthly_total = monthly_total.reset_index()
    pivot_year_month = pd.pivot_table(monthly_total, values='金額', 
                                    index='月', columns='年')
    
    # 日付別支出
    calendar_data = filtered_df.groupby(['年', '月', '日'])['金額'].sum() * -1
    calendar_data = calendar_data.reset_index()
    
    return pivot, pivot_yearly, pivot_year_month, calendar_data

def extract_keywords(text):
    """テキストからキーワードを抽出する関数"""
    if not isinstance(text, str): return []
    return re.findall(r'[a-zA-Z\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+', str(text).lower())

def create_keyword_df(df, column, n=20):
    """キーワード出現頻度のデータフレームを作成する関数"""
    all_words = []
    for desc in df[column].dropna():
        all_words.extend(extract_keywords(desc))
    
    return pd.DataFrame(Counter(all_words).most_common(n), columns=['単語', '出現回数'])

def plot_stacked_bar(pivot_data, title, filename, normalize=False, top_n=10):
    """積み上げ棒グラフを作成する関数"""
    # 合計金額でカテゴリをソート
    sorted_categories = pivot_data.sum().sort_values(ascending=False).index.tolist()
    pivot_plot = pivot_data[sorted_categories[:top_n]]  # 上位n個のカテゴリのみ
    
    if normalize:
        # 各行の合計を100%として正規化
        pivot_plot = pivot_plot.div(pivot_plot.sum(axis=1), axis=0) * 100
    
    # グラフ作成
    fig, ax = plt.subplots(figsize=(15, 8))
    pivot_plot.plot(kind='bar', stacked=True, ax=ax)
    
    # グラフの装飾
    plt.title(title, fontsize=16)
    plt.xlabel('期間', fontsize=12)
    plt.ylabel('支出' + ('割合 (%)' if normalize else ' (円)'), fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # 凡例に金額情報を追加
    total_by_category = pivot_data[sorted_categories[:top_n]].sum()
    handles, labels = ax.get_legend_handles_labels()
    new_labels = [f"{label} ({total_by_category[label]:,.0f}円)" for label in labels]
    ax.legend(handles, new_labels, title='カテゴリ（総額）', loc='upper left', bbox_to_anchor=(1, 1))
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, filename))
    plt.close()

def plot_heatmap(pivot_data, title, filename, fmt='d'):
    """ヒートマップを作成する関数"""
    fig, ax = plt.subplots(figsize=(16, 10))
    sns.heatmap(pivot_data, cmap='YlGnBu', annot=True, fmt=fmt, linewidths=.5, ax=ax)
    plt.title(title, fontsize=16)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, filename))
    plt.close()

def plot_barh(df, x, y, title, filename):
    """横棒グラフを作成する関数"""
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(x=x, y=y, data=df, ax=ax)
    plt.title(title, fontsize=16)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, filename))
    plt.close()

def create_summary(filtered_df, other_expense_df=None):
    """分析サマリーを作成する関数"""
    total_expense = filtered_df['金額'].sum() * -1
    avg_expense = total_expense / len(filtered_df['年月'].unique())
    
    summary_data = {
        'データ件数': len(filtered_df),
        '期間': f"{filtered_df['日付'].min().strftime('%Y/%m/%d')} 〜 {filtered_df['日付'].max().strftime('%Y/%m/%d')}",
        'カテゴリ数': len(filtered_df['カテゴリ'].unique()),
        'カード数': len(filtered_df['カード'].unique()),
        '総支出': f"{int(total_expense):,}円",
        '月平均支出': f"{int(avg_expense):,}円",
        '最大支出': f"{int(filtered_df['金額'].min() * -1):,}円",
        '最小支出': f"{int(filtered_df['金額'].max() * -1):,}円",
        '中央値支出': f"{int(filtered_df['金額'].median() * -1):,}円",
    }
    
    if other_expense_df is not None and len(other_expense_df) > 0:
        other_total = other_expense_df['金額'].sum() * -1
        other_ratio = other_total / total_expense * 100
        summary_data.update({
            '「支出:その他」件数': len(other_expense_df),
            '「支出:その他」総支出': f"{int(other_total):,}円",
            '「支出:その他」の割合': f"{other_ratio:.2f}%",
        })
    
    return pd.DataFrame(list(summary_data.items()), columns=['項目', '値'])

def analyze_household_expenses(file_path):
    """家計簿分析のメイン関数"""
    # データ読み込みと前処理
    df, filtered_df = load_and_preprocess_data(file_path)
    
    # ピボットテーブル作成
    pivot, pivot_yearly, pivot_year_month, calendar_data = create_pivot_tables(filtered_df)
    
    # 「支出:その他」の分析
    other_expense_df = filtered_df[filtered_df['カテゴリ'] == '支出:その他']
    
    # 各種グラフの作成
    # 1. カテゴリ別支出割合（月別）
    plot_stacked_bar(pivot, '月別カテゴリ支出割合（上位10カテゴリ、100%積み上げ）', '月別カテゴリ支出割合.png', normalize=True)
    
    # 2. カテゴリ別支出割合（年別）
    plot_stacked_bar(pivot_yearly, '年別カテゴリ支出割合（上位10カテゴリ）', '年別カテゴリ支出割合.png', normalize=True)
    
    # 3. 月別カテゴリ別支出ヒートマップ
    plot_heatmap(pivot[pivot.sum().sort_values(ascending=False).index[:10]], 
                '月別・カテゴリ別支出ヒートマップ（上位10カテゴリ）', 
                '月別カテゴリ別支出ヒートマップ.png')
    
    # 4. 「支出:その他」の分析
    if len(other_expense_df) > 0:
        other_words_df = create_keyword_df(other_expense_df, '摘要')
        plot_barh(other_words_df, '出現回数', '単語', 
                 '「支出:その他」の摘要欄頻出単語（上位20）', 
                 '支出その他の摘要頻出単語.png')
    
    # 5. 全体の摘要キーワード分析
    words_df = create_keyword_df(filtered_df, '摘要')
    plot_barh(words_df, '出現回数', '単語', 
             '摘要欄の頻出単語（上位20）', 
             '摘要欄頻出単語.png')
    
    # 6. 年別月別ヒートマップ
    plot_heatmap(pivot_year_month, '年別・月別支出ヒートマップ', 
                '年別月別支出ヒートマップ.png', fmt='.0f')
    
    # 7. カレンダー型ヒートマップ（1年ごと）
    for year in filtered_df['年'].unique():
        year_data = calendar_data[calendar_data['年'] == year]
        calendar_pivot = pd.pivot_table(year_data, values='金額', 
                                    index='日', columns='月', 
                                    fill_value=0)
        plot_heatmap(calendar_pivot, f'{year}年 カレンダー型支出ヒートマップ', 
                    f'{year}年_カレンダー型支出ヒートマップ.png', fmt='.0f')
    
    # 8. 月別支出推移
    plot_stacked_bar(pivot, '月別支出推移（カテゴリ別内訳）', '月別支出推移_カテゴリ別内訳.png')
    
    # 詳細データをCSVに出力
    pivot['合計'] = pivot.sum(axis=1)
    pivot.to_csv(os.path.join(output_folder, '月別カテゴリ別支出詳細.csv'), encoding='utf-8-sig')
    
    # サマリー情報の作成と出力
    summary_df = create_summary(filtered_df, other_expense_df)
    summary_df.to_csv(os.path.join(output_folder, '家計簿分析サマリー.csv'), 
                     index=False, encoding='utf-8-sig')
    
    print(f"\n分析が完了しました。結果は{output_folder}フォルダに保存されています。")

if __name__ == "__main__":
    file_path = r"M:\DB\kakeibo\integrated\kakeibo_integrated.csv"
    analyze_household_expenses(file_path)
