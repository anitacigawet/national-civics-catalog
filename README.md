# Civic Source Catalog

**A state-by-state directory of public meeting calendars and source endpoints across the United States.**

This repository answers a practical question: where does a local government, Tribal government, public body, or named civic organization publish information about its meetings?

It contains source links and basic metadata. It does **not** contain meeting records, agendas, minutes, recordings, transcripts, summaries, parsers, or application code.

## Current coverage

The catalog starts with **88 reviewed Arizona sources**. Additional states will be added as their source lists are researched and checked.

Data is organized by state:

```text
data/
  states/
    az/
      sources.jsonl
    ny/
      sources.jsonl
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

## Report a correction

Open a source-correction issue when a link moves, breaks, changes platform, or needs better publisher or coverage information. Please provide a first-party page that supports the correction when possible.

One meeting page, one agenda PDF, and one recording do not belong here. The catalog records continuing sources that help people find meetings over time.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/BOUNDARY.md`](docs/BOUNDARY.md).

## Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that turns civic meeting sources into a public virtual library. Z-SPAN keeps its parser implementations in the Z-SPAN repository. This catalog remains useful on its own to anyone building a different civic project, analysis, map, archive, or tool.

There is no automatic synchronization between the two repositories. Catalog updates are published as reviewed state-by-state changes.

## License

This repository is available for permitted noncommercial uses under the [PolyForm Noncommercial License 1.0.0](LICENSE). The current licensor is James Jones.

The license applies only to copyrightable material and rights the licensor owns in the catalog software, schemas, documentation, metadata, and any protectable selection or arrangement. Government facts, public URLs, and third-party material remain subject to applicable law and their source terms. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
