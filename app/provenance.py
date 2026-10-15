"""Declared provenance metadata. Declaration is not proof of authenticity."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class ProvenanceRecord:
    source_name: str
    source_type: str
    source_uri: Optional[str] = None
    provided_by: Optional[str] = None
    reference_sha256: Optional[str] = None

    def to_dict(self):
        return {
            **asdict(self),
            "provenance_status": "SOURCE_DECLARED",
            "authenticity_verified": False,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "limitations": [
                "Metadata was declared by the submitter.",
                "Source ownership and authenticity have not been independently verified.",
                "A matching hash proves byte equality only against the supplied reference."
            ],
        }
