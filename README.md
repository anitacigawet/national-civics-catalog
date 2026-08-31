<p align="center">
  <img src="repository-assets/banner.png" alt="National Civics Catalog" width="1000">
</p>

# National Civics Catalog

## What is this?

The National Civics Catalog is a nationwide directory of endpoints where states, counties, cities, and towns publish their meeting calendars, agendas, minutes, notices, and recordings. Each listed endpoint belongs either to the government itself or to the official service or vendor it uses.

---

## Who is this for?

- **Developers**

  Anyone building civic tools that need a consistently updated list of official meeting endpoints.

- **Journalists and researchers**

  People comparing meeting information across states and local governments.

- **Anyone**

  Anyone seeking a government's official meeting calendar, agenda, or minutes.

- **Contributors**

  People who want to correct a missing, broken, or deprecated government link.

---

## ⚙️ Extreme technicals below

> **Transparency regarding sources that were not found**
>
> 17,388 records are marked `needs_source` because I was unable to find an official meeting endpoint for them. This does not mean those governments are inactive or do not hold meetings. It means that, for whatever reason, I was unable to obtain an official endpoint for those locations.
>
> Among these locations, 91.4% have populations below 5,000, and the median population is 381.

### Current snapshot as of August 31, 2026

- 🟢 21,319 identified meeting endpoints
- 🟢 20,085 identified meeting endpoints reviewed
- 🟡 1,234 identified meeting endpoints awaiting review
- 🔴 17,388 locations without an identified meeting endpoint

### Coverage total

The identified and unidentified locations above total 38,707 locations checked.

### Auditing the catalog

Catalog entries are stored under [`states/`](states/) as one JSONL file per state or territory. Each line is one complete record.

```text
states/
  az.jsonl
  ca.jsonl
  dc.jsonl
  ny.jsonl
```

Each file uses schema version `2.0.0` and is sorted by `catalog_record_id`.

An endpoint covering more than one state is stored under the alphabetically first state code in its `state_codes` list. Use the record's full `state_codes` and `coverage` values when auditing its geography.

### Auditing a record

Every entry follows [`schema.json`](schema.json). The main field groups are:

- **Identity:** `catalog_record_id`, `public_body_name`, and `public_body_type`.
- **Geography:** `state_codes`, `county_names`, and `coverage`.
- **Government links:** `public_body_website_url` and `roster_source_url`.
- **Meeting endpoint:** `meeting_source_url`, its type, platform, access method, and relationship to the government.
- **Verification:** the endpoint's status, last checked date, and evidence URL.

#### Status values

- `needs_source`: no meeting endpoint is recorded.
- `unverified`: an endpoint is recorded but still awaits maintainer review.
- `working`, `empty`, `blocked`, `broken`, `moved`, or `retired`: the result observed on the record's last checked date, not a guarantee about its condition today.

### How to use

Clone the repository and read the JSONL files directly:

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

Read the [full methodology](methodology/README.md), or give [`RESPAWN.md`](methodology/RESPAWN.md) to an AI to adapt the process for another country.

### Using linked material

CC0 applies to the catalog's data, schema, metadata, and documentation. It does not apply to agendas, minutes, recordings, or other content published at the linked endpoints. If you reuse linked material, follow the source's terms and any applicable laws. See [`NOTICE`](NOTICE) for details.

### Contribute

Factual corrections, source suggestions, and focused pull requests are welcome. The GitHub issue forms ask for the evidence needed to review a change.

If you are comfortable editing JSON, update the appropriate record under [`states/`](states/) and follow [`CONTRIBUTING.md`](CONTRIBUTING.md). [`AI_CONTRIBUTOR.md`](AI_CONTRIBUTOR.md) provides a copy-and-paste workflow for researching one source with an AI assistant and checking the result before opening a pull request.

Catalog contributions are released under CC0. Supporting software and workflow contributions are released under the MIT License.

### Maintenance

ScootSolute LLC maintains the catalog with help from contributors. Newly submitted endpoints remain `unverified` until their evidence and behavior have been reviewed.

### License

Catalog data, schema, metadata, and documentation are released under [CC0 1.0 Universal](LICENSE). Supporting scripts and workflows are released under the [MIT License](LICENSE-MIT). See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for details.
