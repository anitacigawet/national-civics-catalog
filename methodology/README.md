# Methodology

National Civics Catalog was built in two distinct steps: first define the roster
in scope, then research each rostered body for a continuing meeting source. The
project calls the first step the **stencil**.

This separation matters. Search results do not decide which governments appear
in the catalog. A difficult or unsuccessful search leaves an honest
`needs_source` record instead of making the government disappear.

## Build the stencil

The United States stencil began with the U.S. Census Bureau's 2022 Government
Units Listing. It covers active state, county, municipal, and township
governments. Census identifiers were preserved as strings, including leading
zeroes, and used to create stable catalog identities.

A statistical geography is not automatically a government. Census places,
districts, and other geographic features were not used as substitutes for a
government-unit roster. The stencil represents the rostered government, not
each chamber, board, department, or committee inside it.

Every in-scope government received a record before national source discovery
began. The initial records carried the government's identity, geography, and
roster evidence while leaving the meeting-source fields null. The roster,
record count, identifiers, and evidence were independently checked before the
research queue was frozen.

The Census roster is a documented starting boundary, not a claim that every
possible civic body is represented. Tribal governments, special districts,
unincorporated communities, newer governments, and other bodies may require
separate authoritative rosters.

## Research continuing sources

The research target was a continuing place where a public body publishes
meeting information. Qualifying sources include:

- meeting calendars;
- agenda or minutes indexes;
- public-notice pages;
- feeds or APIs;
- meeting portals; and
- maintained video archives.

A single agenda, a single meeting notice, an unsupported search result, or a
generic homepage is not enough. The endpoint must be operated by the public
body or have evidence that it is an authorized publication channel.

Researchers recorded the public-body website, exact meeting-source URL, source
type, platform, access method, relationship to the public body, observation
date, and public evidence. Webpage text was treated as untrusted evidence
rather than as instructions. URLs were not guessed when the official source
could not be established.

Research could end honestly without an identified endpoint. Blocked sites,
ambiguous evidence, and bounded searches that found no qualifying source were
preserved for review. These outcomes count as completed research, but they do
not become published source claims.

## Separate research from publication

National research was divided into immutable work orders. Each worker used a
separate identity, claimed work atomically, and wrote only its assigned result.
Model output created evidence-backed candidates; it did not directly edit the
public catalog.

Candidates then passed through a separate review process. A different model
and isolated context checked whether the public body, endpoint, official or
authorized relationship, and continuing nature of the source were supported.
Failed or incomplete candidates entered a bounded correction pass. Review
receipts remained evidence, not publication authority.

Final disposition was followed by deterministic validation of JSONL syntax,
schema rules, record invariants, duplicate identities, URL defects, Unicode
format characters, and README totals. Publication required an exact manifest,
a clean repository base, explicit human authorization, and verification of the
public result.

## Models used in the U.S. build

The provider-neutral fleet ledger attributes the final 37,035 non-New York
discovery records as follows:

| Discovery model | Final records |
| --- | ---: |
| GPT-5.4 Mini | 36,289 |
| GPT-5.6 Luna | 436 |
| DeepSeek V4 Flash | 157 |
| GLM-5.3 | 100 |
| GPT-5.3 Codex Spark | 26 |
| Claude Haiku | 25 |
| Claude Sonnet | 1 |
| Qwen3-Coder-30B-A3B-Instruct-FP8 | 1 |

Those figures describe final work-order ownership in the non-New York discovery
fleet. They are not quality scores and should not be extended to the New York
seed records.

GPT-5.6 Luna at low reasoning effort performed the independent national QA.
GPT-5.4 Mini at low reasoning effort produced bounded correction proposals,
which Luna reviewed independently. An operator-supervised Sol review made the
final disposition before deterministic validation and release preparation.

The model names document this build; they are not dependencies. The durable
method is the separation of roster construction, discovery, independent review,
correction, deterministic validation, and human-controlled publication.

## Rebuild it for another country

[`RESPAWN.md`](RESPAWN.md) is a self-contained instruction document designed to
be given to an AI along with a country name. It preserves the stencil-first
method without forcing another country into U.S.-specific concepts such as
states, counties, or Census GEOIDs.

This public methodology does not include credentials, account details, worker
identifiers, raw logs, review receipts, or other private operational evidence.
