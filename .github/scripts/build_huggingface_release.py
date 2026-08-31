"""Build or verify the Hugging Face distribution from the canonical repository."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "AI_CONTRIBUTOR.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSE-MIT",
    "MIGRATING_V1_TO_V2.md",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "schema.json",
)
DIRECTORIES = (".github", "methodology", "repository-assets", "states")
HF_GITATTRIBUTES_SOURCE = ".github/huggingface.gitattributes"
HF_EXCLUDED_PATHS = {
    HF_GITATTRIBUTES_SOURCE,
    ".github/scripts/build_huggingface_release.py",
    ".github/scripts/test_build_huggingface_release.py",
}
FRONT_MATTER = """---
license: cc0-1.0
language:
- en
pretty_name: National Civics Catalog
size_categories:
- 10K<n<100K
tags:
- civic-data
- local-government
- public-meetings
- public-records
- open-data
- tabular
configs:
- config_name: default
  data_files:
  - split: catalog
    path: data/national.jsonl
---

"""
HF_BROWSE_INTRO = """This Hugging Face distribution includes two equivalent layouts:

- `data/national.jsonl` contains all {record_count:,} entries in one Dataset Viewer-ready file.
- `states/*.jsonl` preserves the canonical state-and-territory layout used by the [GitHub repository](https://github.com/anitacigawet/national-civics-catalog).

Load the complete catalog with the Hugging Face `datasets` library:

```python
from datasets import load_dataset

catalog = load_dataset(
    "ScootSolute/national-civics-catalog",
    split="catalog",
)
```

"""


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def dataset_card(root: Path, record_count: int) -> bytes:
    readme = (root / "README.md").read_text(encoding="utf-8")
    repository_count = f"total {record_count:,} locations checked."
    if readme.count(repository_count) != 1:
        raise ValueError(
            "README.md catalog count does not match the generated national dataset"
        )
    readme = readme.replace(
        repository_count,
        f"total {record_count:,} locations checked in this dataset release.",
        1,
    )
    marker = "### Auditing the catalog\n\n"
    if readme.count(marker) != 1:
        raise ValueError("README.md must contain exactly one Browse the catalog section")
    readme = readme.replace(
        marker,
        marker + HF_BROWSE_INTRO.format(record_count=record_count),
        1,
    )
    return (FRONT_MATTER + readme).encode("utf-8")


def expected_files(root: Path) -> dict[str, bytes]:
    state_paths = sorted((root / "states").glob("*.jsonl"))
    national = b"".join(path.read_bytes() for path in state_paths)
    record_count = len(national.splitlines())
    expected: dict[str, bytes] = {
        ".gitattributes": (root / HF_GITATTRIBUTES_SOURCE).read_bytes(),
        "README.md": dataset_card(root, record_count),
    }
    for relative in FILES:
        expected[relative] = (root / relative).read_bytes()
    for directory in DIRECTORIES:
        for path in sorted((root / directory).rglob("*")):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                if (
                    relative not in HF_EXCLUDED_PATHS
                    and "__pycache__" not in path.parts
                    and path.suffix != ".pyc"
                ):
                    expected[relative] = path.read_bytes()
    expected["data/national.jsonl"] = national
    return expected


def build(root: Path, output: Path, *, apply: bool) -> dict[str, object]:
    expected = expected_files(root)
    expected_paths = set(expected)
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
        and not path.relative_to(output).as_posix().startswith(".git/")
    }
    unexpected_paths = sorted(actual_paths - expected_paths)
    if unexpected_paths:
        raise ValueError(f"unexpected Hugging Face files: {unexpected_paths}")
    mismatches: list[str] = []
    for relative, payload in expected.items():
        target = output / Path(relative)
        if not target.is_file() or target.read_bytes() != payload:
            mismatches.append(relative)
            if apply:
                atomic_write(target, payload)
    if apply:
        remaining = [
            relative for relative, payload in expected.items()
            if not (output / Path(relative)).is_file()
            or (output / Path(relative)).read_bytes() != payload
        ]
        if remaining:
            raise ValueError(f"Hugging Face files still differ after build: {remaining}")
    records = sum(
        len(payload.splitlines())
        for relative, payload in expected.items()
        if relative.startswith("states/") and relative.endswith(".jsonl")
    )
    return {
        "mode": "applied" if apply else "verified",
        "managed_files": len(expected),
        "mismatches": mismatches,
        "records": records,
        "state_files": sum(
            path.startswith("states/") and path.endswith(".jsonl")
            for path in expected
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.root.resolve(), args.output.resolve(), apply=args.apply)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2))
    if not args.apply and result["mismatches"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
