from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with privacy-preserving defaults."""

    model_config = SettingsConfigDict(
        env_prefix="KAKEIBO_",
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

    file_patterns: dict[str, str] = {
        "sony": r"sony_.*\.txt$",
        "enavi": r"enavi\d{6}\(\d+\)\.csv$",
        "aplus": r"aplus_meisai_\d+_\d{6}\.csv$",
        "generic": r"\d{6}\.csv$",
        "transaction": r"transaction-history\.csv$",
    }

    default_encodings: dict[str, str] = {
        "sony": "utf-8-sig",
        "enavi": "utf-8-sig",
        "aplus": "utf-8-sig",
        "generic": "shift_jis",
        "transaction": "utf-8",
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
        return {
            "input_dir": self.input_dir.name,
            "output_dir": self.output_dir.name,
            "log_dir": self.log_dir.name,
            "api_enabled": self.api_enabled,
            "api_ready": self.api_ready,
            "max_upload_bytes": self.max_upload_bytes,
            "allowed_upload_suffixes": self.allowed_upload_suffixes,
        }


settings = Settings()
