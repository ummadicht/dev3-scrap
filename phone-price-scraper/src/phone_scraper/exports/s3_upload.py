from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import boto3

from phone_scraper.config import Settings

logger = logging.getLogger(__name__)


class S3Exporter:
    """Uploads bucketed CSV and manifest files to an S3-compatible bucket (AWS S3, MinIO, R2)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        client_kwargs: dict[str, Any] = {"region_name": settings.s3_region}
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
        self._client = boto3.client("s3", **client_kwargs)

    def build_key(self, local_path: Path, exports_root: Path) -> str:
        rel = local_path.resolve().relative_to(exports_root.resolve()).as_posix()
        prefix = self.settings.s3_prefix.strip("/")
        return f"{prefix}/{rel}" if prefix else rel

    def upload_file(self, local_path: Path, exports_root: Path) -> str:
        if not self.settings.s3_bucket:
            raise ValueError("S3_BUCKET must be set when S3_ENABLED=true")
        key = self.build_key(local_path, exports_root)
        self._client.upload_file(str(local_path), self.settings.s3_bucket, key)
        logger.info("Uploaded %s -> s3://%s/%s", local_path, self.settings.s3_bucket, key)
        return key
