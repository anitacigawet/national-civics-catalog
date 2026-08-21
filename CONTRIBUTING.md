# Contributing

Thank you for helping people find the continuing sources where public bodies publish meeting information.

You can participate without writing code. If you found a source or a factual error, open a GitHub issue and provide the public evidence. If you are comfortable editing JSON, you can update the catalog directly in a pull request.

## Suggest a source

Use the **Source suggestion** issue form for a continuing calendar, meeting portal, agenda index, public-notice index, feed, API, or video archive.

Please include:

- the publisher's public name and location;
- the continuing source URL;
- a first-party page showing that the publisher uses or authorizes the source; and
- a short explanation of what the source covers.

Use the **Data correction** form when an existing entry is inaccurate, moved, broken, duplicated, or incomplete.

Do not submit an individual meeting page, agenda, minutes file, recording, transcript, summary, private information, credentials, or unpublished research.

## Submit a pull request

1. Fork the repository and create a branch.
2. Edit the appropriate file under [`states/`](states/). Each line is one complete JSON object.
3. Keep the file sorted by `source_id` and avoid reformatting unrelated lines.
4. Run `python .github/scripts/validate_catalog.py` from the repository root.
5. Open a pull request and complete the checklist.

For a small factual change, keep the pull request to one state or one closely related set of entries. Please open an issue before submitting a large automated import or a change to the schema.

### Use an AI assistant

[`AI_CONTRIBUTOR.md`](AI_CONTRIBUTOR.md) is a complete, copy-paste onboarding prompt for an AI coding assistant. It asks you for a place, checks the local Git and GitHub setup, researches one source, prepares and validates one catalog change, shows you the evidence and exact diff, and opens the pull request after you approve it.

The final link-and-diff checkpoint matters because the validator checks structure and consistency; it cannot determine whether an AI assistant found the correct public source.

## Fill a research placeholder

The `needs_source` entries are intentional placeholders in the national roster. When you identify a continuing source for one of them:

- preserve its `source_id` and existing publisher and coverage fields unless public evidence shows they are wrong;
- fill `endpoint_type`, `url`, `platform`, `access_method`, and `source_relationship`;
- set `status` to `unverified` so ordinary maintainer review remains visible;
- set `last_checked` to the date you checked the source, in `YYYY-MM-DD` form; and
- set `provenance_url` to the first-party evidence supporting the source relationship.

If the public body is missing from the roster, you may add a new entry using [`schema.json`](schema.json). Never guess an identifier, geographic relationship, publisher type, or source relationship. Use `null` or an empty array where the schema permits it and the fact is unknown.

## Catalog boundaries

Contributions must remain application-agnostic and collection-level. This repository does not accept parser code, individual meeting content, processed meeting data, Z-SPAN application code, credentials, or private research records.

Inclusion means that a source is first-party to, or an authorized service for, the named publisher. It does not establish legal authority, endorsement, completeness, or continuing availability.

## Contribution terms

By submitting a pull request, you agree to license your contribution under the repository's [PolyForm Noncommercial License 1.0.0](LICENSE), and you represent that you have the right to do so. Contributing does not give you ownership or control of the National Civics Catalog or ScootSolute LLC, and it does not make you a joint author of the catalog. To the extent your contribution contains copyrightable original material, you retain copyright only in that contribution and license it under the same repository terms. Public facts and URLs remain subject to applicable law.

Please contribute facts, links, and your own wording. Do not copy third-party prose, code, images, or datasets unless their terms clearly permit inclusion and you identify the applicable source and license.
