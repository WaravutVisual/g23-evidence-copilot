"""Keep untrusted AI text separate from verifier-owned state."""

from collections.abc import Callable
from typing import Any

from app.verifier import Result, State


def build_guarded_result(
    result: Result,
    ai_explainer: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Return verifier-owned state and never publish raw AI text as verified.

    Raw AI output is withheld because this module does not have a proven
    semantic claim validator. The verifier state is never derived from AI.
    """
    if not isinstance(result, Result) or not isinstance(result.state, State):
        raise TypeError("A valid verifier Result is required.")

    verification = {
        "state": result.state.value,
        "explanation": result.explanation,
        "observed_sha256": result.observed_sha256,
    }

    ai_status = "DISABLED"
    ai_text = "AI explanation is disabled."

    if ai_explainer is not None:
        context = dict(verification)
        try:
            response = ai_explainer(context)
        except Exception:
            ai_status = "UNAVAILABLE"
            ai_text = (
                "AI explanation failed. "
                "Verifier state is unchanged."
            )
        else:
            if isinstance(response, str):
                ai_status = "REVIEW_REQUIRED"
                ai_text = (
                    "Raw AI text withheld pending claim review. "
                    f"Verifier state remains {verification['state']}. "
                    "AI cannot set verification state to VALID."
                )
            else:
                ai_status = "REJECTED"
                ai_text = (
                    "AI response rejected: expected plain text. "
                    "Verifier state is unchanged."
                )

    return {
        "verification": verification,
        "ai_explanation": {
            "status": ai_status,
            "text": ai_text,
            "is_authoritative": False,
        },
        "claim_scope": {
            "source_authenticity": "NOT_ESTABLISHED",
            "runtime_correctness": "NOT_ESTABLISHED",
            "production_readiness": "NOT_ESTABLISHED",
        },
    }
