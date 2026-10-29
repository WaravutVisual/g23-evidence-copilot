import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.provenance import ProvenanceRecord
from app.report import build_report


class MetaReportWiringTests(unittest.TestCase):
    def make_inputs(self, directory):
        artifact = Path(directory) / "artifact.bin"
        content = b"meta report wiring fixture"
        artifact.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        provenance = ProvenanceRecord(
            source_name="local test fixture",
            source_type="test",
            reference_sha256=digest,
        )
        return artifact, digest, provenance

    def test_opt_in_calls_meta_client_through_guardrail(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact, digest, provenance = self.make_inputs(tmp)

            with patch.dict(os.environ, {"G23_META_AI": "1"}):
                with patch(
                    "app.report.explain_verification",
                    return_value="Untrusted model output",
                ) as mocked:
                    report = build_report(
                        str(artifact), digest, provenance
                    )

            mocked.assert_called_once()
            self.assertEqual(
                mocked.call_args.args[0]["state"], "VALID"
            )
            self.assertEqual(report["verification"]["state"], "VALID")
            self.assertEqual(
                report["ai_explanation"]["status"], "REVIEW_REQUIRED"
            )
            self.assertNotIn(
                "Untrusted model output",
                report["ai_explanation"]["text"],
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )

    def test_disabled_by_default_does_not_call_meta_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact, digest, provenance = self.make_inputs(tmp)

            with patch.dict(os.environ, {"G23_META_AI": "0"}):
                with patch(
                    "app.report.explain_verification"
                ) as mocked:
                    report = build_report(
                        str(artifact), digest, provenance
                    )

            mocked.assert_not_called()
            self.assertNotIn("ai_explanation", report)
            self.assertEqual(report["verification"]["state"], "VALID")

    def test_meta_failure_does_not_change_verifier_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact, digest, provenance = self.make_inputs(tmp)

            with patch.dict(os.environ, {"G23_META_AI": "1"}):
                with patch(
                    "app.report.explain_verification",
                    side_effect=RuntimeError("simulated outage"),
                ):
                    report = build_report(
                        str(artifact), digest, provenance
                    )

            self.assertEqual(report["verification"]["state"], "VALID")
            self.assertEqual(
                report["ai_explanation"]["status"], "UNAVAILABLE"
            )
            self.assertFalse(
                report["ai_explanation"]["is_authoritative"]
            )


if __name__ == "__main__":
    unittest.main()
