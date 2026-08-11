from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from demand_radar.config import load_config


class ConfigTests(unittest.TestCase):
    def test_paths_are_resolved_from_project_root(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_dir = root / "project" / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "providers.yaml"
            config_path.write_text(
                """\
version: 1
project_root: ..
collectors:
  source:
    adapter: mediacrawler
    enabled: true
    home: ../MediaCrawler
""",
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.project_root, (root / "project").resolve())
            self.assertEqual(
                config.resolve_path(config.collectors["source"].options["home"]),
                (root / "MediaCrawler").resolve(),
            )


if __name__ == "__main__":
    unittest.main()
