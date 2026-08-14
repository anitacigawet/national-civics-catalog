# State files

Each populated state has one `sources.jsonl` file under its lowercase USPS code.

```text
data/states/az/sources.jsonl
data/states/ny/sources.jsonl
```

The catalog does not create empty state folders. A folder appears when its first reviewed source records are added.

A multi-state source is stored once under the alphabetically first code in its `state_codes` array. Consumers should use each record's full `state_codes` and `covers` values rather than assuming the folder is its only geography.
