import json
import tempfile
import unittest
from pathlib import Path

from app.claim_gate import (
    evaluate_claim,
    run_demo_with_missing_evidence,
)
from app.verifier import Result, State


class TestClaimGate(unittest.TestCase):

    def test_unknown_block_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"

            result = run_demo_with_missing_evidence(
                question="Does G23 automatically back up to the cloud?",
                audit_path=audit_path,
            )

            self.assertEqual(result["verification"]["state"], "UNKNOWN")
            self.assertEqual(result["decision"], "BLOCK")
            self.assertEqual(result["audit"]["event"], "CLAIM_BLOCKED")
            self.assertEqual(
                result["audit"]["reason"],
                "INSUFFICIENT_EVIDENCE",
            )
            self.assertEqual(result["audit"]["evidence_refs"], [])
            self.assertIs(
                result["ai_explanation"]["is_authoritative"],
                False,
            )

            # Prove that the audit event was persisted and can be read back.
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), result["audit"])

    def test_ai_cannot_upgrade_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_demo_with_missing_evidence(
                question="Is this claim proven?",
                audit_path=Path(directory) / "audit.jsonl",
            )

            self.assertEqual(result["verification"]["state"], "UNKNOWN")
            self.assertEqual(result["decision"], "BLOCK")

    def test_valid_hash_does_not_prove_semantic_support(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"

            result = evaluate_claim(
                question="Does the artifact prove cloud backups?",
                result=Result(
                    State.VALID,
                    "Artifact hash matches.",
                    "a" * 64,
                ),
                evidence_refs=["artifact-1"],
                audit_path=audit_path,
                ai_explainer=lambda _: "The claim is definitely true.",
            )

            self.assertEqual(result["decision"], "BLOCK")
            self.assertEqual(
                result["audit"]["reason"],
                "SEMANTIC_SUPPORT_NOT_ESTABLISHED",
            )
            self.assertIs(
                result["ai_explanation"]["is_authoritative"],
                False,
            )

    def test_audit_appends_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"

            for question in ("Claim one?", "Claim two?"):
                run_demo_with_missing_evidence(
                    question=question,
                    audit_path=audit_path,
                )

            lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["question"], "Claim one?")
            self.assertEqual(json.loads(lines[1])["question"], "Claim two?")


if __name__ == "__main__":
    unittest.main()
