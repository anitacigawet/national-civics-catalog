# Publication boundary

The catalog answers a narrow question: **which continuing meeting-information sources are published by, or provided as an authorized service for, a named U.S. local government, Tribal government, or civic body—and what places do those sources cover?**

It does not decide whether a civic body is a government, whether a publisher has legal authority over a place, whether a source is legally required, or whether anyone named endorses this catalog.

## The collection-level test

A source belongs when the same URL is intended to help someone find more than one meeting or public record over time.

- A meeting-calendar landing page passes.
- An archive listing many recordings passes.
- A continuing agenda, minutes, or public-notices index passes.
- An RSS or iCalendar collection feed passes.
- A PDF index covering multiple meetings can pass when labeled `pdf_index`.
- One meeting's page, agenda, minutes, recording, or transcript does not pass.

A stable vendor or calendar identifier may appear in a collection URL. The deciding fact is whether the source represents a continuing collection rather than one event or artifact.

The validator rejects deterministic one-record and downloadable-artifact URL shapes. URL syntax alone cannot prove that a source is a continuing collection; that decision depends on reviewed provenance.

## The publisher and coverage tests

The publisher is the body that actually publishes the source or authorizes the service. A vendor is not substituted for the government or civic body it serves.

A place is the geography covered, not a synonym for the publisher. Coverage can therefore be many-to-many.

- `first_party` means the publisher directly provides the source.
- `authorized_service` means the endpoint is provided as a service for that publisher.
- `direct_jurisdiction` describes a publisher's own jurisdiction.
- `civic_representation` is reserved for a named `community_council`; it does not claim government status or legal authority.

The evidence must support the named relationship. A shared domain, similar name, or model inference is not enough.

## Operational boundary

Do not add meeting rows, event IDs, agenda text, minutes, transcripts, captions, recordings, quotations, summaries, or generated decisions.

Do not add parser code, selectors, request recipes, credentials, non-public API details, source-health logs, review notes, operator records, or unpublished candidates. Public records must remain independently understandable from their publisher, endpoint, provenance, place, and coverage entries.
