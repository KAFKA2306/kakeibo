from datetime import date

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """家計簿の取引データを表すドメインモデル"""

    transaction_date: date = Field(..., description="取引日")
    amount: int = Field(..., description="金額 (入金は正、出金は負)")
    description: str = Field(..., description="摘要")
    balance: int | None = Field(None, description="残高")
    memo: str | None = Field(None, description="メモ")
    source: str = Field(..., description="データソース (例: sony_bank, rakuten_card)")
    category: str | None = Field(None, description="カテゴリ")
    sub_category: str | None = Field(None, description="サブカテゴリ")

    class Config:
        from_attributes = True


class RawTransaction(BaseModel):
    """パース直後の生の取引データ"""

    date_str: str
    amount_str: str  # 入金・出金を統合して符号付きにするか、別フィールドにするかはパーサー次第だが、ここでは汎用的に
    deposit_str: str | None = None
    withdrawal_str: str | None = None
    description: str
    balance_str: str | None = None
    memo: str | None = None
    source: str
