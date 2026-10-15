import hashlib
import tempfile
import unittest
from pathlib import Path

from app.verifier import State, verify_artifact


class VerifierTests(unittest.TestCase):
    def test_valid_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"verified sample")
            digest = hashlib.sha256(b"verified sample").hexdigest()

            result = verify_artifact(str(path), digest)

            self.assertEqual(result.state, State.VALID)

    def test_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.bin"

            result = verify_artifact(str(path), "abc")

            self.assertEqual(result.state, State.UNKNOWN)

    def test_mismatched_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"actual bytes")

            result = verify_artifact(str(path), "0" * 64)

            self.assertEqual(result.state, State.MISMATCH)

    def test_missing_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"some bytes")

            result = verify_artifact(str(path), None)

            self.assertEqual(result.state, State.UNKNOWN)


    def test_invalid_reference_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"some bytes")
            result = verify_artifact(str(path), "abc")
            self.assertEqual(result.state, State.UNKNOWN)

    def test_corrupted_evidence_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_artifact(tmp, "0" * 64)

            self.assertEqual(result.state, State.CORRUPTED)


if __name__ == "__main__":
    unittest.main()
