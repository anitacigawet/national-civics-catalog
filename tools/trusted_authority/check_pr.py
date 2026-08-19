"""Validate one catalog contribution without executing incoming code."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


PACKET_RE = re.compile(
    r"^contributions/(?P<state>[a-z]{2})/(?P<source>[a-z0-9][a-z0-9-]*[a-z0-9])/(?P<author>[a-z0-9-]+)-(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\.json$"
)
BATCH_RE = re.compile(
    r"^batches/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})/(?P<author>[a-z0-9-]+)__(?P<batch>[a-z0-9][a-z0-9-]*[a-z0-9])\.json$"
)
PACKET_FIELDS = ("schema_version", "change_kind", "contributor", "source", "evidence_notes")
CONTRIBUTOR_FIELDS = ("github_login", "ai_tools", "reviewed_by_contributor")
BATCH_FIELDS = (
    "schema_version",
    "batch_id",
    "maintainer",
    "source_bundle_sha256",
    "ai_tools",
    "candidates",
)
BATCH_MAINTAINER_FIELDS = ("github_login",)
BATCH_CANDIDATE_FIELDS = ("state_code", "source_id", "source", "evidence", "notes")
BATCH_EVIDENCE_FIELDS = ("url", "claim", "accessed_on")
MAINTAINER_BATCH_AUTHORS = frozenset({"anitacigawet"})
FILL_IDENTITY_FIELDS = (
    "source_id",
    "publisher_name",
    "publisher_type",
    "state_codes",
    "county_names",
    "covers",
)
BATCH_FILL_FIELDS = frozenset(
    {
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
)
STATE_PATH_RE = re.compile(r"^data/states/(?P<state>[a-z]{2})/sources\.jsonl$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ContributionError(ValueError):
    pass


def _load_validator(base_root: Path):
    path = base_root / "scripts" / "validate_catalog.py"
    spec = importlib.util.spec_from_file_location("trusted_catalog_validator", path)
    if spec is None or spec.loader is None:
        raise ContributionError("trusted catalog validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0"})
    return env


def _tree(root: Path) -> dict[str, tuple[str, str, str]]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=_git_env(),
    )
    if completed.returncode:
        raise ContributionError(completed.stderr.decode("utf-8", "replace").strip() or "cannot inspect Git tree")
    result: dict[str, tuple[str, str, str]] = {}
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        header, raw_path = raw.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ", 2)
        path = raw_path.decode("utf-8")
        result[path] = (mode, kind, oid)
    return result


def _changes(base: dict[str, tuple[str, str, str]], candidate: dict[str, tuple[str, str, str]]) -> dict[str, str]:
    changes: dict[str, str] = {}
    for path in sorted(set(base) | set(candidate)):
        if path not in base:
            changes[path] = "A"
        elif path not in candidate:
            changes[path] = "D"
        elif base[path] != candidate[path]:
            changes[path] = "M"
    return changes


def _json_object(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise ContributionError(f"{path.as_posix()}: duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContributionError(f"{path.as_posix()}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ContributionError(f"{path.as_posix()}: contribution must be a JSON object")
    return value


def _records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ContributionError(f"{path.as_posix()}:{number}: blank lines are not allowed")
        value = json.loads(line)
        if not isinstance(value, dict) or not isinstance(value.get("source_id"), str):
            raise ContributionError(f"{path.as_posix()}:{number}: invalid source record")
        source_id = value["source_id"]
        if source_id in records:
            raise ContributionError(f"{path.as_posix()}:{number}: duplicate source_id {source_id}")
        records[source_id] = value
    return records


def validate_transition(
    *,
    base_records: dict[str, dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
    packet: dict[str, Any],
    author: str,
    state: str,
    source_id: str,
) -> None:
    if tuple(packet) != PACKET_FIELDS:
        raise ContributionError(f"contribution fields must be exactly {list(PACKET_FIELDS)} in that order")
    if packet["schema_version"] != "national-civics-catalog.contribution.v1":
        raise ContributionError("unsupported contribution schema_version")
    if packet["change_kind"] not in {"fill", "add", "correct"}:
        raise ContributionError("change_kind must be fill, add, or correct")
    contributor = packet["contributor"]
    if not isinstance(contributor, dict) or tuple(contributor) != CONTRIBUTOR_FIELDS:
        raise ContributionError(f"contributor fields must be exactly {list(CONTRIBUTOR_FIELDS)} in that order")
    login = contributor["github_login"]
    if not isinstance(login, str) or login.casefold() != author.casefold():
        raise ContributionError("contributor github_login must match the pull-request author")
    tools = contributor["ai_tools"]
    if not isinstance(tools, list) or any(not isinstance(item, str) or not item.strip() for item in tools):
        raise ContributionError("ai_tools must be an array of non-empty tool names")
    if contributor["reviewed_by_contributor"] is not True:
        raise ContributionError("reviewed_by_contributor must be true")
    if not isinstance(packet["evidence_notes"], str) or not packet["evidence_notes"].strip():
        raise ContributionError("evidence_notes must be a non-empty factual note")
    source = packet["source"]
    if not isinstance(source, dict) or source.get("source_id") != source_id:
        raise ContributionError("packet source_id must match its contribution path")
    state_codes = source.get("state_codes")
    if not isinstance(state_codes, list) or not state_codes or min(state_codes).casefold() != state:
        raise ContributionError("contribution state folder must be the alphabetically first source state code")
    if candidate_records.get(source_id) != source:
        raise ContributionError("packet source must exactly match the canonical state record")

    changed_ids = sorted(
        key for key in set(base_records) | set(candidate_records)
        if base_records.get(key) != candidate_records.get(key)
    )
    if changed_ids != [source_id]:
        raise ContributionError(f"canonical state file must change exactly source_id {source_id}")
    if packet["change_kind"] == "fill":
        before = base_records.get(source_id)
        if before is None or len(candidate_records) != len(base_records):
            raise ContributionError("fill contribution must replace exactly one existing source")
        if before.get("status") != "needs_source":
            raise ContributionError("fill contribution must start from a needs_source record")
        if source.get("status") == "needs_source":
            raise ContributionError("fill contribution must provide a reviewed endpoint status")
        changed_identity = [field for field in FILL_IDENTITY_FIELDS if before.get(field) != source.get(field)]
        if changed_identity:
            raise ContributionError(
                "fill contribution cannot change preformed identity fields: " + ", ".join(changed_identity)
            )
    elif packet["change_kind"] == "add":
        if source_id in base_records or len(candidate_records) != len(base_records) + 1:
            raise ContributionError("add contribution must introduce exactly one new source")
    elif source_id not in base_records or len(candidate_records) != len(base_records):
        raise ContributionError("correct contribution must replace exactly one existing source")


def _validate_batch_manifest(
    *,
    packet: dict[str, Any],
    author: str,
    batch_id: str,
    base_root: Path,
    candidate_root: Path,
    state_paths: dict[str, str],
) -> int:
    if author.casefold() not in MAINTAINER_BATCH_AUTHORS:
        raise ContributionError("national batches may be submitted only by a trusted catalog maintainer")
    if tuple(packet) != BATCH_FIELDS:
        raise ContributionError(f"batch fields must be exactly {list(BATCH_FIELDS)} in that order")
    if packet["schema_version"] != "national-civics-catalog.maintainer-batch.v1":
        raise ContributionError("unsupported batch schema_version")
    if packet["batch_id"] != batch_id:
        raise ContributionError("batch_id must match the batch filename")
    maintainer = packet["maintainer"]
    if not isinstance(maintainer, dict) or tuple(maintainer) != BATCH_MAINTAINER_FIELDS:
        raise ContributionError(
            f"maintainer fields must be exactly {list(BATCH_MAINTAINER_FIELDS)} in that order"
        )
    login = maintainer["github_login"]
    if not isinstance(login, str) or login.casefold() != author.casefold():
        raise ContributionError("maintainer github_login must match the pull-request author")
    if not isinstance(packet["source_bundle_sha256"], str) or not SHA256_RE.fullmatch(
        packet["source_bundle_sha256"]
    ):
        raise ContributionError("source_bundle_sha256 must be a lowercase SHA-256 digest")
    tools = packet["ai_tools"]
    if not isinstance(tools, list) or not tools or any(
        not isinstance(item, str) or not item.strip() for item in tools
    ):
        raise ContributionError("ai_tools must be a non-empty array of non-empty tool names")
    candidates = packet["candidates"]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 250:
        raise ContributionError("candidates must contain between 1 and 250 source candidates")

    expected_ids: dict[str, set[str]] = {}
    seen_ids: set[str] = set()
    previous_key: tuple[str, str] | None = None
    for number, item in enumerate(candidates, 1):
        if not isinstance(item, dict) or tuple(item) != BATCH_CANDIDATE_FIELDS:
            raise ContributionError(
                f"candidate {number} fields must be exactly {list(BATCH_CANDIDATE_FIELDS)} in that order"
            )
        state = item["state_code"]
        source_id = item["source_id"]
        if not isinstance(state, str) or not re.fullmatch(r"[A-Z]{2}", state):
            raise ContributionError(f"candidate {number} state_code must be a two-letter uppercase code")
        if not isinstance(source_id, str) or not source_id:
            raise ContributionError(f"candidate {number} source_id must be non-empty")
        state_lower = state.casefold()
        key = (state_lower, source_id)
        if previous_key is not None and key <= previous_key:
            raise ContributionError("batch candidates must be uniquely sorted by state_code and source_id")
        previous_key = key
        if source_id in seen_ids:
            raise ContributionError(f"duplicate batch source_id {source_id}")
        seen_ids.add(source_id)
        if state_lower not in state_paths:
            raise ContributionError(f"candidate {source_id} has no matching changed state file")

        record = item["source"]
        if not isinstance(record, dict) or record.get("source_id") != source_id:
            raise ContributionError(f"candidate {source_id} source object must match source_id")
        state_codes = record.get("state_codes")
        if not isinstance(state_codes, list) or not state_codes or min(state_codes).casefold() != state_lower:
            raise ContributionError(f"candidate {source_id} belongs in a different state file")
        if record.get("status") != "unverified":
            raise ContributionError(f"candidate {source_id} must enter a batch as unverified")

        evidence = item["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ContributionError(f"candidate {source_id} must include at least one evidence item")
        for evidence_number, evidence_item in enumerate(evidence, 1):
            if not isinstance(evidence_item, dict) or tuple(evidence_item) != BATCH_EVIDENCE_FIELDS:
                raise ContributionError(
                    f"candidate {source_id} evidence {evidence_number} fields must be exactly "
                    f"{list(BATCH_EVIDENCE_FIELDS)} in that order"
                )
            if not isinstance(evidence_item["url"], str) or not evidence_item["url"].startswith(
                ("http://", "https://")
            ):
                raise ContributionError(f"candidate {source_id} evidence URL must be http(s)")
            if not isinstance(evidence_item["claim"], str) or not evidence_item["claim"].strip():
                raise ContributionError(f"candidate {source_id} evidence claim must be non-empty")
            if not isinstance(evidence_item["accessed_on"], str) or not DATE_RE.fullmatch(
                evidence_item["accessed_on"]
            ):
                raise ContributionError(f"candidate {source_id} evidence accessed_on must be YYYY-MM-DD")
        if not isinstance(item["notes"], str) or not item["notes"].strip():
            raise ContributionError(f"candidate {source_id} notes must be non-empty")
        expected_ids.setdefault(state_lower, set()).add(source_id)

    for state, state_path in state_paths.items():
        base_records = _records(base_root / state_path)
        candidate_records = _records(candidate_root / state_path)
        changed_ids = {
            source_id
            for source_id in set(base_records) | set(candidate_records)
            if base_records.get(source_id) != candidate_records.get(source_id)
        }
        if changed_ids != expected_ids.get(state, set()):
            raise ContributionError(f"state file {state_path} changes do not exactly match the batch manifest")
        if len(base_records) != len(candidate_records):
            raise ContributionError(f"batch state file {state_path} cannot add or remove source records")
        for source_id in sorted(changed_ids):
            before = base_records[source_id]
            after = candidate_records[source_id]
            manifest_source = next(item["source"] for item in candidates if item["source_id"] == source_id)
            if after != manifest_source:
                raise ContributionError(f"candidate {source_id} must exactly match its canonical state record")
            if before.get("status") != "needs_source":
                raise ContributionError(f"candidate {source_id} must start from a needs_source record")
            changed_fields = {field for field in set(before) | set(after) if before.get(field) != after.get(field)}
            disallowed = sorted(changed_fields - BATCH_FILL_FIELDS)
            if disallowed:
                raise ContributionError(
                    f"candidate {source_id} cannot change preformed fields: " + ", ".join(disallowed)
                )
    return len(candidates)


def _ordinary_repository_change(changes: dict[str, str]) -> bool:
    protected_prefixes = ("data/states/", "contributions/", "batches/")
    return bool(changes) and not any(path.startswith(protected_prefixes) for path in changes)


def run_check(base_root: Path, candidate_root: Path, author: str) -> str:
    base_tree = _tree(base_root)
    candidate_tree = _tree(candidate_root)
    changes = _changes(base_tree, candidate_tree)
    packet_paths = [path for path in changes if PACKET_RE.fullmatch(path)]
    batch_paths = [path for path in changes if BATCH_RE.fullmatch(path)]
    if _ordinary_repository_change(changes):
        return "Ready for human review: this pull request does not change catalog source data."
    if batch_paths:
        if packet_paths or len(batch_paths) != 1:
            raise ContributionError("a maintainer batch pull request must add exactly one batch manifest")
        batch_path = batch_paths[0]
        match = BATCH_RE.fullmatch(batch_path)
        assert match is not None
        if match.group("author").casefold() != author.casefold():
            raise ContributionError("batch filename must use the pull-request author's GitHub login")
        state_paths: dict[str, str] = {}
        for path in changes:
            state_match = STATE_PATH_RE.fullmatch(path)
            if state_match:
                state_paths[state_match.group("state")] = path
        if not state_paths or set(changes) != {batch_path, *state_paths.values()}:
            raise ContributionError("a maintainer batch may change only its manifest and matching state files")
        if changes[batch_path] != "A" or any(changes[path] != "M" for path in state_paths.values()):
            raise ContributionError("a batch manifest must be new and its state files may only be modified")
        for path in changes:
            entry = candidate_tree.get(path)
            if entry is None or entry[0] != "100644" or entry[1] != "blob":
                raise ContributionError(f"changed path must be an ordinary non-executable file: {path}")
        validator = _load_validator(base_root)
        count, errors = validator.validate_catalog(candidate_root / "data" / "states")
        if errors:
            raise ContributionError("catalog validation failed:\n- " + "\n- ".join(errors))
        packet = _json_object(candidate_root / batch_path)
        candidate_count = _validate_batch_manifest(
            packet=packet,
            author=author,
            batch_id=match.group("batch"),
            base_root=base_root,
            candidate_root=candidate_root,
            state_paths=state_paths,
        )
        return (
            f"Ready for human review: maintainer batch contains {candidate_count} unverified source "
            f"candidates; candidate catalog contains {count} source records."
        )
    if len(packet_paths) != 1:
        raise ContributionError(
            "catalog data changes require exactly one public evidence packet or one trusted maintainer batch manifest"
        )
    packet_path = packet_paths[0]
    match = PACKET_RE.fullmatch(packet_path)
    assert match is not None
    state = match.group("state")
    source_id = match.group("source")
    if match.group("author").casefold() != author.casefold():
        raise ContributionError("contribution filename must use the pull-request author's GitHub login")
    state_path = f"data/states/{state}/sources.jsonl"
    if set(changes) != {packet_path, state_path}:
        raise ContributionError("a contribution pull request may change only one state file and its evidence packet")
    if changes[packet_path] != "A" or changes[state_path] not in {"A", "M"}:
        raise ContributionError("evidence packet must be new and the state file may only be added or modified")
    for path in changes:
        entry = candidate_tree.get(path)
        if entry is None or entry[0] != "100644" or entry[1] != "blob":
            raise ContributionError(f"changed path must be an ordinary non-executable file: {path}")

    validator = _load_validator(base_root)
    count, errors = validator.validate_catalog(candidate_root / "data" / "states")
    if errors:
        raise ContributionError("catalog validation failed:\n- " + "\n- ".join(errors))
    packet = _json_object(candidate_root / packet_path)
    validate_transition(
        base_records=_records(base_root / state_path),
        candidate_records=_records(candidate_root / state_path),
        packet=packet,
        author=author,
        state=state,
        source_id=source_id,
    )
    return f"Ready for human review: one source contribution; candidate catalog contains {count} source records."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    try:
        message = run_check(args.base_root.resolve(), args.candidate_root.resolve(), args.author)
    except ContributionError as exc:
        message = f"Changes needed: {exc}"
        print(message, file=sys.stderr)
        if args.summary:
            args.summary.write_text(f"## Catalog contribution check\n\n{message}\n", encoding="utf-8")
        return 1
    print(message)
    if args.summary:
        args.summary.write_text(f"## Catalog contribution check\n\n{message}\n\nA person still reviews and merges every contribution.\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
