from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


def load(name: str):
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load("check_contribution")
validator = load("validate_catalog")


def record(code: str, *, identified: bool = False) -> dict:
    return {
        "schema_version": "2.0.0",
        "catalog_record_id": f"us-{code.lower()}-test--primary-meeting-source",
        "public_body_name": f"{code} Test",
        "public_body_type": "state",
        "state_codes": [code],
        "county_names": [],
        "public_body_website_url": "https://example.gov/" if identified else None,
        "roster_source_url": "https://www.census.gov/example",
        "meeting_source_type": "agenda_index" if identified else None,
        "meeting_source_url": "https://example.gov/agendas" if identified else None,
        "meeting_source_platform": "custom website" if identified else None,
        "meeting_source_access_method": "html" if identified else None,
        "meeting_source_relationship": "first_party" if identified else None,
        "meeting_source_status": "unverified" if identified else "needs_source",
        "meeting_source_last_checked_date": "2026-08-30" if identified else None,
        "meeting_source_evidence_url": "https://example.gov/council" if identified else None,
        "coverage": [{
            "name": f"{code} Test",
            "type": "state",
            "state_codes": [code],
            "county_names": [],
            "coverage_relationship": "direct_jurisdiction",
            "ocd_division_id": None,
            "census_geoid": "04",
        }],
    }


def git(*args: str, cwd: Path) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if completed.returncode:
        raise AssertionError(completed.stderr or completed.stdout)


class ContributionCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.base = self.root / "base"
        self.candidate = self.root / "candidate"
        (self.base / "states").mkdir(parents=True)
        (self.base / ".github" / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT_DIR / "validate_catalog.py", self.base / ".github" / "scripts")
        for code in sorted(validator.USPS_CODES):
            payload = json.dumps(record(code), separators=(",", ":")) + "\n"
            (self.base / "states" / f"{code.lower()}.jsonl").write_text(
                payload, encoding="utf-8", newline="\n"
            )
        self.base.joinpath("README.md").write_text(
            """- 🟢 0 identified meeting endpoints
- 🟢 0 identified meeting endpoints reviewed
- 🟡 0 identified meeting endpoints awaiting review
- 🔴 56 locations without an identified meeting endpoint
The identified and unidentified locations above total 56 locations checked.
""",
            encoding="utf-8",
            newline="\n",
        )
        git("init", "-q", cwd=self.base)
        git("config", "user.email", "test@example.invalid", cwd=self.base)
        git("config", "user.name", "Test", cwd=self.base)
        git("add", ".", cwd=self.base)
        git("commit", "-qm", "base", cwd=self.base)
        shutil.copytree(self.base, self.candidate, ignore=shutil.ignore_patterns(".git"))
        git("init", "-q", cwd=self.candidate)
        git("config", "user.email", "test@example.invalid", cwd=self.candidate)
        git("config", "user.name", "Test", cwd=self.candidate)
        git("add", ".", cwd=self.candidate)
        git("commit", "-qm", "base", cwd=self.candidate)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def commit_candidate(self) -> None:
        git("add", ".", cwd=self.candidate)
        git("commit", "-qm", "candidate", cwd=self.candidate)

    def identify_ak(self) -> None:
        path = self.candidate / "states" / "ak.jsonl"
        path.write_text(
            json.dumps(record("AK", identified=True), separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        validator.update_readme_snapshot(self.candidate)

    def test_one_entry_plus_generated_counts_is_allowed(self) -> None:
        self.identify_ak()
        self.commit_candidate()
        message = checker.run_check(self.base, self.candidate)
        self.assertIn("Ready for maintainer review", message)

    def test_arbitrary_readme_edit_is_rejected(self) -> None:
        self.identify_ak()
        with (self.candidate / "README.md").open("a", encoding="utf-8") as handle:
            handle.write("unrelated edit\n")
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "generated snapshot"):
            checker.run_check(self.base, self.candidate)

    def test_existing_roster_source_is_required(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["roster_source_url"] = None
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "roster_source_url"):
            checker.run_check(self.base, self.candidate)

    def test_maintainer_status_is_rejected(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["meeting_source_status"] = "working"
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        validator.update_readme_snapshot(self.candidate)
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "marked unverified"):
            checker.run_check(self.base, self.candidate)

    def test_unexpected_path_is_rejected(self) -> None:
        self.identify_ak()
        (self.candidate / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "may change one"):
            checker.run_check(self.base, self.candidate)

    def test_overlong_county_name_is_rejected(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["county_names"] = ["X" * 151]
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "at most 150"):
            checker.run_check(self.base, self.candidate)

    def test_missing_observation_date_is_rejected(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["meeting_source_last_checked_date"] = None
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "must be YYYY-MM-DD"):
            checker.run_check(self.base, self.candidate)

    def test_url_with_embedded_newline_is_rejected(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["meeting_source_url"] = "https://example.gov/agenda\nbad"
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "whitespace or control"):
            checker.run_check(self.base, self.candidate)

    def test_executable_readme_is_rejected(self) -> None:
        self.identify_ak()
        self.commit_candidate()
        git("update-index", "--chmod=+x", "README.md", cwd=self.candidate)
        git("commit", "-qm", "executable readme", cwd=self.candidate)
        with self.assertRaisesRegex(checker.ContributionError, "non-executable"):
            checker.run_check(self.base, self.candidate)

    def test_malformed_status_returns_controlled_contribution_error(self) -> None:
        self.identify_ak()
        path = self.candidate / "states" / "ak.jsonl"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["meeting_source_status"] = []
        path.write_text(
            json.dumps(changed, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.commit_candidate()
        with self.assertRaisesRegex(checker.ContributionError, "catalog validation failed"):
            checker.run_check(self.base, self.candidate)


if __name__ == "__main__":
    unittest.main()
