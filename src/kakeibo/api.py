from __future__ import annotations

import secrets
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel

from src.kakeibo.config import settings
from src.kakeibo.statement_types import (
    InvalidStatementSuffix,
    UnknownStatementType,
    statement_spec,
)
from src.kakeibo.use_cases.process_file import ProcessFileUseCase

app = FastAPI(
    title="Kakeibo API",
    description="Private bank statement processing endpoint",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class ProcessResponse(BaseModel):
    message: str
    processed_files: int
    statement_type: str


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if not settings.api_ready or settings.api_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Processing endpoint is disabled",
        )

    expected = settings.api_token.get_secret_value()
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


async def _save_request_limited(request: Request, destination: Path) -> None:
    total = 0
    try:
        with destination.open("xb") as buffer:
            async for chunk in request.stream():
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Upload exceeds the configured size limit",
                    )
                buffer.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is empty",
        )


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process_file(
    request: Request,
    x_file_suffix: Annotated[str | None, Header(alias="X-File-Suffix")],
    x_statement_type: Annotated[str | None, Header(alias="X-Statement-Type")],
    _: Annotated[None, Depends(require_api_key)],
) -> ProcessResponse:
    try:
        spec = statement_spec(x_statement_type, x_file_suffix)
    except UnknownStatementType as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported statement type",
        ) from exc
    except InvalidStatementSuffix as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Statement type and suffix are incompatible",
        ) from exc

    use_case = ProcessFileUseCase()

    with tempfile.TemporaryDirectory(prefix="kakeibo-private-") as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"
        input_dir.mkdir(mode=0o700)

        destination = input_dir / f"upload{spec.allowed_suffixes[0]}"
        await _save_request_limited(request, destination)
        success = use_case.execute(
            destination,
            output_dir,
            source_type=spec.name,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Statement processing failed",
            )

        return ProcessResponse(
            message="Processing complete",
            processed_files=1,
            statement_type=spec.name,
        )
