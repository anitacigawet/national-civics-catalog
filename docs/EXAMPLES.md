# Record examples

These examples use reserved example domains and are not release data. Each block shows one line from each v1 file in canonical field order.

## A municipality publishing its own calendar

`publishers.jsonl`

```json
{"publisher_id":"us-az-example-city","publisher_name":"City of Example","publisher_type":"municipality","country_code":"US","state_codes":["AZ"],"county_names":["Example County"],"official_website_url":"https://www.example.gov/"}
```

`places.jsonl`

```json
{"place_id":"us-az-example-city","place_name":"Example","place_type":"municipality","country_code":"US","state_codes":["AZ"],"county_names":["Example County"],"ocd_division_id":null,"census_geoid":null}
```

`endpoints.jsonl`

```json
{"endpoint_id":"us-az-example-city--meeting-calendar","publisher_id":"us-az-example-city","endpoint_type":"meeting_calendar","url":"https://calendar.example.gov/meetings","platform":"custom","access_method":"html","source_relationship":"first_party","verification_status":"verified_working","provenance_url":"https://www.example.gov/meetings","last_verified":"2026-08-13"}
```

`coverage.jsonl`

```json
{"coverage_id":"us-az-example-city--meeting-calendar--covers--us-az-example-city","endpoint_id":"us-az-example-city--meeting-calendar","place_id":"us-az-example-city","coverage_relationship":"direct_jurisdiction"}
```

## A community council representing an unincorporated place

This form records the council as a named civic publisher. It deliberately does not call the council a government or imply legal authority over the place.

`publishers.jsonl`

```json
{"publisher_id":"us-az-example-community-council","publisher_name":"Example Community Council","publisher_type":"community_council","country_code":"US","state_codes":["AZ"],"county_names":["Example County"],"official_website_url":"https://www.example.gov/"}
```

`places.jsonl`

```json
{"place_id":"us-az-example-community","place_name":"Example Community","place_type":"unincorporated_community","country_code":"US","state_codes":["AZ"],"county_names":["Example County"],"ocd_division_id":null,"census_geoid":null}
```

`endpoints.jsonl`

```json
{"endpoint_id":"us-az-example-community-council--primary-meeting-source","publisher_id":"us-az-example-community-council","endpoint_type":"primary_meeting_source","url":"https://www.example.gov/meetings","platform":"custom","access_method":"html","source_relationship":"first_party","verification_status":"verified_working","provenance_url":"https://www.example.gov/meetings","last_verified":null}
```

`coverage.jsonl`

```json
{"coverage_id":"us-az-example-community-council--primary-meeting-source--covers--us-az-example-community","endpoint_id":"us-az-example-community-council--primary-meeting-source","place_id":"us-az-example-community","coverage_relationship":"civic_representation"}
```

## Multi-state bodies and places

`state_codes` is an array rather than a single state field. A multi-state Tribal publisher or place can use a sorted value such as `["AZ","NM","UT"]`. Its assigned key does not need a state component; `us-navajo-nation-council` is a valid key shape. Publication still requires evidence for the actual publisher, endpoint, place, and coverage relationship.
