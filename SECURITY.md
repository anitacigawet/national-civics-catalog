# Security policy

## Report a vulnerability

Use GitHub's private vulnerability-reporting or security-advisory feature for vulnerabilities in the validator, schemas, or repository automation. Include the affected file, impact, and a minimal reproduction when possible. Do not place an active exploit or sensitive information in a public issue.

Examples include a validator bypass that admits credential-bearing URLs, IP literals, or known special-use or local hostnames; a path-handling flaw; or a schema/validator mismatch that could mislead consumers.

Incorrect, moved, or unavailable publisher/source links are data-quality reports. Use the source-correction issue form for those.

## Consumer responsibility

Every catalog URL remains untrusted runtime input. Consumers must enforce their own egress policy, redirect-host validation, response-size limits, timeouts, and content handling. Inclusion means only that the catalog records a first-party or authorized-service relationship to the named publisher. It is not a security, availability, accuracy, authority, or endorsement guarantee.
