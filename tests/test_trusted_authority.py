from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("trusted_check", ROOT / "tools" / "trusted_authority" / "check_pr.py")
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def source(source_id: str = "us-az-example-source") -> dict:
    return {
        "source_id": source_id,
        "publisher_name": "Example Town",
        "publisher_type": "municipality",
        "state_codes": ["AZ"],
        "county_names": ["Example County"],
        "status": "needs_source",
        "covers": [{"name": "Example Town", "census_geoid": "0412345"}],
    }


def batch_packet(record: dict, *, login: str = "anitacigawet") -> dict:
    return {
        "schema_version": "national-civics-catalog.maintainer-batch.v1",
        "batch_id": "fleet-001",
        "maintainer": {"github_login": login},
        "source_bundle_sha256": "a" * 64,
        "ai_tools": ["Claude Sonnet", "Gemini"],
        "candidates": [
            {
                "state_code": "AZ",
                "source_id": record["source_id"],
                "source": record,
                "evidence": [
                    {
                        "url": "https://example.gov/meetings",
                        "claim": "The official site identifies this as its continuing meetings page.",
                        "accessed_on": "2026-08-19",
                    }
                ],
                "notes": "Candidate retained as unverified for maintainer review.",
            }
        ],
    }


class MaintainerBatchTests(unittest.TestCase):
    def test_external_pull_requests_are_rejected_before_tree_inspection(self) -> None:
        with self.assertRaisesRegex(checker.CatalogChangeError, "does not accept external pull requests"):
            checker.run_check(Path("missing-base"), Path("missing-candidate"), "outside-helper")

    def test_batch_path_separates_author_from_batch_id(self) -> None:
        match = checker.BATCH_RE.fullmatch(
            "batches/2026-08-19/anitacigawet__fleet-2026-08-19-01.json"
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group("author"), "anitacigawet")
        self.assertEqual(match.group("batch"), "fleet-2026-08-19-01")

    def _roots(self, before: dict, after: dict) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        base_root = root / "base"
        candidate_root = root / "candidate"
        relative = Path("data/states/az/sources.jsonl")
        (base_root / relative).parent.mkdir(parents=True)
        (candidate_root / relative).parent.mkdir(parents=True)
        (base_root / relative).write_text(json.dumps(before, separators=(",", ":")) + "\n", encoding="utf-8")
        (candidate_root / relative).write_text(
            json.dumps(after, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        return temporary, base_root, candidate_root

    def test_accepts_trusted_unverified_batch_fill(self) -> None:
        before = source()
        after = {**before, "status": "unverified", "url": "https://example.gov/meetings"}
        temporary, base_root, candidate_root = self._roots(before, after)
        with temporary:
            count = checker._validate_batch_manifest(
                packet=batch_packet(after),
                author="anitacigawet",
                batch_id="fleet-001",
                base_root=base_root,
                candidate_root=candidate_root,
                state_paths={"az": "data/states/az/sources.jsonl"},
            )
        self.assertEqual(count, 1)

    def test_batch_cannot_change_preformed_identity(self) -> None:
        before = source()
        after = {
            **before,
            "publisher_name": "Different Town",
            "status": "unverified",
            "url": "https://example.gov/meetings",
        }
        temporary, base_root, candidate_root = self._roots(before, after)
        with temporary, self.assertRaisesRegex(checker.CatalogChangeError, "publisher_name"):
            checker._validate_batch_manifest(
                packet=batch_packet(after),
                author="anitacigawet",
                batch_id="fleet-001",
                base_root=base_root,
                candidate_root=candidate_root,
                state_paths={"az": "data/states/az/sources.jsonl"},
            )


if __name__ == "__main__":
    unittest.main()
