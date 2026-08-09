from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class SnapshotError(ValueError):
    """Raised when a monthly snapshot cannot be reproduced safely."""


@dataclass(frozen=True)
class MonthlyTotals:
    transaction_count: int
    inflow: int
    outflow: int
    net: int

    def as_dict(self) -> dict[str, int]:
        return {
            "transaction_count": self.transaction_count,
            "inflow": self.inflow,
            "outflow": self.outflow,
            "net": self.net,
        }


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_month(month: str) -> None:
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise SnapshotError("month must use YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != month:
        raise SnapshotError("month must use YYYY-MM")


def _read_input(path: Path, month: str) -> tuple[str, int, MonthlyTotals]:
    raw = path.read_bytes()
    digest = _sha256(raw)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SnapshotError("normalized CSV must be UTF-8") from exc

    reader = csv.DictReader(text.splitlines())
    required = {"transaction_date", "amount"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise SnapshotError("normalized CSV requires transaction_date and amount")

    rows = 0
    count = 0
    inflow = 0
    outflow = 0
    for row in reader:
        rows += 1
        date_text = (row.get("transaction_date") or "").strip()
        amount_text = (row.get("amount") or "").strip()
        try:
            transaction_date = datetime.strptime(date_text, "%Y-%m-%d")
            amount = int(amount_text)
        except ValueError as exc:
            raise SnapshotError("normalized CSV contains an invalid date or amount") from exc
        if transaction_date.strftime("%Y-%m") != month:
            continue
        count += 1
        if amount >= 0:
            inflow += amount
        else:
            outflow += -amount

    return digest, rows, MonthlyTotals(count, inflow, outflow, inflow - outflow)


def build_monthly_snapshot(
    *,
    month: str,
    input_paths: list[Path],
    artifact_root: Path = Path("artifacts"),
    fx_source: str,
    fx_retrieved_at: str,
    fx_rates: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a deterministic monthly audit snapshot from normalized CSV files."""
    _validate_month(month)
    if not input_paths:
        raise SnapshotError("at least one normalized CSV is required")
    if not fx_source.strip() or not fx_retrieved_at.strip():
        raise SnapshotError("FX source and retrieved_at are required")
    try:
        datetime.fromisoformat(fx_retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotError("fx_retrieved_at must be ISO-8601") from exc

    inputs: list[dict[str, str | int]] = []
    totals = MonthlyTotals(0, 0, 0, 0)
    for path in input_paths:
        digest, rows, item = _read_input(path, month)
        inputs.append({"sha256": digest, "row_count": rows})
        totals = MonthlyTotals(
            totals.transaction_count + item.transaction_count,
            totals.inflow + item.inflow,
            totals.outflow + item.outflow,
            totals.net + item.net,
        )

    inputs.sort(key=lambda item: (str(item["sha256"]), int(item["row_count"])))
    for index, item in enumerate(inputs, start=1):
        item["input_id"] = f"input-{index:03d}"

    aggregation = {
        "schema_version": 1,
        "month": month,
        "totals": totals.as_dict(),
    }
    aggregation_bytes = _canonical_json(aggregation)
    aggregation_sha256 = _sha256(aggregation_bytes)
    metadata = {
        "schema_version": 1,
        "month": month,
        "inputs": inputs,
        "fx": {
            "source": fx_source.strip(),
            "retrieved_at": fx_retrieved_at,
            "rates": dict(sorted((fx_rates or {}).items())),
        },
        "aggregation_sha256": aggregation_sha256,
    }
    metadata_bytes = _canonical_json(metadata)

    output_dir = artifact_root / month
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregation.json").write_bytes(aggregation_bytes)
    (output_dir / "metadata.json").write_bytes(metadata_bytes)
    return {
        "output_dir": output_dir,
        "aggregation_sha256": aggregation_sha256,
        "metadata_sha256": _sha256(metadata_bytes),
    }
