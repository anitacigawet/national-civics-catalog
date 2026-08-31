<p align="center">
  <img src="repository-assets/banner.png" alt="National Civics Catalog" width="1000">
</p>

# National Civics Catalog

## What is this?

The National Civics Catalog is a nationwide directory of official endpoints where states, counties, cities, towns, and township governments publish their meeting calendars, agendas, minutes, notices, and recordings. Each link leads to either the government itself or to the service that it officially uses.

---

## Who is this for?

- People trying to find a government's official meeting calendar, agendas, minutes, notices, or recordings.
- Journalists and researchers comparing access to meeting information across states and local governments.
- Developers building civic tools that need a consistent list of official meeting endpoints.
- Contributors correcting a missing, broken, or moved government link.

---

## ⚙️ Extreme technicals below

### Transparency: where no source was found

**17,388 catalog records are marked `needs_source` because no official meeting endpoint has been confirmed for them.** This does not mean those governments are inactive or do not hold meetings.

Of those records, **17,383 matched a government in the U.S. Census Bureau's 2022 Government Units Listing**. Among the matched records, **91.4% have populations below 5,000**, and the median population is **381**. Five state-level records did not have a population value in the matched Census worksheet. The population figures are primarily 2021 estimates published in that listing.

### Current snapshot

- **38,707 catalog records** cover every U.S. state, the District of Columbia, and the five inhabited territories.
- **21,319 records include an identified meeting endpoint.**
- **20,085 of those endpoints have been reviewed.**
- **1,234 identified endpoints are awaiting review.**
- **17,388 records do not yet have an identified meeting endpoint.**

The initial roster comes from the Census Bureau's 2022 Government Units Listing. It covers the active state, county, municipal, and township governments listed there. It is not a complete list of every Tribal government, special district, unincorporated community, newer government, or other civic body.

### Browse the catalog

Records are stored as newline-delimited JSON, with one complete record per line:

```text
states/
  az.jsonl
  ca.jsonl
  dc.jsonl
  ny.jsonl
```

Each file uses schema version `2.0.0` and is sorted by `catalog_record_id`.

An endpoint covering more than one state is stored once under the alphabetically first state code in its `state_codes` list. Use the record's full `state_codes` and `coverage` values instead of treating the filename as its only geography.

Version 2 renamed ambiguous version 1 fields without changing stable record IDs or catalog facts. [`MIGRATING_V1_TO_V2.md`](MIGRATING_V1_TO_V2.md) contains the complete mapping.

### Understand a record

Every entry follows [`schema.json`](schema.json). The main field groups are:

- **Identity:** `catalog_record_id`, `public_body_name`, and `public_body_type`.
- **Geography:** `state_codes`, `county_names`, and `coverage`.
- **Government links:** `public_body_website_url` and `roster_source_url`.
- **Meeting endpoint:** `meeting_source_url`, its type, platform, access method, and relationship to the government.
- **Verification:** the endpoint's status, last checked date, and evidence URL.

The status values mean:

- `needs_source`: no meeting endpoint is recorded.
- `unverified`: an endpoint is recorded but still awaits maintainer review.
- `working`, `empty`, `blocked`, `broken`, `moved`, or `retired`: the result observed on the record's last checked date, not a guarantee about its condition today.

An endpoint is included only when it belongs to the government or to a service the government officially uses. Inclusion does not guarantee that the endpoint is complete or still available.

### Running it locally

National Civics Catalog is a dataset, not an application. There is no server to run and no installation step. Clone the repository and read the JSONL files directly:

```bash
git clone https://github.com/anitacigawet/national-civics-catalog.git
cd national-civics-catalog
```

This Python example loads records that contain a meeting endpoint:

```python
import json
from pathlib import Path

endpoints = []
for state_file in Path("states").glob("*.jsonl"):
    for line in state_file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["meeting_source_url"] is not None:
            endpoints.append(record)

print(f"Loaded {len(endpoints)} identified meeting endpoints")
```

Run the repository's validator with:

```bash
python .github/scripts/validate_catalog.py
```

### Methodology

The catalog starts with a defined government roster. Each government is then checked for an official meeting endpoint. If an endpoint cannot be confirmed, the government remains in the catalog with `needs_source` status.

Read the [full methodology](methodology/README.md), or give [`RESPAWN.md`](methodology/RESPAWN.md) to an AI to adapt the process for another country.

### Using linked material

CC0 covers catalog data, schema, metadata, and documentation that ScootSolute LLC and contributors have the right to dedicate. It does not cover agendas, minutes, recordings, software, personal information, or other material published at the linked endpoints.

Linked material may be governed by laws, licenses, privacy requirements, and the source's own terms. Check those rules before reproducing or redistributing it, especially commercially. This is general information, not legal advice.

### Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that uses civic meeting-source data. This repository contains the catalog and its metadata, not Z-SPAN's parsers or application code.

### Contribute

Factual corrections, source suggestions, and focused pull requests are welcome. The GitHub issue forms ask for the evidence needed to review a change.

If you are comfortable editing JSON, update the appropriate record under [`states/`](states/) and follow [`CONTRIBUTING.md`](CONTRIBUTING.md). [`AI_CONTRIBUTOR.md`](AI_CONTRIBUTOR.md) provides a copy-and-paste workflow for researching one source with an AI assistant and checking the result before opening a pull request.

Catalog contributions are released under CC0. Supporting software and workflow contributions are released under the MIT License.

### Maintenance

ScootSolute LLC maintains the catalog with help from contributors. Newly submitted endpoints remain `unverified` until their evidence and behavior have been reviewed.

### License

Catalog data, schema, metadata, and documentation are released under the [CC0 1.0 Universal public-domain dedication](LICENSE). Supporting scripts and workflows under [`.github/scripts/`](.github/scripts/) and [`.github/workflows/`](.github/workflows/) are available under the [MIT License](LICENSE-MIT).

See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the boundaries covering linked material, third-party content, and trademarks.
