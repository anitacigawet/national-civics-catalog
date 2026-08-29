from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("validate_catalog.py")
SPEC = importlib.util.spec_from_file_location("catalog_validator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class UrlEncodingTests(unittest.TestCase):
    def test_percent_encoded_zero_width_character_is_rejected(self) -> None:
        errors = validator.validate_url(
            "https://example.gov/meetings%E2%80%8B",
            "url",
        )
        self.assertTrue(any("Unicode format characters" in error for error in errors))

    def test_recursive_percent_encoding_is_rejected(self) -> None:
        errors = validator.validate_url(
            "https://example.gov/?order=Display%2525252525252525252Bname",
            "url",
        )
        self.assertTrue(any("recursive percent-encoding" in error for error in errors))

    def test_ordinary_percent_encoding_is_allowed(self) -> None:
        self.assertEqual(
            validator.validate_url("https://example.gov/meeting%20agendas", "url"),
            [],
        )


class ReadmeSnapshotTests(unittest.TestCase):
    def test_repository_snapshot_counts_match_catalog(self) -> None:
        self.assertEqual(validator.validate_readme_snapshot(validator.ROOT), [])


if __name__ == "__main__":
    unittest.main()
