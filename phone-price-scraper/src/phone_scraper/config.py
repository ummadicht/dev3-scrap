from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://scraper:scraper_password@localhost:5432/phone_prices"
    )
    respect_robots_txt: bool = True
    rate_limit_min_sec: float = 1.0
    rate_limit_max_sec: float = 3.0
    max_concurrency_per_domain: int = 2
    http_timeout_sec: float = 20.0
    max_retries: int = 3
    raw_cache_dir: Path = Path("raw")
    exports_dir: Path = Path("exports")
    use_raw_cache: bool = False
    proxy_list: str = ""
    config_dir: Path = Path("config")

    # Scheduler
    schedule_cron_time: str = "02:00"
    schedule_timezone: str = "UTC"

    # Optional S3
    s3_enabled: bool = False
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_prefix: str = ""

    @property
    def proxies(self) -> list[str]:
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]


class SourceTargetConfig(BaseModel):
    enabled: bool = True
    use_playwright: bool = True
    urls: list[str] = Field(default_factory=list)


class AppYamlConfig(BaseModel):
    default_currency: str = "INR"
    respect_robots_txt: bool = True
    rate_limit_min_sec: float = 1.0
    rate_limit_max_sec: float = 3.0
    max_concurrency_per_domain: int = 2
    timeout_sec: float = 20.0
    max_retries: int = 3
    user_agents: list[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ]
    )
    proxies: list[str] = Field(default_factory=list)


class YamlSettings(BaseModel):
    app: AppYamlConfig = Field(default_factory=AppYamlConfig)
    sources: dict[str, SourceTargetConfig] = Field(default_factory=dict)


def load_yaml_settings(settings_path: Path | None = None) -> YamlSettings:
    path = settings_path or Path("config/settings.yaml")
    if not path.exists():
        return YamlSettings()
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}
    return YamlSettings.model_validate(raw)


def load_generic_api_configs(sources_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    directory = sources_dir or Path("config/sources")
    configs: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return configs
    for file_path in sorted(directory.glob("*.y*ml")):
        with file_path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}
        name = str(raw.get("name") or file_path.stem)
        if raw.get("enabled", True):
            configs[name] = raw
    return configs


def get_settings() -> Settings:
    return Settings()
