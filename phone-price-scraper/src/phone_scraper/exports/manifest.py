from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    csv_path: Path,
    *,
    row_count: int,
    run_ids: list[int | str],
    source: str,
    granularity: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write sidecar manifest.json alongside a bucketed export."""
    manifest_path = csv_path.parent / "manifest.json"
    checksum = file_sha256(csv_path)
    unique_runs = sorted({str(r) for r in run_ids})
    payload: dict[str, Any] = {
        "file": csv_path.name,
        "source": source,
        "granularity": granularity,
        "row_count": row_count,
        "sha256": checksum,
        "run_ids": unique_runs,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    if extra:
        payload.update(extra)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path
