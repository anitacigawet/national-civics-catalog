# State files

Every U.S. state, the District of Columbia, and the five inhabited territories has a folder under its lowercase USPS code and a `sources.jsonl` file.

```text
data/states/az/sources.jsonl
data/states/ny/sources.jsonl
```

The state files begin with active general-purpose governments from the 2022 Census of Governments. Their endpoint fields remain empty and their status remains `needs_source` until a contributor supplies evidence for a continuing public meeting source. This gives people and their AI assistants a stable record to fill instead of an empty folder or an invented JSON shape.

A multi-state source is stored once under the alphabetically first code in its `state_codes` array. Consumers should use each record's full `state_codes` and `covers` values rather than assuming the folder is its only geography.
