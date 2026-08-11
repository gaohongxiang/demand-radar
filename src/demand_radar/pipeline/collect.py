from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from demand_radar.contracts import CollectionRequest, CollectorProvider, clean_keywords
from demand_radar.errors import ProviderUnhealthyError
from demand_radar.storage.jsonl import write_canonical_records, write_json


def run_collection(
    *,
    provider: CollectorProvider,
    project_root: Path,
    keywords: Sequence[str] = (),
    max_notes: int = 20,
    max_comments: int = 10,
    include_comments: bool = True,
    include_sub_comments: bool = False,
    options: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    actual_run_id = run_id or _run_id(provider.descriptor.name)
    raw_dir = project_root / "data" / "raw" / provider.descriptor.name / actual_run_id
    normalized_path = (
        project_root
        / "data"
        / "normalized"
        / provider.descriptor.name
        / f"{actual_run_id}.jsonl"
    )
    manifest_path = project_root / "data" / "runs" / f"{actual_run_id}.json"
    health = provider.health()
    base_manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": actual_run_id,
        "provider": provider.descriptor.name,
        "provider_role": provider.descriptor.role.value,
        "capabilities": sorted(item.value for item in provider.descriptor.capabilities),
        "health": {
            "ok": health.ok,
            "message": health.message,
            "details": dict(health.details),
        },
        "keywords": list(clean_keywords(keywords)),
        "started_at": _now(),
    }

    try:
        if not health.ok:
            raise ProviderUnhealthyError(
                f"Provider {provider.descriptor.name!r} is unhealthy: {health.message}"
            )
        request = CollectionRequest(
            run_id=actual_run_id,
            keywords=clean_keywords(keywords),
            output_dir=raw_dir,
            max_notes=max_notes,
            max_comments=max_comments,
            include_comments=include_comments,
            include_sub_comments=include_sub_comments,
            options=options or {},
        )
        result = provider.collect(request)
        counts = write_canonical_records(normalized_path, provider.normalize(result))
        manifest = {
            **base_manifest,
            "status": "success",
            "finished_at": _now(),
            "counts": counts,
            "raw_artifacts": [
                {
                    "kind": artifact.kind,
                    "path": str(artifact.path),
                    "record_count": artifact.record_count,
                }
                for artifact in result.artifacts
            ],
            "normalized_path": str(normalized_path),
            "warnings": list(result.warnings),
            "provider_metadata": dict(result.metadata),
        }
        write_json(manifest_path, manifest)
        manifest["manifest_path"] = str(manifest_path)
        return manifest
    except Exception as exc:
        failure = {
            **base_manifest,
            "status": "failed",
            "finished_at": _now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_json(manifest_path, failure)
        raise


def _run_id(provider_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{provider_name}-{uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
