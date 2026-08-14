"""Tests for the normalized four-file catalog contract."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_catalog import (  # noqa: E402
    ACCESS_METHODS,
    COVERAGE_FIELDS,
    COVERAGE_RELATIONSHIPS,
    ENDPOINT_FIELDS,
    ENDPOINT_TYPES,
    PLACE_FIELDS,
    PLACE_TYPES,
    PUBLISHER_FIELDS,
    PUBLISHER_TYPES,
    SOURCE_RELATIONSHIPS,
    USPS_SUBDIVISION_CODES,
    VERIFICATION_STATUSES,
    validate_catalog,
)


def publisher(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "publisher_id": "us-az-kingman",
        "publisher_name": "City of Kingman",
        "publisher_type": "municipality",
        "country_code": "US",
        "state_codes": ["AZ"],
        "county_names": ["Mohave County"],
        "official_website_url": "https://www.example.gov/",
    }
    record.update(overrides)
    return record


def place(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "place_id": "us-az-kingman",
        "place_name": "Kingman",
        "place_type": "municipality",
        "country_code": "US",
        "state_codes": ["AZ"],
        "county_names": ["Mohave County"],
        "ocd_division_id": "ocd-division/country:us/state:az/place:kingman",
        "census_geoid": "0437620",
    }
    record.update(overrides)
    return record


def endpoint(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "endpoint_id": "us-az-kingman--primary-meeting-source",
        "publisher_id": "us-az-kingman",
        "endpoint_type": "primary_meeting_source",
        "url": "https://calendar.example.gov/meetings",
        "platform": "custom",
        "access_method": "html",
        "source_relationship": "first_party",
        "verification_status": "verified_working",
        "provenance_url": "https://www.example.gov/meetings",
        "last_verified": "2026-08-13",
    }
    record.update(overrides)
    if "publisher_id" in overrides and "endpoint_id" not in overrides:
        record["endpoint_id"] = f"{record['publisher_id']}--primary-meeting-source"
    return record


def coverage(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "coverage_id": (
            "us-az-kingman--primary-meeting-source--covers--us-az-kingman"
        ),
        "endpoint_id": "us-az-kingman--primary-meeting-source",
        "place_id": "us-az-kingman",
        "coverage_relationship": "direct_jurisdiction",
    }
    record.update(overrides)
    if (
        ("endpoint_id" in overrides or "place_id" in overrides)
        and "coverage_id" not in overrides
    ):
        record["coverage_id"] = (
            f"{record['endpoint_id']}--covers--{record['place_id']}"
        )
    return record


class CatalogValidatorTests(unittest.TestCase):
    def validate(
        self,
        publishers: list[dict[str, Any]],
        places: list[dict[str, Any]],
        endpoints: list[dict[str, Any]],
        coverage_rows: list[dict[str, Any]],
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = {
                "publishers": root / "publishers.jsonl",
                "places": root / "places.jsonl",
                "endpoints": root / "endpoints.jsonl",
                "coverage": root / "coverage.jsonl",
            }
            for name, rows in (
                ("publishers", publishers),
                ("places", places),
                ("endpoints", endpoints),
                ("coverage", coverage_rows),
            ):
                paths[name].write_text(
                    "".join(
                        json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
                        for row in rows
                    ),
                    encoding="utf-8",
                )
            return validate_catalog(
                paths["publishers"],
                paths["places"],
                paths["endpoints"],
                paths["coverage"],
            )

    def test_valid_direct_municipal_release(self) -> None:
        self.assertEqual(
            self.validate([publisher()], [place()], [endpoint()], [coverage()]),
            [],
        )

    def test_multi_state_tribal_publisher_and_place_are_valid(self) -> None:
        publisher_record = publisher(
            publisher_id="us-navajo-nation-council",
            publisher_name="Navajo Nation Council",
            publisher_type="tribal_government",
            state_codes=["AZ", "NM", "UT"],
            county_names=[],
            official_website_url="https://www.navajonationcouncil.org/",
        )
        place_record = place(
            place_id="us-navajo-nation",
            place_name="Navajo Nation",
            place_type="tribal_jurisdiction",
            state_codes=["AZ", "NM", "UT"],
            county_names=[],
            ocd_division_id=None,
            census_geoid=None,
        )
        endpoint_record = endpoint(
            publisher_id="us-navajo-nation-council",
            endpoint_id="us-navajo-nation-council--meeting-calendar",
            endpoint_type="meeting_calendar",
            url="https://www.navajonationcouncil.org/events/",
            provenance_url="https://www.navajonationcouncil.org/events/",
        )
        coverage_record = coverage(
            endpoint_id=endpoint_record["endpoint_id"],
            place_id=place_record["place_id"],
        )
        self.assertEqual(
            self.validate(
                [publisher_record],
                [place_record],
                [endpoint_record],
                [coverage_record],
            ),
            [],
        )

    def test_first_party_community_council_representation_is_valid(self) -> None:
        publisher_record = publisher(
            publisher_id="us-az-example-community-council",
            publisher_name="Example Community Council",
            publisher_type="community_council",
            official_website_url="https://www.example.gov/",
        )
        place_record = place(
            place_id="us-az-example-community",
            place_name="Example Community",
            place_type="unincorporated_community",
            ocd_division_id=None,
            census_geoid=None,
        )
        endpoint_record = endpoint(
            publisher_id=publisher_record["publisher_id"],
            endpoint_id=(
                "us-az-example-community-council--primary-meeting-source"
            ),
            url="https://www.example.gov/meetings/",
            provenance_url="https://www.example.gov/meetings/",
        )
        coverage_record = coverage(
            endpoint_id=endpoint_record["endpoint_id"],
            place_id=place_record["place_id"],
            coverage_relationship="civic_representation",
        )
        self.assertEqual(
            self.validate(
                [publisher_record],
                [place_record],
                [endpoint_record],
                [coverage_record],
            ),
            [],
        )

    def test_contract_enums_are_exact(self) -> None:
        self.assertEqual(
            PUBLISHER_TYPES,
            {
                "municipality", "county", "tribal_government", "tribal_chapter",
                "community_council", "special_district", "other_public_body",
            },
        )
        self.assertEqual(
            PLACE_TYPES,
            {
                "municipality", "county", "tribal_jurisdiction",
                "tribal_chapter", "unincorporated_community",
                "special_district", "other",
            },
        )
        self.assertEqual(
            ENDPOINT_TYPES,
            {
                "primary_meeting_source", "meeting_calendar",
                "meeting_documents_index", "agenda_index", "minutes_index",
                "public_notices_index", "video_archive", "other",
            },
        )
        self.assertEqual(
            ACCESS_METHODS,
            {"html", "rss", "ical", "json", "xml", "pdf_index", "other"},
        )
        self.assertEqual(
            SOURCE_RELATIONSHIPS,
            {"first_party", "authorized_service"},
        )
        self.assertEqual(
            COVERAGE_RELATIONSHIPS,
            {"direct_jurisdiction", "civic_representation"},
        )

    def test_state_codes_are_nonempty_sorted_unique_and_exact(self) -> None:
        errors = self.validate(
            [publisher(state_codes=["UT", "AZ", "AZ", "ZZ"])],
            [place()],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("state_codes must not contain" in error for error in errors))
        self.assertTrue(any("state_codes must be deterministically sorted" in error for error in errors))
        self.assertTrue(any("exact USPS" in error for error in errors))

        empty_errors = self.validate(
            [publisher(state_codes=[])],
            [place()],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("must contain at least one" in error for error in empty_errors))

    def test_county_names_allow_explicit_empty_but_reject_bad_order(self) -> None:
        empty_publisher = publisher(county_names=[])
        empty_place = place(county_names=[])
        self.assertEqual(
            self.validate(
                [empty_publisher],
                [empty_place],
                [endpoint()],
                [coverage()],
            ),
            [],
        )

        errors = self.validate(
            [publisher(county_names=["Yavapai County", "Coconino County", "yavapai county"])],
            [place()],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("case-insensitive duplicates" in error for error in errors))
        self.assertTrue(any("deterministically sorted" in error for error in errors))

    def test_country_code_is_us_in_v1(self) -> None:
        errors = self.validate(
            [publisher(country_code="CA")],
            [place()],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("country_code must be 'US'" in error for error in errors))

    def test_entity_keys_are_assigned_us_keys_not_forced_to_a_state_prefix(self) -> None:
        valid = publisher(
            publisher_id="us-navajo-nation-council",
            publisher_name="Navajo Nation Council",
        )
        invalid = publisher(publisher_id="navajo-nation-council")
        valid_errors = self.validate(
            [valid],
            [place()],
            [endpoint(publisher_id=valid["publisher_id"])],
            [coverage(endpoint_id="us-navajo-nation-council--primary-meeting-source")],
        )
        self.assertFalse(any("publisher_id must be an assigned" in error for error in valid_errors))

        invalid_errors = self.validate(
            [invalid],
            [place()],
            [endpoint(publisher_id=invalid["publisher_id"])],
            [coverage(endpoint_id="navajo-nation-council--primary-meeting-source")],
        )
        self.assertTrue(any("assigned lowercase 'us-'" in error for error in invalid_errors))

    def test_endpoint_id_must_be_scoped_to_its_publisher(self) -> None:
        errors = self.validate(
            [publisher()],
            [place()],
            [endpoint(endpoint_id="us-az-mesa--primary-meeting-source")],
            [coverage(endpoint_id="us-az-mesa--primary-meeting-source")],
        )
        self.assertTrue(any("scoped to publisher_id" in error for error in errors))

    def test_coverage_id_is_the_stable_endpoint_place_pair(self) -> None:
        errors = self.validate(
            [publisher()],
            [place()],
            [endpoint()],
            [coverage(coverage_id="us-az-kingman--wrong--covers--us-az-kingman")],
        )
        self.assertTrue(any("coverage_id must be" in error for error in errors))

    def test_references_must_exist(self) -> None:
        missing_publisher = endpoint(
            publisher_id="us-az-missing",
            endpoint_id="us-az-missing--primary-meeting-source",
        )
        errors = self.validate(
            [publisher()],
            [place()],
            [missing_publisher],
            [
                coverage(
                    endpoint_id=missing_publisher["endpoint_id"],
                    place_id="us-az-missing-place",
                )
            ],
        )
        self.assertTrue(any("missing publisher_id" in error for error in errors))
        self.assertTrue(any("missing place_id" in error for error in errors))

    def test_release_rejects_orphan_publishers_places_and_endpoints(self) -> None:
        second_publisher = publisher(
            publisher_id="us-az-mesa",
            publisher_name="City of Mesa",
        )
        second_place = place(
            place_id="us-az-mesa",
            place_name="Mesa",
            ocd_division_id="ocd-division/country:us/state:az/place:mesa",
            census_geoid="0446000",
        )
        second_endpoint = endpoint(
            endpoint_id="us-az-kingman--meeting-calendar",
            endpoint_type="meeting_calendar",
        )
        errors = self.validate(
            [publisher(), second_publisher],
            [place(), second_place],
            [endpoint(), second_endpoint],
            [coverage()],
        )
        self.assertTrue(any("publisher 'us-az-mesa' has no endpoint" in error for error in errors))
        self.assertTrue(any("place 'us-az-mesa' has no coverage" in error for error in errors))
        self.assertTrue(any("endpoint 'us-az-kingman--meeting-calendar' has no coverage" in error for error in errors))

    def test_civic_representation_requires_community_council(self) -> None:
        errors = self.validate(
            [publisher()],
            [place()],
            [endpoint()],
            [coverage(coverage_relationship="civic_representation")],
        )
        self.assertTrue(any("requires a community_council" in error for error in errors))

    def test_community_council_cannot_claim_direct_jurisdiction(self) -> None:
        errors = self.validate(
            [publisher(publisher_type="community_council")],
            [place(place_type="unincorporated_community")],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("cannot claim direct_jurisdiction" in error for error in errors))

    def test_direct_jurisdiction_types_must_match(self) -> None:
        errors = self.validate(
            [publisher(publisher_type="county")],
            [place(place_type="municipality")],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("requires place type 'county'" in error for error in errors))

    def test_every_non_civic_direct_type_pair_is_supported(self) -> None:
        pairs = {
            "municipality": "municipality",
            "county": "county",
            "tribal_government": "tribal_jurisdiction",
            "tribal_chapter": "tribal_chapter",
            "special_district": "special_district",
            "other_public_body": "other",
        }
        for publisher_type, place_type in pairs.items():
            with self.subTest(publisher_type=publisher_type, place_type=place_type):
                self.assertEqual(
                    self.validate(
                        [publisher(publisher_type=publisher_type)],
                        [place(place_type=place_type)],
                        [endpoint()],
                        [coverage()],
                    ),
                    [],
                )

    def test_direct_jurisdiction_geography_must_match_when_known(self) -> None:
        errors = self.validate(
            [publisher(state_codes=["AZ"], county_names=["Mohave County"])],
            [place(state_codes=["NV"], county_names=["Clark County"])],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("state_codes must match" in error for error in errors))
        self.assertTrue(any("county_names must match" in error for error in errors))

    def test_civic_representation_geography_must_overlap_when_known(self) -> None:
        errors = self.validate(
            [
                publisher(
                    publisher_type="community_council",
                    state_codes=["AZ"],
                    county_names=["Mohave County"],
                )
            ],
            [
                place(
                    place_type="unincorporated_community",
                    state_codes=["NV"],
                    county_names=["Clark County"],
                )
            ],
            [endpoint()],
            [coverage(coverage_relationship="civic_representation")],
        )
        self.assertTrue(any("must share a state_code" in error for error in errors))
        self.assertTrue(any("must share a county_name" in error for error in errors))

    def test_external_place_identifiers_are_unique(self) -> None:
        second_place = place(
            place_id="us-az-mesa",
            place_name="Mesa",
        )
        second_coverage = coverage(place_id="us-az-mesa")
        errors = self.validate(
            [publisher()],
            [place(), second_place],
            [endpoint()],
            [coverage(), second_coverage],
        )
        self.assertTrue(any("ocd_division_id" in error and "is shared" in error for error in errors))
        self.assertTrue(any("census_geoid" in error and "is shared" in error for error in errors))

    def test_census_geoid_matches_the_schema_ascii_digit_pattern(self) -> None:
        errors = self.validate(
            [publisher()],
            [place(census_geoid="\u0660\u0664\u0663\u0667\u0666\u0662\u0660")],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(
            any("census_geoid must contain 2 to 15 ASCII digits" in error for error in errors),
            errors,
        )

    def test_exact_fields_and_canonical_order_are_required(self) -> None:
        reordered = {
            "publisher_name": "City of Kingman",
            "publisher_id": "us-az-kingman",
            "publisher_type": "municipality",
            "country_code": "US",
            "state_codes": ["AZ"],
            "county_names": ["Mohave County"],
            "official_website_url": "https://www.example.gov/",
        }
        errors = self.validate(
            [reordered],
            [place()],
            [endpoint()],
            [coverage()],
        )
        self.assertTrue(any("fields are not in canonical order" in error for error in errors))

    def test_forbidden_meeting_record_fields_are_named(self) -> None:
        record = endpoint()
        record["meeting_title"] = "A meeting record does not belong here"
        errors = self.validate(
            [publisher()],
            [place()],
            [record],
            [coverage()],
        )
        self.assertTrue(any("forbidden meeting-record fields: meeting_title" in error for error in errors))

    def test_url_requires_http_dns_shape_and_no_userinfo(self) -> None:
        unsafe_urls = (
            "file:///tmp/catalog",
            "HTTPS://example.gov/meetings",
            "https://calendar/meetings",
            "https://localhost/meetings",
            "https://127.0.0.1/meetings",
            "https://[2606:4700:4700::1111]/meetings",
            "https://user:password@example.gov/meetings",
            "https://bad_label.example.gov/meetings",
        )
        for unsafe_url in unsafe_urls:
            with self.subTest(unsafe_url=unsafe_url):
                errors = self.validate(
                    [publisher()],
                    [place()],
                    [endpoint(url=unsafe_url)],
                    [coverage()],
                )
                self.assertTrue(
                    any(
                        phrase in error
                        for error in errors
                        for phrase in (
                            "must use http or https",
                            "must use lowercase http or https",
                            "DNS-shaped hostname",
                            "must not contain credentials",
                        )
                    )
                )

    def test_special_use_and_alternate_numeric_hosts_are_rejected(self) -> None:
        unsafe_urls = (
            "https://sub.localhost/meetings",
            "https://calendar.city.local/meetings",
            "https://router.home.arpa/meetings",
            "https://hiddenservice.onion/meetings",
            "https://calendar.city.invalid/meetings",
            "https://calendar.city.test/meetings",
            "https://calendar.city.example/meetings",
            "https://calendar.city.alt/meetings",
            "https://service.arpa/meetings",
            "https://1.0.0.127.in-addr.arpa/meetings",
            "https://1.0.0.0.0.0.0.0.ip6.arpa/meetings",
            "https://example.com/meetings",
            "https://calendar.example.net/meetings",
            "https://calendar.example.org/meetings",
            "https://0x7f.0x0.0x0.0x1/meetings",
        )
        for unsafe_url in unsafe_urls:
            with self.subTest(unsafe_url=unsafe_url):
                errors = self.validate(
                    [publisher()],
                    [place()],
                    [endpoint(url=unsafe_url)],
                    [coverage()],
                )
                self.assertTrue(
                    any("DNS-shaped hostname" in error for error in errors),
                    errors,
                )

    def test_encoded_credential_path_assignments_are_rejected(self) -> None:
        unsafe_urls = (
            "https://example.gov/calendar/api_key=supersecret",
            "https://example.gov/calendar;access_token:supersecret",
            "https://example.gov/calendar/password%3Asupersecret",
            "https://example.gov/calendar/api%255Fkey%253Dsupersecret",
        )
        for unsafe_url in unsafe_urls:
            with self.subTest(unsafe_url=unsafe_url):
                errors = self.validate(
                    [publisher()],
                    [place()],
                    [endpoint(url=unsafe_url)],
                    [coverage()],
                )
                self.assertTrue(
                    any("credential-shaped path assignments" in error for error in errors),
                    errors,
                )

        self.assertEqual(
            self.validate(
                [publisher()],
                [place()],
                [endpoint(url="https://example.gov/docs/api-key-reference")],
                [coverage()],
            ),
            [],
        )

    def test_invalid_url_port_is_reported(self) -> None:
        errors = self.validate(
            [publisher()],
            [place()],
            [endpoint(url="https://example.gov:not-a-port/meetings")],
            [coverage()],
        )
        self.assertTrue(any("not a valid URL" in error for error in errors))

    def test_credential_shaped_query_and_fragment_parameters_are_rejected(self) -> None:
        for unsafe_url in (
            "https://example.gov/calendar?api_key=secret",
            "https://example.gov/calendar#/view?access_token=secret",
            "https://example.gov/calendar?client%5Fsecret=secret",
        ):
            with self.subTest(unsafe_url=unsafe_url):
                errors = self.validate(
                    [publisher()],
                    [place()],
                    [endpoint(url=unsafe_url)],
                    [coverage()],
                )
                self.assertTrue(any("credential-shaped" in error for error in errors))

    def test_single_meeting_pages_documents_and_recording_ids_are_rejected(self) -> None:
        unsafe_urls = (
            "https://example.gov/MeetingDetail.aspx?ID=42",
            "https://example.gov/meetings/42",
            "https://example.gov/archive?clip_id=42",
            "https://example.gov/agendas/2026-08-13.pdf",
            "https://example.gov/agendas/2026-08-13%2Epdf",
            "https://example.gov/agendas/2026-08-13%252Epdf",
            "https://example.gov/agendas/2026-08-13.pdf;download",
            "https://example.gov/meetingdetail.aspx;download",
            "https://example.gov/meetings;view/123",
        )
        for unsafe_url in unsafe_urls:
            with self.subTest(unsafe_url=unsafe_url):
                errors = self.validate(
                    [publisher()],
                    [place()],
                    [endpoint(url=unsafe_url)],
                    [coverage()],
                )
                self.assertTrue(
                    any(
                        phrase in error
                        for error in errors
                        for phrase in (
                            "one meeting",
                            "one meeting or recording",
                            "downloadable document or recording",
                        )
                    )
                )

    def test_document_suffix_check_does_not_overread_prose_or_query_text(self) -> None:
        for collection_url in (
            "https://example.gov/docs/pdf-reference",
            "https://example.gov/meeting-documents?filename=agenda.pdf",
        ):
            with self.subTest(collection_url=collection_url):
                self.assertEqual(
                    self.validate(
                        [publisher()],
                        [place()],
                        [endpoint(url=collection_url)],
                        [coverage()],
                    ),
                    [],
                )

    def test_collection_level_pdf_index_is_explicitly_supported(self) -> None:
        endpoint_record = endpoint(
            endpoint_id="us-az-kingman--meeting-documents-index",
            endpoint_type="meeting_documents_index",
            url="https://example.gov/meeting-documents-index.pdf",
            access_method="pdf_index",
            provenance_url="https://example.gov/meeting-documents-index.pdf",
        )
        coverage_record = coverage(endpoint_id=endpoint_record["endpoint_id"])
        self.assertEqual(
            self.validate(
                [publisher()],
                [place()],
                [endpoint_record],
                [coverage_record],
            ),
            [],
        )

    def test_verification_status_and_date_are_bounded(self) -> None:
        self.assertEqual(
            VERIFICATION_STATUSES,
            {"verified_working", "verified_empty", "source_blocked"},
        )
        for status in sorted(VERIFICATION_STATUSES):
            with self.subTest(status=status):
                self.assertEqual(
                    self.validate(
                        [publisher()],
                        [place()],
                        [endpoint(verification_status=status)],
                        [coverage()],
                    ),
                    [],
                )
        errors = self.validate(
            [publisher()],
            [place()],
            [endpoint(verification_status="timeout", last_verified="2026-02-30")],
            [coverage()],
        )
        self.assertTrue(any("verification_status must be one of" in error for error in errors))
        self.assertTrue(any("real YYYY-MM-DD date" in error for error in errors))

    def test_duplicate_ids_and_coverage_pairs_are_rejected(self) -> None:
        second_coverage = coverage(
            coverage_id=(
                "us-az-kingman--primary-meeting-source--covers--us-az-kingman-copy"
            ),
            place_id="us-az-kingman-copy",
        )
        copy_place = place(
            place_id="us-az-kingman-copy",
            place_name="Kingman copy",
            ocd_division_id=None,
            census_geoid=None,
        )
        second_coverage["place_id"] = "us-az-kingman"
        errors = self.validate(
            [publisher(), publisher()],
            [place(), copy_place],
            [endpoint(), endpoint()],
            [coverage(), second_coverage],
        )
        self.assertTrue(any("duplicate publisher_id" in error for error in errors))
        self.assertTrue(any("duplicate endpoint_id" in error for error in errors))
        self.assertTrue(any("more than one coverage record" in error for error in errors))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            publisher_path = root / "publishers.jsonl"
            place_path = root / "places.jsonl"
            endpoint_path = root / "endpoints.jsonl"
            coverage_path = root / "coverage.jsonl"
            line = json.dumps(publisher(), separators=(",", ":"))
            duplicate = line[:-1] + ',"publisher_id":"us-az-other"}'
            publisher_path.write_text(duplicate + "\n", encoding="utf-8")
            place_path.write_text(json.dumps(place()) + "\n", encoding="utf-8")
            endpoint_path.write_text(json.dumps(endpoint()) + "\n", encoding="utf-8")
            coverage_path.write_text(json.dumps(coverage()) + "\n", encoding="utf-8")
            errors = validate_catalog(
                publisher_path,
                place_path,
                endpoint_path,
                coverage_path,
            )
        self.assertTrue(any("duplicate JSON key" in error for error in errors))

    def test_each_file_must_be_nonempty_utf8_jsonl_without_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            publisher_path = root / "publishers.jsonl"
            place_path = root / "places.jsonl"
            endpoint_path = root / "endpoints.jsonl"
            coverage_path = root / "coverage.jsonl"
            publisher_path.write_text("", encoding="utf-8")
            place_path.write_text(json.dumps(place()) + "\n\n", encoding="utf-8")
            endpoint_path.write_text(json.dumps(endpoint()) + "\n", encoding="utf-8")
            coverage_path.write_text(json.dumps(coverage()) + "\n", encoding="utf-8")
            errors = validate_catalog(
                publisher_path,
                place_path,
                endpoint_path,
                coverage_path,
            )
        self.assertTrue(any("contains no records" in error for error in errors))
        self.assertTrue(any("blank lines are not allowed" in error for error in errors))

    def test_records_in_every_file_must_be_sorted_by_id(self) -> None:
        p2 = publisher(publisher_id="us-az-mesa", publisher_name="City of Mesa")
        pl2 = place(
            place_id="us-az-mesa",
            place_name="Mesa",
            ocd_division_id=None,
            census_geoid=None,
        )
        e2 = endpoint(
            publisher_id="us-az-mesa",
            endpoint_id="us-az-mesa--primary-meeting-source",
        )
        c2 = coverage(endpoint_id=e2["endpoint_id"], place_id=pl2["place_id"])
        errors = self.validate(
            [p2, publisher()],
            [pl2, place()],
            [e2, endpoint()],
            [c2, coverage()],
        )
        self.assertTrue(any("sorted by publisher_id" in error for error in errors))
        self.assertTrue(any("sorted by place_id" in error for error in errors))
        self.assertTrue(any("sorted by endpoint_id" in error for error in errors))
        self.assertTrue(any("sorted by coverage_id" in error for error in errors))

    def test_json_schemas_match_validator_fields_and_enums(self) -> None:
        schemas = {
            "publisher": json.loads((ROOT / "schemas" / "publisher.schema.json").read_text(encoding="utf-8")),
            "place": json.loads((ROOT / "schemas" / "place.schema.json").read_text(encoding="utf-8")),
            "endpoint": json.loads((ROOT / "schemas" / "endpoint.schema.json").read_text(encoding="utf-8")),
            "coverage": json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")),
        }
        self.assertEqual(tuple(schemas["publisher"]["required"]), PUBLISHER_FIELDS)
        self.assertEqual(tuple(schemas["place"]["required"]), PLACE_FIELDS)
        self.assertEqual(tuple(schemas["endpoint"]["required"]), ENDPOINT_FIELDS)
        self.assertEqual(tuple(schemas["coverage"]["required"]), COVERAGE_FIELDS)
        self.assertEqual(
            set(schemas["publisher"]["properties"]["publisher_type"]["enum"]),
            PUBLISHER_TYPES,
        )
        self.assertEqual(
            set(schemas["place"]["properties"]["place_type"]["enum"]),
            PLACE_TYPES,
        )
        self.assertEqual(
            set(schemas["endpoint"]["properties"]["endpoint_type"]["enum"]),
            ENDPOINT_TYPES,
        )
        self.assertEqual(
            set(schemas["endpoint"]["properties"]["access_method"]["enum"]),
            ACCESS_METHODS,
        )
        self.assertEqual(
            set(schemas["endpoint"]["properties"]["source_relationship"]["enum"]),
            SOURCE_RELATIONSHIPS,
        )
        self.assertEqual(
            set(schemas["endpoint"]["properties"]["verification_status"]["enum"]),
            VERIFICATION_STATUSES,
        )
        self.assertEqual(
            set(
                schemas["coverage"]["properties"]["coverage_relationship"]["enum"]
            ),
            COVERAGE_RELATIONSHIPS,
        )
        self.assertEqual(
            set(schemas["publisher"]["$defs"]["stateCodes"]["items"]["enum"]),
            USPS_SUBDIVISION_CODES,
        )
        self.assertEqual(
            set(schemas["place"]["$defs"]["stateCodes"]["items"]["enum"]),
            USPS_SUBDIVISION_CODES,
        )
        self.assertEqual(
            schemas["publisher"]["$id"],
            "urn:civic-source-catalog:publisher:v1",
        )
        self.assertEqual(schemas["place"]["$id"], "urn:civic-source-catalog:place:v1")
        self.assertEqual(schemas["endpoint"]["$id"], "urn:civic-source-catalog:endpoint:v1")
        self.assertEqual(schemas["coverage"]["$id"], "urn:civic-source-catalog:coverage:v1")

    def test_data_package_inventory_is_exactly_the_four_v1_resources(self) -> None:
        package = json.loads((ROOT / "datapackage.json").read_text(encoding="utf-8"))
        self.assertEqual(package["catalog_schema_version"], "v1")
        self.assertEqual(package["version"], "0.1.0")
        self.assertEqual(
            package["release_status"],
            "initial Arizona snapshot",
        )
        self.assertEqual(
            [
                (resource["name"], resource["path"], resource["schema"])
                for resource in package["resources"]
            ],
            [
                ("publishers", "data/publishers.jsonl", "schemas/publisher.schema.json"),
                ("places", "data/places.jsonl", "schemas/place.schema.json"),
                ("endpoints", "data/endpoints.jsonl", "schemas/endpoint.schema.json"),
                ("coverage", "data/coverage.jsonl", "schemas/coverage.schema.json"),
            ],
        )

    def test_legacy_jurisdiction_schema_is_fail_closed(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "jurisdiction.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["$id"],
            "urn:civic-source-catalog:jurisdiction:retired",
        )
        self.assertEqual(schema["not"], {})


if __name__ == "__main__":
    unittest.main()
