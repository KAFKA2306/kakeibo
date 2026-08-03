from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.kakeibo.adapters.parsers.profiled_csv import (
    AplusCsvParser,
    EnaviCsvParser,
    TransactionHistoryCsvParser,
)
from src.kakeibo.adapters.parsers.sony import SonyBankParser
from src.kakeibo.api import app
from src.kakeibo.config import settings
from src.kakeibo.statement_types import (
    InvalidStatementSuffix,
    UnknownStatementType,
    infer_statement_type,
    statement_spec,
)
from src.kakeibo.use_cases.process_file import ProcessFileUseCase


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "api_enabled", True)
    monkeypatch.setattr(settings, "api_token", SecretStr("x" * 32))
    return TestClient(app)


@pytest.mark.parametrize(
    ("statement_type", "expected_parser", "expected_encoding"),
    [
        ("sony", SonyBankParser, "utf-8-sig"),
        ("enavi", EnaviCsvParser, "utf-8-sig"),
        ("aplus", AplusCsvParser, "utf-8-sig"),
        ("transaction", TransactionHistoryCsvParser, "utf-8"),
    ],
)
def test_processing_plan_is_explicit(
    statement_type: str,
    expected_parser: type,
    expected_encoding: str,
) -> None:
    suffix = ".txt" if statement_type == "sony" else ".csv"
    plan = ProcessFileUseCase().processing_plan(statement_type, suffix)
    assert isinstance(plan.parser, expected_parser)
    assert plan.encoding == expected_encoding
    assert plan.source_type == statement_type


def test_unknown_type_and_invalid_suffix_fail_closed() -> None:
    with pytest.raises(UnknownStatementType):
        statement_spec("unknown-bank", ".csv")
    with pytest.raises(InvalidStatementSuffix):
        statement_spec("sony", ".csv")
    with pytest.raises(InvalidStatementSuffix):
        statement_spec("transaction", ".txt")


def test_arbitrary_txt_is_not_inferred_as_sony() -> None:
    assert infer_statement_type("notes.txt") is None
    assert infer_statement_type("sony_202608.txt") == "sony"


def test_cli_inference_and_api_plan_are_identical() -> None:
    use_case = ProcessFileUseCase()
    inferred = use_case.infer_source_type("transaction-history.csv")
    assert inferred == "transaction"
    cli_plan = use_case.processing_plan(inferred, ".csv")
    api_plan = use_case.processing_plan("transaction", ".csv")
    assert type(cli_plan.parser) is type(api_plan.parser)
    assert cli_plan.encoding == api_plan.encoding == "utf-8"


@pytest.mark.parametrize("statement_type", ["enavi", "transaction"])
def test_api_preserves_explicit_type_without_original_filename(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    statement_type: str,
) -> None:
    captured: dict[str, object] = {}

    def fake_execute(
        self: ProcessFileUseCase,
        file_path: Path,
        output_dir: Path | None = None,
        *,
        source_type: str | None = None,
    ) -> bool:
        del self, output_dir
        captured["temporary_name"] = file_path.name
        captured["source_type"] = source_type
        return True

    monkeypatch.setattr(ProcessFileUseCase, "execute", fake_execute)
    response = api_client.post(
        "/process",
        content="Date,Description,Amount\n2026-08-01,synthetic,100\n",
        headers={
            "X-API-Key": "x" * 32,
            "X-File-Suffix": ".csv",
            "X-Statement-Type": statement_type,
        },
    )

    assert response.status_code == 200
    assert response.json()["statement_type"] == statement_type
    assert captured == {
        "temporary_name": "upload.csv",
        "source_type": statement_type,
    }
    assert "transaction-history.csv" not in response.text
    assert "enavi" not in response.text or statement_type == "enavi"


def test_api_rejects_unknown_or_incompatible_contract(api_client: TestClient) -> None:
    common = {
        "X-API-Key": "x" * 32,
        "X-File-Suffix": ".csv",
    }
    unknown = api_client.post(
        "/process",
        content="synthetic",
        headers={**common, "X-Statement-Type": "unknown"},
    )
    incompatible = api_client.post(
        "/process",
        content="synthetic",
        headers={**common, "X-Statement-Type": "sony"},
    )
    assert unknown.status_code == 415
    assert incompatible.status_code == 415
    assert "synthetic" not in unknown.text
    assert "synthetic" not in incompatible.text
