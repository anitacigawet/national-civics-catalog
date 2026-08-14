# State files

Every U.S. state, the District of Columbia, and the five inhabited territories has a folder under its lowercase USPS code. A populated folder also has a `sources.jsonl` file.

```text
data/states/az/sources.jsonl
data/states/ny/README.md
```

Placeholder folders give people a stable link from Z-SPAN and a clear starting point for AI-assisted contributions. Do not create an empty `sources.jsonl`; that file appears with the first reviewed source.

A multi-state source is stored once under the alphabetically first code in its `state_codes` array. Consumers should use each record's full `state_codes` and `covers` values rather than assuming the folder is its only geography.
