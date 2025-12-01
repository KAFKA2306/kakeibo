# bank_parser.py
import os
import re
import importlib
import sys
import traceback
import chardet
import logging
import csv
import pandas as pd
from datetime import datetime
from config import (INPUT_DIR, OUTPUT_DIR, STANDARD_HEADERS, 
                   FALLBACK_ENCODINGS, FILE_PATTERNS, DEFAULT_ENCODINGS)

# ロギング設定
def setup_logging():
    """ロギング設定を初期化"""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    except NameError:
        # Jupyter環境での実行時
        log_dir = os.path.join(os.getcwd(), 'logs')
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'bank_parser_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def detect_encoding(file_path):
    """ファイルのエンコーディングを検出"""
    # BOMの検出
    with open(file_path, 'rb') as f:
        raw_data = f.read(4096)
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
    
    # chardetによる検出
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']
    
    logger.info(f"エンコーディング検出: {encoding}, 確信度: {confidence}")
    
    # 確信度が低い場合はNoneを返す
    return encoding if confidence >= 0.7 else None

def identify_file_type(filename):
    """ファイル名からファイルタイプを識別"""
    for file_type, pattern in FILE_PATTERNS.items():
        if re.search(pattern, filename, re.IGNORECASE):
            return file_type
    return None

def get_parser_module(file_type):
    """パーサーモジュールを取得"""
    try:
        module_name = f"parsers.{file_type}_parser"
        return importlib.import_module(module_name)
    except ImportError as e:
        logger.warning(f"警告: {file_type}用のパーサーモジュールが見つかりません: {e}")
        return None

def get_file_preview(file_path, encoding):
    """ファイルのプレビュー（列名とデータ先頭）を取得"""
    try:
        # CSVファイルの場合
        if file_path.lower().endswith('.csv'):
            try:
                df = pd.read_csv(file_path, encoding=encoding, nrows=5)
                return {
                    'columns': list(df.columns),
                    'head': df.head(3).to_dict('records')
                }
            except Exception:
                # 通常のCSV読み込みで失敗した場合、低レベルの読み込みを試行
                with open(file_path, 'r', encoding=encoding) as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])
                    rows = [next(reader, []) for _ in range(3)]
                return {
                    'columns': headers,
                    'head': rows
                }
        
        # テキストファイルの場合
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [line.strip() for line in f.readlines()[:5]]
                
            # タブ区切りの場合は分割
            if lines and '\t' in lines[0]:
                headers = lines[0].split('\t')
                rows = [line.split('\t') for line in lines[1:4]]
                return {
                    'columns': headers,
                    'head': rows
                }
            else:
                return {
                    'columns': ['テキスト'],
                    'head': lines[:3]
                }
    
    except Exception as e:
        logger.error(f"ファイルプレビュー取得エラー: {e}")
        return {'columns': [], 'head': []}

def process_file(input_file, output_file=None):
    """ファイルを処理"""
    # ファイルの存在確認
    if not os.path.isfile(input_file):
        logger.error(f"エラー: ファイルが存在しません: {input_file}")
        return False
    
    # ファイル処理開始
    logger.info(f"==== 処理開始: {input_file} ====")
    
    # ファイルタイプの識別
    file_type = identify_file_type(os.path.basename(input_file))
    if not file_type:
        logger.error(f"エラー: ファイルタイプを識別できません: {input_file}")
        return False
    
    logger.info(f"ファイルタイプ: {file_type}")
    
    # パーサーモジュールの取得
    parser_module = get_parser_module(file_type)
    if not parser_module:
        return False
    
    logger.info(f"使用パーサー: {parser_module.__name__}")
    
    # 出力ファイル名の設定
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}.csv")
    
    # 出力ディレクトリの作成
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # エンコーディングの検出と処理
    encoding = detect_encoding(input_file) or DEFAULT_ENCODINGS.get(file_type, 'utf-8')
    logger.info(f"使用エンコーディング: {encoding}")
    
    # ファイルのプレビュー情報を取得
    try:
        preview = get_file_preview(input_file, encoding)
        logger.info(f"ファイル列名: {preview['columns']}")
        logger.info(f"データプレビュー: {preview['head']}")
    except Exception as e:
        logger.warning(f"プレビュー取得失敗: {e}")
    
    # ファイル処理の試行
    return try_parse_file(parser_module, input_file, output_file, encoding)

def try_parse_file(parser_module, input_file, output_file, encoding):
    """ファイル解析を試行（フォールバック処理含む）"""
    try:
        # メイン処理
        parser_module.parse_and_save(input_file, output_file, encoding)
        logger.info(f"処理完了: {input_file} -> {output_file}")
        
        # 出力ファイルのプレビュー
        try:
            output_preview = get_file_preview(output_file, 'utf-8-sig')
            logger.info(f"出力ファイル列名: {output_preview['columns']}")
            logger.info(f"出力データプレビュー: {output_preview['head']}")
        except Exception:
            pass
        
        return True
    
    except Exception as e:
        logger.error(f"エラー: {e}")
        logger.error(traceback.format_exc())
        
        # フォールバックエンコーディングで再試行
        for fallback_encoding in FALLBACK_ENCODINGS:
            if fallback_encoding != encoding:
                try:
                    logger.info(f"{fallback_encoding}で再試行...")
                    parser_module.parse_and_save(input_file, output_file, fallback_encoding)
                    logger.info(f"処理完了: {input_file} -> {output_file} ({fallback_encoding})")
                    return True
                except Exception:
                    continue
        
        return False

def process_directory(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    """ディレクトリ内のすべてのファイルを処理"""
    logger.info(f"入力ディレクトリ: {input_dir}")
    logger.info(f"出力ディレクトリ: {output_dir}")
    
    # ディレクトリの存在確認
    if not os.path.isdir(input_dir):
        logger.error(f"エラー: 入力ディレクトリが存在しません: {input_dir}")
        return
    
    # 出力ディレクトリの作成
    os.makedirs(output_dir, exist_ok=True)
    
    # 処理対象ファイルの取得
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    logger.info(f"処理対象ファイル数: {len(files)}")
    
    # 処理結果のカウント
    success_count = error_count = skipped_count = 0
    
    # ファイル処理
    for filename in files:
        input_path = os.path.join(input_dir, filename)
        
        # ファイルタイプの識別
        file_type = identify_file_type(filename)
        if not file_type:
            logger.warning(f"スキップ: サポートされていないファイル形式: {filename}")
            skipped_count += 1
            continue
        
        # 出力ファイル名の設定
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(output_dir, f"{base_name}.csv")
        
        # ファイル処理
        if process_file(input_path, output_path):
            success_count += 1
        else:
            error_count += 1
    
    logger.info(f"処理完了: 成功={success_count}, 失敗={error_count}, スキップ={skipped_count}")

def main():
    """メイン処理"""
    logger.info("=== 処理を開始します ===")
    
    # Jupyter環境での実行か判定
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            logger.info("Jupyter環境で実行しています")
    except ImportError:
        pass
    
    process_directory()
    logger.info("=== 処理を終了します ===")

# 実行
if __name__ == "__main__" or 'ipykernel' in sys.modules:
    main()
