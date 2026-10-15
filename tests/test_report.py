import hashlib
import tempfile
import unittest
from pathlib import Path

from app.provenance import ProvenanceRecord
from app.report import build_report


class ReportTests(unittest.TestCase):
    def test_report_preserves_claim_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            content = b"g23 report test"
            path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()

            provenance = ProvenanceRecord(
                source_name="local test fixture",
                source_type="test",
                reference_sha256=digest,
            )
            report = build_report(str(path), digest, provenance)

            self.assertEqual(report["verification"]["state"], "VALID")
            self.assertEqual(
                report["artifact"]["observed_sha256"], digest
            )
            self.assertFalse(
                report["provenance"]["authenticity_verified"]
            )
            self.assertIn(
                "Production readiness",
                report["claim_scope"]["not_established"],
            )
            self.assertTrue(
                report["claim_scope"]["report_fingerprint_is_not_a_signature"]
            )

    def test_mismatch_is_not_upgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"actual bytes")
            provenance = ProvenanceRecord(
                source_name="unknown",
                source_type="undeclared_origin",
            )

            report = build_report(str(path), "0" * 64, provenance)
            self.assertEqual(report["verification"]["state"], "MISMATCH")


if __name__ == "__main__":
    unittest.main()
