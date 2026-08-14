from __future__ import annotations

import copy
import importlib.util
import json
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_validator", ROOT / "scripts" / "validate_catalog.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _base_record() -> dict:
    return {
        "source_id": "us-az-example-town--meeting-calendar",
        "publisher_name": "Example Town",
        "publisher_type": "municipality",
        "state_codes": ["AZ"],
        "county_names": ["Example County"],
        "official_website_url": "https://samplecity.gov",
        "endpoint_type": "meeting_calendar",
        "url": "https://meetings.samplecity.gov/calendar",
        "platform": "civicplus",
        "access_method": "html",
        "source_relationship": "authorized_service",
        "status": "working",
        "last_checked": "2026-08-14",
        "provenance_url": "https://samplecity.gov/meetings",
        "covers": [{
            "name": "Example Town",
            "type": "municipality",
            "state_codes": ["AZ"],
            "county_names": ["Example County"],
            "relationship": "direct_jurisdiction",
            "ocd_division_id": None,
            "census_geoid": "0400001",
        }],
    }


class CatalogValidatorTests(unittest.TestCase):
    def _write(self, records: list[dict], state: str = "az") -> Path:
        root = ROOT / "operator_only" / "validator_test_runs" / uuid.uuid4().hex
        target = root / state / "sources.jsonl"
        target.parent.mkdir(parents=True)
        target.write_text(
            "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
            encoding="utf-8",
            newline="\n",
        )
        return root

    def test_checked_in_arizona_catalog_is_valid(self) -> None:
        count, errors = validator.validate_catalog(ROOT / "data" / "states")
        self.assertEqual(88, count)
        self.assertEqual([], errors)

    def test_minimal_record_is_valid(self) -> None:
        count, errors = validator.validate_catalog(self._write([_base_record()]))
        self.assertEqual(1, count)
        self.assertEqual([], errors)

    def test_duplicate_source_id_fails(self) -> None:
        record = _base_record()
        count, errors = validator.validate_catalog(self._write([record, copy.deepcopy(record)]))
        self.assertEqual(2, count)
        self.assertTrue(any("source_id duplicates" in error for error in errors))

    def test_state_folder_must_match_first_state_code(self) -> None:
        _, errors = validator.validate_catalog(self._write([_base_record()], state="ny"))
        self.assertTrue(any("file must live under the first state code" in error for error in errors))

    def test_meeting_fields_are_rejected(self) -> None:
        record = _base_record()
        record["meeting_title"] = "One meeting"
        _, errors = validator.validate_catalog(self._write([record]))
        self.assertTrue(any("unexpected meeting_title" in error for error in errors))

    def test_bad_status_fails(self) -> None:
        record = _base_record()
        record["status"] = "healthy"
        _, errors = validator.validate_catalog(self._write([record]))
        self.assertTrue(any("unsupported status" in error for error in errors))

    def test_credentials_and_single_records_fail(self) -> None:
        credential = _base_record()
        credential["url"] = "https://meetings.samplecity.gov/calendar/api_key:secret"
        single = _base_record()
        single["source_id"] = "us-az-second-town--meeting-calendar"
        single["url"] = "https://meetings.samplecity.gov/meetingdetail.aspx;download"
        _, errors = validator.validate_catalog(self._write([credential, single]))
        self.assertTrue(any("credential material" in error for error in errors))
        self.assertTrue(any("one meeting" in error for error in errors))

    def test_ip_and_download_urls_fail(self) -> None:
        ip_record = _base_record()
        ip_record["url"] = "https://8.8.8.8/calendar"
        pdf_record = _base_record()
        pdf_record["source_id"] = "us-az-second-town--meeting-calendar"
        pdf_record["url"] = "https://meetings.samplecity.gov/agendas/meeting%252Epdf"
        _, errors = validator.validate_catalog(self._write([ip_record, pdf_record]))
        self.assertTrue(any("IP literal" in error for error in errors))
        self.assertTrue(any("downloadable artifact" in error for error in errors))

    def test_multistate_source_lives_under_first_code(self) -> None:
        record = _base_record()
        record["source_id"] = "us-navajo-nation--primary-meeting-source"
        record["publisher_name"] = "Navajo Nation"
        record["publisher_type"] = "tribal_government"
        record["state_codes"] = ["AZ", "NM", "UT"]
        record["county_names"] = []
        record["covers"][0].update({
            "name": "Navajo Nation",
            "type": "tribal_jurisdiction",
            "state_codes": ["AZ", "NM", "UT"],
            "county_names": [],
            "census_geoid": None,
        })
        count, errors = validator.validate_catalog(self._write([record], state="az"))
        self.assertEqual(1, count)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
