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
PACKET_FIELDS = ("schema_version", "change_kind", "contributor", "source", "evidence_notes")
CONTRIBUTOR_FIELDS = ("github_login", "ai_tools", "reviewed_by_contributor")


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
    if packet["change_kind"] not in {"add", "correct"}:
        raise ContributionError("change_kind must be add or correct")
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
    if packet["change_kind"] == "add":
        if source_id in base_records or len(candidate_records) != len(base_records) + 1:
            raise ContributionError("add contribution must introduce exactly one new source")
    elif source_id not in base_records or len(candidate_records) != len(base_records):
        raise ContributionError("correct contribution must replace exactly one existing source")


def run_check(base_root: Path, candidate_root: Path, author: str) -> str:
    base_tree = _tree(base_root)
    candidate_tree = _tree(candidate_root)
    changes = _changes(base_tree, candidate_tree)
    packet_paths = [path for path in changes if PACKET_RE.fullmatch(path)]
    if len(packet_paths) != 1:
        raise ContributionError("a contribution pull request must add exactly one evidence packet")
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
