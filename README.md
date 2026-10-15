# G23 Evidence Copilot

An evidence-based software verification prototype.

## Verification states

- VALID: evidence passed the defined deterministic checks
- UNKNOWN: required evidence is missing
- MISMATCH: evidence does not match the trusted reference
- CORRUPTED: evidence cannot be read or fails integrity validation

VALID does not imply runtime correctness or production readiness.
AI explanations must not override deterministic verification results.
