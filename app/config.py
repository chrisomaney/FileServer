from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Absolute path to footage root. The app never serves files outside this tree.
    footage_root: Path = Field(default=Path("/var/lib/cctv-footage"))

    # Where user credentials are stored (JSON, argon2 hashes).
    data_dir: Path = Field(default=Path("data"))

    # Session cookie signing secret. MUST be set in production.
    session_secret: str = Field(default="change-me-generate-a-long-random-secret")

    # Cookie / session lifetime (hours).
    session_hours: int = Field(default=12, ge=1, le=168)

    # Bind address for uvicorn (behind nginx use 127.0.0.1).
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)

    # App title shown in UI.
    app_name: str = "FileServer"

    # Comma-separated media extensions allowed for inline preview.
    media_extensions: str = ".mp4,.mkv,.webm,.mov,.avi,.m4v,.jpg,.jpeg,.png,.webp,.gif"

    # Login rate limit: max failed attempts per IP before temporary lockout.
    login_max_attempts: int = Field(default=8, ge=3, le=50)
    login_lockout_seconds: int = Field(default=300, ge=30, le=3600)

    # Trust X-Forwarded-For only when behind a reverse proxy you control.
    trust_proxy_headers: bool = False

    @field_validator("footage_root", "data_dir", mode="before")
    @classmethod
    def _expand_path(cls, value: object) -> Path:
        return Path(str(value)).expanduser().resolve()

    @property
    def users_file(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def media_ext_set(self) -> set[str]:
        return {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in self.media_extensions.split(",")
            if ext.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
