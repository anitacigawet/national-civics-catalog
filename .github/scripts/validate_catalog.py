"""Validate the National Civics Catalog with the Python standard library."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path
from typing import Any
import unicodedata
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
STATES = ROOT / "states"

SOURCE_FIELDS = (
    "schema_version", "catalog_record_id", "public_body_name",
    "public_body_type", "state_codes", "county_names",
    "public_body_website_url", "roster_source_url", "meeting_source_type",
    "meeting_source_url", "meeting_source_platform",
    "meeting_source_access_method", "meeting_source_relationship",
    "meeting_source_status", "meeting_source_last_checked_date",
    "meeting_source_evidence_url", "coverage",
)
COVER_FIELDS = (
    "name", "type", "state_codes", "county_names", "coverage_relationship",
    "ocd_division_id", "census_geoid",
)
PUBLIC_BODY_TYPES = {
    "state", "county", "municipality", "township", "school_district",
    "special_district", "tribal_government", "tribal_chapter",
    "community_council", "civic_body", "other",
}
PLACE_TYPES = {
    "state", "county", "municipality", "township", "unincorporated_community",
    "school_district", "special_district", "tribal_jurisdiction",
    "tribal_chapter", "other",
}
MEETING_SOURCE_TYPES = {
    "primary_meeting_source", "meeting_calendar", "agenda_index",
    "minutes_index", "public_notices_index", "video_archive", "api", "feed",
    "other",
}
ACCESS_METHODS = {"html", "json", "rss", "ical", "api", "pdf_index", "other"}
MEETING_SOURCE_RELATIONSHIPS = {"first_party", "authorized_service"}
STATUSES = {"needs_source", "working", "empty", "blocked", "broken", "moved", "retired", "unverified"}
RELATIONSHIPS = {"direct_jurisdiction", "governing_parent", "civic_representation", "regional_service"}
USPS_CODES = {
    "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
    "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
    "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI", "WV", "WY",
}
CATALOG_RECORD_ID = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
CENSUS_GEOID = re.compile(r"^[0-9]{2,15}$")
MAX_PERCENT_DECODE_ROUNDS = 3
SNAPSHOT_PATTERNS = {
    "total": re.compile(r"total ([0-9,]+) locations checked\."),
    "identified": re.compile(r"🟢 ([0-9,]+) identified meeting endpoints(?:\r?\n|$)"),
    "not_unverified": re.compile(r"🟢 ([0-9,]+) identified meeting endpoints reviewed"),
    "unverified": re.compile(r"🟡 ([0-9,]+) identified meeting endpoints awaiting review"),
    "needs_source": re.compile(r"🔴 ([0-9,]+) locations without an identified meeting endpoint"),
}


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


def validate_url_encoding(value: str, label: str) -> list[str]:
    current = value
    for decode_round in range(MAX_PERCENT_DECODE_ROUNDS + 1):
        format_characters = sorted(
            {f"U+{ord(character):04X}" for character in current if unicodedata.category(character) == "Cf"}
        )
        if format_characters:
            return [
                f"{label} contains Unicode format characters after percent-decoding: "
                + ", ".join(format_characters)
            ]
        if any(
            unicodedata.category(character) in {"Cc", "Cs"}
            or (
                character.isspace()
                and (decode_round == 0 or character != " ")
            )
            for character in current
        ):
            return [f"{label} contains whitespace or control characters after percent-decoding"]
        decoded = unquote(current)
        if decoded == current:
            return []
        current = decoded
        if decode_round == MAX_PERCENT_DECODE_ROUNDS:
            return [
                f"{label} contains excessive recursive percent-encoding "
                f"(more than {MAX_PERCENT_DECODE_ROUNDS} decoding rounds)"
            ]
    raise AssertionError("unreachable")


def validate_url(value: Any, label: str, *, nullable: bool = False) -> list[str]:
    if value is None and nullable:
        return []
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 2048:
        return [f"{label} must be a non-empty, trimmed URL of at most 2048 characters"]
    errors = validate_url_encoding(value, label)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        return errors + [f"{label} is invalid: {exc}"]
    if parsed.scheme != "https" or not parsed.hostname or port not in (None, 443):
        errors.append(f"{label} must use HTTPS, a DNS hostname, and the default port")
    if parsed.hostname is None:
        return errors
    if parsed.username is not None or parsed.password is not None:
        errors.append(f"{label} must not contain credentials")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        try:
            ascii_hostname = parsed.hostname.encode("idna").decode("ascii")
        except UnicodeError:
            errors.append(f"{label} contains an invalid DNS hostname")
            return errors
        dns_label = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
        if (
            len(ascii_hostname) > 253
            or ascii_hostname.endswith(".")
            or any(not dns_label.fullmatch(part) for part in ascii_hostname.split("."))
        ):
            errors.append(f"{label} contains an invalid DNS hostname")
        return errors
    errors.append(f"{label} must use a DNS hostname, not an IP address")
    return errors


def validate_string_list(
    value: Any,
    label: str,
    *,
    required: bool = False,
    max_length: int | None = None,
) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        return [f"{label} must be {'a non-empty' if required else 'an'} array"]
    errors: list[str] = []
    if any(not isinstance(item, str) or not item or item != item.strip() for item in value):
        errors.append(f"{label} entries must be non-empty, trimmed strings")
    if not all(isinstance(item, str) for item in value):
        return errors
    if max_length is not None and any(len(item) > max_length for item in value):
        errors.append(f"{label} entries must be at most {max_length} characters")
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
    if not isinstance(cover["type"], str) or cover["type"] not in PLACE_TYPES:
        errors.append(f"{label}.type is unsupported")
    errors += validate_string_list(cover["state_codes"], f"{label}.state_codes", required=True)
    if (
        isinstance(cover["state_codes"], list)
        and all(isinstance(item, str) for item in cover["state_codes"])
        and set(cover["state_codes"]) - USPS_CODES
    ):
        errors.append(f"{label}.state_codes contains an unsupported code")
    errors += validate_string_list(
        cover["county_names"], f"{label}.county_names", max_length=150
    )
    if (
        not isinstance(cover["coverage_relationship"], str)
        or cover["coverage_relationship"] not in RELATIONSHIPS
    ):
        errors.append(f"{label}.coverage_relationship is unsupported")
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
    if record["schema_version"] != "2.0.0":
        errors.append(f"{label}: schema_version must be 2.0.0")
    catalog_record_id = record["catalog_record_id"]
    if not isinstance(catalog_record_id, str) or not CATALOG_RECORD_ID.fullmatch(catalog_record_id):
        errors.append(f"{label}: catalog_record_id must be a lowercase, hyphenated stable ID")
    if (
        not isinstance(record["public_body_name"], str)
        or record["public_body_name"] != record["public_body_name"].strip()
        or not 1 <= len(record["public_body_name"]) <= 200
    ):
        errors.append(f"{label}: public_body_name must be a trimmed string of 1-200 characters")
    if (
        not isinstance(record["public_body_type"], str)
        or record["public_body_type"] not in PUBLIC_BODY_TYPES
    ):
        errors.append(f"{label}: public_body_type is unsupported")
    errors += validate_string_list(record["state_codes"], f"{label}: state_codes", required=True)
    if isinstance(record["state_codes"], list):
        if (
            all(isinstance(item, str) for item in record["state_codes"])
            and set(record["state_codes"]) - USPS_CODES
        ):
            errors.append(f"{label}: state_codes contains an unsupported code")
        if (
            record["state_codes"]
            and isinstance(record["state_codes"][0], str)
            and record["state_codes"][0].lower() != state_code
        ):
            errors.append(f"{label}: record belongs in states/{record['state_codes'][0].lower()}.jsonl")
    errors += validate_string_list(
        record["county_names"], f"{label}: county_names", max_length=150
    )
    errors += validate_url(
        record["public_body_website_url"],
        f"{label}: public_body_website_url",
        nullable=True,
    )
    errors += validate_url(record["roster_source_url"], f"{label}: roster_source_url", nullable=True)
    status = record["meeting_source_status"]
    if not isinstance(status, str) or status not in STATUSES:
        errors.append(f"{label}: meeting_source_status is unsupported")
    meeting_source_fields = (
        "meeting_source_type", "meeting_source_url", "meeting_source_platform",
        "meeting_source_access_method", "meeting_source_relationship",
        "meeting_source_last_checked_date", "meeting_source_evidence_url",
    )
    if status == "needs_source":
        if record["roster_source_url"] is None:
            errors.append(f"{label}: roster_source_url is required while meeting_source_status is needs_source")
        for field in meeting_source_fields:
            if record[field] is not None:
                errors.append(
                    f"{label}: {field} must be null while meeting_source_status is needs_source"
                )
    else:
        if (
            not isinstance(record["meeting_source_type"], str)
            or record["meeting_source_type"] not in MEETING_SOURCE_TYPES
        ):
            errors.append(f"{label}: meeting_source_type is unsupported")
        errors += validate_url(record["meeting_source_url"], f"{label}: meeting_source_url")
        if (
            not isinstance(record["meeting_source_platform"], str)
            or record["meeting_source_platform"] != record["meeting_source_platform"].strip()
            or not 1 <= len(record["meeting_source_platform"]) <= 100
        ):
            errors.append(
                f"{label}: meeting_source_platform must be a trimmed string of 1-100 characters"
            )
        if (
            not isinstance(record["meeting_source_access_method"], str)
            or record["meeting_source_access_method"] not in ACCESS_METHODS
        ):
            errors.append(f"{label}: meeting_source_access_method is unsupported")
        if (
            not isinstance(record["meeting_source_relationship"], str)
            or record["meeting_source_relationship"] not in MEETING_SOURCE_RELATIONSHIPS
        ):
            errors.append(f"{label}: meeting_source_relationship is unsupported")
        errors += validate_url(
            record["meeting_source_evidence_url"],
            f"{label}: meeting_source_evidence_url",
        )
        checked = record["meeting_source_last_checked_date"]
        try:
            if not isinstance(checked, str) or date.fromisoformat(checked).isoformat() != checked:
                raise ValueError
        except ValueError:
            errors.append(
                f"{label}: meeting_source_last_checked_date must be YYYY-MM-DD for an identified source"
            )

    coverage = record["coverage"]
    if not isinstance(coverage, list) or not coverage:
        errors.append(f"{label}: coverage must be a non-empty array")
    else:
        for index, cover in enumerate(coverage):
            errors += validate_cover(cover, f"{label}.coverage[{index}]")
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
            catalog_record_id = record.get("catalog_record_id") if isinstance(record, dict) else None
            if isinstance(catalog_record_id, str):
                if catalog_record_id in seen:
                    errors.append(
                        f"{label}: catalog_record_id duplicates {seen[catalog_record_id]}"
                    )
                else:
                    seen[catalog_record_id] = label
                file_ids.append(catalog_record_id)
            total += 1
        if file_ids != sorted(file_ids):
            errors.append(
                f"{path.relative_to(root).as_posix()}: records must be sorted by catalog_record_id"
            )
    return total, errors


def snapshot_counts(root: Path) -> dict[str, int]:
    statuses: Counter[str] = Counter()
    total = 0
    identified = 0
    for path in sorted((root / "states").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            total += 1
            statuses[record["meeting_source_status"]] += 1
            if record["meeting_source_url"] is not None:
                identified += 1
    unverified = statuses["unverified"]
    return {
        "total": total,
        "identified": identified,
        "not_unverified": identified - unverified,
        "unverified": unverified,
        "needs_source": statuses["needs_source"],
    }


def validate_readme_snapshot(root: Path) -> list[str]:
    readme = root / "README.md"
    if not readme.is_file():
        return ["README.md: file not found"]
    text = readme.read_text(encoding="utf-8")
    expected = snapshot_counts(root)
    errors: list[str] = []
    for key, pattern in SNAPSHOT_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            errors.append(f"README.md: expected exactly one {key} snapshot count")
            continue
        actual = int(matches[0].group(1).replace(",", ""))
        if actual != expected[key]:
            errors.append(
                f"README.md: {key} snapshot count is {actual:,}; catalog data says {expected[key]:,}"
            )
    return errors


def render_readme_snapshot(text: str, expected: dict[str, int]) -> str:
    for key, pattern in SNAPSHOT_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise SystemExit(f"README.md: expected exactly one {key} snapshot count")
        match = matches[0]
        replacement = match.group(0).replace(match.group(1), f"{expected[key]:,}")
        text = text[: match.start()] + replacement + text[match.end() :]
    return text


def update_readme_snapshot(root: Path) -> None:
    readme = root / "README.md"
    text = render_readme_snapshot(
        readme.read_text(encoding="utf-8"),
        snapshot_counts(root),
    )
    readme.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--fix-readme",
        action="store_true",
        help="update the five README snapshot counts from validated JSONL data",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    count, errors = validate_catalog(root)
    if not errors and args.fix_readme:
        update_readme_snapshot(root)
    if not errors:
        errors.extend(validate_readme_snapshot(root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Catalog invalid: {len(errors)} error(s), {count} parsed entries.", file=sys.stderr)
        return 1
    print(f"Catalog valid: {count} entries across {len(list((root / 'states').glob('*.jsonl')))} state and territory files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
