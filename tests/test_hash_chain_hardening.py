import json
import tempfile
import unittest
from pathlib import Path

from app.hash_chain import build_chain, verify_hash_chain
from app.verifier import State


class HashChainHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "chain.json"
        self.entries = build_chain([
            {"event": "first"},
            {"event": "second"},
        ])

    def write_document(self, document):
        self.path.write_text(
            json.dumps(document, ensure_ascii=False),
            encoding="utf-8",
        )
        return self.path

    def test_schema_v1_is_supported(self):
        result = verify_hash_chain(
            self.write_document({
                "schema_version": 1,
                "entries": self.entries,
            })
        )
        self.assertEqual(result.state, State.VALID)

    def test_missing_schema_version_is_unknown(self):
        result = verify_hash_chain(
            self.write_document({"entries": self.entries})
        )
        self.assertEqual(result.state, State.UNKNOWN)

    def test_unsupported_schema_version_is_corrupted(self):
        result = verify_hash_chain(
            self.write_document({
                "schema_version": 999,
                "entries": self.entries,
            })
        )
        self.assertEqual(result.state, State.CORRUPTED)

    def test_truncation_with_trusted_head_is_mismatch(self):
        expected_head = self.entries[-1]["entry_hash"]
        truncated = self.entries[:-1]

        result = verify_hash_chain(
            self.write_document({
                "schema_version": 1,
                "entries": truncated,
            }),
            expected_head=expected_head,
        )
        self.assertEqual(result.state, State.MISMATCH)

    def test_matching_trusted_head_is_valid(self):
        result = verify_hash_chain(
            self.write_document({
                "schema_version": 1,
                "entries": self.entries,
            }),
            expected_head=self.entries[-1]["entry_hash"],
        )
        self.assertEqual(result.state, State.VALID)

    def test_wrong_trusted_head_is_mismatch(self):
        result = verify_hash_chain(
            self.write_document({
                "schema_version": 1,
                "entries": self.entries,
            }),
            expected_head="f" * 64,
        )
        self.assertEqual(result.state, State.MISMATCH)

    def test_malformed_trusted_head_is_corrupted(self):
        result = verify_hash_chain(
            self.write_document({
                "schema_version": 1,
                "entries": self.entries,
            }),
            expected_head="not-a-sha256",
        )
        self.assertEqual(result.state, State.CORRUPTED)


if __name__ == "__main__":
    unittest.main()
