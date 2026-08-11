from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from demand_radar.contracts import (
    CanonicalRecord,
    Capability,
    CollectionRequest,
    CollectionResult,
    CollectorProvider,
    HealthReport,
    ProviderDescriptor,
    ProviderRole,
    RawArtifact,
)
from demand_radar.errors import ProviderDataError, ProviderExecutionError


class ManualImportCollector(CollectorProvider):
    """Fallback collector for already-normalized JSONL exports."""

    def __init__(self, *, name: str = "manual_import") -> None:
        self.name = name

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name=self.name,
            role=ProviderRole.COLLECTOR,
            capabilities=frozenset(
                {Capability.COLLECT_NOTES, Capability.COLLECT_COMMENTS}
            ),
        )

    def health(self) -> HealthReport:
        return HealthReport(True, "ready")

    def collect(self, request: CollectionRequest) -> CollectionResult:
        started_at = _now()
        raw_inputs = request.options.get("input_paths") or ()
        input_paths = tuple(Path(str(item)).expanduser().resolve() for item in raw_inputs)
        if not input_paths:
            raise ProviderExecutionError("manual_import requires at least one input path")

        request.output_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[RawArtifact] = []
        for index, source in enumerate(input_paths, start=1):
            if not source.is_file():
                raise ProviderExecutionError(f"Manual import file not found: {source}")
            destination = request.output_dir / f"{index:02d}-{source.name}"
            shutil.copy2(source, destination)
            artifacts.append(
                RawArtifact(
                    kind="canonical",
                    path=destination,
                    record_count=_count_lines(destination),
                )
            )

        return CollectionResult(
            provider=self.name,
            run_id=request.run_id,
            started_at=started_at,
            finished_at=_now(),
            artifacts=tuple(artifacts),
            metadata={"input_paths": [str(path) for path in input_paths]},
        )

    def normalize(self, result: CollectionResult) -> Iterable[CanonicalRecord]:
        for artifact in result.artifacts:
            with artifact.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        value: Any = json.loads(line)
                        if not isinstance(value, dict):
                            raise TypeError("record is not an object")
                        yield CanonicalRecord.from_dict(value)
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        raise ProviderDataError(
                            f"Invalid canonical JSONL at {artifact.path}:{line_number}: {exc}"
                        ) from exc


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
