from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from demand_radar.contracts import (
    CollectionRequest,
    CollectionResult,
    RawArtifact,
    RecordType,
)
from demand_radar.providers.collectors.mediacrawler import MediaCrawlerCollector


FIXTURES = Path(__file__).parent / "fixtures" / "mediacrawler"


class MediaCrawlerCollectorTests(unittest.TestCase):
    def test_command_keeps_output_outside_upstream_repo(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "MediaCrawler"
            home.mkdir()
            output = root / "demand-radar" / "data" / "raw" / "run-1"
            provider = MediaCrawlerCollector(
                name="mediacrawler", home=home, command=("python", "main.py")
            )
            request = CollectionRequest(
                run_id="run-1",
                keywords=("求推荐工具",),
                output_dir=output,
            )

            command = provider.build_command(request)

            self.assertIn(str(output.resolve()), command)
            self.assertEqual(command[command.index("--save_data_option") + 1], "jsonl")
            self.assertEqual(command[command.index("--keywords") + 1], "求推荐工具")

    def test_normalizes_notes_and_comments_to_common_schema(self) -> None:
        provider = MediaCrawlerCollector(
            name="mediacrawler", home=Path("/tmp/unused"), command=("true",)
        )
        notes = FIXTURES / "search_contents_2026-08-11.jsonl"
        comments = FIXTURES / "search_comments_2026-08-11.jsonl"
        result = CollectionResult(
            provider="mediacrawler",
            run_id="run-1",
            started_at="2026-08-11T00:00:00+00:00",
            finished_at="2026-08-11T00:01:00+00:00",
            artifacts=(
                RawArtifact("notes", notes, 1),
                RawArtifact("comments", comments, 1),
            ),
        )

        records = list(provider.normalize(result))

        self.assertEqual([record.record_type for record in records], [RecordType.NOTE, RecordType.COMMENT])
        self.assertEqual(records[0].metrics["likes"], 12_000)
        self.assertEqual(
            records[0].canonical_url,
            "https://www.xiaohongshu.com/explore/note-1",
        )
        self.assertIn("xsec_token", records[0].observed_url or "")
        self.assertEqual(records[1].note_external_id, "note-1")


if __name__ == "__main__":
    unittest.main()
