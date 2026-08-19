"""Provider-neutral, file-backed discovery fleet for catalog source records.

The runtime workspace is generated outside the catalog repository.  This module
is copied into that workspace and deliberately uses only the Python standard
library so Manus, Claude, Gemini, or another local agent can run the same
commands without installing dependencies.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit
import uuid


WORKSPACE_SCHEMA = "national-civics-catalog.ai-fleet.v1"
QUEUE_SCHEMA = "national-civics-catalog.ai-fleet.queue.v1"
RESULT_SCHEMA = "national-civics-catalog.ai-fleet.result.v1"
EVENT_SCHEMA = "national-civics-catalog.ai-fleet.event.v1"
MAX_ATTEMPTS = 3

RESULT_FIELDS = (
    "schema_version",
    "job_id",
    "work_order_id",
    "agent",
    "source_record",
    "research_outcome",
    "continuing_source_confirmed",
    "officiality_confirmed",
    "proposed_source",
    "evidence",
    "request_log",
    "notes",
)
AGENT_FIELDS = ("agent_id", "provider", "model", "surface")
EVIDENCE_FIELDS = ("url", "claim", "accessed_on")
REQUEST_FIELDS = ("url", "tool", "outcome", "observed_at")
SOURCE_FIELDS = (
    "source_id",
    "publisher_name",
    "publisher_type",
    "state_codes",
    "county_names",
    "official_website_url",
    "endpoint_type",
    "url",
    "platform",
    "access_method",
    "source_relationship",
    "status",
    "last_checked",
    "provenance_url",
    "covers",
)
IDENTITY_FIELDS = (
    "source_id",
    "publisher_name",
    "publisher_type",
    "state_codes",
    "county_names",
    "covers",
)
MUTABLE_SOURCE_FIELDS = (
    "official_website_url",
    "endpoint_type",
    "url",
    "platform",
    "access_method",
    "source_relationship",
    "status",
    "last_checked",
    "provenance_url",
)
OUTCOMES = {
    "source_identified",
    "source_blocked",
    "no_official_source_found",
    "needs_review",
}
ENDPOINT_TYPES = {
    "primary_meeting_source",
    "meeting_calendar",
    "agenda_index",
    "minutes_index",
    "public_notices_index",
    "video_archive",
    "api",
    "feed",
    "other",
}
ACCESS_METHODS = {"html", "json", "rss", "ical", "api", "pdf_index", "other"}
SOURCE_RELATIONSHIPS = {"first_party", "authorized_service"}
SAFE_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
CREDENTIAL_RE = re.compile(
    r"(?:^|[/?&#;])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|"
    r"password|passwd|secret|client[_-]?secret|signature|sig|credential)[=:]",
    re.IGNORECASE,
)
SINGLE_RECORD_PATH_RE = re.compile(
    r"(?:^|/)(?:meeting[_-]?details?|meetingdetail(?:\.aspx)?|events?/\d+|"
    r"meetings?/\d+|recordings?/\d+|clips?/\d+)(?:/|$)",
    re.IGNORECASE,
)
SINGLE_RECORD_QUERY_RE = re.compile(
    r"(?:^|[?&#;])(?:meeting[_-]?id|event[_-]?id|clip[_-]?id)=",
    re.IGNORECASE,
)
DOCUMENT_SUFFIXES = {
    ".doc", ".docx", ".m4a", ".mov", ".mp3", ".mp4", ".pdf",
    ".ppt", ".pptx", ".srt", ".vtt", ".wav", ".xls", ".xlsx",
}
SPECIAL_HOST_SUFFIXES = {
    "localhost", "local", "home.arpa", "arpa", "onion", "invalid",
    "test", "example", "example.com", "example.net", "example.org",
}


class FleetError(ValueError):
    """A contract or integrity error that should stop the current command."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    def unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise FleetError(f"duplicate JSON key {key!r} in {path}")
            result[key] = item
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FleetError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FleetError(f"expected a JSON object in {path}")
    return value


