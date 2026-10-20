# G23 Release Candidate Checklist

- [ ] Identify and explain the old manifest/source hash discrepancy.
- [ ] Run tests from a clean clone at a recorded commit SHA.
- [ ] Record Python version, exact command, exit code, and full logs.
- [ ] Add negative tests for invalid input and trusted-head mismatch.
- [ ] Obtain a real successful GitHub Actions run.
- [ ] Review security boundaries and trusted-head provenance.
- [ ] Generate SHA-256 sums for the final release files.
- [ ] Re-check sums from a separate clean directory.
- [ ] Attach demo input, test logs, audit record, and limitations.
- [ ] Tag a release candidate only after the checks above are evidenced.

## Release status

Until the checklist is supported by recorded evidence, this project
remains a prototype / release candidate in preparation, not a
production-ready security product.
