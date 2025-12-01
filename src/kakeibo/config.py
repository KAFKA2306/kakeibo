from pydantic import DirectoryPath
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """アプリケーション設定"""

    input_dir: DirectoryPath = r"M:\DB\kakeibo\input"
    output_dir: str = r"M:\DB\kakeibo\clean"
    log_dir: str = "logs"

    # ファイル名パターン設定
    file_patterns: dict[str, str] = {
        "sony": r"sony_.*\.txt$",
        "enavi": r"enavi\d{6}\(\d+\)\.csv$",
        "aplus": r"aplus_meisai_\d+_\d{6}\.csv$",
        "generic": r"\d{6}\.csv$",
        "transaction": r"transaction-history\.csv$",
    }

    # エンコーディング設定
    default_encodings: dict[str, str] = {
        "sony": "utf-8-sig",
        "enavi": "utf-8-sig",
        "aplus": "utf-8-sig",
        "generic": "shift_jis",
        "transaction": "utf-8",
    }

    fallback_encodings: list[str] = [
        "utf-8-sig",
        "utf-8",
        "shift_jis",
        "cp932",
        "euc-jp",
        "iso-2022-jp",
    ]

    class Config:
        env_prefix = "KAKEIBO_"


settings = Settings()
