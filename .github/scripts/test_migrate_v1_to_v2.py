from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("migrate_v1_to_v2.py")
SPEC = importlib.util.spec_from_file_location("catalog_migrator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
migrator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migrator)


def v1_record(status: str) -> dict:
    identified = status != "needs_source"
    return {
        "source_id": "us-az-example--primary-meeting-source",
        "publisher_name": "Example",
        "publisher_type": "municipality",
        "state_codes": ["AZ"],
        "county_names": ["Example County"],
        "official_website_url": "https://example.gov/" if identified else None,
        "endpoint_type": "agenda_index" if identified else None,
        "url": "https://example.gov/agendas" if identified else None,
        "platform": "custom website" if identified else None,
        "access_method": "html" if identified else None,
        "source_relationship": "first_party" if identified else None,
        "status": status,
        "last_checked": "2026-08-30" if identified else None,
        "provenance_url": (
            "https://example.gov/council" if identified
            else "https://www.census.gov/example"
        ),
        "covers": [{
            "name": "Example",
            "type": "municipality",
            "state_codes": ["AZ"],
            "county_names": ["Example County"],
            "relationship": "direct_jurisdiction",
            "ocd_division_id": None,
            "census_geoid": "0400001",
        }],
    }


class MigrationTests(unittest.TestCase):
    def test_needs_source_provenance_becomes_roster_source(self) -> None:
        old = v1_record("needs_source")
        new = migrator.migrate_record(old)
        self.assertEqual(new["roster_source_url"], old["provenance_url"])
        self.assertIsNone(new["meeting_source_evidence_url"])
        self.assertEqual(migrator.restore_v1_record(new), old)

    def test_identified_provenance_becomes_meeting_evidence(self) -> None:
        old = v1_record("working")
        new = migrator.migrate_record(old)
        self.assertIsNone(new["roster_source_url"])
        self.assertEqual(new["meeting_source_evidence_url"], old["provenance_url"])
        self.assertEqual(migrator.restore_v1_record(new), old)

    def test_every_v1_field_is_removed(self) -> None:
        new = migrator.migrate_record(v1_record("working"))
        self.assertEqual(tuple(new), migrator.V2_FIELDS)
        self.assertFalse(set(new) & {"source_id", "publisher_name", "provenance_url", "covers"})

    def test_duplicate_v1_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            states = root / "states"
            states.mkdir()
            payload = json.dumps(v1_record("working"), separators=(",", ":"))
            payload = payload.replace(
                '{"source_id":',
                '{"source_id":"duplicate","source_id":',
                1,
            )
            (states / "az.jsonl").write_text(payload + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                migrator.migrate_catalog(root, apply=False)

    def test_identified_v1_record_requires_check_date(self) -> None:
        old = v1_record("working")
        old["last_checked"] = None
        with self.assertRaisesRegex(ValueError, "requires last_checked"):
            migrator.migrate_record(old)


if __name__ == "__main__":
    unittest.main()
