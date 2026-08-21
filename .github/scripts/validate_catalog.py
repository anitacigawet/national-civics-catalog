"""Validate the National Civics Catalog with the Python standard library."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
STATES = ROOT / "states"

SOURCE_FIELDS = (
    "source_id", "publisher_name", "publisher_type", "state_codes",
    "county_names", "official_website_url", "endpoint_type", "url",
    "platform", "access_method", "source_relationship", "status",
    "last_checked", "provenance_url", "covers",
)
COVER_FIELDS = (
    "name", "type", "state_codes", "county_names", "relationship",
    "ocd_division_id", "census_geoid",
)
PUBLISHER_TYPES = {
    "state", "county", "municipality", "township", "school_district",
    "special_district", "tribal_government", "tribal_chapter",
    "community_council", "civic_body", "other",
}
PLACE_TYPES = {
    "state", "county", "municipality", "township", "unincorporated_community",
    "school_district", "special_district", "tribal_jurisdiction",
    "tribal_chapter", "other",
}
ENDPOINT_TYPES = {
    "primary_meeting_source", "meeting_calendar", "agenda_index",
    "minutes_index", "public_notices_index", "video_archive", "api", "feed",
    "other",
}
ACCESS_METHODS = {"html", "json", "rss", "ical", "api", "pdf_index", "other"}
SOURCE_RELATIONSHIPS = {"first_party", "authorized_service"}
STATUSES = {"needs_source", "working", "empty", "blocked", "broken", "moved", "retired", "unverified"}
RELATIONSHIPS = {"direct_jurisdiction", "governing_parent", "civic_representation", "regional_service"}
USPS_CODES = {
    "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
    "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
    "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI", "WV", "WY",
}
SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
CENSUS_GEOID = re.compile(r"^[0-9]{2,15}$")


class DuplicateKey(ValueError):
    pass


def ordered_object(pairs: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
    value: OrderedDict[str, Any] = OrderedDict()
    for key, item in pairs:
        if key in value:
            raise DuplicateKey(f"duplicate key {key!r}")
        value[key] = item
    return value


def reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r}")


def validate_url(value: Any, label: str, *, nullable: bool = False) -> list[str]:
    if value is None and nullable:
        return []
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 2048:
        return [f"{label} must be a non-empty, trimmed URL of at most 2048 characters"]
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        return [f"{label} is invalid: {exc}"]
    if parsed.scheme != "https" or not parsed.hostname or port not in (None, 443):
        return [f"{label} must use HTTPS, a DNS hostname, and the default port"]
    if parsed.username is not None or parsed.password is not None:
        return [f"{label} must not contain credentials"]
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return []
    return [f"{label} must use a DNS hostname, not an IP address"]


def validate_string_list(value: Any, label: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        return [f"{label} must be {'a non-empty' if required else 'an'} array"]
    errors: list[str] = []
    if any(not isinstance(item, str) or not item or item != item.strip() for item in value):
        errors.append(f"{label} entries must be non-empty, trimmed strings")
    if not all(isinstance(item, str) for item in value):
        return errors
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    if value != sorted(value, key=lambda item: (item.casefold(), item)):
        errors.append(f"{label} must be sorted")
    return errors


def validate_cover(cover: Any, label: str) -> list[str]:
    if not isinstance(cover, OrderedDict):
        return [f"{label} must be an object"]
    if tuple(cover) != COVER_FIELDS:
        return [f"{label} must contain the schema fields in canonical order"]
    errors: list[str] = []
    if (
        not isinstance(cover["name"], str)
        or cover["name"] != cover["name"].strip()
        or not 1 <= len(cover["name"]) <= 200
    ):
        errors.append(f"{label}.name must be a trimmed string of 1-200 characters")
    if cover["type"] not in PLACE_TYPES:
        errors.append(f"{label}.type is unsupported")
    errors += validate_string_list(cover["state_codes"], f"{label}.state_codes", required=True)
    if isinstance(cover["state_codes"], list) and set(cover["state_codes"]) - USPS_CODES:
        errors.append(f"{label}.state_codes contains an unsupported code")
    errors += validate_string_list(cover["county_names"], f"{label}.county_names")
    if cover["relationship"] not in RELATIONSHIPS:
        errors.append(f"{label}.relationship is unsupported")
    ocd = cover["ocd_division_id"]
    if ocd is not None and (not isinstance(ocd, str) or not ocd.startswith("ocd-division/")):
        errors.append(f"{label}.ocd_division_id must be null or an OCD division ID")
    geoid = cover["census_geoid"]
    if geoid is not None and (not isinstance(geoid, str) or not CENSUS_GEOID.fullmatch(geoid)):
        errors.append(f"{label}.census_geoid must be null or 2-15 digits")
    return errors


def validate_record(record: Any, label: str, state_code: str) -> list[str]:
    if not isinstance(record, OrderedDict):
        return [f"{label}: each line must be a JSON object"]
    if tuple(record) != SOURCE_FIELDS:
        return [f"{label}: record must contain the schema fields in canonical order"]
    errors: list[str] = []
    source_id = record["source_id"]
    if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
        errors.append(f"{label}: source_id must be a lowercase, hyphenated stable ID")
    if (
        not isinstance(record["publisher_name"], str)
        or record["publisher_name"] != record["publisher_name"].strip()
        or not 1 <= len(record["publisher_name"]) <= 200
    ):
        errors.append(f"{label}: publisher_name must be a trimmed string of 1-200 characters")
    if record["publisher_type"] not in PUBLISHER_TYPES:
        errors.append(f"{label}: publisher_type is unsupported")
    errors += validate_string_list(record["state_codes"], f"{label}: state_codes", required=True)
    if isinstance(record["state_codes"], list):
        if set(record["state_codes"]) - USPS_CODES:
            errors.append(f"{label}: state_codes contains an unsupported code")
        if record["state_codes"] and record["state_codes"][0].lower() != state_code:
            errors.append(f"{label}: record belongs in states/{record['state_codes'][0].lower()}.jsonl")
    errors += validate_string_list(record["county_names"], f"{label}: county_names")
    errors += validate_url(record["official_website_url"], f"{label}: official_website_url", nullable=True)
    errors += validate_url(record["provenance_url"], f"{label}: provenance_url")

    status = record["status"]
    if status not in STATUSES:
        errors.append(f"{label}: status is unsupported")
    endpoint_fields = ("endpoint_type", "url", "platform", "access_method", "source_relationship")
    if status == "needs_source":
        for field in (*endpoint_fields, "last_checked"):
            if record[field] is not None:
                errors.append(f"{label}: {field} must be null while status is needs_source")
    else:
        if record["endpoint_type"] not in ENDPOINT_TYPES:
            errors.append(f"{label}: endpoint_type is unsupported")
        errors += validate_url(record["url"], f"{label}: url")
        if (
            not isinstance(record["platform"], str)
            or record["platform"] != record["platform"].strip()
            or not 1 <= len(record["platform"]) <= 100
        ):
            errors.append(f"{label}: platform must be a trimmed string of 1-100 characters")
        if record["access_method"] not in ACCESS_METHODS:
            errors.append(f"{label}: access_method is unsupported")
        if record["source_relationship"] not in SOURCE_RELATIONSHIPS:
            errors.append(f"{label}: source_relationship is unsupported")
        checked = record["last_checked"]
        if checked is not None:
            try:
                if not isinstance(checked, str) or date.fromisoformat(checked).isoformat() != checked:
                    raise ValueError
            except ValueError:
                errors.append(f"{label}: last_checked must be null or YYYY-MM-DD")

    covers = record["covers"]
    if not isinstance(covers, list) or not covers:
        errors.append(f"{label}: covers must be a non-empty array")
    else:
        for index, cover in enumerate(covers):
            errors += validate_cover(cover, f"{label}.covers[{index}]")
    return errors


def validate_catalog(root: Path = ROOT) -> tuple[int, list[str]]:
    states = root / "states"
    files = sorted(states.glob("*.jsonl"))
    errors: list[str] = []
    seen: dict[str, str] = {}
    total = 0
    if not files:
        return 0, ["states/: no JSONL files found"]
    present_codes = {path.stem for path in files}
    expected_codes = {code.lower() for code in USPS_CODES}
    if present_codes != expected_codes:
        missing = sorted(expected_codes - present_codes)
        extra = sorted(present_codes - expected_codes)
        if missing:
            errors.append(f"states/: missing files for {', '.join(missing)}")
        if extra:
            errors.append(f"states/: unexpected files for {', '.join(extra)}")
    for path in files:
        state_code = path.stem
        if state_code.upper() not in USPS_CODES:
            errors.append(f"{path}: filename must be a lowercase USPS code")
        file_ids: list[str] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            label = f"{path.relative_to(root).as_posix()}:{line_number}"
            if not line:
                errors.append(f"{label}: blank lines are not allowed")
                continue
            try:
                record = json.loads(
                    line,
                    object_pairs_hook=ordered_object,
                    parse_constant=reject_nonfinite,
                )
            except (json.JSONDecodeError, DuplicateKey, ValueError) as exc:
                errors.append(f"{label}: invalid JSON: {exc}")
                continue
            errors += validate_record(record, label, state_code)
            source_id = record.get("source_id") if isinstance(record, dict) else None
            if isinstance(source_id, str):
                if source_id in seen:
                    errors.append(f"{label}: source_id duplicates {seen[source_id]}")
                else:
                    seen[source_id] = label
                file_ids.append(source_id)
            total += 1
        if file_ids != sorted(file_ids):
            errors.append(f"{path.relative_to(root).as_posix()}: records must be sorted by source_id")
    return total, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    count, errors = validate_catalog(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Catalog invalid: {len(errors)} error(s), {count} parsed entries.", file=sys.stderr)
        return 1
    print(f"Catalog valid: {count} entries across {len(list((root / 'states').glob('*.jsonl')))} state and territory files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
