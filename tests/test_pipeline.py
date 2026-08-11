from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
import json
import unittest

from demand_radar.contracts import (
    CanonicalRecord,
    Capability,
    CollectionRequest,
    CollectionResult,
    CollectorProvider,
    HealthReport,
    ProviderDescriptor,
    ProviderRole,
    RecordType,
)
from demand_radar.errors import EmptyCollectionError
from demand_radar.pipeline.collect import run_collection


class FakeCollector(CollectorProvider):
    def __init__(self, records: list[CanonicalRecord]) -> None:
        self.records = records

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="fake",
            role=ProviderRole.COLLECTOR,
            capabilities=frozenset({Capability.COLLECT_NOTES}),
        )

    def health(self) -> HealthReport:
        return HealthReport(True, "ready", {"revision": "abc123"})

    def collect(self, request: CollectionRequest) -> CollectionResult:
        return CollectionResult(
            provider="fake",
            run_id=request.run_id,
            started_at="2026-08-11T00:00:00+00:00",
            finished_at="2026-08-11T00:01:00+00:00",
            artifacts=(),
        )

    def normalize(self, result: CollectionResult) -> Iterable[CanonicalRecord]:
        yield from self.records


class PipelineTests(unittest.TestCase):
    def test_successful_collection_writes_normalized_data_and_manifest(self) -> None:
        record = CanonicalRecord(
            record_type=RecordType.NOTE,
            platform="xhs",
            provider="fake",
            external_id="note-1",
            collected_at="2026-08-11T00:01:00+00:00",
            text="有需求",
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = run_collection(
                provider=FakeCollector([record]),
                project_root=root,
                keywords=["需求"],
                run_id="test-success",
            )

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["counts"], {"note": 1})
            self.assertTrue(Path(manifest["normalized_path"]).is_file())
            self.assertTrue(Path(manifest["manifest_path"]).is_file())

    def test_zero_notes_is_recorded_as_failure(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(EmptyCollectionError):
                run_collection(
                    provider=FakeCollector([]),
                    project_root=root,
                    run_id="test-empty",
                )

            manifest_path = root / "data" / "runs" / "test-empty.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["error_type"], "EmptyCollectionError")
            self.assertFalse(
                (root / "data" / "normalized" / "fake" / "test-empty.jsonl").exists()
            )


if __name__ == "__main__":
    unittest.main()
