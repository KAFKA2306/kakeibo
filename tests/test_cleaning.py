import polars as pl

from src.kakeibo.domain.cleaning import CleaningPipeline


def test_cleaning_pipeline_basic():
    pipeline = CleaningPipeline()

    # テストデータ (Raw)
    data = {
        "raw_date": ["2023年10月01日", "2023/10/05"],
        "raw_deposit": ["100,000", None],
        "raw_withdrawal": [None, "5,000"],
        "raw_description": ["給与", "スーパー"],
        "raw_balance": ["1,000,000", "995,000"],
        "raw_memo": [None, "メモ"],
    }
    df = pl.DataFrame(data)

    clean_df = pipeline.process(df, source="test")

    assert clean_df.shape == (2, 6)
    assert clean_df["amount"][0] == 100000
    assert clean_df["amount"][1] == -5000
    assert str(clean_df["transaction_date"][0]) == "2023-10-01"
    assert str(clean_df["transaction_date"][1]) == "2023-10-05"
    assert clean_df["source"][0] == "test"
