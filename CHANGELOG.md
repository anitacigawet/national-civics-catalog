# Changelog

## 2.0.0 - 2026-08-30

- Replaced ambiguous source and publisher field names with explicit
  public-body, meeting-source, and coverage names.
- Split the overloaded version 1 `provenance_url` into `roster_source_url` and
  `meeting_source_evidence_url` without inventing or duplicating evidence.
- Added `schema_version` to every standalone JSONL record.
- Preserved all 38,707 record ID values, catalog facts, enum values, state-file
  placement, and record order.
- Updated validation, contribution instructions, issue forms, examples, and
  public schema explanations for the v2 contract.

## 1.0.0

- Published the first reviewed national roster and meeting-source catalog.
