# Record examples

The checked-in Arizona file contains real examples. The records below use fictional names and domains only to explain the shape.

## Municipal calendar

```json
{"source_id":"us-az-sample-town--meeting-calendar","publisher_name":"Sample Town","publisher_type":"municipality","state_codes":["AZ"],"county_names":["Sample County"],"official_website_url":"https://sampletown.gov","endpoint_type":"meeting_calendar","url":"https://meetings.sampletown.gov/calendar","platform":"custom","access_method":"html","source_relationship":"first_party","status":"working","last_checked":"2026-08-14","provenance_url":"https://sampletown.gov/meetings","covers":[{"name":"Sample Town","type":"municipality","state_codes":["AZ"],"county_names":["Sample County"],"relationship":"direct_jurisdiction","ocd_division_id":null,"census_geoid":null}]}
```

## Community representation

A community council can be recorded as the publisher without calling it a government. Its `covers` relationship is `civic_representation`.

```json
{"source_id":"us-az-sample-community-council--primary-meeting-source","publisher_name":"Sample Community Council","publisher_type":"community_council","state_codes":["AZ"],"county_names":["Sample County"],"official_website_url":"https://samplecouncil.org","endpoint_type":"primary_meeting_source","url":"https://samplecouncil.org/meetings","platform":"custom","access_method":"html","source_relationship":"first_party","status":"working","last_checked":null,"provenance_url":"https://samplecouncil.org/about","covers":[{"name":"Sample Community","type":"unincorporated_community","state_codes":["AZ"],"county_names":["Sample County"],"relationship":"civic_representation","ocd_division_id":null,"census_geoid":null}]}
```

## Multi-state source

A source spanning Arizona, New Mexico, and Utah uses `"state_codes":["AZ","NM","UT"]` and is stored once in `data/states/az/sources.jsonl`.
