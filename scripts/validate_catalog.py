"""Validate the state-organized National Civics Catalog without dependencies."""

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
DEFAULT_DATA_ROOT = ROOT / "data" / "states"

SOURCE_FIELDS = (
    "source_id",
    "publisher_name",
    "publisher_type",
    "state_codes",
    "county_names",
    "official_website_url",
    "endpoint_type",
    "url",
    "platform",
    "access_method",
    "source_relationship",
    "status",
    "last_checked",
    "provenance_url",
    "covers",
)
COVER_FIELDS = (
    "name",
    "type",
    "state_codes",
    "county_names",
    "relationship",
    "ocd_division_id",
    "census_geoid",
)
PUBLISHER_TYPES = {
    "state", "county", "municipality", "township", "school_district",
    "special_district", "tribal_government", "tribal_chapter",
    "community_council", "civic_body", "other",
}
PLACE_TYPES = {
    "state", "county", "municipality", "township",
    "unincorporated_community", "school_district", "special_district",
    "tribal_jurisdiction", "tribal_chapter", "other",
}
ENDPOINT_TYPES = {
    "primary_meeting_source", "meeting_calendar", "agenda_index",
    "minutes_index", "public_notices_index", "video_archive", "api",
    "feed", "other",
}
ACCESS_METHODS = {"html", "json", "rss", "ical", "api", "pdf_index", "other"}
SOURCE_RELATIONSHIPS = {"first_party", "authorized_service"}
STATUSES = {"working", "empty", "blocked", "broken", "moved", "retired", "unverified"}
COVERAGE_RELATIONSHIPS = {
    "direct_jurisdiction", "governing_parent", "civic_representation",
    "regional_service",
}
USPS_CODES = {
    "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
    "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
    "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI", "WV",
    "WY",
}
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
CENSUS_GEOID_RE = re.compile(r"^[0-9]{2,15}$")
DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
CREDENTIAL_RE = re.compile(
    r"(?:^|[/?&#;])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|"
    r"password|passwd|secret|client[_-]?secret|signature|sig|credential)[=:]",
    re.IGNORECASE,
)
SINGLE_RECORD_PATH_RE = re.compile(
    r"(?:^|/)(?:meeting[_-]?details?|meetingdetail(?:\.aspx)?|events?/\d+|"
    r"meetings?/\d+|recordings?/\d+|clips?/\d+)(?:/|$)",
    re.IGNORECASE,
)
SINGLE_RECORD_QUERY_RE = re.compile(
    r"(?:^|[?&#;])(?:meeting[_-]?id|event[_-]?id|clip[_-]?id)=",
    re.IGNORECASE,
)
DOCUMENT_SUFFIXES = {
    ".doc", ".docx", ".m4a", ".mov", ".mp3", ".mp4", ".pdf", ".ppt",
    ".pptx", ".srt", ".vtt", ".wav", ".xls", ".xlsx",
}
SPECIAL_HOST_SUFFIXES = {
    "localhost", "local", "home.arpa", "arpa", "onion", "invalid", "test",
    "example", "example.com", "example.net", "example.org",
}


class DuplicateJsonKeyError(ValueError):
    pass


def _ordered_object(pairs: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
    value: OrderedDict[str, Any] = OrderedDict()
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKeyError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r}")


