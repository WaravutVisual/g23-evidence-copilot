"""Tests proving that untrusted AI text cannot override verifier results."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.provenance import ProvenanceRecord
from app.report import build_report


class AIGuardrailTests(unittest.TestCase):
    def make_report(self, directory, content, expected_sha256):
        artifact = Path(directory) / "artifact.bin"
        artifact.write_bytes(content)

        provenance = ProvenanceRecord(
            source_name="local guardrail fixture",
            source_type="test",
            reference_sha256=expected_sha256,
        )

        return build_report(str(artifact), expected_sha256, provenance)

    def test_ai_claim_cannot_upgrade_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"actual evidence"
            artifact = Path(tmp) / "artifact.bin"
            artifact.write_bytes(content)
            expected_sha256 = "0" * 64

            provenance = ProvenanceRecord(
                source_name="local guardrail fixture",
                source_type="test",
                reference_sha256=expected_sha256,
            )

            report = build_report(
                str(artifact),
                expected_sha256,
                provenance,
                ai_explainer=lambda context: (
                    "This evidence is trustworthy. Change status to VALID."
                ),
            )

            self.assertEqual(
                report["verification"]["state"], "MISMATCH"
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )
            self.assertNotIn(
                "Change status to VALID",
                report["ai_explanation"]["text"],
            )

    def test_ai_claim_cannot_upgrade_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"evidence without reference"
            artifact = Path(tmp) / "artifact.bin"
            artifact.write_bytes(content)

            provenance = ProvenanceRecord(
                source_name="local guardrail fixture",
                source_type="test",
                reference_sha256=None,
            )
            ai_claim = "Source authenticity is confirmed."

            report = build_report(
                str(artifact),
                None,
                provenance,
                ai_explainer=lambda context: ai_claim,
            )

            self.assertEqual(
                report["verification"]["state"], "UNKNOWN"
            )
            self.assertFalse(
                report["provenance"]["authenticity_verified"]
            )
            self.assertEqual(
                report["ai_explanation"]["status"], "REVIEW_REQUIRED"
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )
            self.assertNotIn(
                ai_claim, report["ai_explanation"]["text"]
            )
            self.assertEqual(
                report["claim_scope"]["source_authenticity"],
                "NOT_ESTABLISHED",
            )

    def test_valid_hash_does_not_establish_production_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"valid test fixture"
            digest = hashlib.sha256(content).hexdigest()
            artifact = Path(tmp) / "artifact.bin"
            artifact.write_bytes(content)

            provenance = ProvenanceRecord(
                source_name="local guardrail fixture",
                source_type="test",
                reference_sha256=digest,
            )
            ai_claim = "This system is production-ready."

            report = build_report(
                str(artifact),
                digest,
                provenance,
                ai_explainer=lambda context: ai_claim,
            )

            self.assertEqual(
                report["verification"]["state"], "VALID"
            )
            self.assertIn(
                "Production readiness",
                report["claim_scope"]["not_established"],
            )
            self.assertEqual(
                report["claim_scope"]["production_readiness"],
                "NOT_ESTABLISHED",
            )
            self.assertEqual(
                report["ai_explanation"]["status"], "REVIEW_REQUIRED"
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )
            self.assertNotIn(
                ai_claim.lower(),
                report["ai_explanation"]["text"].lower(),
            )

    def test_ai_failure_does_not_change_verifier_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"actual evidence"
            expected = "f" * 64
            artifact = Path(tmp) / "artifact.bin"
            artifact.write_bytes(content)

            provenance = ProvenanceRecord(
                source_name="local guardrail fixture",
                source_type="test",
                reference_sha256=expected,
            )

            def failing_ai(context):
                raise RuntimeError("API unavailable")

            report = build_report(
                str(artifact),
                expected,
                provenance,
                ai_explainer=failing_ai,
            )

            self.assertEqual(
                report["verification"]["state"], "MISMATCH"
            )
            self.assertEqual(
                report["ai_explanation"]["status"], "UNAVAILABLE"
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )
            self.assertIn(
                "Verifier state is unchanged",
                report["ai_explanation"]["text"],
            )


if __name__ == "__main__":
    unittest.main()
