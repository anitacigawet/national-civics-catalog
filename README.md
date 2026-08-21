# National Civics Catalog

**A state-by-state catalog of public bodies and the continuing sources they use to publish meeting information.**

The catalog gives civic projects a national starting shape. It identifies the governments and jurisdictions that need research, then fills their entries with continuing calendars, agenda indexes, public-notice pages, feeds, APIs, and meeting portals as those sources are found and reviewed.

It does not contain individual meetings, agendas, minutes, recordings, transcripts, summaries, or parser code.

## Current snapshot

The repository contains **38,707 catalog entries** across every U.S. state, the District of Columbia, and the five inhabited territories.

- **139 entries contain identified meeting-source endpoints.**
- **88 of those endpoints have completed an initial review.**
- **51 are clearly marked `unverified` while review is pending.**
- **38,568 entries are intentional research placeholders** with `status: "needs_source"` and no claimed endpoint.

The placeholders are part of the product. They preserve the national roster and a stable record shape while the catalog is filled in. They should not be read as discovered sources or working links.

The starting roster comes from the U.S. Census Bureau's 2022 Government Units Listing and covers active state, county, municipal, and township governments. It is a foundation, not a claim that every Tribal government, civic body, unincorporated community, special district, or newer government is already represented.

## Browse the catalog

State and territory files are newline-delimited JSON:

```text
states/
  az.jsonl
  ca.jsonl
  dc.jsonl
  ny.jsonl
```

Each line is one catalog entry. Records are sorted by `source_id`.

A source spanning more than one state is stored once under the alphabetically first state code in its `state_codes` list. Consumers should use each record's full `state_codes` and `covers` values rather than treating its filename as its only geography.

## Understand a record

Every entry uses the structure defined in [`schema.json`](schema.json). Important fields include:

- `source_id`: stable identifier for the catalog entry;
- `publisher_name` and `publisher_type`: the body publishing or authorizing the source;
- `state_codes` and `county_names`: geographic placement;
- `url`: the continuing meeting source, or `null` while research is incomplete;
- `endpoint_type`, `platform`, and `access_method`: what kind of source it is and how it is published;
- `status`: its current research or review state;
- `last_checked` and `provenance_url`: when it was checked and the first-party evidence supporting it; and
- `covers`: the places or jurisdictions represented by the source.

The most important status distinction is:

- `needs_source` means the national roster entry exists, but no continuing source has been identified yet.
- `unverified` means an endpoint has been identified but has not completed ordinary catalog review.
- `working`, `empty`, `blocked`, `broken`, `moved`, and `retired` describe the result of a completed check.

Inclusion means the URL is first-party to, or an authorized service for, the named publisher. It does not establish legal authority, endorsement, completeness, or continuing availability.

## Build with it

The JSONL files can be loaded with ordinary command-line tools, Python, JavaScript, databases, and data notebooks. For example, this Python snippet reads only entries that currently contain an endpoint:

```python
import json
from pathlib import Path

sources = []
for state_file in Path("states").glob("*.jsonl"):
    for line in state_file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["url"] is not None:
            sources.append(record)

print(f"Loaded {len(sources)} identified endpoints")
```

You can use the catalog as a starting point for a noncommercial map, archive, research project, civic application, or another source directory permitted by the license.

## Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that turns civic meeting sources into a public virtual library. Z-SPAN maintains its parsers and application code in its own repository. National Civics Catalog remains application-agnostic and contains only the source roster and its metadata.

## Maintenance

ScootSolute LLC maintains the catalog directly. The repository does not accept outside pull requests, public issues, source submissions, or data corrections. Its public visibility is for transparency, citation, and uses permitted by the license.

## License

This repository is source-available for permitted noncommercial uses under the [PolyForm Noncommercial License 1.0.0](LICENSE). The current copyright owner and licensor is ScootSolute LLC.

The license applies only to copyrightable material and rights the licensor owns in the catalog, schema, documentation, metadata, and any protectable selection or arrangement. Government facts, public URLs, and third-party material remain subject to applicable law and their source terms. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
