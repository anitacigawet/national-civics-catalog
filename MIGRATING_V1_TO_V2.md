# Migrate from schema v1 to v2

Schema v2 replaces ambiguous field names. It does not change stable record ID
values, source URLs, status values, geography, or coverage facts. The tagged
`v1.0.0` release remains the tagged v1 snapshot.

## Field mapping

| Version 1 | Version 2 |
| --- | --- |
| `source_id` | `catalog_record_id` |
| `publisher_name` | `public_body_name` |
| `publisher_type` | `public_body_type` |
| `official_website_url` | `public_body_website_url` |
| `endpoint_type` | `meeting_source_type` |
| `url` | `meeting_source_url` |
| `platform` | `meeting_source_platform` |
| `access_method` | `meeting_source_access_method` |
| `source_relationship` | `meeting_source_relationship` |
| `status` | `meeting_source_status` |
| `last_checked` | `meeting_source_last_checked_date` |
| `covers` | `coverage` |
| nested `relationship` | nested `coverage_relationship` |

Version 2 also adds `schema_version: "2.0.0"` to every record.

## Evidence URL split

Version 1 used `provenance_url` for two different claims. Version 2 separates
them without inventing or duplicating evidence:

- On a `needs_source` record, the old value becomes `roster_source_url` and
  `meeting_source_evidence_url` is `null`.
- On a record with an identified meeting source, the old value becomes
  `meeting_source_evidence_url` and `roster_source_url` is `null`.

`roster_source_url` explains Census links on records that make no meeting-source
claim. `meeting_source_evidence_url` supports the relationship between an
identified source and the named public body.

## Automated migration

The migration script ships with schema v2. Run it from a v2 checkout and point
`--root` to a separate, untouched v1 checkout:

```bash
python .github/scripts/migrate_v1_to_v2.py --root ../national-civics-catalog-v1
python .github/scripts/migrate_v1_to_v2.py --root ../national-civics-catalog-v1 --apply
```

The first command is a dry run. The migrator verifies a v2-to-v1 semantic round
trip for every row before writing. `--apply` rewrites only `states/*.jsonl` in
the target tree; it does not replace that tree's schema, documentation, or
validator. Each state file is replaced atomically, but the complete multi-file
run is not a whole-tree transaction. Use the schema v2 release when a complete
v2 repository is required.
