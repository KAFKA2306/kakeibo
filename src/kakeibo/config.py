from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.kakeibo.statement_types import STATEMENT_TYPES


class Settings(BaseSettings):
    """Application settings with privacy-preserving defaults."""

    model_config = SettingsConfigDict(
        env_prefix="KAKEIBO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    input_dir: Path = Path("private/input")
    output_dir: Path = Path("private/output")
    log_dir: Path = Path("private/logs")

    api_enabled: bool = False
    api_token: SecretStr | None = None
    max_upload_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1,
        le=50 * 1024 * 1024,
    )
    allowed_upload_suffixes: tuple[str, ...] = (".csv", ".txt")

    # Compatibility snapshots derived from the canonical registry. Processing
    # code does not use these dictionaries for dispatch.
    file_patterns: dict[str, str] = {
        name: spec.filename_pattern.pattern
        for name, spec in STATEMENT_TYPES.items()
        if spec.filename_pattern is not None
    }
    default_encodings: dict[str, str] = {
        name: spec.encoding for name, spec in STATEMENT_TYPES.items()
    }
    fallback_encodings: list[str] = [
        "utf-8-sig",
        "utf-8",
        "shift_jis",
        "cp932",
        "euc-jp",
        "iso-2022-jp",
    ]

    @property
    def api_ready(self) -> bool:
        if not self.api_enabled or self.api_token is None:
            return False
        return len(self.api_token.get_secret_value()) >= 32

    def public_snapshot(self) -> dict[str, object]:
        """Return non-sensitive operational settings for CLI diagnostics."""
        statement_contracts = {
            name: {
                "allowed_suffixes": spec.allowed_suffixes,
                "encoding": spec.encoding,
            }
            for name, spec in STATEMENT_TYPES.items()
        }
        return {
            "input_dir": self.input_dir.name,
            "output_dir": self.output_dir.name,
            "log_dir": self.log_dir.name,
            "api_enabled": self.api_enabled,
            "api_ready": self.api_ready,
            "max_upload_bytes": self.max_upload_bytes,
            "allowed_upload_suffixes": self.allowed_upload_suffixes,
            "statement_contracts": statement_contracts,
        }


settings = Settings()
