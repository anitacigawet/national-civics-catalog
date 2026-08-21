# National Civics Catalog

**A state-by-state directory of public meeting calendars and source endpoints across the United States.**

This repository answers a practical question: where does a local government, Tribal government, public body, or named civic organization publish information about its meetings?

It contains source links and basic metadata. It does **not** contain meeting records, agendas, minutes, recordings, transcripts, summaries, parsers, or application code.

## Current coverage

The catalog contains **38,707 source records** across every U.S. state, the District of Columbia, and the five inhabited territories. **88 Arizona records already contain reviewed sources.** The remaining records identify an active general-purpose government and leave the endpoint fields explicitly unfilled until ScootSolute LLC reviews and adds a continuing source.

The starting shape comes from the U.S. Census Bureau's 2022 Government Units Listing. It covers state, county, municipal, and township governments. It is a practical foundation, not a claim that every Tribal government, civic body, unincorporated community, or newer government is already represented; those can be added with evidence.

Data is organized by state:

```text
data/
  states/
    az/
      sources.jsonl
    ny/
      sources.jsonl
```

Each line in a state file is one source slot. A reviewed record identifies a continuing calendar, agenda index, public-notices page, feed, or meeting portal. A preformed record has the same shape, but its endpoint fields are `null` and its status is `needs_source`. ScootSolute LLC maintains those records as sources are researched and reviewed.

Multi-state sources are stored once under the alphabetically first state code in the record. For example, a source covering Arizona, New Mexico, and Utah lives under `data/states/az/`.

## Use the data

The files are newline-delimited JSON, so they work with ordinary command-line tools, Python, JavaScript, databases, and data notebooks.

Validate the full catalog with Python 3.11 or newer:

```bash
python scripts/validate_catalog.py
python -m unittest discover -s tests -v
```

The validator uses only the Python standard library. [`schemas/source.schema.json`](schemas/source.schema.json) describes the record shape, and [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) explains each field.

## Maintenance

ScootSolute LLC maintains this catalog directly. The repository does not accept outside pull requests, source submissions, public issues, data corrections, code, or documentation changes. Its public visibility is for transparency, citation, and uses permitted by the license, not collaborative maintenance.

Private security reports remain welcome through GitHub's private vulnerability-reporting channel. See [`SECURITY.md`](SECURITY.md). The catalog's scope is described in [`docs/BOUNDARY.md`](docs/BOUNDARY.md).

## Relationship to Z-SPAN

[Z-SPAN](https://zspan.org) is a separate application that turns civic meeting sources into a public virtual library. Z-SPAN keeps its parser implementations in the Z-SPAN repository. National Civics Catalog remains useful on its own to anyone building a different civic project, analysis, map, archive, or tool.

There is no automatic synchronization between the two repositories. After a catalog source is reviewed and added, Z-SPAN may bring the endpoint into its own project, write and verify the parser, and update the location's shelf.

## License

This repository, including its dataset files, is available for permitted noncommercial uses under the [PolyForm Noncommercial License 1.0.0](LICENSE). The current copyright owner and licensor is ScootSolute LLC.

The license applies only to copyrightable material and rights the licensor owns in the catalog software, schemas, documentation, metadata, and any protectable selection or arrangement. Government facts, public URLs, and third-party material remain subject to applicable law and their source terms. See [`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
