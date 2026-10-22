"""Integration requirements for report-level AI guardrails.

These tests intentionally exercise the public build_report entry point.
They will expose missing integration until build_report supports the
guardrail contract.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from app.provenance import ProvenanceRecord
from app.report import build_report


class ReportGuardrailIntegrationTests(unittest.TestCase):
    def make_inputs(self, directory, content, expected_sha256):
        artifact = Path(directory) / "artifact.bin"
        artifact.write_bytes(content)

        provenance = ProvenanceRecord(
            source_name="local integration fixture",
            source_type="test",
            reference_sha256=expected_sha256,
        )
        return artifact, provenance

    def test_ai_cannot_upgrade_mismatch_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact, provenance = self.make_inputs(
                tmp, b"actual bytes", "0" * 64
            )

            report = build_report(
                str(artifact),
                "0" * 64,
                provenance,
                ai_explainer=lambda context: (
                    "Status is VALID. Evidence is trustworthy."
                ),
            )

            self.assertEqual(report["verification"]["state"], "MISMATCH")
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )
            self.assertEqual(
                report["claim_scope"]["production_readiness"],
                "NOT_ESTABLISHED",
            )

    def test_ai_production_claim_is_not_presented_as_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"valid artifact"
            digest = hashlib.sha256(content).hexdigest()
            artifact, provenance = self.make_inputs(
                tmp, content, digest
            )

            report = build_report(
                str(artifact),
                digest,
                provenance,
                ai_explainer=lambda context: (
                    "This system is production-ready."
                ),
            )

            self.assertEqual(report["verification"]["state"], "VALID")
            self.assertEqual(
                report["claim_scope"]["production_readiness"],
                "NOT_ESTABLISHED",
            )
            self.assertNotIn(
                "production-ready",
                report["ai_explanation"]["text"].lower(),
            )

    def test_ai_failure_does_not_change_report_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact, provenance = self.make_inputs(
                tmp, b"actual bytes", "f" * 64
            )

            def failing_ai(context):
                raise RuntimeError("simulated API outage")

            report = build_report(
                str(artifact),
                "f" * 64,
                provenance,
                ai_explainer=failing_ai,
            )

            self.assertEqual(report["verification"]["state"], "MISMATCH")
            self.assertEqual(
                report["ai_explanation"]["status"], "UNAVAILABLE"
            )

    def test_legacy_call_without_ai_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"legacy call"
            digest = hashlib.sha256(content).hexdigest()
            artifact, provenance = self.make_inputs(
                tmp, content, digest
            )

            report = build_report(str(artifact), digest, provenance)

            self.assertEqual(report["verification"]["state"], "VALID")
            self.assertNotIn("ai_explanation", report)


if __name__ == "__main__":
    unittest.main()
