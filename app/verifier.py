from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
import re


class State(str, Enum):
    VALID = "VALID"
    UNKNOWN = "UNKNOWN"
    MISMATCH = "MISMATCH"
    CORRUPTED = "CORRUPTED"


@dataclass
class Result:
    state: State
    explanation: str


def verify_artifact(path: str, expected_sha256: str | None) -> Result:
    artifact = Path(path)

    if not artifact.exists():
        return Result(State.UNKNOWN, "Required evidence is missing.")

    if not artifact.is_file():
        return Result(State.CORRUPTED, "Evidence path is not a regular file.")

    if not expected_sha256:
        return Result(
            State.UNKNOWN,
            "Trusted reference SHA-256 is missing; integrity cannot be established."
        )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        return Result(
            State.UNKNOWN,
            "Reference SHA-256 must contain exactly 64 hexadecimal characters."
        )

    try:
        digest = sha256(artifact.read_bytes()).hexdigest()
    except (OSError, PermissionError):
        return Result(State.CORRUPTED, "Evidence could not be read.")

    if digest != expected_sha256.lower():
        return Result(
            State.MISMATCH,
            "Artifact SHA-256 does not match the supplied reference."
        )

    return Result(
        State.VALID,
        "Artifact bytes match the supplied SHA-256 reference. "
        "Runtime behavior and production readiness are not established."
    )
