import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.release import changelog_section, normalize_tag, read_collection_version, validate


class ReleaseMetadataTests(unittest.TestCase):
    def test_normalize_tag(self):
        self.assertEqual(normalize_tag("v1.5.0"), "1.5.0")
        self.assertEqual(normalize_tag("refs/tags/v1.5.0"), "1.5.0")

    def test_invalid_tag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "vMAJOR.MINOR.PATCH"):
            normalize_tag("release-1.5")

    def test_read_collection_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "galaxy.yml"
            path.write_text("namespace: mraibo\nversion: 1.5.0\n", encoding="utf-8")
            self.assertEqual(read_collection_version(path), "1.5.0")

    def test_changelog_section_stops_at_next_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(
                "# Changelog\n\n## 1.5.0 — 2026-07-14\n\n- New feature.\n\n"
                "## 1.4.0 — 2026-07-01\n\n- Old feature.\n",
                encoding="utf-8",
            )
            self.assertEqual(changelog_section(path, "1.5.0"), "- New feature.\n")

    def test_validate_requires_matching_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "galaxy.yml").write_text("version: 1.5.0\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 1.5.0\n\n- Ready.\n",
                encoding="utf-8",
            )
            archive, notes = validate("v1.5.0", root)
            self.assertEqual(archive, "mraibo-yacompress-1.5.0.tar.gz")
            self.assertEqual(notes, "- Ready.\n")

            with self.assertRaisesRegex(ValueError, "does not match"):
                validate("v1.6.0", root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
