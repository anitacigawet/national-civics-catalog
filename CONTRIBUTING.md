# Contributing

Thank you for helping make continuing civic meeting sources easier to find.

## Report a source or correction

Use the source-correction issue form and provide factual evidence for:

- the publisher's public name and type;
- the place or places the source covers;
- the collection-level endpoint URL and type;
- whether the source is first-party or an authorized service;
- the first-party page that establishes that relationship; and
- what is missing, moved, or incorrect.

A `community_council` can be reported as a named civic publisher without claiming it is a government. Inclusion does not establish governmental status, authority over a place, endorsement, or legal sufficiency.

Do not paste agenda text, minutes, transcripts, captions, recordings, personal information, or other meeting content into an issue. Do not submit one meeting's page, document, or recording. Do not submit parser recipes, credentials, non-public API details, screenshots, third-party prose, or unpublished collection notes.

## Generated records

All four JSONL files are generated. A maintainer independently checks the evidence and recreates the resulting publisher, place, endpoint, and coverage records. Do not hand-edit generated output.

Use `null` for an unknown external identifier or verification date. Use `[]` when counties are explicitly unknown or inapplicable. Never guess a type, relationship, vendor, identifier, or geography merely to fill a field.

## Pull-request boundary

The repository does not currently accept code, schema, documentation, or generated-data pull requests. This keeps the current copyright and licensor record accurate until a reviewed inbound-rights process exists.

You may report a factual defect without supplying replacement code or prose. A maintainer will investigate and independently implement any change.
