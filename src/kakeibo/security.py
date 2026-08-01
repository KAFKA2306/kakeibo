from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import uuid4

_SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,8}$")


class UnsafeUploadName(ValueError):
    """Raised when an uploaded file type is unsafe or unsupported."""


def validate_upload_suffix(
    suffix: str | None,
    allowed_suffixes: tuple[str, ...],
) -> str:
    if suffix is None:
        raise UnsafeUploadName("missing upload type")

    normalized = suffix.lower().strip()
    if not _SAFE_SUFFIX.fullmatch(normalized) or normalized not in allowed_suffixes:
        raise UnsafeUploadName("unsupported upload type")
    return normalized


def opaque_file_id(file_path: Path) -> str:
    """Create a stable log identifier without exposing a path or filename."""
    return hashlib.sha256(
        file_path.name.encode("utf-8", errors="replace")
    ).hexdigest()[:12]


def private_output_name() -> str:
    """Generate an output name that cannot reveal the input filename."""
    return f"transactions-{uuid4().hex[:16]}.csv"
