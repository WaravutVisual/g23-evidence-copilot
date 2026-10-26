"""Fail-closed claim gate with a persistent JSONL audit trail."""

import json
import os
from pathlib import Path
from typing import Any

from app.ai_guardrail import build_guarded_result
from app.verifier import Result, State, verify_artifact


def _append_and_read_audit(
    audit_path: str | Path,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Append one audit event and read it back for verification."""
    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
    )

    # O_APPEND prevents accidental replacement of earlier audit records.
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # fdopen owns fd once successfully created.
        raise

    with path.open("r", encoding="utf-8") as stream:
        records = [
            json.loads(item)
            for item in stream
            if item.strip()
        ]

    if not records or records[-1] != event:
        raise RuntimeError("Audit read-back verification failed.")

    return records[-1]


def evaluate_claim(
    *,
    question: str,
    result: Result,
    evidence_refs: list[str],
    audit_path: str | Path,
    ai_explainer=None,
) -> dict[str, Any]:
    """Block claims unless verification is VALID and evidence is referenced.

    VALID here means only that the existing verifier passed. It does not
    prove that the evidence semantically supports the question.
    """
    if not isinstance(result, Result):
        raise TypeError("result must be a verifier Result.")

    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string.")

    if not isinstance(evidence_refs, list) or any(
        not isinstance(ref, str) or not ref.strip()
        for ref in evidence_refs
    ):
        raise ValueError("evidence_refs must be a list of non-empty strings.")

    guarded = build_guarded_result(result, ai_explainer)

    # This initial gate is deliberately conservative. A semantic evidence
    # validator is not implemented, so it never approves a claim as proven.
    decision = "BLOCK"
    reason = (
        "INSUFFICIENT_EVIDENCE"
        if result.state == State.UNKNOWN or not evidence_refs
        else "SEMANTIC_SUPPORT_NOT_ESTABLISHED"
    )

    event = {
        "schema_version": 1,
        "event": "CLAIM_BLOCKED",
        "decision": decision,
        "reason": reason,
        "question": question,
        "verification_state": result.state.value,
        "evidence_refs": list(evidence_refs),
        "ai_is_authoritative": False,
    }

    persisted_event = _append_and_read_audit(audit_path, event)

    return {
        "verification": guarded["verification"],
        "decision": decision,
        "audit": persisted_event,
        "ai_explanation": guarded["ai_explanation"],
        "claim_scope": guarded["claim_scope"],
    }


def run_demo_with_missing_evidence(
    question: str,
    audit_path: str | Path = "evidence/audit/claim-gate.jsonl",
) -> dict[str, Any]:
    """Demonstrate fail-closed behavior when the evidence file is absent."""
    missing_result = verify_artifact(
        "evidence/claim-gate-demo-evidence-missing.json",
        None,
    )

    return evaluate_claim(
        question=question,
        result=missing_result,
        evidence_refs=[],
        audit_path=audit_path,
    )