def require_exact_keys(value: Any, keys: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or tuple(value) != keys:
        raise FleetError(f"{label} fields must be exactly {list(keys)} in that order")
    return value


def clean_text(value: Any, label: str, *, max_length: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FleetError(f"{label} must be a non-empty, trimmed string")
    if len(value) > max_length:
        raise FleetError(f"{label} exceeds {max_length} characters")
    return value


def _decode_bounded(value: str) -> str:
    decoded = value
    for _ in range(3):
        candidate = unquote(decoded)
        if candidate == decoded:
            break
        decoded = candidate
    return decoded


def validate_url(value: Any, label: str, *, continuing: bool = False) -> str:
    url = clean_text(value, label, max_length=2048)
    if not url.startswith("https://"):
        raise FleetError(f"{label} must begin with literal https://")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise FleetError(f"{label} is invalid: {exc}") from exc
    if parsed.username is not None or parsed.password is not None:
        raise FleetError(f"{label} must not contain credentials")
    if parsed.scheme != "https" or not parsed.hostname or port not in (None, 443):
        raise FleetError(f"{label} must use HTTPS, a DNS hostname, and the default port")
    host = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise FleetError(f"{label} must use a DNS hostname, not an IP literal")
    labels = host.split(".")
    if len(labels) < 2 or any(not DNS_LABEL_RE.fullmatch(part) for part in labels):
        raise FleetError(f"{label} has an invalid DNS hostname")
    if any(host == suffix or host.endswith("." + suffix) for suffix in SPECIAL_HOST_SUFFIXES):
        raise FleetError(f"{label} uses a local, reserved, or example hostname")
    decoded_path = _decode_bounded(parsed.path)
    decoded_query = _decode_bounded(parsed.query)
    decoded_fragment = _decode_bounded(parsed.fragment)
    surface = f"/{decoded_path}?{decoded_query}#{decoded_fragment}"
    if CREDENTIAL_RE.search(surface):
        raise FleetError(f"{label} appears to contain credential material")
    if continuing:
        clean_path = "/".join(part.split(";", 1)[0] for part in decoded_path.split("/"))
        if PurePosixPath(clean_path).suffix.casefold() in DOCUMENT_SUFFIXES:
            raise FleetError(f"{label} points to one downloadable artifact, not a continuing source")
        if SINGLE_RECORD_PATH_RE.search(clean_path) or SINGLE_RECORD_QUERY_RE.search(
            f"?{decoded_query}#{decoded_fragment}"
        ):
            raise FleetError(f"{label} appears to identify one meeting or recording")
    return url


class PortableFileLock:
    """One-byte advisory lock that leaves a harmless lock file in place."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "PortableFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        assert self.handle is not None
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


class Fleet:
    def __init__(self, workspace: Path) -> None:
        self.root = workspace.resolve()
        self.manifest_path = self.root / "fleet_manifest.json"
        self.global_events_path = self.root / "fleet_events.jsonl"
        self.lock_path = self.root / "fleet.lock"
        self.manifest = load_json(self.manifest_path)

    @contextmanager
    def locked(self, *, full_verify: bool = False) -> Iterator[None]:
        with PortableFileLock(self.lock_path):
            self.verify_integrity(full=full_verify)
            yield

    def verify_integrity(self, *, full: bool = True) -> None:
        if self.manifest.get("schema_version") != WORKSPACE_SCHEMA:
            raise FleetError("unsupported workspace schema")
        excluded = self.manifest.get("excluded_states")
        if not isinstance(excluded, list) or "NY" not in excluded:
            raise FleetError("workspace does not carry the mandatory New York exclusion")
        expected_engine = self.manifest.get("engine_sha256")
        if not isinstance(expected_engine, str) or sha256_file(Path(__file__).resolve()) != expected_engine:
            raise FleetError("fleet engine hash differs from the pinned workspace engine")
        orders = self.manifest.get("work_orders")
        if not isinstance(orders, list) or not orders:
            raise FleetError("workspace has no work orders")
        seen: set[str] = set()
        for order in orders:
            if not isinstance(order, dict):
                raise FleetError("invalid work-order manifest entry")
            order_id = order.get("work_order_id")
            state_code = order.get("state_code")
            if not isinstance(order_id, str) or order_id in seen:
                raise FleetError("duplicate or invalid work-order id")
            if state_code == "NY":
                raise FleetError("New York is forbidden in this workspace")
            seen.add(order_id)
            queue_path = self.safe_relative_path(order.get("queue_path"), "queue path")
            if not queue_path.is_file():
                raise FleetError(f"immutable queue is missing for {order_id}")
            if full and sha256_file(queue_path) != order.get("queue_sha256"):
                raise FleetError(f"immutable queue hash changed for {order_id}")
        self.read_ledger(self.global_events_path)
        if full:
            for order in orders:
                self.read_ledger(self.order_events_path(order["work_order_id"]))

    def safe_relative_path(self, value: Any, label: str) -> Path:
        if not isinstance(value, str) or not value:
            raise FleetError(f"{label} is missing")
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise FleetError(f"{label} escapes the workspace") from exc
        return candidate

    def order_entry(self, order_id: str) -> dict[str, Any]:
        for order in self.manifest["work_orders"]:
            if order["work_order_id"] == order_id:
                return order
        raise FleetError(f"unknown work order {order_id}")

    def order_root(self, order_id: str) -> Path:
        return self.root / "work_orders" / order_id

    def order_events_path(self, order_id: str) -> Path:
        return self.order_root(order_id) / "events.jsonl"

    def order_queue(self, order_id: str) -> dict[str, Any]:
        entry = self.order_entry(order_id)
        queue_path = self.safe_relative_path(entry["queue_path"], "queue path")
        if sha256_file(queue_path) != entry.get("queue_sha256"):
            raise FleetError(f"immutable queue hash changed for {order_id}")
        queue = load_json(queue_path)
        if queue.get("schema_version") != QUEUE_SCHEMA or queue.get("work_order_id") != order_id:
            raise FleetError(f"queue identity mismatch for {order_id}")
        if queue.get("state_code") == "NY":
            raise FleetError("New York is forbidden in this workspace")
        jobs = queue.get("jobs")
        if not isinstance(jobs, list) or len(jobs) != entry.get("job_count"):
            raise FleetError(f"queue count mismatch for {order_id}")
        return queue

    def read_ledger(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise FleetError(f"ledger is missing: {path}")
        events: list[dict[str, Any]] = []
        previous = "GENESIS"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise FleetError(f"blank line in ledger {path}:{number}")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FleetError(f"invalid ledger JSON {path}:{number}: {exc}") from exc
            if not isinstance(event, dict) or event.get("schema_version") != EVENT_SCHEMA:
                raise FleetError(f"invalid event schema in {path}:{number}")
            supplied_hash = event.get("event_hash")
            payload = {key: value for key, value in event.items() if key != "event_hash"}
            if event.get("previous_hash") != previous:
                raise FleetError(f"broken ledger chain in {path}:{number}")
            actual_hash = sha256_bytes(canonical_json(payload).encode("utf-8"))
            if supplied_hash != actual_hash:
                raise FleetError(f"event hash mismatch in {path}:{number}")
            previous = actual_hash
            events.append(event)
        return events

    def append_event(self, path: Path, event_type: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = self.read_ledger(path)
        previous = events[-1]["event_hash"] if events else "GENESIS"
        payload = {
            "schema_version": EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "recorded_at": utc_now(),
            "event_type": event_type,
            "detail": detail,
            "previous_hash": previous,
        }
        event = {**payload, "event_hash": sha256_bytes(canonical_json(payload).encode("utf-8"))}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def agents(self) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for event in self.read_ledger(self.global_events_path):
            if event["event_type"] == "agent_registered":
                detail = event["detail"]
                result[detail["agent_id"]] = {
                    "agent_id": detail["agent_id"],
                    "provider": detail["provider"],
                    "model": detail["model"],
                    "surface": detail["surface"],
                }
        return result

    def assignments(self) -> tuple[dict[str, str], set[str]]:
        active: dict[str, str] = {}
        completed: set[str] = set()
        for event in self.read_ledger(self.global_events_path):
            detail = event["detail"]
            if event["event_type"] == "work_order_assigned":
                active[detail["agent_id"]] = detail["work_order_id"]
            elif event["event_type"] == "work_order_completed":
                completed.add(detail["work_order_id"])
                if active.get(detail["agent_id"]) == detail["work_order_id"]:
                    active.pop(detail["agent_id"], None)
        return active, completed

    def register(self, provider: str, model: str, surface: str) -> dict[str, Any]:
        provider = provider.strip().lower()
        if not SAFE_TOKEN_RE.fullmatch(provider):
            raise FleetError("provider must use 1-64 lowercase letters, digits, dots, underscores, or hyphens")
        clean_text(model, "model", max_length=120)
        clean_text(surface, "surface", max_length=120)
        with self.locked():
            agent_id = f"{provider}-{uuid.uuid4().hex[:10]}"
            detail = {"agent_id": agent_id, "provider": provider, "model": model, "surface": surface}
            self.append_event(self.global_events_path, "agent_registered", detail)
            order_id = self.assign_next(agent_id)
            return self.agent_receipt(agent_id, order_id)

    def require_agent(self, agent_id: str) -> dict[str, str]:
        agent = self.agents().get(agent_id)
        if agent is None:
            raise FleetError(f"unknown agent id {agent_id}; register through AI_START_HERE.md")
        return agent

    def assign_next(self, agent_id: str) -> str | None:
        active, completed = self.assignments()
        if agent_id in active:
            return active[agent_id]
        assigned_orders = set(active.values())
        for order in self.manifest["work_orders"]:
            order_id = order["work_order_id"]
            if order_id not in completed and order_id not in assigned_orders:
                self.append_event(
                    self.global_events_path,
                    "work_order_assigned",
                    {"agent_id": agent_id, "work_order_id": order_id, "state_code": order["state_code"]},
                )
                return order_id
        return None

    def agent_receipt(self, agent_id: str, order_id: str | None) -> dict[str, Any]:
        agent = self.require_agent(agent_id)
        result: dict[str, Any] = {"agent": agent, "work_order_id": order_id}
        if order_id is None:
            result["fleet_exhausted"] = True
        else:
            order = self.order_entry(order_id)
            result.update({
                "state_code": order["state_code"],
                "assigned_jobs": order["job_count"],
                "next_action": "claim",
                "claim_command": self.command("claim", "--agent-id", agent_id),
            })
        return result

    def command(self, action: str, *parts: str) -> str:
        python = self.manifest.get("python_command") or sys.executable
        engine = self.root / "engine" / "fleet.py"
        quoted = [f'"{python}"', "-B", f'"{engine}"', "--workspace", f'"{self.root}"', action]
        quoted.extend(f'"{part}"' if any(char.isspace() for char in part) else part for part in parts)
        return " ".join(quoted)

    def work_state(self, order_id: str) -> dict[str, Any]:
        queue = self.order_queue(order_id)
        jobs = {job["job_id"]: job for job in queue["jobs"]}
        completed: set[str] = set()
        blocked: set[str] = set()
        attempts: dict[str, int] = {}
        active: dict[str, dict[str, Any]] = {}
        for event in self.read_ledger(self.order_events_path(order_id)):
            detail = event["detail"]
            job_id = detail.get("job_id")
            if event["event_type"] == "job_claimed":
                attempts[job_id] = int(detail["attempt"])
                active[detail["agent_id"]] = detail
            elif event["event_type"] in {"job_submitted", "attempt_failed", "job_blocked"}:
                for active_agent, claim in list(active.items()):
                    if claim.get("job_id") == job_id:
                        active.pop(active_agent, None)
                if event["event_type"] == "job_submitted":
                    completed.add(job_id)
                elif event["event_type"] == "job_blocked":
                    blocked.add(job_id)
        unknown = (completed | blocked | {item["job_id"] for item in active.values()}) - set(jobs)
        if unknown:
            raise FleetError(f"ledger references unknown jobs in {order_id}: {sorted(unknown)}")
        ready = [job for job in queue["jobs"] if job["job_id"] not in completed | blocked]
        return {
            "queue": queue,
            "jobs": jobs,
            "completed": completed,
            "blocked": blocked,
            "attempts": attempts,
            "active": active,
            "ready": ready,
        }

    def claim(self, agent_id: str) -> dict[str, Any]:
        with self.locked():
            agent = self.require_agent(agent_id)
            active_assignments, _ = self.assignments()
            order_id = active_assignments.get(agent_id) or self.assign_next(agent_id)
            while order_id is not None:
                state = self.work_state(order_id)
                if agent_id in state["active"]:
                    return self.claim_receipt(agent, order_id, state["active"][agent_id], resumed=True)
                if state["ready"]:
                    job = state["ready"][0]
                    attempt = state["attempts"].get(job["job_id"], 0) + 1
                    result_path = self.create_result_skeleton(agent, order_id, job, attempt)
                    detail = {
                        "agent_id": agent_id,
                        "job_id": job["job_id"],
                        "source_id": job["source"]["source_id"],
                        "attempt": attempt,
                        "result_path": result_path.relative_to(self.root).as_posix(),
                    }
                    self.append_event(self.order_events_path(order_id), "job_claimed", detail)
                    return self.claim_receipt(agent, order_id, detail, resumed=False)
                if state["active"]:
                    raise FleetError(f"work order {order_id} has a claim owned by another agent")
                self.append_event(
                    self.global_events_path,
                    "work_order_completed",
                    {"agent_id": agent_id, "work_order_id": order_id, "state_code": state["queue"]["state_code"]},
                )
                order_id = self.assign_next(agent_id)
            return {"agent_id": agent_id, "fleet_exhausted": True}

    def create_result_skeleton(
        self,
        agent: dict[str, str],
        order_id: str,
        job: dict[str, Any],
        attempt: int,
    ) -> Path:
        attempts = self.order_root(order_id) / "attempts"
        attempts.mkdir(parents=True, exist_ok=True)
        path = attempts / f"{job['job_id']}--attempt-{attempt:02d}.json"
        if path.exists():
            raise FleetError(f"attempt result already exists: {path}")
        source = job["source"]
        skeleton = {
            "schema_version": RESULT_SCHEMA,
            "job_id": job["job_id"],
            "work_order_id": order_id,
            "agent": {field: agent[field] for field in AGENT_FIELDS},
            "source_record": source,
            "research_outcome": "needs_review",
            "continuing_source_confirmed": False,
            "officiality_confirmed": False,
            "proposed_source": None,
            "evidence": [],
            "request_log": [],
            "notes": "Replace with a precise factual note before submission.",
        }
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(skeleton, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return path

    def claim_receipt(
        self,
        agent: dict[str, str],
        order_id: str,
        detail: dict[str, Any],
        *,
        resumed: bool,
    ) -> dict[str, Any]:
        order = self.order_entry(order_id)
        result_path = self.safe_relative_path(detail["result_path"], "result path")
        job = self.work_state(order_id)["jobs"][detail["job_id"]]
        return {
            "resumed": resumed,
            "agent_id": agent["agent_id"],
            "provider": agent["provider"],
            "model": agent["model"],
            "work_order_id": order_id,
            "state_code": order["state_code"],
            "job_id": detail["job_id"],
            "attempt": detail["attempt"],
            "publisher_name": job["source"]["publisher_name"],
            "publisher_type": job["source"]["publisher_type"],
            "result_path": str(result_path),
            "instruction": "Research only this continuing civic source. Edit only result_path, submit it, then claim again.",
            "submit_command": self.command(
                "submit", "--agent-id", agent["agent_id"], "--job-id", detail["job_id"],
                "--result", str(result_path),
            ),
        }

    def active_claim(self, agent_id: str, job_id: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        active_assignments, _ = self.assignments()
        order_id = active_assignments.get(agent_id)
        if order_id is None:
            raise FleetError(f"agent {agent_id} has no active work order")
        state = self.work_state(order_id)
        claim = state["active"].get(agent_id)
        if claim is None or claim.get("job_id") != job_id:
            raise FleetError(f"job {job_id} is not the active claim for {agent_id}")
        return order_id, state, claim

    def validate_result(
        self,
        result_path: Path,
        agent: dict[str, str],
        order_id: str,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = result_path.resolve()
        expected_root = (self.order_root(order_id) / "attempts").resolve()
        try:
            resolved.relative_to(expected_root)
        except ValueError as exc:
            raise FleetError("result path is outside the active work order") from exc
        result = load_json(resolved)
        require_exact_keys(result, RESULT_FIELDS, "result")
        if result["schema_version"] != RESULT_SCHEMA:
            raise FleetError("unsupported result schema")
        if result["job_id"] != job["job_id"] or result["work_order_id"] != order_id:
            raise FleetError("result identity differs from the active claim")
        if result["agent"] != {field: agent[field] for field in AGENT_FIELDS}:
            raise FleetError("result agent provenance differs from registration")
        source = job["source"]
        if result["source_record"] != source:
            raise FleetError("preformed source record was changed")
        outcome = result["research_outcome"]
        if outcome not in OUTCOMES:
            raise FleetError(f"unsupported research_outcome {outcome!r}")
        evidence = result["evidence"]
        requests = result["request_log"]
        if not isinstance(evidence, list) or not evidence:
            raise FleetError("evidence must contain at least one exact supporting page")
        if not isinstance(requests, list) or not requests:
            raise FleetError("request_log must contain at least one observed research request")
        for index, item in enumerate(evidence):
            require_exact_keys(item, EVIDENCE_FIELDS, f"evidence[{index}]")
            validate_url(item["url"], f"evidence[{index}].url")
            clean_text(item["claim"], f"evidence[{index}].claim", max_length=1000)
            try:
                date.fromisoformat(item["accessed_on"])
            except (TypeError, ValueError) as exc:
                raise FleetError(f"evidence[{index}].accessed_on must be YYYY-MM-DD") from exc
        for index, item in enumerate(requests):
            require_exact_keys(item, REQUEST_FIELDS, f"request_log[{index}]")
            validate_url(item["url"], f"request_log[{index}].url")
            clean_text(item["tool"], f"request_log[{index}].tool", max_length=80)
            clean_text(item["outcome"], f"request_log[{index}].outcome", max_length=1000)
            try:
                datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise FleetError(f"request_log[{index}].observed_at must be an ISO timestamp") from exc
        clean_text(result["notes"], "notes", max_length=4000)
        if outcome == "source_identified":
            if result["continuing_source_confirmed"] is not True:
                raise FleetError("source_identified requires continuing_source_confirmed=true")
            if result["officiality_confirmed"] is not True:
                raise FleetError("source_identified requires officiality_confirmed=true")
            self.validate_proposed_source(result["proposed_source"], source)
        else:
            if result["proposed_source"] is not None:
                raise FleetError("unresolved outcomes must leave proposed_source null")
            if result["continuing_source_confirmed"] is not False:
                raise FleetError("unresolved outcomes must leave continuing_source_confirmed=false")
        return result

    def validate_proposed_source(self, proposed: Any, original: dict[str, Any]) -> None:
        require_exact_keys(proposed, SOURCE_FIELDS, "proposed_source")
        for field in IDENTITY_FIELDS:
            if proposed[field] != original[field]:
                raise FleetError(f"proposed_source cannot change preformed identity field {field}")
        for field in MUTABLE_SOURCE_FIELDS:
            if field not in proposed:
                raise FleetError(f"proposed_source is missing {field}")
        validate_url(proposed["official_website_url"], "proposed_source.official_website_url")
        if proposed["endpoint_type"] not in ENDPOINT_TYPES:
            raise FleetError("proposed_source.endpoint_type is unsupported")
        validate_url(proposed["url"], "proposed_source.url", continuing=True)
        clean_text(proposed["platform"], "proposed_source.platform", max_length=100)
        if proposed["access_method"] not in ACCESS_METHODS:
            raise FleetError("proposed_source.access_method is unsupported")
        if proposed["source_relationship"] not in SOURCE_RELATIONSHIPS:
            raise FleetError("proposed_source.source_relationship is unsupported")
        if proposed["status"] != "unverified":
            raise FleetError("AI-discovered sources must enter review as status=unverified")
        if proposed["last_checked"] is not None:
            try:
                date.fromisoformat(proposed["last_checked"])
            except (TypeError, ValueError) as exc:
                raise FleetError("proposed_source.last_checked must be null or YYYY-MM-DD") from exc
        validate_url(proposed["provenance_url"], "proposed_source.provenance_url")

    def submit(self, agent_id: str, job_id: str, result_path: Path) -> dict[str, Any]:
        with self.locked():
            agent = self.require_agent(agent_id)
            order_id, state, claim = self.active_claim(agent_id, job_id)
            expected_path = self.safe_relative_path(claim["result_path"], "active result path")
            if result_path.resolve() != expected_path:
                raise FleetError("submit must use the exact result_path printed by claim")
            result = self.validate_result(result_path, agent, order_id, state["jobs"][job_id])
            detail = {
                "agent_id": agent_id,
                "job_id": job_id,
                "attempt": claim["attempt"],
                "research_outcome": result["research_outcome"],
                "result_path": claim["result_path"],
                "result_sha256": sha256_file(result_path),
            }
            self.append_event(self.order_events_path(order_id), "job_submitted", detail)
            next_command = self.command("claim", "--agent-id", agent_id)
            return {
                "accepted": True,
                "agent_id": agent_id,
                "work_order_id": order_id,
                "job_id": job_id,
                "research_outcome": result["research_outcome"],
                "next_action": "claim",
                "next_command": next_command,
            }

    def fail_attempt(self, agent_id: str, job_id: str, reason: str) -> dict[str, Any]:
        clean_text(reason, "reason", max_length=1000)
        with self.locked():
            self.require_agent(agent_id)
            order_id, state, claim = self.active_claim(agent_id, job_id)
            self.append_event(
                self.order_events_path(order_id),
                "attempt_failed",
                {"agent_id": agent_id, "job_id": job_id, "attempt": claim["attempt"], "reason": reason},
            )
            blocked = claim["attempt"] >= MAX_ATTEMPTS
            if blocked:
                self.append_event(
                    self.order_events_path(order_id),
                    "job_blocked",
                    {"agent_id": agent_id, "job_id": job_id, "attempts": claim["attempt"], "reason": reason},
                )
            return {
                "recorded": True,
                "blocked": blocked,
                "agent_id": agent_id,
                "job_id": job_id,
                "next_command": self.command("claim", "--agent-id", agent_id),
            }

    def status(self, agent_id: str | None = None) -> dict[str, Any]:
        with self.locked():
            agents = self.agents()
            if agent_id is not None and agent_id not in agents:
                raise FleetError(f"unknown agent id {agent_id}")
            assignments, completed_orders = self.assignments()
            total_jobs = completed_jobs = blocked_jobs = active_jobs = 0
            state_counts: dict[str, dict[str, int]] = {}
            for order in self.manifest["work_orders"]:
                state = self.work_state(order["work_order_id"])
                count = len(state["jobs"])
                total_jobs += count
                completed_jobs += len(state["completed"])
                blocked_jobs += len(state["blocked"])
                active_jobs += len(state["active"])
                bucket = state_counts.setdefault(order["state_code"], {"total": 0, "completed": 0, "blocked": 0})
                bucket["total"] += count
                bucket["completed"] += len(state["completed"])
                bucket["blocked"] += len(state["blocked"])
            selected_agents = agents if agent_id is None else {agent_id: agents[agent_id]}
            agent_rows = []
            for current_id, metadata in selected_agents.items():
                order_id = assignments.get(current_id)
                row: dict[str, Any] = {**metadata, "work_order_id": order_id}
                if order_id:
                    row["state_code"] = self.order_entry(order_id)["state_code"]
                    active = self.work_state(order_id)["active"].get(current_id)
                    row["active_job_id"] = active["job_id"] if active else None
                agent_rows.append(row)
            return {
                "schema_version": WORKSPACE_SCHEMA,
                "excluded_states": self.manifest["excluded_states"],
                "work_orders": {
                    "total": len(self.manifest["work_orders"]),
                    "completed": len(completed_orders),
                    "assigned": len(assignments),
                },
                "jobs": {
                    "total": total_jobs,
                    "completed": completed_jobs,
                    "blocked": blocked_jobs,
                    "active": active_jobs,
                    "ready": total_jobs - completed_jobs - blocked_jobs - active_jobs,
                },
                "agents": agent_rows,
                "states": dict(sorted(state_counts.items())),
            }

    def collect(self, output: Path) -> dict[str, Any]:
        with self.locked():
            if output.exists():
                raise FleetError("collection output already exists; choose a new path")
            rows: list[dict[str, Any]] = []
            for order in self.manifest["work_orders"]:
                order_id = order["work_order_id"]
                state = self.work_state(order_id)
                for event in self.read_ledger(self.order_events_path(order_id)):
                    if event["event_type"] != "job_submitted":
                        continue
                    detail = event["detail"]
                    result_path = self.safe_relative_path(detail["result_path"], "submitted result path")
                    if sha256_file(result_path) != detail["result_sha256"]:
                        raise FleetError(f"submitted result changed after acceptance: {result_path}")
                    result = load_json(result_path)
                    if result["research_outcome"] != "source_identified":
                        continue
                    rows.append({
                        "state_code": order["state_code"],
                        "work_order_id": order_id,
                        "job_id": detail["job_id"],
                        "agent": result["agent"],
                        "source": result["proposed_source"],
                        "evidence": result["evidence"],
                        "request_log": result["request_log"],
                        "notes": result["notes"],
                    })
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                for row in sorted(rows, key=lambda item: (item["state_code"], item["source"]["source_id"])):
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            return {"collected_source_candidates": len(rows), "output": str(output.resolve())}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--provider", required=True)
    register.add_argument("--model", required=True)
    register.add_argument("--surface", required=True)
    claim = commands.add_parser("claim")
    claim.add_argument("--agent-id", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("--agent-id", required=True)
    submit.add_argument("--job-id", required=True)
    submit.add_argument("--result", type=Path, required=True)
    failed = commands.add_parser("fail-attempt")
    failed.add_argument("--agent-id", required=True)
    failed.add_argument("--job-id", required=True)
    failed.add_argument("--reason", required=True)
    status = commands.add_parser("status")
    status.add_argument("--agent-id")
    commands.add_parser("verify")
    collect = commands.add_parser("collect")
    collect.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        fleet = Fleet(args.workspace)
        if args.command == "register":
            result = fleet.register(args.provider, args.model, args.surface)
        elif args.command == "claim":
            result = fleet.claim(args.agent_id)
        elif args.command == "submit":
            result = fleet.submit(args.agent_id, args.job_id, args.result)
        elif args.command == "fail-attempt":
            result = fleet.fail_attempt(args.agent_id, args.job_id, args.reason)
        elif args.command == "status":
            result = fleet.status(args.agent_id)
        elif args.command == "verify":
            with fleet.locked(full_verify=True):
                result = {"verified": True, "workspace": str(fleet.root)}
        elif args.command == "collect":
            result = fleet.collect(args.output)
        else:  # pragma: no cover
            raise FleetError(f"unsupported command {args.command}")
    except FleetError as exc:
        print(f"FLEET_STOP: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