def _decode_bounded(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def _validate_url(value: Any, field: str, label: str) -> list[str]:
    if not isinstance(value, str) or not value or value != value.strip():
        return [f"{label}: {field} must be a non-empty, trimmed HTTPS URL"]
    if not value.startswith("https://") or len(value) > 2048:
        return [f"{label}: {field} must begin with literal https:// and be at most 2048 characters"]
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        return [f"{label}: {field} is invalid: {exc}"]
    if parsed.username is not None or parsed.password is not None:
        return [f"{label}: {field} must not contain credentials"]
    if parsed.scheme != "https" or not parsed.hostname or port not in (None, 443):
        return [f"{label}: {field} must use HTTPS, a DNS hostname, and the default port"]
    host = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [f"{label}: {field} must use a DNS hostname, not an IP literal"]
    labels = host.split(".")
    if len(labels) < 2 or any(not DNS_LABEL_RE.fullmatch(part) for part in labels):
        return [f"{label}: {field} has an invalid DNS hostname"]
    if any(host == suffix or host.endswith("." + suffix) for suffix in SPECIAL_HOST_SUFFIXES):
        return [f"{label}: {field} uses a local, reserved, or example hostname"]

    decoded_path = _decode_bounded(parsed.path)
    decoded_query = _decode_bounded(parsed.query)
    decoded_fragment = _decode_bounded(parsed.fragment)
    credential_surface = f"/{decoded_path}?{decoded_query}#{decoded_fragment}"
    if CREDENTIAL_RE.search(credential_surface):
        return [f"{label}: {field} appears to contain credential material"]
    clean_path = "/".join(segment.split(";", 1)[0] for segment in decoded_path.split("/"))
    if PurePosixPath(clean_path).suffix.casefold() in DOCUMENT_SUFFIXES:
        return [f"{label}: {field} points to a single downloadable artifact"]
    if SINGLE_RECORD_PATH_RE.search(clean_path) or SINGLE_RECORD_QUERY_RE.search(
        f"?{decoded_query}#{decoded_fragment}"
    ):
        return [f"{label}: {field} appears to identify one meeting or recording"]
    return []


def _text(value: Any, field: str, label: str) -> list[str]:
    if not isinstance(value, str) or not value or value != value.strip():
        return [f"{label}: {field} must be a non-empty, trimmed string"]
    return []


def _string_list(value: Any, field: str, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        return [f"{label}: {field} must be {'a non-empty' if nonempty else 'an'} array"]
    errors: list[str] = []
    if any(not isinstance(item, str) or not item or item != item.strip() for item in value):
        errors.append(f"{label}: {field} entries must be non-empty, trimmed strings")
    if value != sorted(value, key=lambda item: (item.casefold(), item)):
        errors.append(f"{label}: {field} must be sorted case-insensitively")
    if len({item.casefold() for item in value}) != len(value):
        errors.append(f"{label}: {field} must not contain duplicates")
    return errors


def _field_order(record: OrderedDict[str, Any], expected: tuple[str, ...], label: str) -> list[str]:
    actual = tuple(record.keys())
    if actual == expected:
        return []
    missing = [key for key in expected if key not in record]
    extra = [key for key in actual if key not in expected]
    parts: list[str] = []
    if missing:
        parts.append("missing " + ", ".join(missing))
    if extra:
        parts.append("unexpected " + ", ".join(extra))
    if not parts:
        parts.append("fields are not in canonical order")
    return [f"{label}: {'; '.join(parts)}"]


def _validate_cover(value: Any, label: str) -> list[str]:
    if not isinstance(value, OrderedDict):
        return [f"{label}: coverage entry must be an object"]
    errors = _field_order(value, COVER_FIELDS, label)
    if errors:
        return errors
    errors += _text(value["name"], "name", label)
    if value["type"] not in PLACE_TYPES:
        errors.append(f"{label}: unsupported covered-place type {value['type']!r}")
    errors += _string_list(value["state_codes"], "state_codes", label, nonempty=True)
    if isinstance(value["state_codes"], list):
        bad = sorted(set(value["state_codes"]) - USPS_CODES)
        if bad:
            errors.append(f"{label}: unsupported state codes: {', '.join(bad)}")
    errors += _string_list(value["county_names"], "county_names", label)
    if value["relationship"] not in COVERAGE_RELATIONSHIPS:
        errors.append(f"{label}: unsupported coverage relationship {value['relationship']!r}")
    ocd_id = value["ocd_division_id"]
    if ocd_id is not None and (not isinstance(ocd_id, str) or not ocd_id.startswith("ocd-division/")):
        errors.append(f"{label}: ocd_division_id must be null or an OCD division ID")
    geoid = value["census_geoid"]
    if geoid is not None and (not isinstance(geoid, str) or not CENSUS_GEOID_RE.fullmatch(geoid)):
        errors.append(f"{label}: census_geoid must be null or 2-15 ASCII digits")
    return errors


def _validate_source(record: OrderedDict[str, Any], label: str, folder_code: str) -> list[str]:
    errors = _field_order(record, SOURCE_FIELDS, label)
    if errors:
        return errors
    source_id = record["source_id"]
    errors += _text(source_id, "source_id", label)
    if isinstance(source_id, str) and not SOURCE_ID_RE.fullmatch(source_id):
        errors.append(f"{label}: source_id must be a lowercase, hyphenated stable ID")
    errors += _text(record["publisher_name"], "publisher_name", label)
    if record["publisher_type"] not in PUBLISHER_TYPES:
        errors.append(f"{label}: unsupported publisher_type {record['publisher_type']!r}")
    errors += _string_list(record["state_codes"], "state_codes", label, nonempty=True)
    if isinstance(record["state_codes"], list):
        bad = sorted(set(record["state_codes"]) - USPS_CODES)
        if bad:
            errors.append(f"{label}: unsupported state codes: {', '.join(bad)}")
        if record["state_codes"] and record["state_codes"][0].casefold() != folder_code:
            errors.append(f"{label}: file must live under the first state code, {record['state_codes'][0].lower()}")
    errors += _string_list(record["county_names"], "county_names", label)
    official_url = record["official_website_url"]
    if official_url is not None:
        errors += _validate_url(official_url, "official_website_url", label)
    if record["endpoint_type"] not in ENDPOINT_TYPES:
        errors.append(f"{label}: unsupported endpoint_type {record['endpoint_type']!r}")
    errors += _validate_url(record["url"], "url", label)
    errors += _text(record["platform"], "platform", label)
    if record["access_method"] not in ACCESS_METHODS:
        errors.append(f"{label}: unsupported access_method {record['access_method']!r}")
    if record["source_relationship"] not in SOURCE_RELATIONSHIPS:
        errors.append(f"{label}: unsupported source_relationship {record['source_relationship']!r}")
    if record["status"] not in STATUSES:
        errors.append(f"{label}: unsupported status {record['status']!r}")
    checked = record["last_checked"]
    if checked is not None:
        if not isinstance(checked, str):
            errors.append(f"{label}: last_checked must be null or YYYY-MM-DD")
        else:
            try:
                if date.fromisoformat(checked).isoformat() != checked:
                    raise ValueError
            except ValueError:
                errors.append(f"{label}: last_checked must be null or YYYY-MM-DD")
    errors += _validate_url(record["provenance_url"], "provenance_url", label)

    covers = record["covers"]
    if not isinstance(covers, list) or not covers:
        errors.append(f"{label}: covers must be a non-empty array")
    else:
        for index, cover in enumerate(covers):
            errors += _validate_cover(cover, f"{label}.covers[{index}]")
        keys = [
            (cover.get("name", "").casefold(), cover.get("name", ""), cover.get("type", ""))
            for cover in covers if isinstance(cover, dict)
        ]
        if len(keys) == len(covers) and keys != sorted(keys):
            errors.append(f"{label}: covers must be sorted by name and type")
        identities = [
            (cover.get("name", "").casefold(), tuple(cover.get("state_codes", [])))
            for cover in covers if isinstance(cover, dict)
        ]
        if len(identities) == len(covers) and len(set(identities)) != len(identities):
            errors.append(f"{label}: covers contains a duplicate covered place")
    return errors


def validate_catalog(data_root: Path = DEFAULT_DATA_ROOT) -> tuple[int, list[str]]:
    if not data_root.is_dir():
        return 0, [f"{data_root.as_posix()}: state data directory does not exist"]
    files = sorted(data_root.glob("*/sources.jsonl"), key=lambda path: path.parent.name)
    if not files:
        return 0, [f"{data_root.as_posix()}: no state source files found"]

    errors: list[str] = []
    source_ids: dict[str, str] = {}
    total = 0
    for path in files:
        folder_code = path.parent.name
        if folder_code not in {code.lower() for code in USPS_CODES}:
            errors.append(f"{path.as_posix()}: parent directory must be a lowercase USPS code")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.as_posix()}: cannot read UTF-8 JSONL: {exc}")
            continue
        if not text.strip():
            errors.append(f"{path.as_posix()}: file contains no source records")
            continue
        file_ids: list[str] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            label = f"{path.as_posix()}:{line_number}"
            if not raw_line.strip():
                errors.append(f"{label}: blank lines are not allowed")
                continue
            try:
                record = json.loads(
                    raw_line,
                    object_pairs_hook=_ordered_object,
                    parse_constant=_reject_nonfinite,
                )
            except (json.JSONDecodeError, DuplicateJsonKeyError, ValueError) as exc:
                errors.append(f"{label}: invalid JSON: {exc}")
                continue
            if not isinstance(record, OrderedDict):
                errors.append(f"{label}: each line must be a JSON object")
                continue
            errors += _validate_source(record, label, folder_code)
            source_id = record.get("source_id")
            if isinstance(source_id, str):
                if source_id in source_ids:
                    errors.append(f"{label}: source_id duplicates {source_ids[source_id]}")
                else:
                    source_ids[source_id] = label
                file_ids.append(source_id)
            total += 1
        if file_ids != sorted(file_ids):
            errors.append(f"{path.as_posix()}: records must be sorted by source_id")
    return total, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args(argv)
    count, errors = validate_catalog(args.data_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Catalog invalid: {len(errors)} error(s), {count} parsed source record(s).", file=sys.stderr)
        return 1
    print(f"Catalog valid: {count} source record(s) across state files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
