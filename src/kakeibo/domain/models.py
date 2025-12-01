from datetime import date
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class Transaction(BaseModel):
    """家計簿の取引データを表すドメインモデル"""
    transaction_date: date = Field(..., description="取引日")
    amount: int = Field(..., description="金額 (入金は正、出金は負)")
    description: str = Field(..., description="摘要")
    balance: Optional[int] = Field(None, description="残高")
    memo: Optional[str] = Field(None, description="メモ")
    source: str = Field(..., description="データソース (例: sony_bank, rakuten_card)")
    category: Optional[str] = Field(None, description="カテゴリ")
    sub_category: Optional[str] = Field(None, description="サブカテゴリ")

    class Config:
        from_attributes = True

class RawTransaction(BaseModel):
    """パース直後の生の取引データ"""
    date_str: str
    amount_str: str # 入金・出金を統合して符号付きにするか、別フィールドにするかはパーサー次第だが、ここでは汎用的に
    deposit_str: Optional[str] = None
    withdrawal_str: Optional[str] = None
    description: str
    balance_str: Optional[str] = None
    memo: Optional[str] = None
    source: str
