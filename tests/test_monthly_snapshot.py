from pathlib import Path

import pytest

from src.kakeibo.monthly_snapshot import SnapshotError, build_monthly_snapshot


def _write_csv(path: Path, rows: list[tuple[str, int]]) -> None:
    lines = ["transaction_date,amount,description,balance,memo,source"]
    lines.extend(f"{day},{amount},x,,,fixture" for day, amount in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_same_input_produces_identical_snapshot(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized.csv"
    _write_csv(
        input_path,
        [("2026-07-01", 1000), ("2026-07-02", -250), ("2026-06-30", 999)],
    )
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    kwargs = {
        "month": "2026-07",
        "input_paths": [input_path],
        "fx_source": "fixture://fx",
        "fx_retrieved_at": "2026-08-10T00:00:00Z",
        "fx_rates": {"USDJPY": "147.25"},
    }

    first = build_monthly_snapshot(artifact_root=first_root, **kwargs)
    second = build_monthly_snapshot(artifact_root=second_root, **kwargs)

    assert first["aggregation_sha256"] == second["aggregation_sha256"]
    assert first["metadata_sha256"] == second["metadata_sha256"]
    assert (first_root / "2026-07" / "aggregation.json").read_bytes() == (
        second_root / "2026-07" / "aggregation.json"
    ).read_bytes()
    assert (first_root / "2026-07" / "metadata.json").read_bytes() == (
        second_root / "2026-07" / "metadata.json"
    ).read_bytes()


def test_snapshot_records_hash_totals_and_fx_provenance(tmp_path: Path) -> None:
    input_path = tmp_path / "private-name.csv"
    _write_csv(input_path, [("2026-07-01", 1000), ("2026-07-02", -250)])

    result = build_monthly_snapshot(
        month="2026-07",
        input_paths=[input_path],
        artifact_root=tmp_path / "artifacts",
        fx_source="https://example.invalid/fx",
        fx_retrieved_at="2026-08-10T00:00:00Z",
        fx_rates={"EURJPY": "171.00"},
    )

    output = result["output_dir"]
    aggregation = (output / "aggregation.json").read_text(encoding="utf-8")
    metadata = (output / "metadata.json").read_text(encoding="utf-8")
    assert '"transaction_count":2' in aggregation
    assert '"inflow":1000' in aggregation
    assert '"outflow":250' in aggregation
    assert '"net":750' in aggregation
    assert '"source":"https://example.invalid/fx"' in metadata
    assert '"retrieved_at":"2026-08-10T00:00:00Z"' in metadata
    assert '"EURJPY":"171.00"' in metadata
    assert "private-name.csv" not in metadata


def test_invalid_month_and_csv_fail_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("date,value\n2026-07-01,1\n", encoding="utf-8")

    with pytest.raises(SnapshotError):
        build_monthly_snapshot(
            month="2026-7",
            input_paths=[bad],
            artifact_root=tmp_path / "artifacts",
            fx_source="fixture://fx",
            fx_retrieved_at="2026-08-10T00:00:00Z",
        )

    with pytest.raises(SnapshotError):
        build_monthly_snapshot(
            month="2026-07",
            input_paths=[bad],
            artifact_root=tmp_path / "artifacts",
            fx_source="fixture://fx",
            fx_retrieved_at="2026-08-10T00:00:00Z",
        )
