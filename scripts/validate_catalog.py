"""Validate a four-file Civic Source Catalog release without dependencies."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLISHERS = ROOT / "data" / "publishers.jsonl"
DEFAULT_PLACES = ROOT / "data" / "places.jsonl"
DEFAULT_ENDPOINTS = ROOT / "data" / "endpoints.jsonl"
DEFAULT_COVERAGE = ROOT / "data" / "coverage.jsonl"

PUBLISHER_FIELDS = (
    "publisher_id",
    "publisher_name",
    "publisher_type",
    "country_code",
    "state_codes",
    "county_names",
    "official_website_url",
)
PLACE_FIELDS = (
    "place_id",
    "place_name",
    "place_type",
    "country_code",
    "state_codes",
    "county_names",
    "ocd_division_id",
    "census_geoid",
)
ENDPOINT_FIELDS = (
    "endpoint_id",
    "publisher_id",
    "endpoint_type",
    "url",
    "platform",
    "access_method",
    "source_relationship",
    "verification_status",
    "provenance_url",
    "last_verified",
)
COVERAGE_FIELDS = (
    "coverage_id",
    "endpoint_id",
    "place_id",
    "coverage_relationship",
)

PUBLISHER_TYPES = {
    "municipality",
    "county",
    "tribal_government",
    "tribal_chapter",
    "community_council",
    "special_district",
    "other_public_body",
}
PLACE_TYPES = {
    "municipality",
    "county",
    "tribal_jurisdiction",
    "tribal_chapter",
    "unincorporated_community",
    "special_district",
    "other",
}
ENDPOINT_TYPES = {
    "primary_meeting_source",
    "meeting_calendar",
    "meeting_documents_index",
    "agenda_index",
    "minutes_index",
    "public_notices_index",
    "video_archive",
    "other",
}
ACCESS_METHODS = {"html", "rss", "ical", "json", "xml", "pdf_index", "other"}
SOURCE_RELATIONSHIPS = {"first_party", "authorized_service"}
COVERAGE_RELATIONSHIPS = {"direct_jurisdiction", "civic_representation"}
VERIFICATION_STATUSES = {"verified_working", "verified_empty", "source_blocked"}

USPS_SUBDIVISION_CODES = {
    "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
    "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
    "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI", "WV",
    "WY",
}

ENTITY_ID_RE = re.compile(r"^us-[a-z0-9]+(?:-[a-z0-9]+)*$")
ENDPOINT_ID_RE = re.compile(
    r"^us-[a-z0-9]+(?:-[a-z0-9]+)*--[a-z0-9]+(?:-[a-z0-9]+)*$"
)
COVERAGE_ID_RE = re.compile(
    r"^us-[a-z0-9]+(?:-[a-z0-9]+)*--[a-z0-9]+(?:-[a-z0-9]+)*"
    r"--covers--us-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
CENSUS_GEOID_RE = re.compile(r"^[0-9]{2,15}$")
DOCUMENT_SUFFIXES = {
    ".doc", ".docx", ".m4a", ".mov", ".mp3", ".mp4", ".pdf", ".ppt",
    ".pptx", ".srt", ".vtt", ".wav", ".xls", ".xlsx",
}
CREDENTIAL_PARAMETER_RE = re.compile(
    r"(?:^|[?&#;])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|"
    r"password|passwd|secret|client[_-]?secret|signature|sig|credential)="
)
CREDENTIAL_PATH_ASSIGNMENT_RE = re.compile(
    r"(?:^|[/;])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|"
    r"password|passwd|secret|client[_-]?secret|signature|sig|credential)[=:]",
    re.IGNORECASE,
)
SINGLE_RECORD_PATH_RE = re.compile(
    r"(?:^|/)(?:meeting[_-]?details?|meetingdetail(?:\.aspx)?|"
    r"events?/\d+|meetings?/\d+|recordings?/\d+|clips?/\d+)(?:/|$)",
    re.IGNORECASE,
)
SINGLE_RECORD_PARAMETER_RE = re.compile(
    r"(?:^|[?&#;])(?:meeting[_-]?id|event[_-]?id|clip[_-]?id)=",
    re.IGNORECASE,
)
DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
NUMERIC_HOST_LABEL_RE = re.compile(r"^(?:[0-9]+|0x[0-9a-f]+)$", re.IGNORECASE)
SPECIAL_USE_DNS_SUFFIXES = (
    "localhost",
    "local",
    "arpa",
    "onion",
    "invalid",
    "test",
    "example",
    "alt",
    "example.com",
    "example.net",
    "example.org",
)
FORBIDDEN_MEETING_FIELDS = {
    "meeting_id", "meeting_title", "meeting_date", "meeting_time",
    "meeting_location", "meeting_status", "agenda_url", "minutes_url",
    "video_url", "agenda_packet_url", "transcript", "captions", "summary",
    "decision", "quotation",
}
DIRECT_TYPE_PAIRS = {
    "municipality": "municipality",
    "county": "county",
    "tribal_government": "tribal_jurisdiction",
    "tribal_chapter": "tribal_chapter",
    "special_district": "special_district",
    "other_public_body": "other",
}


class DuplicateJsonKeyError(ValueError):
    """Raised when one JSON object repeats a key."""


def _ordered_object(pairs: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
    value: OrderedDict[str, Any] = OrderedDict()
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKeyError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r}")


def _record_label(path: Path, line_number: int) -> str:
    return f"{path.as_posix()}:{line_number}"


def _load_jsonl(path: Path) -> tuple[list[tuple[int, OrderedDict[str, Any]]], list[str]]:
    records: list[tuple[int, OrderedDict[str, Any]]] = []
    if not path.is_file():
        return records, [f"{path.as_posix()}: file does not exist"]

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return records, [f"{path.as_posix()}: cannot read UTF-8 JSONL: {exc}"]
    if not text.strip():
        return records, [f"{path.as_posix()}: catalog file contains no records"]

    errors: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        label = _record_label(path, line_number)
        if not raw_line.strip():
            errors.append(f"{label}: blank lines are not allowed")
            continue
        try:
            value = json.loads(
                raw_line,
                object_pairs_hook=_ordered_object,
                parse_constant=_reject_nonfinite,
            )
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: invalid JSON: {exc.msg}")
            continue
        except (DuplicateJsonKeyError, ValueError) as exc:
            errors.append(f"{label}: invalid JSON: {exc}")
            continue
        if not isinstance(value, OrderedDict):
            errors.append(f"{label}: each line must be a JSON object")
            continue
        records.append((line_number, value))
    return records, errors


def _require_field_order(
    record: OrderedDict[str, Any],
    expected: tuple[str, ...],
    label: str,
) -> list[str]:
    actual = tuple(record.keys())
    if actual == expected:
        return []

    missing = [field for field in expected if field not in record]
    extra = [field for field in actual if field not in expected]
    forbidden = sorted(set(actual) & FORBIDDEN_MEETING_FIELDS)
    details: list[str] = []
    if forbidden:
        details.append(f"forbidden meeting-record fields: {', '.join(forbidden)}")
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    if not details:
        details.append("fields are not in canonical order")
    return [f"{label}: {'; '.join(details)}"]


def _required_text(value: Any, field: str, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label}: {field} must be a non-empty string"]
    if value != value.strip():
        return [f"{label}: {field} must not have leading or trailing whitespace"]
    return []


def _nullable_text(value: Any, field: str, label: str) -> list[str]:
    if value is None:
        return []
    return _required_text(value, field, label)


def _validate_entity_id(value: Any, field: str, label: str) -> list[str]:
    errors = _required_text(value, field, label)
    if isinstance(value, str) and not ENTITY_ID_RE.fullmatch(value):
        errors.append(
            f"{label}: {field} must be an assigned lowercase 'us-' kebab-case key"
        )
    return errors


def _validate_sorted_text_array(
    value: Any,
    field: str,
    label: str,
    *,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        return [f"{label}: {field} must be an array"]
    errors: list[str] = []
    if not allow_empty and not value:
        errors.append(f"{label}: {field} must contain at least one value")

    normalized: list[str] = []
    for index, item in enumerate(value):
        item_errors = _required_text(item, f"{field}[{index}]", label)
        errors.extend(item_errors)
        if not item_errors and isinstance(item, str):
            normalized.append(item)

    folded = [item.casefold() for item in normalized]
    if len(folded) != len(set(folded)):
        errors.append(f"{label}: {field} must not contain case-insensitive duplicates")
    expected_order = sorted(normalized, key=lambda item: (item.casefold(), item))
    if normalized != expected_order:
        errors.append(f"{label}: {field} must be deterministically sorted")
    return errors


def _validate_state_codes(value: Any, label: str) -> list[str]:
    errors = _validate_sorted_text_array(
        value,
        "state_codes",
        label,
        allow_empty=False,
    )
    if isinstance(value, list):
        for index, code in enumerate(value):
            if isinstance(code, str) and code not in USPS_SUBDIVISION_CODES:
                errors.append(
                    f"{label}: state_codes[{index}] must be an exact USPS state or territory code"
                )
    return errors


def _validate_county_names(value: Any, label: str) -> list[str]:
    return _validate_sorted_text_array(
        value,
        "county_names",
        label,
        allow_empty=True,
    )


def _dns_hostname_is_public_shape(hostname: str) -> bool:
    if len(hostname) > 253 or "." not in hostname:
        return False
    labels = hostname.split(".")
    if any(not DNS_LABEL_RE.fullmatch(label) for label in labels):
        return False
    if any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in SPECIAL_USE_DNS_SUFFIXES
    ):
        return False
    if all(NUMERIC_HOST_LABEL_RE.fullmatch(label) for label in labels):
        return False
    return not labels[-1].isdigit()


def _bounded_percent_decode(value: str, *, rounds: int = 3) -> str:
    """Decode nested percent escapes without an unbounded normalization loop."""

    decoded = value
    for _ in range(rounds):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def _safe_http_url(
    value: Any,
    field: str,
    label: str,
    *,
    reject_documents: bool,
    allowed_document_suffixes: frozenset[str] = frozenset(),
) -> list[str]:
    errors = _required_text(value, field, label)
    if errors:
        return errors

    assert isinstance(value, str)
    if len(value) > 4096:
        return [f"{label}: {field} exceeds 4096 characters"]
    if any(character.isspace() for character in value):
        return [f"{label}: {field} must not contain whitespace"]

    try:
        parsed = urlsplit(value)
        hostname_value = parsed.hostname
        parsed.port
    except ValueError as exc:
        return [f"{label}: {field} is not a valid URL: {exc}"]

    if parsed.scheme not in {"http", "https"}:
        errors.append(f"{label}: {field} must use http or https")
    elif not value.startswith(("http://", "https://")):
        errors.append(f"{label}: {field} must use lowercase http or https")
    if not hostname_value:
        errors.append(f"{label}: {field} must include a hostname")
        return errors
    if parsed.username is not None or parsed.password is not None:
        errors.append(f"{label}: {field} must not contain credentials")

    query_and_fragment = _bounded_percent_decode(
        f"?{parsed.query}#{parsed.fragment}"
    ).lower()
    if CREDENTIAL_PARAMETER_RE.search(query_and_fragment):
        errors.append(
            f"{label}: {field} must not contain credential-shaped query or fragment parameters"
        )

    decoded_path = _bounded_percent_decode(parsed.path)
    if CREDENTIAL_PATH_ASSIGNMENT_RE.search(decoded_path):
        errors.append(
            f"{label}: {field} must not contain credential-shaped path assignments"
        )

    hostname = hostname_value.lower().rstrip(".")
    if hostname.endswith(".internal") or hostname == "internal":
        errors.append(f"{label}: {field} must not use a local hostname")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if not _dns_hostname_is_public_shape(hostname):
            errors.append(
                f"{label}: {field} must use a DNS-shaped hostname that is not "
                "special-use or local"
            )
    else:
        errors.append(
            f"{label}: {field} must use a DNS-shaped hostname, not an IP address"
        )

    decoded_path_without_parameters = "/".join(
        segment.split(";", 1)[0]
        for segment in decoded_path.lower().split("/")
    )
    suffix = PurePosixPath(decoded_path_without_parameters).suffix
    if (
        reject_documents
        and suffix in DOCUMENT_SUFFIXES
        and suffix not in allowed_document_suffixes
    ):
        errors.append(
            f"{label}: {field} points to a downloadable document or recording, "
            "not a collection endpoint"
        )

    if reject_documents and SINGLE_RECORD_PATH_RE.search(
        decoded_path_without_parameters
    ):
        errors.append(f"{label}: {field} appears to point to one meeting's detail page")
    if reject_documents and SINGLE_RECORD_PARAMETER_RE.search(query_and_fragment):
        errors.append(f"{label}: {field} appears to identify one meeting or recording")
    return errors


def _validate_country_and_geography(record: OrderedDict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    country_code = record["country_code"]
    errors.extend(_required_text(country_code, "country_code", label))
    if country_code != "US":
        errors.append(f"{label}: country_code must be 'US' in catalog schema v1")
    errors.extend(_validate_state_codes(record["state_codes"], label))
    errors.extend(_validate_county_names(record["county_names"], label))
    return errors


def _validate_publisher(record: OrderedDict[str, Any], label: str) -> list[str]:
    errors = _require_field_order(record, PUBLISHER_FIELDS, label)
    if errors:
        return errors

    errors.extend(_validate_entity_id(record["publisher_id"], "publisher_id", label))
    errors.extend(_required_text(record["publisher_name"], "publisher_name", label))
    publisher_type = record["publisher_type"]
    if not isinstance(publisher_type, str) or publisher_type not in PUBLISHER_TYPES:
        errors.append(
            f"{label}: publisher_type must be one of {', '.join(sorted(PUBLISHER_TYPES))}"
        )
    errors.extend(_validate_country_and_geography(record, label))

    website = record["official_website_url"]
    if website is not None:
        errors.extend(
            _safe_http_url(
                website,
                "official_website_url",
                label,
                reject_documents=True,
            )
        )
    return errors


def _validate_place(record: OrderedDict[str, Any], label: str) -> list[str]:
    errors = _require_field_order(record, PLACE_FIELDS, label)
    if errors:
        return errors

    errors.extend(_validate_entity_id(record["place_id"], "place_id", label))
    errors.extend(_required_text(record["place_name"], "place_name", label))
    place_type = record["place_type"]
    if not isinstance(place_type, str) or place_type not in PLACE_TYPES:
        errors.append(f"{label}: place_type must be one of {', '.join(sorted(PLACE_TYPES))}")
    errors.extend(_validate_country_and_geography(record, label))

    ocd_division_id = record["ocd_division_id"]
    errors.extend(_nullable_text(ocd_division_id, "ocd_division_id", label))
    if isinstance(ocd_division_id, str) and not ocd_division_id.startswith("ocd-division/"):
        errors.append(f"{label}: ocd_division_id must begin with 'ocd-division/'")

    census_geoid = record["census_geoid"]
    errors.extend(_nullable_text(census_geoid, "census_geoid", label))
    if isinstance(census_geoid, str) and not CENSUS_GEOID_RE.fullmatch(census_geoid):
        errors.append(f"{label}: census_geoid must contain 2 to 15 ASCII digits")
    return errors


def _validate_endpoint(record: OrderedDict[str, Any], label: str) -> list[str]:
    errors = _require_field_order(record, ENDPOINT_FIELDS, label)
    if errors:
        return errors

    endpoint_id = record["endpoint_id"]
    publisher_id = record["publisher_id"]
    errors.extend(_required_text(endpoint_id, "endpoint_id", label))
    if isinstance(endpoint_id, str) and not ENDPOINT_ID_RE.fullmatch(endpoint_id):
        errors.append(
            f"{label}: endpoint_id must use '<publisher-id>--<stable-slug>' lowercase form"
        )
    errors.extend(_validate_entity_id(publisher_id, "publisher_id", label))
    if (
        isinstance(endpoint_id, str)
        and isinstance(publisher_id, str)
        and not endpoint_id.startswith(f"{publisher_id}--")
    ):
        errors.append(f"{label}: endpoint_id must be scoped to publisher_id")

    endpoint_type = record["endpoint_type"]
    if not isinstance(endpoint_type, str) or endpoint_type not in ENDPOINT_TYPES:
        errors.append(f"{label}: endpoint_type must be one of {', '.join(sorted(ENDPOINT_TYPES))}")

    access_method = record["access_method"]
    if not isinstance(access_method, str) or access_method not in ACCESS_METHODS:
        errors.append(f"{label}: access_method must be one of {', '.join(sorted(ACCESS_METHODS))}")
    allowed_documents = frozenset({".pdf"}) if access_method == "pdf_index" else frozenset()

    errors.extend(
        _safe_http_url(
            record["url"],
            "url",
            label,
            reject_documents=True,
            allowed_document_suffixes=allowed_documents,
        )
    )
    errors.extend(_required_text(record["platform"], "platform", label))

    source_relationship = record["source_relationship"]
    if (
        not isinstance(source_relationship, str)
        or source_relationship not in SOURCE_RELATIONSHIPS
    ):
        errors.append(
            f"{label}: source_relationship must be one of "
            f"{', '.join(sorted(SOURCE_RELATIONSHIPS))}"
        )

    verification_status = record["verification_status"]
    if (
        not isinstance(verification_status, str)
        or verification_status not in VERIFICATION_STATUSES
    ):
        errors.append(
            f"{label}: verification_status must be one of "
            f"{', '.join(sorted(VERIFICATION_STATUSES))}"
        )

    errors.extend(
        _safe_http_url(
            record["provenance_url"],
            "provenance_url",
            label,
            reject_documents=True,
            allowed_document_suffixes=allowed_documents,
        )
    )

    last_verified = record["last_verified"]
    if last_verified is not None:
        if not isinstance(last_verified, str):
            errors.append(f"{label}: last_verified must be an ISO date or null")
        else:
            try:
                parsed_date = date.fromisoformat(last_verified)
            except ValueError:
                errors.append(f"{label}: last_verified must use a real YYYY-MM-DD date")
            else:
                if parsed_date.isoformat() != last_verified:
                    errors.append(f"{label}: last_verified must use canonical YYYY-MM-DD form")
    return errors


def _validate_coverage(record: OrderedDict[str, Any], label: str) -> list[str]:
    errors = _require_field_order(record, COVERAGE_FIELDS, label)
    if errors:
        return errors

    coverage_id = record["coverage_id"]
    endpoint_id = record["endpoint_id"]
    place_id = record["place_id"]

    errors.extend(_required_text(coverage_id, "coverage_id", label))
    if isinstance(coverage_id, str) and not COVERAGE_ID_RE.fullmatch(coverage_id):
        errors.append(
            f"{label}: coverage_id must use "
            "'<endpoint-id>--covers--<place-id>' lowercase form"
        )
    errors.extend(_required_text(endpoint_id, "endpoint_id", label))
    if isinstance(endpoint_id, str) and not ENDPOINT_ID_RE.fullmatch(endpoint_id):
        errors.append(f"{label}: endpoint_id is not a valid catalog endpoint key")
    errors.extend(_validate_entity_id(place_id, "place_id", label))
    if isinstance(coverage_id, str) and isinstance(endpoint_id, str) and isinstance(place_id, str):
        expected_id = f"{endpoint_id}--covers--{place_id}"
        if coverage_id != expected_id:
            errors.append(f"{label}: coverage_id must be {expected_id!r}")

    relationship = record["coverage_relationship"]
    if (
        not isinstance(relationship, str)
        or relationship not in COVERAGE_RELATIONSHIPS
    ):
        errors.append(
            f"{label}: coverage_relationship must be one of "
            f"{', '.join(sorted(COVERAGE_RELATIONSHIPS))}"
        )
    return errors


def _register_unique(
    rows: list[tuple[int, OrderedDict[str, Any]]],
    path: Path,
    id_field: str,
    validator: Any,
    errors: list[str],
) -> tuple[dict[str, OrderedDict[str, Any]], list[str]]:
    records: dict[str, OrderedDict[str, Any]] = {}
    order: list[str] = []
    for line_number, record in rows:
        label = _record_label(path, line_number)
        errors.extend(validator(record, label))
        record_id = record.get(id_field)
        if isinstance(record_id, str):
            if record_id in records:
                errors.append(f"{label}: duplicate {id_field} {record_id!r}")
            else:
                records[record_id] = record
                order.append(record_id)
    if order != sorted(order):
        errors.append(f"{path.as_posix()}: records must be sorted by {id_field}")
    return records, order


def _normalized_counties(record: OrderedDict[str, Any]) -> set[str] | None:
    value = record.get("county_names")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return {item.casefold() for item in value}


def _normalized_states(record: OrderedDict[str, Any]) -> set[str] | None:
    value = record.get("state_codes")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return set(value)


def _validate_coverage_semantics(
    coverage: OrderedDict[str, Any],
    label: str,
    endpoint: OrderedDict[str, Any],
    publisher: OrderedDict[str, Any],
    place: OrderedDict[str, Any],
) -> list[str]:
    errors: list[str] = []
    relationship = coverage.get("coverage_relationship")
    publisher_type = publisher.get("publisher_type")
    place_type = place.get("place_type")

    if publisher.get("country_code") != place.get("country_code"):
        errors.append(f"{label}: publisher and place country_code values do not match")

    publisher_states = _normalized_states(publisher)
    place_states = _normalized_states(place)
    publisher_counties = _normalized_counties(publisher)
    place_counties = _normalized_counties(place)

    if relationship == "civic_representation":
        if publisher_type != "community_council":
            errors.append(
                f"{label}: civic_representation requires a community_council publisher"
            )
        if (
            publisher_states is not None
            and place_states is not None
            and not publisher_states.intersection(place_states)
        ):
            errors.append(
                f"{label}: civic_representation publisher and place must share a state_code"
            )
        if (
            publisher_counties
            and place_counties
            and not publisher_counties.intersection(place_counties)
        ):
            errors.append(
                f"{label}: civic_representation publisher and place must share a county_name"
            )
    elif relationship == "direct_jurisdiction":
        expected_place_type = DIRECT_TYPE_PAIRS.get(publisher_type)
        if expected_place_type is None:
            errors.append(
                f"{label}: {publisher_type!r} cannot claim direct_jurisdiction coverage"
            )
        elif place_type != expected_place_type:
            errors.append(
                f"{label}: direct_jurisdiction publisher type {publisher_type!r} "
                f"requires place type {expected_place_type!r}, not {place_type!r}"
            )
        if (
            publisher_states is not None
            and place_states is not None
            and publisher_states != place_states
        ):
            errors.append(
                f"{label}: direct_jurisdiction publisher and place state_codes must match"
            )
        if (
            publisher_counties
            and place_counties
            and publisher_counties != place_counties
        ):
            errors.append(
                f"{label}: direct_jurisdiction publisher and place county_names must match"
            )

    if endpoint.get("publisher_id") != publisher.get("publisher_id"):
        errors.append(f"{label}: endpoint publisher reference is internally inconsistent")
    return errors


def validate_catalog(
    publishers_path: Path,
    places_path: Path,
    endpoints_path: Path,
    coverage_path: Path,
) -> list[str]:
    """Return every structural, safety, reference, or semantic release error."""

    publisher_rows, errors = _load_jsonl(publishers_path)
    place_rows, load_errors = _load_jsonl(places_path)
    errors.extend(load_errors)
    endpoint_rows, load_errors = _load_jsonl(endpoints_path)
    errors.extend(load_errors)
    coverage_rows, load_errors = _load_jsonl(coverage_path)
    errors.extend(load_errors)

    publishers, _ = _register_unique(
        publisher_rows,
        publishers_path,
        "publisher_id",
        _validate_publisher,
        errors,
    )
    places, _ = _register_unique(
        place_rows,
        places_path,
        "place_id",
        _validate_place,
        errors,
    )
    endpoints, _ = _register_unique(
        endpoint_rows,
        endpoints_path,
        "endpoint_id",
        _validate_endpoint,
        errors,
    )
    coverage, _ = _register_unique(
        coverage_rows,
        coverage_path,
        "coverage_id",
        _validate_coverage,
        errors,
    )

    external_ids: dict[tuple[str, str], str] = {}
    for place_id, record in places.items():
        for field in ("ocd_division_id", "census_geoid"):
            value = record.get(field)
            if not isinstance(value, str):
                continue
            key = (field, value)
            prior = external_ids.get(key)
            if prior is not None:
                errors.append(
                    f"{places_path.as_posix()}: {field} {value!r} is shared by "
                    f"{prior!r} and {place_id!r}"
                )
            else:
                external_ids[key] = place_id

    publisher_endpoint_counts = {publisher_id: 0 for publisher_id in publishers}
    endpoint_coverage_counts = {endpoint_id: 0 for endpoint_id in endpoints}
    place_coverage_counts = {place_id: 0 for place_id in places}
    coverage_pairs: set[tuple[str, str]] = set()

    for endpoint_id, record in endpoints.items():
        publisher_id = record.get("publisher_id")
        if isinstance(publisher_id, str):
            if publisher_id not in publishers:
                errors.append(
                    f"{endpoints_path.as_posix()}: endpoint {endpoint_id!r} references "
                    f"missing publisher_id {publisher_id!r}"
                )
            else:
                publisher_endpoint_counts[publisher_id] += 1

    for coverage_id, record in coverage.items():
        endpoint_id = record.get("endpoint_id")
        place_id = record.get("place_id")
        endpoint = endpoints.get(endpoint_id) if isinstance(endpoint_id, str) else None
        place = places.get(place_id) if isinstance(place_id, str) else None

        if endpoint is None and isinstance(endpoint_id, str):
            errors.append(
                f"{coverage_path.as_posix()}: coverage {coverage_id!r} references "
                f"missing endpoint_id {endpoint_id!r}"
            )
        if place is None and isinstance(place_id, str):
            errors.append(
                f"{coverage_path.as_posix()}: coverage {coverage_id!r} references "
                f"missing place_id {place_id!r}"
            )

        if isinstance(endpoint_id, str) and isinstance(place_id, str):
            pair = (endpoint_id, place_id)
            if pair in coverage_pairs:
                errors.append(
                    f"{coverage_path.as_posix()}: endpoint/place pair {pair!r} "
                    "has more than one coverage record"
                )
            else:
                coverage_pairs.add(pair)

        if endpoint is not None:
            endpoint_coverage_counts[endpoint_id] += 1
        if place is not None:
            place_coverage_counts[place_id] += 1

        if endpoint is None or place is None:
            continue
        publisher_id = endpoint.get("publisher_id")
        publisher = publishers.get(publisher_id) if isinstance(publisher_id, str) else None
        if publisher is None:
            continue
        errors.extend(
            _validate_coverage_semantics(
                record,
                f"{coverage_path.as_posix()}:{coverage_id}",
                endpoint,
                publisher,
                place,
            )
        )

    for publisher_id, count in publisher_endpoint_counts.items():
        if count == 0:
            errors.append(
                f"{publishers_path.as_posix()}: publisher {publisher_id!r} has no endpoint"
            )
    for endpoint_id, count in endpoint_coverage_counts.items():
        if count == 0:
            errors.append(
                f"{endpoints_path.as_posix()}: endpoint {endpoint_id!r} has no coverage"
            )
    for place_id, count in place_coverage_counts.items():
        if count == 0:
            errors.append(f"{places_path.as_posix()}: place {place_id!r} has no coverage")

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publishers", type=Path, default=DEFAULT_PUBLISHERS)
    parser.add_argument("--places", type=Path, default=DEFAULT_PLACES)
    parser.add_argument("--endpoints", type=Path, default=DEFAULT_ENDPOINTS)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    errors = validate_catalog(
        args.publishers,
        args.places,
        args.endpoints,
        args.coverage,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Civic Source Catalog validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
