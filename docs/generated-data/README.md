# Catalog data

Published records live in `data/states/<code>/sources.jsonl`.

Version 0.1.0 contains a Census-shaped starting roster across every state, the District of Columbia, and the five populated U.S. territories, plus 88 reviewed Arizona sources. Records marked `needs_source` are preformed maintenance slots with no endpoint claim. The catalog contains continuing endpoints and their basic metadata, never individual meeting records or application code.

Run `python scripts/validate_catalog.py` before publishing any data change.
