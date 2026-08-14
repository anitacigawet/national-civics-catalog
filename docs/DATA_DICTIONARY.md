# Data dictionary

A valid v1 release is four UTF-8 newline-delimited JSON files. Every non-empty line is one object. Fields appear in the order documented below, and records in each file are sorted by that file's stable ID.

All IDs are assigned keys. Display-name changes do not change an ID, and consumers must not recreate an ID from a name. Entity IDs begin with `us-` because schema v1 is U.S.-only, but they are not required to contain a state code. An endpoint ID is scoped to its publisher. A coverage ID is the stable endpoint/place pair.

## `data/publishers.jsonl`

A publisher is the actual government, Tribal government, chapter, district, or named civic body that publishes a source or authorizes a service to publish it.

- `publisher_id`: assigned lowercase `us-` key, such as `us-az-kingman` or `us-navajo-nation-council`.
- `publisher_name`: the body's public name.
- `publisher_type`: `municipality`, `county`, `tribal_government`, `tribal_chapter`, `community_council`, `special_district`, or `other_public_body`.
- `country_code`: `US` in v1.
- `state_codes`: one or more exact USPS state, district, or territory codes, sorted and unique. Multi-state publishers use every applicable code.
- `county_names`: complete known counties or equivalents, sorted and unique. `[]` explicitly means unknown or inapplicable.
- `official_website_url`: the established homepage for the named publisher, or `null`.

The word `official` in `official_website_url` identifies the publisher's own established homepage. It does not assert that a `community_council` is a government or that the body endorses this catalog.

## `data/places.jsonl`

A place is the geography or jurisdiction an endpoint covers. It is separate from the publisher so one endpoint can cover several places and several publishers can serve the same place.

- `place_id`: assigned lowercase `us-` key.
- `place_name`: public geographic or jurisdiction name.
- `place_type`: `municipality`, `county`, `tribal_jurisdiction`, `tribal_chapter`, `unincorporated_community`, `special_district`, or `other`.
- `country_code`: `US` in v1.
- `state_codes`: complete sorted USPS codes; multi-state places are allowed.
- `county_names`: complete known counties or equivalents, sorted and unique; `[]` is explicit.
- `ocd_division_id`: established Open Civic Data division identifier, or `null`. It is never generated from a name.
- `census_geoid`: established Census geographic identifier as a string preserving leading zeroes, or `null`.

A place record identifies coverage geography. It does not by itself establish that a publisher governs the place.

## `data/endpoints.jsonl`

An endpoint is one continuing collection-level source.

- `endpoint_id`: assigned lowercase key beginning with `<publisher_id>--`; the suffix is stable and is not recomputed from the display label.
- `publisher_id`: reference to `publishers.jsonl`.
- `endpoint_type`: `primary_meeting_source`, `meeting_calendar`, `meeting_documents_index`, `agenda_index`, `minutes_index`, `public_notices_index`, `video_archive`, or `other`.
- `url`: collection-level HTTP or HTTPS URL on a DNS-shaped hostname that is not an IP literal or a known special-use or local name. Consumers still enforce DNS-resolution and egress policy at runtime.
- `platform`: public platform/vendor label; use a documented neutral value such as `custom` when no named platform is established.
- `access_method`: `html`, `rss`, `ical`, `json`, `xml`, `pdf_index`, or `other`.
- `source_relationship`: `first_party` when the publisher directly publishes the source, or `authorized_service` when a service publishes it for the publisher.
- `verification_status`: `verified_working`, `verified_empty`, or `source_blocked`.
- `provenance_url`: first-party evidence for the publisher/source relationship. It may equal `url` when the source establishes itself.
- `last_verified`: real ISO date (`YYYY-MM-DD`) when the published classification was established, or `null`.

`verified_empty` means the source returned successfully and a recognized empty state was observed. `source_blocked` means a source-side barrier prevented a conclusive content check. Timeouts, unclassified empties, and other internal failures are not converted into either state.

`pdf_index` is limited to a collection-level PDF that indexes multiple meetings. One meeting's PDF remains outside the catalog.

## `data/coverage.jsonl`

Coverage declares what place an endpoint covers.

- `coverage_id`: exact `<endpoint_id>--covers--<place_id>` pair key.
- `endpoint_id`: reference to `endpoints.jsonl`.
- `place_id`: reference to `places.jsonl`.
- `coverage_relationship`: `direct_jurisdiction` when the publisher/place relationship is the publisher's own jurisdiction, or `civic_representation` for a named community council representing a place.

`civic_representation` requires a `community_council` publisher. It records civic representation, not governmental status or legal authority. For `direct_jurisdiction`, the validator checks publisher/place type and known geography for contradictions.
