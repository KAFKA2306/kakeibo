import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
from datetime import datetime
import japanize_matplotlib
from collections import Counter

plt.rcParams['font.family'] = 'Meiryo'

output_folder = "家計簿分析結果"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def load_and_preprocess_data(file_path):
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    df['日付'] = pd.to_datetime(df['日付'], format='%Y年%m月%d日', errors='coerce')
    df['年月'] = df['日付'].dt.strftime('%Y-%m')
    df['年'] = df['日付'].dt.year
    df['月'] = df['日付'].dt.month
    df['曜日'] = df['日付'].dt.day_name()
    
    for col in ['入金', '出金', '残高']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['金額'] = df['入金'].fillna(0) - df['出金'].fillna(0)
    
    filtered_df = df[(df['金額'] < 0) & 
#                  (df['金額'] > -90000) & 
                    (df['カテゴリ'] != '支出:投資') &
                    (df['カテゴリ'] != '支出:資金移動')]

    return df, filtered_df

def save_plot(fig, filename):
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, filename))
    plt.close(fig)

def plot_monthly_expense(filtered_df):
    monthly_expense = filtered_df.groupby('年月')['金額'].sum() * -1
    
    fig, ax = plt.subplots(figsize=(15, 8))
    monthly_expense.plot(kind='bar', color='lightcoral', ax=ax)
    
    if len(monthly_expense) >= 3:
        monthly_expense.rolling(window=3).mean().plot(kind='line', marker='o', color='navy', ax=ax)
        plt.legend(['3ヶ月移動平均', '月別支出'])
    
    plt.title('月別支出推移と3ヶ月移動平均', fontsize=16)
    plt.xlabel('年月', fontsize=12)
    plt.ylabel('支出 (円)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    save_plot(fig, '月別支出推移と移動平均.png')
    return monthly_expense

def plot_category_expense(filtered_df):
    expense_by_category = filtered_df.groupby('カテゴリ')['金額'].sum() * -1
    top_expense_categories = expense_by_category.sort_values(ascending=False).head(10)
    
    fig = plt.figure(figsize=(12, 8))
    top_expense_categories.plot(kind='pie', autopct='%1.1f%%', startangle=90, 
                               shadow=False, explode=[0.05]*len(top_expense_categories))
    plt.title('カテゴリ別支出割合（上位10カテゴリ）', fontsize=16)
    plt.axis('equal')
    
    save_plot(fig, 'カテゴリ別支出割合.png')
    return expense_by_category

def plot_monthly_category_expense(filtered_df, expense_by_category):
    top_categories = expense_by_category.sort_values(ascending=False).head(10).index.tolist()
    other_categories = [cat for cat in filtered_df['カテゴリ'].unique() if cat not in top_categories]
    
    monthly_category_expense = filtered_df.groupby(['年月', 'カテゴリ'])['金額'].sum() * -1
    monthly_category_expense = monthly_category_expense.reset_index()
    
    pivot_data = pd.pivot_table(
        monthly_category_expense,
        values='金額',
        index='年月',
        columns='カテゴリ',
        aggfunc='sum'
    ).fillna(0)
    
    if len(other_categories) > 0:
        pivot_data['その他'] = pivot_data[other_categories].sum(axis=1)
        plot_categories = top_categories + ['その他']
    else:
        plot_categories = top_categories
    
    fig, ax = plt.subplots(figsize=(15, 8))
    pivot_data[plot_categories].plot(kind='bar', stacked=True, ax=ax)
    plt.title('月別支出推移（カテゴリ別内訳）', fontsize=16)
    plt.xlabel('年月', fontsize=12)
    plt.ylabel('支出 (円)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    
    save_plot(fig, '月別支出推移_カテゴリ別内訳.png')
    
    monthly_category_pivot = pd.pivot_table(
        monthly_category_expense,
        values='金額',
        index='年月',
        columns='カテゴリ',
        aggfunc='sum'
    ).fillna(0)
    monthly_category_pivot['合計'] = monthly_category_pivot.sum(axis=1)
    monthly_category_pivot.to_csv(os.path.join(output_folder, '月別カテゴリ別支出詳細.csv'), encoding='utf-8-sig')
    
    return monthly_category_expense

def plot_heatmap(filtered_df, expense_by_category):
    top_categories = expense_by_category.sort_values(ascending=False).head(10).index.tolist()
    filtered_top_categories = filtered_df[filtered_df['カテゴリ'].isin(top_categories)]
    
    pivot_data = pd.pivot_table(filtered_top_categories, 
                               values='金額', 
                               index='年月', 
                               columns='カテゴリ', 
                               aggfunc='sum') * -1
    pivot_data = pivot_data.fillna(0)
    
    fig = plt.figure(figsize=(16, 10))
    sns.heatmap(pivot_data, cmap='YlGnBu', annot=True, fmt='.0f', linewidths=.5)
    plt.title('月別・カテゴリ別支出ヒートマップ（上位10カテゴリ）', fontsize=16)
    
    save_plot(fig, '月別カテゴリ別支出ヒートマップ.png')

def plot_weekday_expense(filtered_df):
    day_counts = filtered_df.groupby('曜日')['日付'].apply(lambda x: len(x.dt.date.unique()))
    day_expense = filtered_df.groupby('曜日')['金額'].sum() * -1
    day_avg_expense = day_expense / day_counts
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_avg_expense = day_avg_expense.reindex(day_order)
    
    day_names_ja = {
        'Monday': '月曜日', 'Tuesday': '火曜日', 'Wednesday': '水曜日',
        'Thursday': '木曜日', 'Friday': '金曜日', 'Saturday': '土曜日', 'Sunday': '日曜日'
    }
    day_avg_expense.index = [day_names_ja[day] for day in day_avg_expense.index]
    
    fig = plt.figure(figsize=(12, 6))
    sns.barplot(x=day_avg_expense.index, y=day_avg_expense.values)
    plt.title('曜日別平均支出', fontsize=16)
    plt.xlabel('曜日', fontsize=12)
    plt.ylabel('平均支出 (円/日)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    save_plot(fig, '曜日別平均支出.png')
    
    day_expense_detail = pd.DataFrame({
        '曜日': day_avg_expense.index,
        '平均支出(円/日)': day_avg_expense.values,
        '総支出(円)': [day_expense.reindex(day_order)[day] for day in day_order],
        '日数': [day_counts.reindex(day_order)[day] for day in day_order]
    })
    day_expense_detail.to_csv(os.path.join(output_folder, '曜日別支出詳細.csv'), index=False, encoding='utf-8-sig')
    
    return day_avg_expense, day_expense, day_counts

def plot_card_expense(filtered_df):
    card_expense = filtered_df.groupby('カード')['金額'].sum() * -1
    card_expense = card_expense.sort_values(ascending=False)
    
    fig = plt.figure(figsize=(12, 6))
    sns.barplot(x=card_expense.index, y=card_expense.values)
    plt.title('カード別支出金額', fontsize=16)
    plt.xlabel('カード', fontsize=12)
    plt.ylabel('支出 (円)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    
    save_plot(fig, 'カード別支出金額.png')
    
    card_expense_detail = pd.DataFrame({
        'カード': card_expense.index,
        '支出金額(円)': card_expense.values,
        '割合(%)': card_expense / card_expense.sum() * 100
    })
    card_expense_detail.to_csv(os.path.join(output_folder, 'カード別支出詳細.csv'), index=False, encoding='utf-8-sig')
    
    return card_expense

def plot_expense_distribution(filtered_df):
    fig = plt.figure(figsize=(14, 7))
    
    plt.subplot(1, 2, 1)
    sns.histplot(filtered_df['金額'] * -1, bins=30, kde=True)
    plt.title('支出金額の分布', fontsize=14)
    plt.xlabel('支出金額 (円)', fontsize=12)
    plt.ylabel('頻度', fontsize=12)
    
    plt.subplot(1, 2, 2)
    sns.boxplot(y=filtered_df['金額'] * -1)
    plt.title('支出金額の箱ひげ図', fontsize=14)
    plt.ylabel('支出金額 (円)', fontsize=12)
    
    save_plot(fig, '支出金額の分布分析.png')

def plot_category_trends(filtered_df):
    top_categories = filtered_df['カテゴリ'].value_counts().head(10).index.tolist()
    category_monthly = pd.DataFrame()
    
    for category in top_categories:
        cat_data = filtered_df[filtered_df['カテゴリ'] == category]
        monthly_sum = cat_data.groupby('年月')['金額'].sum() * -1
        category_monthly[category] = monthly_sum
    
    fig = plt.figure(figsize=(15, 8))
    category_monthly.plot(kind='line', marker='o')
    plt.title('主要カテゴリの月別支出推移', fontsize=16)
    plt.xlabel('年月', fontsize=12)
    plt.ylabel('支出 (円)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='best')
    
    save_plot(fig, 'カテゴリ別月次支出推移.png')
    
    return category_monthly

def analyze_other_expense(filtered_df):
    other_expense_df = filtered_df[filtered_df['カテゴリ'] == '支出:その他']
    
    if len(other_expense_df) > 0:
        other_expense_summary = {
            '件数': len(other_expense_df),
            '総支出': other_expense_df['金額'].sum() * -1,
            '平均支出': other_expense_df['金額'].mean() * -1,
            '最大支出': other_expense_df['金額'].min() * -1,
            '最小支出': other_expense_df['金額'].max() * -1
        }
        
        other_monthly = other_expense_df.groupby('年月')['金額'].sum() * -1
        
        fig = plt.figure(figsize=(15, 7))
        sns.barplot(x=other_monthly.index, y=other_monthly.values)
        plt.title('「支出:その他」の月別推移', fontsize=16)
        plt.xlabel('年月', fontsize=12)
        plt.ylabel('支出 (円)', fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        
        save_plot(fig, '支出その他の月別推移.png')
        
        def extract_keywords(text):
            if not isinstance(text, str):
                return []
            text = str(text).lower()
            words = re.findall(r'[a-zA-Z\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+', text)
            return words
        
        other_words = []
        for desc in other_expense_df['摘要'].dropna():
            other_words.extend(extract_keywords(desc))
        
        other_word_counts = Counter(other_words)
        other_common_words = other_word_counts.most_common(20)
        other_common_words_df = pd.DataFrame(other_common_words, columns=['単語', '出現回数'])
        
        fig = plt.figure(figsize=(12, 8))
        sns.barplot(x='出現回数', y='単語', data=other_common_words_df)
        plt.title('「支出:その他」の摘要欄頻出単語（上位20）', fontsize=16)
        
        save_plot(fig, '支出その他の摘要頻出単語.png')
        
        other_card_expense = other_expense_df.groupby('カード')['金額'].sum() * -1
        other_card_expense = other_card_expense.sort_values(ascending=False)
        
        fig = plt.figure(figsize=(12, 6))
        sns.barplot(x=other_card_expense.index, y=other_card_expense.values)
        plt.title('「支出:その他」のカード別支出金額', fontsize=16)
        plt.xlabel('カード', fontsize=12)
        plt.ylabel('支出 (円)', fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        
        save_plot(fig, '支出その他のカード別支出金額.png')
        
        return other_expense_summary, other_monthly
    
    return None, None

def analyze_description_keywords(filtered_df):
    def extract_keywords(text):
        if not isinstance(text, str):
            return []
        text = str(text).lower()
        words = re.findall(r'[a-zA-Z\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+', text)
        return words
    
    all_words = []
    for desc in filtered_df['摘要'].dropna():
        all_words.extend(extract_keywords(desc))
    
    word_counts = Counter(all_words)
    common_words = word_counts.most_common(20)
    common_words_df = pd.DataFrame(common_words, columns=['単語', '出現回数'])
    
    fig = plt.figure(figsize=(12, 8))
    sns.barplot(x='出現回数', y='単語', data=common_words_df)
    plt.title('摘要欄の頻出単語（上位20）', fontsize=16)
    
    save_plot(fig, '摘要欄頻出単語.png')
    
    return common_words_df

def plot_year_month_heatmap(filtered_df):
    if len(filtered_df['年'].unique()) > 1:
        monthly_by_year = filtered_df.pivot_table(
            values='金額', 
            index='月', 
            columns='年', 
            aggfunc='sum'
        ) * -1
        
        fig = plt.figure(figsize=(12, 8))
        sns.heatmap(monthly_by_year, cmap='YlGnBu', annot=True, fmt='.0f')
        plt.title('年別・月別支出ヒートマップ', fontsize=16)
        plt.xlabel('年', fontsize=12)
        plt.ylabel('月', fontsize=12)
        
        save_plot(fig, '年別月別支出ヒートマップ.png')
        
        return monthly_by_year
    
    return None

def plot_daily_expense_analysis(filtered_df, monthly_expense):
    monthly_days = filtered_df.groupby('年月')['日付'].apply(lambda x: len(x.dt.date.unique()))
    monthly_avg_per_day = monthly_expense / monthly_days
    
    fig = plt.figure(figsize=(15, 7))
    sns.barplot(x=monthly_avg_per_day.index, y=monthly_avg_per_day.values)
    plt.title('月別1日あたり平均支出', fontsize=16)
    plt.xlabel('年月', fontsize=12)
    plt.ylabel('1日あたり平均支出 (円/日)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    
    save_plot(fig, '月別1日あたり平均支出.png')
    
    return monthly_avg_per_day


def main():
    file_path = r"M:\DB\kakeibo\integrated\kakeibo_integrated.csv"
    df, filtered_df = load_and_preprocess_data(file_path)
    
    monthly_expense = plot_monthly_expense(filtered_df)
    expense_by_category = plot_category_expense(filtered_df)
    monthly_category_expense = plot_monthly_category_expense(filtered_df, expense_by_category)
    plot_heatmap(filtered_df, expense_by_category)
    day_avg_expense, day_expense, day_counts = plot_weekday_expense(filtered_df)
    card_expense = plot_card_expense(filtered_df)
    plot_expense_distribution(filtered_df)
    category_monthly = plot_category_trends(filtered_df)
    analyze_other_expense(filtered_df)
    analyze_description_keywords(filtered_df)
    plot_year_month_heatmap(filtered_df)
    plot_daily_expense_analysis(filtered_df, monthly_expense)
    
    # 支出の統計情報
    total_expense = filtered_df['金額'].sum() * -1
    avg_expense = total_expense / len(filtered_df['年月'].unique())
    
    # 支出金額帯別の分析
    expense_bins = [0, 1000, 3000, 5000, 10000]
    expense_labels = ['〜1,000円', '1,001〜3,000円', '3,001〜5,000円', '5,001〜10,000円']
    filtered_df['支出金額帯'] = pd.cut((filtered_df['金額'] * -1), bins=expense_bins, labels=expense_labels)
    
    expense_by_range = filtered_df.groupby('支出金額帯').agg({
        '金額': lambda x: (x.sum() * -1),
        '日付': 'count'
    }).rename(columns={'金額': '支出合計', '日付': '件数'})
    
    # 金額帯別グラフ（hueパラメータを削除）
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    sns.barplot(x=expense_by_range.index, y=expense_by_range['支出合計'], ax=ax1)
    ax1.set_title('金額帯別支出合計', fontsize=14)
    ax1.set_xlabel('支出金額帯', fontsize=12)
    ax1.set_ylabel('支出合計 (円)', fontsize=12)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    
    sns.barplot(x=expense_by_range.index, y=expense_by_range['件数'], ax=ax2)
    ax2.set_title('金額帯別件数', fontsize=14)
    ax2.set_xlabel('支出金額帯', fontsize=12)
    ax2.set_ylabel('件数', fontsize=12)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    save_plot(fig, '支出金額帯別分析.png')
    
    # 支出金額帯別の詳細情報をCSVに出力
    expense_by_range['平均金額'] = expense_by_range['支出合計'] / expense_by_range['件数']
    expense_by_range['割合(%)'] = expense_by_range['支出合計'] / expense_by_range['支出合計'].sum() * 100
    expense_by_range.to_csv(os.path.join(output_folder, '支出金額帯別詳細.csv'), encoding='utf-8-sig')
    
    # 月別支出と支出日数の関係
    monthly_days = filtered_df.groupby('年月')['日付'].apply(lambda x: len(x.dt.date.unique()))
    monthly_data = pd.DataFrame({
        '月別支出': monthly_expense,
        '支出日数': monthly_days
    })
    
    fig = plt.figure(figsize=(10, 8))
    sns.scatterplot(data=monthly_data, x='支出日数', y='月別支出')
    plt.title('月別支出と支出日数の関係', fontsize=16)
    plt.xlabel('月間支出日数 (日)', fontsize=12)
    plt.ylabel('月間支出 (円)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # 回帰直線を追加
    x = monthly_data['支出日数']
    y = monthly_data['月別支出']
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    plt.plot(x, p(x), "r--")
    
    save_plot(fig, '月別支出と支出日数の関係.png')
    
    # 結果の出力
    summary_data = {
        'データ件数': len(filtered_df),
        '期間': f"{filtered_df['日付'].min().strftime('%Y/%m/%d')} 〜 {filtered_df['日付'].max().strftime('%Y/%m/%d')}",
        'カテゴリ数': len(filtered_df['カテゴリ'].unique()),
        'カード数': len(filtered_df['カード'].unique()),
        '総支出': f"{total_expense:,.0f}円",
        '月平均支出': f"{avg_expense:,.0f}円",
        '最大支出': f"{filtered_df['金額'].min() * -1:,.0f}円",
        '最小支出': f"{filtered_df['金額'].max() * -1:,.0f}円",
        '中央値支出': f"{filtered_df['金額'].median() * -1:,.0f}円",
    }
    
    # 「支出:その他」の情報を追加
    other_expense_df = filtered_df[filtered_df['カテゴリ'] == '支出:その他']
    if len(other_expense_df) > 0:
        other_expense_summary = {
            '件数': len(other_expense_df),
            '総支出': other_expense_df['金額'].sum() * -1,
        }
        other_ratio = other_expense_summary['総支出'] / total_expense * 100
        summary_data.update({
            '「支出:その他」件数': other_expense_summary['件数'],
            '「支出:その他」総支出': f"{other_expense_summary['総支出']:,.0f}円",
            '「支出:その他」の割合': f"{other_ratio:.2f}%",
        })
    
    summary_df = pd.DataFrame(list(summary_data.items()), columns=['項目', '値'])
    summary_df.to_csv(os.path.join(output_folder, '家計簿分析サマリー.csv'), index=False, encoding='utf-8-sig')
    
    # 月別支出の詳細情報をCSVに出力
    monthly_avg_per_day = monthly_expense / monthly_days
    monthly_detail = pd.DataFrame({
        '年月': monthly_expense.index,
        '支出合計(円)': monthly_expense.values,
        '支出日数(日)': monthly_days.values,
        '1日あたり平均支出(円/日)': monthly_avg_per_day.values
    })
    monthly_detail.to_csv(os.path.join(output_folder, '月別支出詳細.csv'), index=False, encoding='utf-8-sig')
    
    print(f"\n分析が完了しました。結果は{output_folder}フォルダに保存されています。")

if __name__ == "__main__":
    main()
