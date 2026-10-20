import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from app.hash_chain import build_chain, main


class TestHashChainCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "chain.json"
        self.entries = build_chain([
            {"event": "created"},
            {"event": "verified"},
        ])
        self.write_chain(self.entries)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_chain(self, entries):
        self.path.write_text(
            json.dumps({
                "schema_version": 1,
                "entries": entries,
            }),
            encoding="utf-8",
        )

    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([str(self.path), *args])
        return code, json.loads(output.getvalue())

    def test_legacy_cli_remains_valid(self):
        code, result = self.run_cli([])
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "VALID")

    def test_matching_expected_head_is_valid(self):
        head = self.entries[-1]["entry_hash"]
        code, result = self.run_cli(["--expected-head", head])
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "VALID")
        self.assertEqual(result["observed_sha256"], head)

    def test_wrong_expected_head_is_mismatch(self):
        code, result = self.run_cli(["--expected-head", "f" * 64])
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "MISMATCH")

    def test_malformed_expected_head_is_corrupted(self):
        code, result = self.run_cli(["--expected-head", "not-a-sha256"])
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "CORRUPTED")

    def test_truncated_chain_is_detected_with_trusted_head(self):
        trusted_head = self.entries[-1]["entry_hash"]
        self.write_chain(self.entries[:-1])
        code, result = self.run_cli(["--expected-head", trusted_head])
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "MISMATCH")


if __name__ == "__main__":
    unittest.main()
