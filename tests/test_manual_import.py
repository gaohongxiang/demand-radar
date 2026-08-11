from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from demand_radar.pipeline.collect import run_collection
from demand_radar.providers.collectors.manual_import import ManualImportCollector


FIXTURE = Path(__file__).parent / "fixtures" / "canonical.jsonl"


class ManualImportTests(unittest.TestCase):
    def test_manual_import_is_a_functional_fallback_provider(self) -> None:
        with TemporaryDirectory() as temporary:
            manifest = run_collection(
                provider=ManualImportCollector(),
                project_root=Path(temporary),
                options={"input_paths": [str(FIXTURE)]},
                run_id="manual-test",
            )

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["counts"]["note"], 1)


if __name__ == "__main__":
    unittest.main()
