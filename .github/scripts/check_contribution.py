"""Check an outside contribution using trusted code from the base branch."""

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


STATE_FILE = re.compile(r"^states/(?P<state>[a-z]{2})\.jsonl$")


class ContributionError(ValueError):
    pass


def git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0"})
    return env


def tree(root: Path) -> dict[str, tuple[str, str, str]]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=git_env(),
    )
    if result.returncode:
        raise ContributionError(result.stderr.decode("utf-8", "replace").strip() or "cannot inspect Git tree")
    entries: dict[str, tuple[str, str, str]] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        header, raw_path = raw.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ", 2)
        entries[raw_path.decode("utf-8")] = (mode, kind, oid)
    return entries


def changed_paths(base: dict[str, tuple[str, str, str]], candidate: dict[str, tuple[str, str, str]]) -> list[str]:
    return sorted(path for path in set(base) | set(candidate) if base.get(path) != candidate.get(path))


def records(path: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContributionError(f"{path.as_posix()}:{number}: invalid JSON: {exc}") from exc
        source_id = value.get("source_id") if isinstance(value, dict) else None
        if not isinstance(source_id, str):
            raise ContributionError(f"{path.as_posix()}:{number}: missing source_id")
        if source_id in found:
            raise ContributionError(f"{path.as_posix()}:{number}: duplicate source_id {source_id}")
        found[source_id] = value
    return found


def load_validator(base_root: Path):
    path = base_root / ".github" / "scripts" / "validate_catalog.py"
    spec = importlib.util.spec_from_file_location("trusted_catalog_validator", path)
    if spec is None or spec.loader is None:
        raise ContributionError("trusted catalog validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_check(base_root: Path, candidate_root: Path) -> str:
    base_tree = tree(base_root)
    candidate_tree = tree(candidate_root)
    changes = changed_paths(base_tree, candidate_tree)
    if len(changes) != 1 or not STATE_FILE.fullmatch(changes[0]):
        raise ContributionError("an outside contribution must change exactly one states/<code>.jsonl file")
    state_path = changes[0]
    entry = candidate_tree.get(state_path)
    if entry is None or entry[0] != "100644" or entry[1] != "blob":
        raise ContributionError("the changed state path must be an ordinary, non-executable file")

    validator = load_validator(base_root)
    count, errors = validator.validate_catalog(candidate_root)
    if errors:
        raise ContributionError("catalog validation failed:\n- " + "\n- ".join(errors))

    before = records(base_root / state_path)
    after = records(candidate_root / state_path)
    changed_ids = sorted(source_id for source_id in set(before) | set(after) if before.get(source_id) != after.get(source_id))
    if len(changed_ids) != 1:
        raise ContributionError("the state file must add or correct exactly one catalog entry")
    source_id = changed_ids[0]
    if source_id not in after:
        raise ContributionError("outside contributions may not delete catalog entries")
    if source_id in before and before[source_id].get("source_id") != after[source_id].get("source_id"):
        raise ContributionError("an existing source_id must be preserved")
    if after[source_id].get("status") != "unverified":
        raise ContributionError("an outside contribution must leave its changed entry marked unverified")
    return f"Ready for maintainer review: one entry changed; candidate catalog contains {count} entries."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        message = run_check(args.base_root.resolve(), args.candidate_root.resolve())
    except ContributionError as exc:
        message = f"Changes needed: {exc}"
        print(message, file=sys.stderr)
        if args.summary:
            args.summary.write_text(f"## Trusted contribution check\n\n{message}\n", encoding="utf-8")
        return 1
    print(message)
    if args.summary:
        args.summary.write_text(
            f"## Trusted contribution check\n\n{message}\n\nThe check verifies structure; a maintainer still verifies the public evidence.\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
