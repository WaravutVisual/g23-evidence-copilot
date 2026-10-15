"""Build a structured report without upgrading verification claims."""
from datetime import datetime, timezone
from hashlib import sha256
import re

from app.verifier import verify_artifact


def build_report(path: str, expected_sha256: str | None, provenance):
    result = verify_artifact(path, expected_sha256)

    observed_sha256 = result.observed_sha256

    reference_format_valid = bool(
        expected_sha256
        and re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)
    )

    return {
        "report_version": "1.0",
        "report_id": sha256(
            (
                datetime.now(timezone.utc).isoformat()
                + "|"
                + str(path)
                + "|"
                + str(observed_sha256)
            ).encode("utf-8")
        ).hexdigest(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
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
        },
    }
