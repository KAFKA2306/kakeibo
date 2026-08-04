from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.kakeibo.config import Settings
from src.kakeibo.import_review import LocalImportService, create_app

SYNTHETIC_STATEMENT = (
    b"Date,Description,Amount\n"
    b"2026-08-01,PRIVATE_MERCHANT_ALPHA,100\n"
    b"2026-08-02,PRIVATE_MERCHANT_BETA,250\n"
)


def client_for(tmp_path: Path) -> tuple[TestClient, Settings]:
    app_settings = Settings(
        _env_file=None,
        input_dir=tmp_path / "local-input",
        output_dir=tmp_path / "local-output",
        log_dir=tmp_path / "local-logs",
    )
    service = LocalImportService(app_settings)
    return TestClient(create_app(service)), app_settings


def review_statement(client: TestClient):  # type: ignore[no-untyped-def]
    return client.post(
        "/review",
        content=SYNTHETIC_STATEMENT,
        headers={
            "X-Statement-Type": "transaction",
            "X-File-Suffix": ".csv",
            "Content-Type": "application/octet-stream",
        },
    )


def test_page_is_local_only_and_hides_transaction_rows(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    response = client.get("/")

    assert response.status_code == 200
    assert "LOCAL ONLY" in response.text
    assert "外部CDN・外部API・外部送信を使用しません" in response.text
    assert "個別明細" in response.text
    assert "https://" not in response.text
    assert "http://" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_review_uses_registry_and_returns_aggregate_only(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    response = review_statement(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["statement_type"] == "transaction"
    assert payload["parser"] == "TransactionHistoryCsvParser"
    assert payload["encoding"] == "utf-8"
    assert payload["source_rows"] == 2
    assert payload["output_rows"] == 2
    assert payload["dropped_rows"] == 0
    assert payload["amount_total"] == -350
    assert payload["date_min"] == "2026-08-01"
    assert payload["date_max"] == "2026-08-02"
    assert payload["transaction_rows_included"] is False
    assert "PRIVATE_MERCHANT_ALPHA" not in response.text
    assert "PRIVATE_MERCHANT_BETA" not in response.text


def test_type_suffix_mismatch_is_rejected_before_parsing(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    response = client.post(
        "/review",
        content=SYNTHETIC_STATEMENT,
        headers={
            "X-Statement-Type": "transaction",
            "X-File-Suffix": ".txt",
        },
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "statement type and suffix are incompatible"


def test_commit_requires_exact_destination_and_reconciles_output(
    tmp_path: Path,
) -> None:
    client, app_settings = client_for(tmp_path)
    review_response = review_statement(client)
    review = review_response.json()

    mismatch = client.post(
        "/commit",
        json={
            "review_token": review["review_token"],
            "destination": str(app_settings.output_dir / "different.csv"),
            "confirmed": True,
        },
    )
    assert mismatch.status_code == 409
    assert not app_settings.output_dir.joinpath("different.csv").exists()

    unconfirmed = client.post(
        "/commit",
        json={
            "review_token": review["review_token"],
            "destination": review["destination"],
            "confirmed": False,
        },
    )
    assert unconfirmed.status_code == 409

    committed = client.post(
        "/commit",
        json={
            "review_token": review["review_token"],
            "destination": review["destination"],
            "confirmed": True,
        },
    )
    assert committed.status_code == 200
    receipt = committed.json()
    assert receipt["reconciled"] is True
    assert receipt["written_rows"] == 2
    assert receipt["amount_total"] == -350
    assert receipt["transaction_rows_included"] is False
    assert Path(receipt["destination"]).is_file()
    assert "PRIVATE_MERCHANT_ALPHA" not in committed.text
    assert "PRIVATE_MERCHANT_BETA" not in committed.text

    replay = client.post(
        "/commit",
        json={
            "review_token": review["review_token"],
            "destination": review["destination"],
            "confirmed": True,
        },
    )
    assert replay.status_code == 409


def test_cancel_removes_staged_file_and_invalidates_session(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    review = review_statement(client).json()

    cancelled = client.post(
        "/cancel",
        json={"review_token": review["review_token"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json() == {"cancelled": True}

    committed = client.post(
        "/commit",
        json={
            "review_token": review["review_token"],
            "destination": review["destination"],
            "confirmed": True,
        },
    )
    assert committed.status_code == 409
