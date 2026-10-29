"""Build a structured report without upgrading verification claims."""

import os
from datetime import datetime, timezone
from hashlib import sha256
import re

from app.verifier import verify_artifact
from app.ai_guardrail import build_guarded_result
from app.meta_api import explain_verification


from collections.abc import Mapping


class FrozenDict(dict):
    """Dict-compatible container that rejects ordinary mutation."""

    def _immutable(self, *args, **kwargs):
        raise TypeError("Report data is immutable.")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def _freeze_report_value(value):
    """Recursively freeze nested report values."""
    if isinstance(value, Mapping):
        return FrozenDict({
            key: _freeze_report_value(item)
            for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_report_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_report_value(item) for item in value)
    return value


def build_report(
    path: str,
    expected_sha256: str | None,
    provenance,
    ai_explainer=None,
):
    # Meta AI is opt-in. Its output remains untrusted and is
    # passed through the existing guardrail below.
    if (
        ai_explainer is None
        and os.environ.get("G23_META_AI", "").strip() == "1"
    ):
        ai_explainer = explain_verification

    result = verify_artifact(path, expected_sha256)
    observed_sha256 = result.observed_sha256
    generated_at = datetime.now(timezone.utc).isoformat()

    reference_format_valid = bool(
        expected_sha256
        and re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)
    )

    report = {
        "report_version": "1.0",
        "report_id": sha256(
            (
                generated_at
                + "|"
                + str(path)
                + "|"
                + str(observed_sha256)
            ).encode("utf-8")
        ).hexdigest(),
        "generated_at_utc": generated_at,
        "artifact": {
            "path": str(path),
            "observed_sha256": observed_sha256,
            "reference_sha256": expected_sha256,
            "reference_format_valid": reference_format_valid,
        },
        "verification": {
            "state": result.state.value,
            "explanation": result.explanation,
        },
        "provenance": provenance.to_dict(),
        "claim_scope": {
            "hash_match_means": (
                "Artifact bytes matched the supplied SHA-256 reference "
                "during the verifier check."
            ),
            "not_established": [
                "Reference source authenticity",
                "Artifact runtime behavior",
                "Production readiness",
            ],
            "report_fingerprint_is_not_a_signature": True,
            "source_authenticity": "NOT_ESTABLISHED",
            "runtime_correctness": "NOT_ESTABLISHED",
            "production_readiness": "NOT_ESTABLISHED",
        },
    }

    # Preserve the legacy three-argument call. AI is opt-in.
    if ai_explainer is not None:
        guarded = build_guarded_result(result, ai_explainer)
        report["ai_explanation"] = guarded["ai_explanation"]

    return _freeze_report_value(report)
