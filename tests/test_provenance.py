import unittest

from app.provenance import ProvenanceRecord


class ProvenanceTests(unittest.TestCase):
    def test_declared_source_is_not_verified(self):
        record = ProvenanceRecord(
            source_name="test source",
            source_type="user_supplied",
            reference_sha256="a" * 64,
        ).to_dict()

        self.assertEqual(record["provenance_status"], "SOURCE_DECLARED")
        self.assertFalse(record["authenticity_verified"])
        self.assertTrue(record["recorded_at_utc"])
        self.assertTrue(record["limitations"])


if __name__ == "__main__":
    unittest.main()
