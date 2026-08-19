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


def packet(record: dict, *, kind: str = "add", login: str = "helper") -> dict:
    return {
        "schema_version": "national-civics-catalog.contribution.v1",
        "change_kind": kind,
        "contributor": {
            "github_login": login,
            "ai_tools": ["assistant"],
            "reviewed_by_contributor": True,
        },
        "source": record,
        "evidence_notes": "An official page identifies this continuing source.",
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


class TransitionTests(unittest.TestCase):
    def test_accepts_one_addition(self) -> None:
        record = source()
        checker.validate_transition(
            base_records={}, candidate_records={record["source_id"]: record},
            packet=packet(record), author="helper", state="az", source_id=record["source_id"],
        )

    def test_accepts_one_correction(self) -> None:
        before = source()
        after = {**before, "state_codes": ["AZ", "NM"]}
        checker.validate_transition(
            base_records={before["source_id"]: before}, candidate_records={after["source_id"]: after},
            packet=packet(after, kind="correct"), author="helper", state="az", source_id=after["source_id"],
        )

    def test_accepts_fill_of_preformed_record(self) -> None:
        before = source()
        after = {**before, "status": "unverified", "url": "https://example.gov/meetings"}
        checker.validate_transition(
            base_records={before["source_id"]: before}, candidate_records={after["source_id"]: after},
            packet=packet(after, kind="fill"), author="helper", state="az", source_id=after["source_id"],
        )

    def test_fill_cannot_rewrite_preformed_identity(self) -> None:
        before = source()
        after = {**before, "publisher_name": "Different Town", "status": "unverified"}
        with self.assertRaisesRegex(checker.ContributionError, "publisher_name"):
            checker.validate_transition(
                base_records={before["source_id"]: before}, candidate_records={after["source_id"]: after},
                packet=packet(after, kind="fill"), author="helper", state="az", source_id=after["source_id"],
            )

    def test_fill_requires_needs_source_base(self) -> None:
        before = {**source(), "status": "working"}
        after = {**before, "url": "https://example.gov/new-meetings"}
        with self.assertRaisesRegex(checker.ContributionError, "needs_source"):
            checker.validate_transition(
                base_records={before["source_id"]: before}, candidate_records={after["source_id"]: after},
                packet=packet(after, kind="fill"), author="helper", state="az", source_id=after["source_id"],
            )

    def test_rejects_an_unrelated_record_change(self) -> None:
        record = source()
        other = source("us-az-other-source")
        with self.assertRaises(checker.ContributionError):
            checker.validate_transition(
                base_records={}, candidate_records={record["source_id"]: record, other["source_id"]: other},
                packet=packet(record), author="helper", state="az", source_id=record["source_id"],
            )

    def test_rejects_author_mismatch(self) -> None:
        record = source()
        with self.assertRaises(checker.ContributionError):
            checker.validate_transition(
                base_records={}, candidate_records={record["source_id"]: record},
                packet=packet(record, login="someone-else"), author="helper", state="az", source_id=record["source_id"],
            )


class MaintainerBatchTests(unittest.TestCase):
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
        with temporary, self.assertRaisesRegex(checker.ContributionError, "publisher_name"):
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
