"""Promote validated fleet candidates into state JSONL files for PR review."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_FIELDS = {
    "official_website_url",
    "endpoint_type",
    "url",
    "platform",
    "access_method",
    "source_relationship",
    "status",
    "last_checked",
    "provenance_url",
}


class PromotionError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validator():
    path = ROOT / "scripts" / "validate_catalog.py"
    spec = importlib.util.spec_from_file_location("promotion_catalog_validator", path)
    if spec is None or spec.loader is None:
        raise PromotionError(f"cannot load catalog validator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_bundle(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PromotionError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict) or not isinstance(row.get("source"), dict):
                raise PromotionError(f"{path}:{line_number}: expected a candidate object with source")
            source_id = row["source"].get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise PromotionError(f"{path}:{line_number}: candidate source_id is missing")
            if source_id in seen:
                raise PromotionError(f"duplicate candidate source_id {source_id}")
            seen.add(source_id)
            rows.append(row)
    if not rows:
        raise PromotionError("candidate bundle is empty")
    return rows


def read_state(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PromotionError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise PromotionError(f"{path}:{line_number}: source record must be an object")
            records.append(record)
    return records


def validate_transition(before: dict[str, Any], after: dict[str, Any]) -> None:
    source_id = before.get("source_id")
    if before.get("status") != "needs_source":
        raise PromotionError(f"{source_id}: promotion must start from status=needs_source")
    if after.get("status") != "unverified":
        raise PromotionError(f"{source_id}: promoted source must enter as status=unverified")
    if tuple(before) != tuple(after):
        raise PromotionError(f"{source_id}: candidate fields or canonical order changed")
    changed = {key for key in before if before[key] != after[key]}
    forbidden = sorted(changed - RESEARCH_FIELDS)
    if forbidden:
        raise PromotionError(f"{source_id}: identity fields changed: {', '.join(forbidden)}")
    if not changed:
        raise PromotionError(f"{source_id}: candidate does not change its needs_source record")


def encoded_state(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )


def promote_candidates(
    *,
    bundle: Path,
    catalog_root: Path,
    receipt: Path,
    apply: bool,
) -> dict[str, Any]:
    catalog_root = catalog_root.resolve()
    bundle = bundle.resolve()
    receipt = receipt.resolve()
    if receipt.exists():
        raise PromotionError("promotion receipt already exists; choose a new path")
    validator = load_validator()
    catalog_count, existing_errors = validator.validate_catalog(catalog_root / "data" / "states")
    if existing_errors:
        raise PromotionError("catalog is invalid before promotion: " + existing_errors[0])

    candidates = load_bundle(bundle)
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        state_code = row.get("state_code")
        source = row["source"]
        if (
            not isinstance(state_code, str)
            or len(state_code) != 2
            or source.get("state_codes", [None])[0] != state_code
        ):
            raise PromotionError(f"{source.get('source_id')}: candidate state does not match source")
        by_state.setdefault(state_code.lower(), []).append(source)

    originals: dict[Path, str] = {}
    replacements: dict[Path, str] = {}
    promoted: list[str] = []
    skipped: list[str] = []
    for state_code, sources in sorted(by_state.items()):
        path = catalog_root / "data" / "states" / state_code / "sources.jsonl"
        records = read_state(path)
        positions = {record.get("source_id"): index for index, record in enumerate(records)}
        for candidate in sorted(sources, key=lambda item: item["source_id"]):
            source_id = candidate["source_id"]
            if source_id not in positions:
                raise PromotionError(f"{source_id}: no matching catalog record in {path}")
            index = positions[source_id]
            current = records[index]
            if current == candidate:
                skipped.append(source_id)
                continue
            validate_transition(current, candidate)
            records[index] = candidate
            promoted.append(source_id)
        originals[path] = path.read_text(encoding="utf-8")
        replacements[path] = encoded_state(records)

    summary = {
        "schema_version": "national-civics-catalog.fleet-promotion.v1",
        "bundle": str(bundle),
        "bundle_sha256": sha256_file(bundle),
        "catalog_records": catalog_count,
        "candidate_count": len(candidates),
        "promoted_count": len(promoted),
        "skipped_identical_count": len(skipped),
        "states": sorted(by_state),
        "state_files": [str(path.relative_to(catalog_root).as_posix()) for path in sorted(replacements)],
        "promoted_source_ids": sorted(promoted),
        "skipped_source_ids": sorted(skipped),
        "applied": apply,
    }
    if not apply:
        return summary

    try:
        for path, text in replacements.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        final_count, final_errors = validator.validate_catalog(catalog_root / "data" / "states")
        if final_errors:
            raise PromotionError("catalog is invalid after promotion: " + final_errors[0])
        if final_count != catalog_count:
            raise PromotionError(
                f"catalog record count changed from {catalog_count} to {final_count}"
            )
    except BaseException:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        raise

    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bundle", type=Path, required=True)
    result.add_argument("--catalog-root", type=Path, default=ROOT)
    result.add_argument("--receipt", type=Path, required=True)
    result.add_argument("--apply", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        summary = promote_candidates(
            bundle=args.bundle,
            catalog_root=args.catalog_root,
            receipt=args.receipt,
            apply=args.apply,
        )
    except (OSError, PromotionError) as exc:
        print(f"PROMOTION_STOP: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
