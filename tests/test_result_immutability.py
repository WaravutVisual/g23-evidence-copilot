"""Regression tests for immutable verifier results."""

import unittest
from dataclasses import FrozenInstanceError

from app.verifier import Result, State
from app.ai_guardrail import build_guarded_result


class ResultImmutabilityTests(unittest.TestCase):
    def make_result(self):
        return Result(
            State.MISMATCH,
            "Artifact SHA-256 does not match the supplied reference.",
            "a" * 64,
        )

    def test_state_cannot_be_reassigned(self):
        result = self.make_result()

        with self.assertRaises(FrozenInstanceError):
            result.state = State.VALID

        self.assertEqual(result.state, State.MISMATCH)

    def test_explanation_cannot_be_reassigned(self):
        result = self.make_result()

        with self.assertRaises(FrozenInstanceError):
            result.explanation = "Changed by callback"

        self.assertEqual(
            result.explanation,
            "Artifact SHA-256 does not match the supplied reference.",
        )

    def test_callback_cannot_mutate_result_state(self):
        result = self.make_result()

        def mutating_callback(context):
            result.state = State.VALID
            return "The artifact is valid."

        guarded = build_guarded_result(result, mutating_callback)

        self.assertEqual(result.state, State.MISMATCH)
        self.assertEqual(
            guarded["verification"]["state"],
            State.MISMATCH.value,
        )
        self.assertEqual(
            guarded["ai_explanation"]["status"],
            "UNAVAILABLE",
        )
        self.assertFalse(
            guarded["ai_explanation"]["is_authoritative"]
        )


if __name__ == "__main__":
    unittest.main()
