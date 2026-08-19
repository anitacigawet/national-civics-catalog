"""Safely update only the pinned external-model supervisor in a live workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def update_supervisor(workspace: Path, source: Path) -> dict[str, str]:
    workspace = workspace.resolve()
    source = source.resolve()
    manifest_path = workspace / "fleet_manifest.json"
    target = workspace / "engine" / "worker_supervisor.py"
    if not manifest_path.is_file() or not target.is_file() or not source.is_file():
        raise ValueError("workspace manifest, pinned supervisor, or replacement source is missing")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    current_bytes = target.read_bytes()
    current_hash = sha256_bytes(current_bytes)
    if current_hash != manifest.get("supervisor_sha256"):
        raise ValueError("current workspace supervisor differs from its manifest pin")
    replacement = source.read_bytes()
    replacement_hash = sha256_bytes(replacement)
    history = workspace / "engine" / "history"
    history.mkdir(parents=True, exist_ok=True)
    supervisor_backup = history / f"worker_supervisor.{current_hash}.py"
    manifest_backup = history / f"fleet_manifest.before-supervisor-{replacement_hash}.json"
    if not supervisor_backup.exists():
        with supervisor_backup.open("xb") as handle:
            handle.write(current_bytes)
    if not manifest_backup.exists():
        with manifest_backup.open("xb") as handle:
            handle.write(manifest_bytes)
    with target.open("wb") as handle:
        handle.write(replacement)
    manifest["supervisor_sha256"] = replacement_hash
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {
        "workspace": str(workspace),
        "previous_supervisor_sha256": current_hash,
        "supervisor_sha256": replacement_hash,
        "supervisor_backup": str(supervisor_backup),
        "manifest_backup": str(manifest_backup),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().with_name("worker_supervisor.py"),
    )
    args = parser.parse_args(argv)
    try:
        result = update_supervisor(args.workspace, args.source)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"UPDATE_STOP: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
