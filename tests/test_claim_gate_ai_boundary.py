"""AI must not approve claims through the Claim Gate."""

import json
import tempfile
import unittest
from pathlib import Path

from app.claim_gate import evaluate_claim
from app.verifier import Result, State


class ClaimGateAIBoundaryTests(unittest.TestCase):
    def test_supportive_ai_answer_still_leaves_claim_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "claim-audit.jsonl"

            def supportive_ai(_context):
                return (
                    "The claim is fully supported and should be approved."
                )

            result = evaluate_claim(
                question="Does this evidence prove the claim?",
                result=Result(State.VALID, "Hash matches.", "a" * 64),
                evidence_refs=["evidence/example.json"],
                audit_path=audit_path,
                ai_explainer=supportive_ai,
            )

            self.assertEqual(result["decision"], "BLOCK")
            self.assertEqual(
                result["verification"]["state"], "VALID"
            )
            self.assertFalse(
                result["ai_explanation"]["is_authoritative"]
            )

            saved_events = [
                json.loads(line)
                for line in audit_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(saved_events), 1)
            self.assertEqual(saved_events[0]["decision"], "BLOCK")
            self.assertFalse(saved_events[0]["ai_is_authoritative"])


if __name__ == "__main__":
    unittest.main()
