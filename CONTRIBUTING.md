# Contributing

Thank you for helping people find public meeting sources.

## Report a source or correction

Open a source-correction issue and include:

- the state and place the source covers;
- the publisher's public name;
- the continuing calendar, portal, feed, or index URL;
- what is missing, moved, broken, or incorrect; and
- a first-party page supporting the change when one is available.

Good reports are factual. They do not need to follow the repository's JSON format; a maintainer will review the evidence and update the appropriate state file.

Do not submit meeting text, transcripts, recordings, personal information, credentials, parser code, or private research notes. Do not submit a link that covers only one meeting or one downloadable document.

## Data rules

- Never guess a publisher, place, relationship, identifier, county, or status.
- Use `null` when an external identifier or check date is unknown.
- Use `[]` when county information is unknown or not applicable.
- Keep one source in one state file. A multi-state source belongs under its alphabetically first state code.
- Preserve a published `source_id` when a display name or URL changes.

The catalog is validated before publication. See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) for the record fields.

## Rights and factual contributions

Please submit factual source information rather than copied third-party prose, screenshots, or code. A maintainer independently writes the catalog change so the repository's ownership and licensing record stays clear.
