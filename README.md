<p align="center">
  <img src="repository-assets/banner.png" alt="National Civics Catalog" width="1000">
</p>

# National Civics Catalog

## What is this?

National Civics Catalog contains roster records for U.S. public bodies. A record includes a continuing meeting source when one has been identified and supported as first-party or authorized; otherwise it remains `needs_source` with no meeting-source claim.

It does not contain individual meetings, agendas, minutes, recordings, transcripts, summaries, or parser code.

---

## Who is this for?

<!-- James will provide the wording for this section. -->

---

## What it actually does

### Current snapshot

The repository contains **38,707 catalog entries** across every U.S. state, the District of Columbia, and the five inhabited territories.

- **21,319 entries contain an identified meeting source.**
- **20,085 identified meeting sources have a status other than `unverified`.**
- **1,234 identified meeting sources have `meeting_source_status: "unverified"`.**
- **17,388 entries have `meeting_source_status: "needs_source"` and no meeting-source claim.**

These records preserve roster identities when no meeting source is claimed. They are not discovered sources or working links, and `needs_source` alone does not encode the record's search history.

> ### Transparency: where no continuing source was found
>
> Of the **17,388 current `needs_source` records**, **17,383 matched** a government in the Census Bureau's 2022 Government Units Listing. Among those matched records, **91.4% have populations below 5,000**, and the median population is **381**. Five state-level records did not have a population value in the matched Census worksheet.
>
> “No qualifying source found” does not mean that the government is inactive or holds no meetings. It means that no recurring first-party or demonstrably authorized online calendar, agenda or minutes index, public-notice page, feed, API, or meeting portal passed the catalog's evidence rules. Population figures come from the Census Bureau's 2022 Government Units Listing and are primarily 2021 estimates.

The starting roster comes from the U.S. Census Bureau's 2022 Government Units Listing and covers active state, county, municipal, and township governments. It is a foundation, not a claim that every Tribal government, civic body, unincorporated community, special district, or newer government is already represented.

### Browse the catalog

State and territory files are newline-delimited JSON:

```text
states/
  az.jsonl
  ca.jsonl
  dc.jsonl
  ny.jsonl
```

Each line is one catalog entry using schema version `2.0.0`. Records are sorted by `catalog_record_id`.

A source spanning more than one state is stored once under the alphabetically first state code in its `state_codes` list. Consumers should use each record's full `state_codes` and `coverage` values rather than treating its filename as its only geography.

Version 2 replaced the ambiguous version 1 field names without changing any stable record ID value or catalog fact. See [`MIGRATING_V1_TO_V2.md`](MIGRATING_V1_TO_V2.md) for the exact mapping.

### Understand a record

Every entry uses the structure defined in [`schema.json`](schema.json). Important fields include:

- `schema_version`: schema used by the standalone JSONL record;
- `catalog_record_id`: stable identifier for the catalog entry, not a government identifier;
- `public_body_name` and `public_body_type`: the government or civic body represented by the record;
- `state_codes` and `county_names`: geographic placement;
- `public_body_website_url`: the body's official website when identified;
- `roster_source_url`: authoritative roster evidence retained for a body with no claimed meeting source;
- `meeting_source_url`: the continuing meeting source, or `null` when no source is claimed;
- `meeting_source_type`, `meeting_source_platform`, and `meeting_source_access_method`: what kind of source it is and how it is published;
- `meeting_source_relationship`: whether the source is first-party or an authorized service;
- `meeting_source_status`: whether no source is claimed, review is pending, or a checked source was working, empty, blocked, broken, moved, or retired;
- `meeting_source_last_checked_date`: the most recent recorded observation date;
- `meeting_source_evidence_url`: public evidence that the body operates or authorizes the identified source; and
- `coverage`: the jurisdictions, districts, communities, or other civic areas represented by the record.

The most important status distinction is:

- `needs_source` means the record makes no meeting-source claim. It does not say whether research is pending or a bounded search ended without a qualifying source.
- `unverified` means a meeting source is recorded but maintainer review is pending.
- `working`, `empty`, `blocked`, `broken`, `moved`, and `retired` record the result of a completed check as of `meeting_source_last_checked_date`; they do not guarantee current availability.

Inclusion means the meeting-source URL is first-party to, or an authorized service for, the named public body. It does not establish legal authority, endorsement, completeness, or continuing availability.

---

## Running it locally

### Build with it

The JSONL files can be loaded with ordinary command-line tools, Python, JavaScript, databases, and data notebooks. For example, this Python snippet reads only entries that currently contain a meeting source:

```python
import json
from pathlib import Path

sources = []
for state_file in Path("states").glob("*.jsonl"):
    for line in state_file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["meeting_source_url"] is not None:
            sources.append(record)

print(f"Loaded {len(sources)} identified meeting sources")
```

Catalog material released under CC0 may be copied, combined, redistributed, or used in commercial and noncommercial projects without separate permission.

---

## ⚙️ Extreme technicals below

### Methodology

The catalog was built by defining a government roster, then researching
continuing meeting sources for every body in that roster without removing
unresolved bodies. See the [human-readable methodology](methodology/README.md)
or give [RESPAWN.md](methodology/RESPAWN.md) to an AI to adapt the process for
another country.

### Using linked material

The catalog's CC0 dedication covers the catalog material that ScootSolute LLC and contributors have the right to dedicate. It does not grant rights to records, documents, media, software, personal information, or other content available through the sources it identifies.

Rules governing access, reproduction, redistribution, and commercial use of linked material may differ by source and jurisdiction, including under applicable federal, state, Tribal, territorial, or local law and the source's own terms. Before using linked material—especially commercially—users are responsible for determining and complying with any applicable laws, licenses, terms, privacy obligations, and permission requirements. This notice provides general information only, not legal advice; consult a qualified attorney about a specific use.

### Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that consumes civic meeting-source data. Its parsers and application code live in another repository. National Civics Catalog contains only the source roster and metadata.

### Contribute

Factual source suggestions, data corrections, and focused pull requests are welcome. The GitHub issue forms collect the public evidence needed to update an entry without requiring contributors to edit code.

If you are comfortable editing JSON, you can fill an existing `needs_source` placeholder or correct an entry directly in its [`states/`](states/) file. The contribution guide explains the record rules, catalog boundaries, local validation command, and licensing terms: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

[`AI_CONTRIBUTOR.md`](AI_CONTRIBUTOR.md) provides a copy-and-paste workflow for using an AI coding assistant to research a place, validate the proposed record, and prepare a pull request.

Contributors are credited through Git history. Catalog contributions are released under CC0 so that everyone can reuse them freely; supporting software contributions are released under the MIT License. Contributing does not create ownership or control of the catalog.

### Maintenance

ScootSolute LLC maintains and reviews the catalog with help from contributors. Identified meeting sources submitted from outside the maintainer's completed review process enter as `unverified` until their evidence and behavior have been checked.

### License

ScootSolute LLC has released the catalog data, schema, metadata, documentation, and any protectable selection or arrangement it owns under the [CC0 1.0 Universal public-domain dedication](LICENSE). These materials may be used for any purpose, including commercial products, without separate permission or required attribution.

Supporting software and workflow code under [`.github/scripts/`](.github/scripts/) and [`.github/workflows/`](.github/workflows/) is available under the [MIT License](LICENSE-MIT).

CC0 applies only to rights ScootSolute LLC and contributors can legally dedicate. Government facts, public URLs, linked content, and third-party material remain subject to applicable law and their source terms. CC0 does not grant trademark rights in the National Civics Catalog name or other branding. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
