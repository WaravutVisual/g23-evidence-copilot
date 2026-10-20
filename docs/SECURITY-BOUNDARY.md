# G23 Evidence Copilot: Security Boundary

## What the verifier establishes

- VALID: the supplied evidence satisfies the implemented deterministic
  checks and, when configured, matches the supplied trusted head.
- MISMATCH: observed data conflicts with the expected structure, link,
  digest, or trusted head.
- UNKNOWN: required evidence or fields are missing.
- CORRUPTED: evidence cannot be parsed or violates supported formats.

The exact interpretation depends on the specific verifier and test.

## What it does not establish

A valid SHA-256 hash chain alone does not prove:

- that a claim in the payload is true;
- who originally created the evidence;
- that timestamps are genuine;
- that the source system or runtime behaved as claimed;
- that the evidence was not replaced together with its untrusted
  reference hash;
- resistance to every attack or production readiness.

## Trusted-head requirement

The expected head must come from a separately controlled, authenticated
trust source. If the chain and expected head are both supplied by the
same untrusted party, an attacker may replace both.

For stronger provenance, use signed attestations, controlled key
management, independent timestamping where required, and access
controls. These are separate controls and must be tested independently.

## Release rule

Never upgrade a claim beyond its evidence. Preserve original records;
write new audit results to new files. Report VERIFIED, PENDING, and
NOT ESTABLISHED separately. A passing test suite is not a production
security certification.
