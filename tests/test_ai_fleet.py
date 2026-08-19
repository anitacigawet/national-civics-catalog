from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module("ai_fleet_builder", ROOT / "tools" / "ai_fleet" / "build_workspace.py")
fleet_module = load_module("ai_fleet_runtime", ROOT / "tools" / "ai_fleet" / "fleet.py")
supervisor_module = load_module(
    "ai_fleet_supervisor", ROOT / "tools" / "ai_fleet" / "worker_supervisor.py"
)


def source(state: str, suffix: str, publisher: str) -> dict:
    state_lower = state.lower()
    return {
        "source_id": f"us-{state_lower}-{suffix}--primary-meeting-source",
        "publisher_name": publisher,
        "publisher_type": "municipality",
        "state_codes": [state],
        "county_names": ["Example County"],
        "official_website_url": None,
        "endpoint_type": None,
        "url": None,
        "platform": None,
        "access_method": None,
        "source_relationship": None,
        "status": "needs_source",
        "last_checked": None,
        "provenance_url": "https://www.census.gov/data/datasets/2022/econ/gus/public-use-files.html",
        "covers": [
            {
                "name": publisher,
                "type": "municipality",
                "state_codes": [state],
                "county_names": ["Example County"],
                "relationship": "direct_jurisdiction",
                "ocd_division_id": None,
                "census_geoid": f"{ord(state[0]):02d}{ord(state[1]):02d}{len(suffix):03d}",
            }
        ],
    }


def write_state(catalog: Path, state: str, records: list[dict]) -> None:
    path = catalog / "data" / "states" / state.lower() / "sources.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


class FleetTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="civic-ai-fleet-test-"))
        self.catalog = base / "catalog"
        self.workspace = base / "workspace"
        write_state(
            self.catalog,
            "CA",
            [source("CA", "alpha", "Alpha City"), source("CA", "bravo", "Bravo City")],
        )
        write_state(self.catalog, "TX", [source("TX", "charlie", "Charlie City")])
        write_state(self.catalog, "NY", [source("NY", "protected", "Protected New York City")])
        self.built = builder.build_workspace(
            catalog_root=self.catalog,
            output_root=self.workspace,
            max_jobs_per_work_order=1,
            excluded_states={"NY"},
            python_command="python",
        )
        self.fleet = fleet_module.Fleet(self.workspace)

    def register(self, provider: str) -> dict:
        return self.fleet.register(provider, f"{provider}-model", f"{provider}-local-agent")

    def fill_identified_result(self, receipt: dict) -> Path:
        path = Path(receipt["result_path"])
        result = json.loads(path.read_text(encoding="utf-8"))
        original = self.fleet.work_state(receipt["work_order_id"])["jobs"][receipt["job_id"]]["source"]
        proposed = dict(original)
        proposed.update(
            {
                "official_website_url": "https://www.cityofpasadena.net/",
                "endpoint_type": "meeting_calendar",
                "url": "https://www.cityofpasadena.net/commissions/meetings/",
                "platform": "custom",
                "access_method": "html",
                "source_relationship": "first_party",
                "status": "unverified",
                "last_checked": "2026-08-19",
                "provenance_url": "https://www.cityofpasadena.net/city-clerk/",
            }
        )
        result.update(
            {
                "research_outcome": "source_identified",
                "continuing_source_confirmed": True,
                "officiality_confirmed": True,
                "proposed_source": proposed,
                "evidence": [
                    {
                        "url": "https://www.cityofpasadena.net/city-clerk/",
                        "claim": "The official city clerk page links to the continuing meetings surface.",
                        "accessed_on": "2026-08-19",
                    }
                ],
                "request_log": [
                    {
                        "url": "https://www.cityofpasadena.net/city-clerk/",
                        "tool": "chrome",
                        "outcome": "Official city page observed.",
                        "observed_at": "2026-08-19T12:00:00Z",
                    }
                ],
                "notes": "Official page and continuing calendar were both observed.",
            }
        )
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return path

    def test_builds_one_entry_point_and_excludes_new_york(self) -> None:
        self.assertTrue((self.workspace / "AI_START_HERE.md").is_file())
        text = (self.workspace / "AI_START_HERE.md").read_text(encoding="utf-8")
        self.assertIn("one canonical entry point", text)
        self.assertIn("New York is excluded", text)
        self.assertIn("C:/", text)
        self.assertNotIn('"python" -B', text)
        self.assertTrue((self.workspace / "GEMINI_FLEET_POLICY.toml").is_file())
        self.assertTrue((self.workspace / "engine" / "worker_supervisor.py").is_file())
        manifest = json.loads((self.workspace / "fleet_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(["NY"], manifest["excluded_states"])
        self.assertNotIn("NY", {item["state_code"] for item in manifest["work_orders"]})
        self.assertEqual(3, self.built["source_records"])

    def test_claude_and_gemini_receive_distinct_state_work_orders(self) -> None:
        claude = self.register("claude")
        gemini = self.register("gemini")
        self.assertTrue(claude["agent"]["agent_id"].startswith("claude-"))
        self.assertTrue(gemini["agent"]["agent_id"].startswith("gemini-"))
        self.assertNotEqual(claude["work_order_id"], gemini["work_order_id"])
        self.assertEqual("CA", claude["state_code"])
        self.assertEqual("TX", gemini["state_code"])

    def test_submit_preserves_identity_and_advances_across_work_orders(self) -> None:
        registered = self.register("claude")
        agent_id = registered["agent"]["agent_id"]
        first = self.fleet.claim(agent_id)
        result_path = self.fill_identified_result(first)
        accepted = self.fleet.submit(agent_id, first["job_id"], result_path)
        self.assertTrue(accepted["accepted"])
        second = self.fleet.claim(agent_id)
        self.assertEqual("TX", second["state_code"])

    def test_single_meeting_url_is_rejected_without_closing_claim(self) -> None:
        registered = self.register("gemini")
        agent_id = registered["agent"]["agent_id"]
        receipt = self.fleet.claim(agent_id)
        path = self.fill_identified_result(receipt)
        result = json.loads(path.read_text(encoding="utf-8"))
        result["proposed_source"]["url"] = "https://www.cityofpasadena.net/meetings/1234"
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(fleet_module.FleetError, "one meeting"):
            self.fleet.submit(agent_id, receipt["job_id"], path)
        resumed = self.fleet.claim(agent_id)
        self.assertTrue(resumed["resumed"])
        self.assertEqual(receipt["job_id"], resumed["job_id"])

    def test_unresolved_result_is_valid_terminal_research(self) -> None:
        registered = self.register("manus")
        agent_id = registered["agent"]["agent_id"]
        receipt = self.fleet.claim(agent_id)
        path = Path(receipt["result_path"])
        result = json.loads(path.read_text(encoding="utf-8"))
        result.update(
            {
                "research_outcome": "source_blocked",
                "evidence": [
                    {
                        "url": "https://www.cityofpasadena.net/city-clerk/",
                        "claim": "The official site was established but the meeting surface denied access.",
                        "accessed_on": "2026-08-19",
                    }
                ],
                "request_log": [
                    {
                        "url": "https://www.cityofpasadena.net/city-clerk/",
                        "tool": "chrome",
                        "outcome": "Official page loaded; linked meeting portal returned an access barrier.",
                        "observed_at": "2026-08-19T12:00:00Z",
                    }
                ],
                "notes": "The official publisher was established, but the continuing source could not be witnessed.",
            }
        )
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        accepted = self.fleet.submit(agent_id, receipt["job_id"], path)
        self.assertEqual("source_blocked", accepted["research_outcome"])

    def test_collect_writes_only_identified_candidates(self) -> None:
        registered = self.register("claude")
        agent_id = registered["agent"]["agent_id"]
        receipt = self.fleet.claim(agent_id)
        path = self.fill_identified_result(receipt)
        self.fleet.submit(agent_id, receipt["job_id"], path)
        output = self.workspace.parent / "review-bundle.jsonl"
        summary = self.fleet.collect(output)
        self.assertEqual(1, summary["collected_source_candidates"])
        row = json.loads(output.read_text(encoding="utf-8").strip())
        self.assertEqual(receipt["job_id"], row["job_id"])
        self.assertEqual("unverified", row["source"]["status"])

    def test_engine_or_queue_tampering_fails_loud(self) -> None:
        queue_path = next((self.workspace / "work_orders").glob("*/queue.json"))
        queue_path.write_text(queue_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(fleet_module.FleetError, "queue hash changed"):
            self.fleet.verify_integrity(full=True)

    def test_supervisor_gives_models_no_terminal_work(self) -> None:
        registered = self.register("gemini")
        receipt = self.fleet.claim(registered["agent"]["agent_id"])
        prompt = supervisor_module.research_prompt(receipt)
        self.assertIn("Do not use a terminal", prompt)
        self.assertIn("first_party or authorized_service", prompt)
        self.assertIn("url, tool, outcome, observed_at", prompt)
        self.assertIn(Path(receipt["result_path"]).as_posix(), prompt)
        command = supervisor_module.model_command(
            provider="gemini",
            executable=Path("agy.exe"),
            model="gemini-3.1-pro-high",
            prompt=prompt,
            attempt_directory=Path(receipt["result_path"]).parent,
            timeout="20m",
        )
        self.assertIn("--sandbox", command)
        self.assertNotIn("--dangerously-skip-permissions", command)

    def test_supervisor_recognizes_only_explicit_quota_failures(self) -> None:
        self.assertTrue(
            supervisor_module.quota_exhausted(
                '{"error":"RESOURCE_EXHAUSTED: Resource has been exhausted"}', ""
            )
        )
        self.assertTrue(supervisor_module.quota_exhausted("", "Quota exceeded; retry later"))
        self.assertFalse(supervisor_module.quota_exhausted("authentication expired", ""))

    def test_claude_command_preapproves_only_bounded_tools(self) -> None:
        command = supervisor_module.model_command(
            provider="claude",
            executable=Path("claude.exe"),
            model="sonnet",
            prompt="bounded task",
            attempt_directory=Path("attempts"),
            timeout="20m",
        )
        self.assertIn("--allowedTools", command)
        self.assertIn("Read,Edit,WebSearch,WebFetch", command)
        self.assertNotIn("Bash", command)
        self.assertIn("--safe-mode", command)


if __name__ == "__main__":
    unittest.main()
