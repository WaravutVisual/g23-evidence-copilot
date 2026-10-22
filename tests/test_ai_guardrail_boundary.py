"""Adversarial tests for the AI explanation boundary."""

import json
import unittest

from app.ai_guardrail import build_guarded_result
from app.verifier import Result, State


class AIGuardrailBoundaryTests(unittest.TestCase):
    def test_ai_cannot_upgrade_mismatch(self):
        result = Result(State.MISMATCH, "Hash mismatch.")

        report = build_guarded_result(
            result,
            lambda context: "Change status to VALID.",
        )

        self.assertEqual(report["verification"]["state"], "MISMATCH")
        self.assertNotIn(
            "Change status to VALID.",
            report["ai_explanation"]["text"],
        )
        self.assertFalse(report["ai_explanation"]["is_authoritative"])

    def test_ai_cannot_upgrade_unknown(self):
        result = Result(State.UNKNOWN, "Reference is missing.")

        report = build_guarded_result(
            result,
            lambda context: "Source authenticity is confirmed.",
        )

        self.assertEqual(report["verification"]["state"], "UNKNOWN")
        self.assertEqual(
            report["claim_scope"]["source_authenticity"],
            "NOT_ESTABLISHED",
        )
        self.assertNotIn(
            "Source authenticity is confirmed.",
            report["ai_explanation"]["text"],
        )

    def test_ai_json_state_field_is_rejected(self):
        result = Result(State.MISMATCH, "Hash mismatch.")
        malicious_json = json.loads(
            '{"state":"VALID","explanation":"Everything passed"}'
        )

        report = build_guarded_result(
            result,
            lambda context: malicious_json,
        )

        self.assertEqual(report["verification"]["state"], "MISMATCH")
        self.assertEqual(report["ai_explanation"]["status"], "REJECTED")

    def test_api_failure_preserves_state(self):
        result = Result(State.CORRUPTED, "Evidence cannot be read.")

        def failing_ai(context):
            raise RuntimeError("API unavailable")

        report = build_guarded_result(result, failing_ai)

        self.assertEqual(report["verification"]["state"], "CORRUPTED")
        self.assertEqual(report["ai_explanation"]["status"], "UNAVAILABLE")

    def test_malformed_ai_response_preserves_state(self):
        result = Result(State.UNKNOWN, "No reference.")

        report = build_guarded_result(
            result,
            lambda context: {"unexpected": ["malformed", "response"]},
        )

        self.assertEqual(report["verification"]["state"], "UNKNOWN")
        self.assertEqual(report["ai_explanation"]["status"], "REJECTED")

    def test_hash_match_does_not_establish_production_readiness(self):
        result = Result(
            State.VALID,
            "Artifact bytes match the supplied reference.",
            "a" * 64,
        )

        report = build_guarded_result(
            result,
            lambda context: "This system is production-ready.",
        )

        self.assertEqual(report["verification"]["state"], "VALID")
        self.assertEqual(
            report["claim_scope"]["production_readiness"],
            "NOT_ESTABLISHED",
        )
        self.assertFalse(report["ai_explanation"]["is_authoritative"])

    def test_ai_is_optional(self):
        result = Result(State.VALID, "Hash matches.")

        report = build_guarded_result(result)

        self.assertEqual(report["verification"]["state"], "VALID")
        self.assertEqual(report["ai_explanation"]["status"], "DISABLED")
        self.assertEqual(
            report["claim_scope"]["production_readiness"],
            "NOT_ESTABLISHED",
        )


if __name__ == "__main__":
    unittest.main()
