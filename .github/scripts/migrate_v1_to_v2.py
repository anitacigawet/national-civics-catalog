"""Deterministically migrate National Civics Catalog v1 JSONL records to v2."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
V1_FIELDS = (
    "source_id", "publisher_name", "publisher_type", "state_codes",
    "county_names", "official_website_url", "endpoint_type", "url",
    "platform", "access_method", "source_relationship", "status",
    "last_checked", "provenance_url", "covers",
)
V2_FIELDS = (
    "schema_version", "catalog_record_id", "public_body_name",
    "public_body_type", "state_codes", "county_names",
    "public_body_website_url", "roster_source_url", "meeting_source_type",
    "meeting_source_url", "meeting_source_platform",
    "meeting_source_access_method", "meeting_source_relationship",
    "meeting_source_status", "meeting_source_last_checked_date",
    "meeting_source_evidence_url", "coverage",
)
V1_COVERAGE_FIELDS = (
    "name", "type", "state_codes", "county_names", "relationship",
    "ocd_division_id", "census_geoid",
)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def migrate_coverage_item(item: dict[str, Any]) -> dict[str, Any]:
    if tuple(item) != V1_COVERAGE_FIELDS:
        raise ValueError("v1 coverage item does not use the canonical field order")
    return {
        "name": item["name"],
        "type": item["type"],
        "state_codes": item["state_codes"],
        "county_names": item["county_names"],
        "coverage_relationship": item["relationship"],
        "ocd_division_id": item["ocd_division_id"],
        "census_geoid": item["census_geoid"],
    }


def restore_v1_coverage_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item["name"],
        "type": item["type"],
        "state_codes": item["state_codes"],
        "county_names": item["county_names"],
        "relationship": item["coverage_relationship"],
        "ocd_division_id": item["ocd_division_id"],
        "census_geoid": item["census_geoid"],
    }


def migrate_record(record: dict[str, Any]) -> dict[str, Any]:
    if tuple(record) != V1_FIELDS:
        raise ValueError("v1 record does not use the canonical field order")
    status = record["status"]
    if not isinstance(status, str):
        raise ValueError("v1 status must be a string")
    needs_source = status == "needs_source"
    if not needs_source:
        checked = record["last_checked"]
        try:
            if not isinstance(checked, str) or date.fromisoformat(checked).isoformat() != checked:
                raise ValueError
        except ValueError as exc:
            raise ValueError(
                "v1 identified source requires last_checked in YYYY-MM-DD format"
            ) from exc
    return {
        "schema_version": "2.0.0",
        "catalog_record_id": record["source_id"],
        "public_body_name": record["publisher_name"],
        "public_body_type": record["publisher_type"],
        "state_codes": record["state_codes"],
        "county_names": record["county_names"],
        "public_body_website_url": record["official_website_url"],
        "roster_source_url": record["provenance_url"] if needs_source else None,
        "meeting_source_type": record["endpoint_type"],
        "meeting_source_url": record["url"],
        "meeting_source_platform": record["platform"],
        "meeting_source_access_method": record["access_method"],
        "meeting_source_relationship": record["source_relationship"],
        "meeting_source_status": status,
        "meeting_source_last_checked_date": record["last_checked"],
        "meeting_source_evidence_url": None if needs_source else record["provenance_url"],
        "coverage": [migrate_coverage_item(item) for item in record["covers"]],
    }


def restore_v1_record(record: dict[str, Any]) -> dict[str, Any]:
    if tuple(record) != V2_FIELDS or record.get("schema_version") != "2.0.0":
        raise ValueError("v2 record does not use the canonical field order and version")
    needs_source = record["meeting_source_status"] == "needs_source"
    provenance = (
        record["roster_source_url"] if needs_source
        else record["meeting_source_evidence_url"]
    )
    return {
        "source_id": record["catalog_record_id"],
        "publisher_name": record["public_body_name"],
        "publisher_type": record["public_body_type"],
        "state_codes": record["state_codes"],
        "county_names": record["county_names"],
        "official_website_url": record["public_body_website_url"],
        "endpoint_type": record["meeting_source_type"],
        "url": record["meeting_source_url"],
        "platform": record["meeting_source_platform"],
        "access_method": record["meeting_source_access_method"],
        "source_relationship": record["meeting_source_relationship"],
        "status": record["meeting_source_status"],
        "last_checked": record["meeting_source_last_checked_date"],
        "provenance_url": provenance,
        "covers": [restore_v1_coverage_item(item) for item in record["coverage"]],
    }


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def migrate_catalog(root: Path, *, apply: bool) -> dict[str, Any]:
    state_files = sorted((root / "states").glob("*.jsonl"))
    if not state_files:
        raise ValueError("states/: no JSONL files found")
    outputs: dict[Path, bytes] = {}
    records = 0
    roster_sources = 0
    meeting_sources = 0
    v1_digest = hashlib.sha256()
    v2_digest = hashlib.sha256()
    for path in state_files:
        rendered: list[str] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                old = json.loads(line, object_pairs_hook=reject_duplicate_keys)
                new = migrate_record(old)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
            if restore_v1_record(new) != old:
                raise ValueError(f"{path}:{number}: v2 round trip changed v1 semantics")
            old_line = json.dumps(old, ensure_ascii=False, separators=(",", ":"))
            new_line = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
            v1_digest.update((old_line + "\n").encode("utf-8"))
            v2_digest.update((new_line + "\n").encode("utf-8"))
            rendered.append(new_line)
            records += 1
            roster_sources += new["roster_source_url"] is not None
            meeting_sources += new["meeting_source_url"] is not None
        outputs[path] = ("\n".join(rendered) + "\n").encode("utf-8")
    if apply:
        for path, payload in outputs.items():
            atomic_write(path, payload)
    return {
        "mode": "applied" if apply else "dry_run",
        "files": len(state_files),
        "records": records,
        "roster_source_urls": roster_sources,
        "meeting_source_urls": meeting_sources,
        "v1_semantic_sha256": v1_digest.hexdigest(),
        "v2_semantic_sha256": v2_digest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        summary = migrate_catalog(args.root.resolve(), apply=args.apply)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
