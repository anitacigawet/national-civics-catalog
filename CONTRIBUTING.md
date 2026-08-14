# Contributing

Thank you for helping people find public meeting sources.

## Fill a source record with an AI assistant

Open the folder for your state under [`data/states/`](data/states/), find your government in `sources.jsonl`, and give that preformed record plus [`contribute/AI-INSTRUCTIONS.md`](contribute/AI-INSTRUCTIONS.md) to your AI coding assistant. The assistant fills the missing endpoint fields. A source contribution changes exactly two files: the state's canonical `sources.jsonl` file and one contribution packet under `contributions/`.

The pull-request checker runs trusted code from the repository's base branch and treats all incoming files as untrusted data. Passing the check means the proposed catalog change is structurally consistent and ready for human review; it does not merge the pull request or publish anything to Z-SPAN.

After a contribution is reviewed and merged, the separate Z-SPAN project handles parser creation. Contributors never need to write a parser or modify the Z-SPAN application.

## Report a source or correction

Open a source-correction issue and include:

- the state and place the source covers;
- the publisher's public name;
- the continuing calendar, portal, feed, or index URL;
- what is missing, moved, broken, or incorrect; and
- a first-party page supporting the change when one is available.

Good issue reports are factual. They do not need to follow the repository's JSON format; a maintainer or contributor can turn the evidence into a checked pull request.

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
