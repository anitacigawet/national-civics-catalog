from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "census_scaffolds", ROOT / "scripts" / "build_census_source_scaffolds.py"
)
assert SPEC and SPEC.loader
scaffolds = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scaffolds)


class CensusScaffoldTests(unittest.TestCase):
    def test_placeholder_has_source_shape_without_endpoint_claim(self) -> None:
        record = scaffolds._placeholder_record(
            source_id="us-az-census-government-123456--primary-meeting-source",
            name="Example Town",
            publisher_type="municipality",
            state="AZ",
            county_names=["Example County"],
            census_geoid="0412345",
        )
        self.assertEqual(record["status"], "needs_source")
        for field in (
            "official_website_url",
            "endpoint_type",
            "url",
            "platform",
            "access_method",
            "source_relationship",
            "last_checked",
        ):
            self.assertIsNone(record[field])
        self.assertEqual(record["covers"][0]["census_geoid"], "0412345")

    def test_reviewed_geoid_suppresses_census_placeholder(self) -> None:
        placeholder = scaffolds._placeholder_record(
            source_id="us-az-census-government-123456--primary-meeting-source",
            name="Example Town",
            publisher_type="municipality",
            state="AZ",
            county_names=["Example County"],
            census_geoid="0412345",
        )
        reviewed = {
            **placeholder,
            "source_id": "us-az-example-town-primary-meeting-source",
            "status": "working",
            "url": "https://example.gov/meetings",
        }
        self.assertEqual(scaffolds._merge_existing([placeholder], [reviewed]), [reviewed])

    def test_distinct_geographies_are_retained_and_sorted(self) -> None:
        first = scaffolds._placeholder_record(
            source_id="us-az-census-government-000002--primary-meeting-source",
            name="Second Town",
            publisher_type="municipality",
            state="AZ",
            county_names=[],
            census_geoid="0400002",
        )
        second = scaffolds._placeholder_record(
            source_id="us-az-census-government-000001--primary-meeting-source",
            name="First Town",
            publisher_type="municipality",
            state="AZ",
            county_names=[],
            census_geoid="0400001",
        )
        merged = scaffolds._merge_existing([first, second], [])
        self.assertEqual(
            [record["source_id"] for record in merged],
            [second["source_id"], first["source_id"]],
        )


if __name__ == "__main__":
    unittest.main()
