from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def raw_record_sha256(*, rendered_html: str, rendered_text: str) -> str:
    """Hash the rendered evidence payload without source-specific parsing."""
    payload = {
        "rendered_html": rendered_html,
        "rendered_text": rendered_text,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def semantic_sha256(rows: Sequence[Any]) -> str:
    """Hash normalized rows deterministically for replay verification."""
    return hashlib.sha256(_canonical_json_bytes(rows)).hexdigest()
