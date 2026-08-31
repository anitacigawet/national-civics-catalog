from __future__ import annotations

import importlib.util
import json
from collections import OrderedDict
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

    def test_whitespace_and_controls_are_rejected(self) -> None:
        for url in (
            "https://example.gov/meeting agenda",
            "https://example.gov/meeting\nagenda",
            "https://example.gov/meeting%0Aagenda",
        ):
            with self.subTest(url=url):
                errors = validator.validate_url(url, "url")
                self.assertTrue(any("whitespace or control" in error for error in errors))

    def test_invalid_dns_labels_are_rejected(self) -> None:
        for url in (
            "https://-bad.gov/meetings",
            "https://bad-.gov/meetings",
            "https://bad..gov/meetings",
            "https://bad_host.gov/meetings",
        ):
            with self.subTest(url=url):
                errors = validator.validate_url(url, "url")
                self.assertTrue(any("invalid DNS hostname" in error for error in errors))

    def test_url_without_hostname_returns_a_controlled_error(self) -> None:
        errors = validator.validate_url("https://", "url")
        self.assertTrue(any("DNS hostname" in error for error in errors))


class ReadmeSnapshotTests(unittest.TestCase):
    def test_repository_snapshot_counts_match_catalog(self) -> None:
        self.assertEqual(validator.validate_readme_snapshot(validator.ROOT), [])


class VersionTwoSchemaTests(unittest.TestCase):
    def test_schema_and_manual_validator_share_the_v2_contract(self) -> None:
        schema = json.loads((validator.ROOT / "schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]
        coverage = schema["$defs"]["coverageItem"]

        self.assertEqual(tuple(schema["required"]), validator.SOURCE_FIELDS)
        self.assertEqual(tuple(properties), validator.SOURCE_FIELDS)
        self.assertEqual(tuple(coverage["required"]), validator.COVER_FIELDS)
        self.assertEqual(tuple(coverage["properties"]), validator.COVER_FIELDS)
        self.assertEqual(properties["schema_version"]["const"], "2.0.0")
        self.assertEqual(set(properties["public_body_type"]["enum"]), validator.PUBLIC_BODY_TYPES)
        self.assertEqual(set(properties["meeting_source_type"]["anyOf"][1]["enum"]), validator.MEETING_SOURCE_TYPES)
        self.assertEqual(set(properties["meeting_source_access_method"]["anyOf"][1]["enum"]), validator.ACCESS_METHODS)
        self.assertEqual(set(properties["meeting_source_relationship"]["anyOf"][1]["enum"]), validator.MEETING_SOURCE_RELATIONSHIPS)
        self.assertEqual(set(properties["meeting_source_status"]["enum"]), validator.STATUSES)
        self.assertEqual(set(coverage["properties"]["type"]["enum"]), validator.PLACE_TYPES)
        self.assertEqual(
            set(coverage["properties"]["coverage_relationship"]["enum"]),
            validator.RELATIONSHIPS,
        )

        status_rule = schema["allOf"][0]
        self.assertEqual(
            status_rule["if"]["properties"]["meeting_source_status"]["const"],
            "needs_source",
        )
        for field in (
            "meeting_source_type",
            "meeting_source_url",
            "meeting_source_platform",
            "meeting_source_access_method",
            "meeting_source_relationship",
            "meeting_source_last_checked_date",
            "meeting_source_evidence_url",
        ):
            self.assertIsNone(status_rule["then"]["properties"][field]["const"])
        self.assertEqual(
            status_rule["else"]["properties"]["meeting_source_last_checked_date"]["type"],
            "string",
        )
        self.assertEqual(properties["county_names"]["items"]["maxLength"], 150)
        self.assertEqual(
            coverage["properties"]["county_names"]["items"]["maxLength"], 150
        )

    @staticmethod
    def records() -> list[OrderedDict]:
        found = []
        for path in sorted(validator.STATES.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line, object_pairs_hook=OrderedDict)
                found.append(record)
                if {item["meeting_source_status"] for item in found} >= {
                    "needs_source", "working"
                }:
                    return found
        raise AssertionError("repository lacks representative records")

    def test_needs_source_requires_roster_evidence(self) -> None:
        record = next(
            item for item in self.records()
            if item["meeting_source_status"] == "needs_source"
        )
        record["roster_source_url"] = None
        errors = validator.validate_record(record, "record", record["state_codes"][0].lower())
        self.assertTrue(any("roster_source_url is required" in error for error in errors))

    def test_identified_source_requires_meeting_evidence(self) -> None:
        record = next(
            item for item in self.records()
            if item["meeting_source_status"] == "working"
        )
        record["meeting_source_evidence_url"] = None
        errors = validator.validate_record(record, "record", record["state_codes"][0].lower())
        self.assertTrue(any("meeting_source_evidence_url" in error for error in errors))

    def test_identified_source_requires_observation_date(self) -> None:
        record = next(
            item for item in self.records()
            if item["meeting_source_status"] == "working"
        )
        record["meeting_source_last_checked_date"] = None
        errors = validator.validate_record(record, "record", record["state_codes"][0].lower())
        self.assertTrue(any("must be YYYY-MM-DD" in error for error in errors))

    def test_v1_alias_is_rejected(self) -> None:
        record = self.records()[0]
        record["provenance_url"] = record["meeting_source_evidence_url"]
        errors = validator.validate_record(record, "record", record["state_codes"][0].lower())
        self.assertTrue(any("canonical order" in error for error in errors))

    def test_json_valid_wrong_types_return_errors_instead_of_raising(self) -> None:
        record = self.records()[0]
        mutations = {
            "public_body_type": [],
            "state_codes": [{}],
            "meeting_source_status": [],
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                changed = record.copy()
                changed[field] = value
                errors = validator.validate_record(changed, "record", "az")
                self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
