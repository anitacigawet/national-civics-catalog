# National Civics Catalog

**A state-by-state catalog of public bodies and the continuing sources they use to publish meeting information.**

The catalog gives civic projects a national starting shape. It identifies the governments and jurisdictions that need research, then fills their entries with continuing calendars, agenda indexes, public-notice pages, feeds, APIs, and meeting portals as those sources are found and reviewed.

It does not contain individual meetings, agendas, minutes, recordings, transcripts, summaries, or parser code.

## Current snapshot

The repository contains **38,707 catalog entries** across every U.S. state, the District of Columbia, and the five inhabited territories.

- **18,905 entries contain identified meeting-source endpoints.**
- **17,628 of those endpoints have completed an initial review.**
- **1,277 are clearly marked `unverified` while review is pending.**
- **19,802 entries are intentional research placeholders** with `status: "needs_source"` and no claimed endpoint.

The placeholders are part of the product. They preserve the national roster and a stable record shape while the catalog is filled in. They should not be read as discovered sources or working links.

> ### Transparency: where no continuing source was found
>
> The completed national research and review pass found **10,764 roster entries with no qualifying official continuing online meeting source**. These gaps are concentrated among very small governments: **97.0% represent populations below 5,000**, and the median population is **270**. Most are townships and small municipalities.
>
> “No qualifying source found” does not mean that the government is inactive or holds no meetings. It means that no recurring first-party or demonstrably authorized online calendar, agenda or minutes index, public-notice page, feed, API, or meeting portal passed the catalog's evidence rules. Population figures come from the Census Bureau's 2022 Government Units Listing and are primarily 2021 estimates.

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

Anyone is encouraged to use, copy, combine, redistribute, and build on the catalog in **any project—commercial or noncommercial, large or small**. That includes paid products, volunteer tools, research, archives, maps, civic applications, and other source directories. No separate permission is needed for material released under CC0.

## Using linked material

The catalog's CC0 dedication covers the catalog material that ScootSolute LLC and contributors have the right to dedicate. It does not grant rights to records, documents, media, software, personal information, or other content available through the sources it identifies.

Rules governing access, reproduction, redistribution, and commercial use of linked material may differ by source and jurisdiction, including under applicable federal, state, Tribal, territorial, or local law and the source's own terms. Before using linked material—especially commercially—users are responsible for determining and complying with any applicable laws, licenses, terms, privacy obligations, and permission requirements. This notice provides general information only, not legal advice; consult a qualified attorney about a specific use.

## Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that turns civic meeting sources into a public virtual library. Z-SPAN maintains its parsers and application code in its own repository. National Civics Catalog remains application-agnostic and contains only the source roster and its metadata.

## Contribute

The catalog welcomes factual source suggestions, data corrections, and focused pull requests. You do not need to write code: the GitHub issue forms collect the public evidence a maintainer or another contributor needs to update an entry.

If you are comfortable editing JSON, you can fill an existing `needs_source` placeholder or correct an entry directly in its [`states/`](states/) file. The contribution guide explains the record rules, catalog boundaries, local validation command, and licensing terms: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

If you would like an AI coding assistant to guide you through the complete workflow, copy and paste [`AI_CONTRIBUTOR.md`](AI_CONTRIBUTOR.md). It begins by asking which place you want to research and continues through tool setup, source research, validation, and pull-request creation.

Contributors are credited through Git history. Catalog contributions are released under CC0 so that everyone can reuse them freely; supporting software contributions are released under the MIT License. Contributing does not create ownership or control of the catalog.

## Maintenance

ScootSolute LLC maintains and reviews the catalog with help from contributors. Identified endpoints submitted from outside the maintainer's completed review process enter as `unverified` until their evidence and behavior have been checked.

## License

ScootSolute LLC has released the catalog data, schema, metadata, documentation, and any protectable selection or arrangement it owns under the [CC0 1.0 Universal public-domain dedication](LICENSE). These materials may be used for any purpose, including commercial products, without separate permission or required attribution.

Supporting software and workflow code under [`.github/scripts/`](.github/scripts/) and [`.github/workflows/`](.github/workflows/) is available under the [MIT License](LICENSE-MIT).

CC0 applies only to rights ScootSolute LLC and contributors can legally dedicate. Government facts, public URLs, linked content, and third-party material remain subject to applicable law and their source terms. CC0 does not grant trademark rights in the National Civics Catalog name or other branding. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
