# Civic Source Catalog

**A source-available directory of collection-level meeting-information sources published by U.S. local governments, Tribal governments, and named civic bodies.**

The catalog separates three facts that are easy to blur: who publishes or authorizes a source, which continuing source is being described, and what place that source covers. That separation lets one publisher serve several places, one place use several source collections, and a multi-state Tribal government be represented without forcing it into a city-shaped record.

This repository contains endpoints, not meeting records. It does not republish meetings, agendas, minutes, transcripts, recordings, summaries, or the software and operational material used to collect them.

## The four-file release

A valid v1 release consists of four newline-delimited JSON files:

- `data/publishers.jsonl` names the government, Tribal government, chapter, district, or civic body that publishes or authorizes a source.
- `data/places.jsonl` names the geography or jurisdiction covered.
- `data/endpoints.jsonl` describes a continuing collection-level source and its relationship to its publisher.
- `data/coverage.jsonl` connects endpoints to places, including many-to-many coverage.

Inclusion means the URL is first-party to, or an authorized service of, the named publisher. **It does not establish that a publisher is a government, that a publisher has legal authority over a place, or that any publisher endorses this catalog or an application using it.** A `community_council` publisher is therefore described as the named civic body it is, without converting it into a government claim.

Identifiers are assigned stable keys. Consumers must store them as opaque values rather than reconstructing them from display names. Publishers and places can span more than one state; `us-navajo-nation-council` is a valid publisher-key shape.

## Current release

Version 0.1.0 is the first normalized v1 snapshot. It contains 88 reviewed Arizona source routes, represented as 88 publishers, 88 places, 88 endpoints, and 88 coverage links. The snapshot is an endpoint directory, not a claim that every Arizona public meeting or public body is covered.

Every release is generated from reviewed evidence and validated as one four-file graph. The files in `data/` are the release; generated records are not edited by hand.

## What belongs here

A source belongs when the same URL is meant to help someone find multiple meetings or public records over time and the publisher relationship has evidence. Examples include:

- a meeting calendar;
- a continuing agenda or minutes index;
- a public-notices index;
- a video archive;
- an RSS, iCalendar, JSON, or XML collection source; or
- another continuing meeting-information landing page.

One meeting's page, agenda PDF, minutes file, recording, transcript, or summary does not belong. Collection implementations belong in the applications that use the catalog: parser recipes, selectors, credentials, health logs, review queues, and unpublished candidates are not part of this repository.

See [the publication boundary](docs/BOUNDARY.md) and [worked record examples](docs/EXAMPLES.md).

## Validate a release

After the four generated v1 files exist, validate them with Python 3.11 or newer:

```bash
python scripts/validate_catalog.py
python -m unittest discover -s tests -v
```

The validator uses only the Python standard library. It enforces exact fields and field order, assigned-key shapes and snapshot uniqueness, sorted geography arrays, references among all four files, publisher/place relationship consistency, and deterministic URL-shape exclusions for credentials, IP literals, known special-use or local names, downloadable artifacts, and common single-record forms. URL syntax cannot prove that a source is a continuing collection; maintainers establish that fact from reviewed provenance before generation. Catalog validation does not replace a consumer's own DNS-resolution and egress controls.

The JSON Schemas in `schemas/` describe each record. [`datapackage.json`](datapackage.json) is the machine-readable v1 resource inventory.

## Contribute a source or correction

Use the source-correction issue form to provide factual evidence about a publisher, place, endpoint, or coverage relationship. A maintainer checks the evidence and regenerates records; generated JSONL is not edited by hand.

Do not paste meeting content, personal information, copyrighted third-party prose, screenshots, code, credentials, or unpublished collection details into an issue. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Repository map

- `data/` — the generated 0.1.0 release files.
- `schemas/` — the four v1 record contracts and a fail-closed marker for the retired jurisdiction schema.
- `scripts/validate_catalog.py` — dependency-free release validation.
- `tests/` — fixture-based validator and contract tests.
- `docs/` — the data dictionary, examples, and publication boundary.

## Licensing

This repository is source-available for permitted noncommercial purposes under the [PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not granted by that license. The current licensor is James Jones; [`NOTICE`](NOTICE) states the scope.

The license reaches only rights the licensor owns in the catalog software, schemas, documentation, metadata, and any protectable selection, coordination, or arrangement. Underlying government facts and third-party material remain subject to applicable law and their source terms. [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) identifies Open Civic Data identifiers carried in place records.

## A related project

[Z-SPAN](https://zspan.org) is a separate virtual library for local politics designed to consume pinned catalog releases. Its application code, parser recipes, internal collection operations, and separate license are outside this repository.
