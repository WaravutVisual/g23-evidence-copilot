import json
import tempfile
import unittest
from pathlib import Path

from app.hash_chain import (
    build_chain,
    calculate_entry_hash,
    verify_hash_chain,
)
from app.verifier import State


class HashChainTests(unittest.TestCase):
    def write_chain(self, folder, entries):
        path = Path(folder) / "chain.json"
        path.write_text(
            json.dumps({"schema_version": 1, "entries": entries}),
            encoding="utf-8",
        )
        return path

    def test_valid_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = build_chain([{"event": "one"}, {"event": "two"}])
            result = verify_hash_chain(str(self.write_chain(tmp, entries)))
            self.assertEqual(result.state, State.VALID)

    def test_payload_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = build_chain([{"event": "original"}])
            entries[0]["payload"]["event"] = "tampered"
            result = verify_hash_chain(str(self.write_chain(tmp, entries)))
            self.assertEqual(result.state, State.MISMATCH)

    def test_previous_link_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = build_chain([{"event": "one"}, {"event": "two"}])
            entries[1]["previous_hash"] = "f" * 64
            entries[1]["entry_hash"] = calculate_entry_hash(
                entries[1]["sequence"],
                entries[1]["payload"],
                entries[1]["previous_hash"],
            )
            result = verify_hash_chain(str(self.write_chain(tmp, entries)))
            self.assertEqual(result.state, State.MISMATCH)

    def test_missing_file_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_hash_chain(str(Path(tmp) / "missing.json"))
            self.assertEqual(result.state, State.UNKNOWN)

    def test_missing_entries_collection_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.json"
            path.write_text('{"schema_version":1}', encoding="utf-8")
            self.assertEqual(verify_hash_chain(str(path)).state, State.UNKNOWN)

    def test_sequence_gap_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = build_chain([
                {"event": "one"}, {"event": "two"}, {"event": "three"}
            ])
            entries.pop(1)
            result = verify_hash_chain(str(self.write_chain(tmp, entries)))
            self.assertEqual(result.state, State.UNKNOWN)

    def test_placeholder_is_never_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = build_chain([{"event": "test"}])
            entries[0]["entry_hash"] = "PLACEHOLDER_INSERT_REAL_SHA256_HERE"
            result = verify_hash_chain(str(self.write_chain(tmp, entries)))
            self.assertEqual(result.state, State.CORRUPTED)

    def test_malformed_json_is_corrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.json"
            path.write_text('{"entries":[', encoding="utf-8")
            self.assertEqual(verify_hash_chain(str(path)).state, State.CORRUPTED)

    def test_non_array_entries_are_corrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.json"
            path.write_text(
                '{"schema_version":1,"entries":"invalid"}',
                encoding="utf-8",
            )
            self.assertEqual(verify_hash_chain(str(path)).state, State.CORRUPTED)

    def test_tamper_then_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = build_chain([{"event": "baseline"}])
            path = self.write_chain(tmp, original)
            self.assertEqual(verify_hash_chain(str(path)).state, State.VALID)

            tampered = build_chain([{"event": "baseline"}])
            tampered[0]["payload"]["event"] = "modified"
            path.write_text(
                json.dumps({"schema_version": 1, "entries": tampered}),
                encoding="utf-8",
            )
            self.assertEqual(verify_hash_chain(str(path)).state, State.MISMATCH)

            path.write_text(
                json.dumps({"schema_version": 1, "entries": original}),
                encoding="utf-8",
            )
            self.assertEqual(verify_hash_chain(str(path)).state, State.VALID)


if __name__ == "__main__":
    unittest.main()
