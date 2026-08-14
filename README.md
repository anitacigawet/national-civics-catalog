# National Civics Catalog

**A state-by-state directory of public meeting calendars and source endpoints across the United States.**

This repository answers a practical question: where does a local government, Tribal government, public body, or named civic organization publish information about its meetings?

It contains source links and basic metadata. It does **not** contain meeting records, agendas, minutes, recordings, transcripts, summaries, parsers, or application code.

## Current coverage

The catalog starts with **88 reviewed Arizona sources**. Every U.S. state, the District of Columbia, and the five inhabited territories has a folder ready for contributors. Additional source lists are added as they are researched and checked.

Data is organized by state:

```text
data/
  states/
    az/
      sources.jsonl
    ny/
      README.md
```

Each line in a state file is one continuing source, such as a calendar, agenda index, public-notices page, feed, or meeting portal. A record also identifies the publisher, the place or places it covers, when it was last checked, and whether it was working, empty, blocked, broken, moved, retired, or not yet verified.

Multi-state sources are stored once under the alphabetically first state code in the record. For example, a source covering Arizona, New Mexico, and Utah lives under `data/states/az/`.

## Use the data

The files are newline-delimited JSON, so they work with ordinary command-line tools, Python, JavaScript, databases, and data notebooks.

Validate the full catalog with Python 3.11 or newer:

```bash
python scripts/validate_catalog.py
python -m unittest discover -s tests -v
```

The validator uses only the Python standard library. [`schemas/source.schema.json`](schemas/source.schema.json) describes the record shape, and [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) explains each field.

## Help build a state

Open any state folder under [`data/states/`](data/states/) to see its current coverage. Each folder includes a short contribution path designed to work with an AI coding assistant. The assistant prepares one source record and one evidence packet; the repository's trusted base-branch checker validates the exact pull-request shape and catalog output before a person reviews it.

Start with [`contribute/AI-INSTRUCTIONS.md`](contribute/AI-INSTRUCTIONS.md). The checker never executes code from an incoming pull request, never merges a contribution, and never publishes anything to Z-SPAN.

## Report a correction

Open a source-correction issue when a link moves, breaks, changes platform, or needs better publisher or coverage information. Please provide a first-party page that supports the correction when possible.

One meeting page, one agenda PDF, and one recording do not belong here. The catalog records continuing sources that help people find meetings over time.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/BOUNDARY.md`](docs/BOUNDARY.md).

## Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that turns civic meeting sources into a public virtual library. Z-SPAN keeps its parser implementations in the Z-SPAN repository. National Civics Catalog remains useful on its own to anyone building a different civic project, analysis, map, archive, or tool.

There is no automatic synchronization between the two repositories. After a catalog contribution is reviewed and merged, Z-SPAN manually brings the endpoint into its own project, writes and verifies the parser, and updates the location's shelf.

### Z-SPAN three-day response

Within three days of an accepted catalog contribution, Z-SPAN will add the contributed location with either:

- a working parser and usable meeting shelf; or
- a visible source-blocked status explaining why the official endpoint cannot yet be collected and what happens next.

This response applies after the contribution is merged into National Civics Catalog. It does not promise that a broken or access-blocked government source can be made collectable. Once a meeting is available, people can use the Z-SPAN client with their own supported account to process it locally.

## License

This repository is available for permitted noncommercial uses under the [PolyForm Noncommercial License 1.0.0](LICENSE). The current licensor is James Jones.

The license applies only to copyrightable material and rights the licensor owns in the catalog software, schemas, documentation, metadata, and any protectable selection or arrangement. Government facts, public URLs, and third-party material remain subject to applicable law and their source terms. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
