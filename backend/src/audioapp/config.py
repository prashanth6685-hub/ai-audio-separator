"""Environment-driven configuration. All tunables live here; see .env.example."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUDIOAPP_", env_file=".env", extra="ignore")

    app_name: str = "AI Audio Separator"
    api_prefix: str = "/api/v1"

    # Storage
    data_dir: Path = Field(default=Path("data"))

    # Upload limits
    max_upload_mb: int = 200
    max_duration_s: int = 600  # 10 minutes per file for MVP

    # Retention (hours)
    upload_ttl_hours: int = 2
    results_ttl_hours: int = 24

    # Worker
    separator_workers: int = 1  # keep 1 on CPU; raise only with GPU workers
    max_retries: int = 1
    job_timeout_s: int = 3600
    retention_sweep_s: int = 300

    # Model
    demucs_model: str = "htdemucs"  # htdemucs | htdemucs_ft | htdemucs_6s
    device: str = "auto"  # auto | cpu | cuda

    # Server
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
