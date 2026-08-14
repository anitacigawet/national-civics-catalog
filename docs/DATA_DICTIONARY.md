# Data dictionary

Each `data/states/<code>/sources.jsonl` file is UTF-8 newline-delimited JSON. Every non-empty line is one source object. Records are sorted by `source_id`.

- `source_id`: stable lowercase identifier. Keep it unchanged when a name or URL changes.
- `publisher_name`: public name of the body publishing or authorizing the source.
- `publisher_type`: kind of publisher, such as `municipality`, `county`, `tribal_government`, or `community_council`.
- `state_codes`: every applicable USPS state, district, or territory code, sorted and unique.
- `county_names`: complete known counties or equivalents, sorted and unique. `[]` means unknown or not applicable.
- `official_website_url`: publisher homepage when established, otherwise `null`.
- `endpoint_type`: kind of continuing source, such as `meeting_calendar`, `agenda_index`, `public_notices_index`, `video_archive`, `api`, or `feed`.
- `url`: collection-level HTTPS endpoint.
- `platform`: public vendor or platform label; `custom` is used when no named platform is established.
- `access_method`: `html`, `json`, `rss`, `ical`, `api`, `pdf_index`, or `other`.
- `source_relationship`: `first_party` or `authorized_service`.
- `status`: `working`, `empty`, `blocked`, `broken`, `moved`, `retired`, or `unverified`.
- `last_checked`: real ISO date (`YYYY-MM-DD`) for the status, or `null`.
- `provenance_url`: first-party evidence for the publisher/source relationship. It may equal `url`.
- `covers`: one or more places or jurisdictions served by the source.

Each object in `covers` contains:

- `name`: public place or jurisdiction name.
- `type`: geography or jurisdiction type.
- `state_codes`: complete sorted state-code list.
- `county_names`: complete known county list, or `[]`.
- `relationship`: `direct_jurisdiction`, `governing_parent`, `civic_representation`, or `regional_service`.
- `ocd_division_id`: established Open Civic Data identifier, or `null`.
- `census_geoid`: established Census identifier preserving leading zeroes, or `null`.

## State-file rule

A source is stored under the alphabetically first entry in its `state_codes` list. This prevents multi-state sources from being duplicated while keeping the catalog easy to browse by state.

## Status meaning

- `working`: the source was reachable and recognizable at the last check.
- `empty`: the source worked and showed a recognized empty state.
- `blocked`: a source-side barrier prevented a conclusive content check.
- `broken`: the source failed or no longer matched its expected purpose.
- `moved`: a replacement source is known and the record is awaiting or documenting migration.
- `retired`: the source is intentionally no longer active.
- `unverified`: the source has not yet completed a documented check.
