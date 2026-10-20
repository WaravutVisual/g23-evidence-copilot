"""Deterministic SHA-256 hash-chain verifier."""
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sys

from app.verifier import Result, State

GENESIS_HASH = "0" * 64


def canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def calculate_entry_hash(sequence, payload, previous_hash):
    return sha256(canonical_bytes({
        "sequence": sequence,
        "payload": payload,
        "previous_hash": previous_hash,
    })).hexdigest()


def build_chain(payloads):
    entries = []
    previous_hash = GENESIS_HASH

    for sequence, payload in enumerate(payloads, start=1):
        if not isinstance(payload, dict):
            raise TypeError("Each payload must be a JSON object.")

        digest = calculate_entry_hash(
            sequence, payload, previous_hash
        )
        entries.append({
            "sequence": sequence,
            "payload": payload,
            "previous_hash": previous_hash,
            "entry_hash": digest,
        })
        previous_hash = digest

    return entries


def verify_hash_chain(path, expected_head=None):
    source = Path(path)

    if not source.exists():
        return Result(State.UNKNOWN, "Hash-chain evidence is missing.")
    if not source.is_file():
        return Result(State.CORRUPTED, "Evidence path is not a regular file.")

    if expected_head is not None:
        if (
            not isinstance(expected_head, str)
            or len(expected_head) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in expected_head)
        ):
            return Result(State.CORRUPTED, "Trusted expected_head is not a valid SHA-256.")

        expected_head = expected_head.lower()

    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return Result(State.CORRUPTED, "Evidence is unreadable or invalid JSON.")

    if not isinstance(document, dict):
        return Result(State.CORRUPTED, "Document must be a JSON object.")

    if "schema_version" not in document:
        return Result(State.UNKNOWN, "Required schema_version is missing.")

    version = document["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        return Result(State.CORRUPTED, "schema_version must be an integer.")
    if version != 1:
        return Result(State.CORRUPTED, f"Unsupported schema_version: {version}.")

    if "entries" not in document:
        return Result(State.UNKNOWN, "Required entries collection is missing.")

    entries = document["entries"]

    if not isinstance(entries, list):
        return Result(State.CORRUPTED, "Entries must be a JSON array.")
    if not entries:
        return Result(State.UNKNOWN, "Chain contains no entries.")

    previous_hash = GENESIS_HASH

    for expected_sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            return Result(State.CORRUPTED, f"Entry {expected_sequence} is not an object.")

        required = {"sequence", "payload", "previous_hash", "entry_hash"}
        missing = required - entry.keys()
        if missing:
            return Result(
                State.UNKNOWN,
                f"Entry {expected_sequence} missing fields: {', '.join(sorted(missing))}.",
            )

        sequence = entry["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return Result(State.CORRUPTED, f"Entry {expected_sequence} has invalid sequence type.")

        if sequence > expected_sequence:
            return Result(
                State.UNKNOWN,
                f"Missing chain entry at position {expected_sequence}.",
            )
        if sequence != expected_sequence:
            return Result(State.MISMATCH, f"Sequence mismatch at entry {expected_sequence}.")

        payload = entry["payload"]
        if not isinstance(payload, dict):
            return Result(State.CORRUPTED, f"Entry {expected_sequence} payload is not an object.")

        claimed_previous = entry["previous_hash"]
        claimed_hash = entry["entry_hash"]

        for label, value in (
            ("previous_hash", claimed_previous),
            ("entry_hash", claimed_hash),
        ):
            if not isinstance(value, str):
                return Result(State.CORRUPTED, f"{label} must be a string.")

            upper = value.strip().upper()
            if "PLACEHOLDER" in upper or upper in {"", "TODO", "TBD"}:
                return Result(State.CORRUPTED, f"{label} contains a placeholder.")

            if len(value) != 64 or any(
                char not in "0123456789abcdefABCDEF" for char in value
            ):
                return Result(State.CORRUPTED, f"{label} is not a valid SHA-256.")

        if claimed_previous.lower() != previous_hash:
            return Result(
                State.MISMATCH,
                f"Entry {expected_sequence} previous_hash does not link to prior entry.",
            )

        calculated = calculate_entry_hash(
            sequence, payload, claimed_previous.lower()
        )
        if claimed_hash.lower() != calculated:
            return Result(
                State.MISMATCH,
                f"Entry {expected_sequence} hash does not match its contents.",
            )

        previous_hash = calculated

    if expected_head is not None and previous_hash != expected_head:
        return Result(
            State.MISMATCH,
            "Computed chain head does not match the trusted expected_head.",
            previous_hash,
        )

    return Result(
        State.VALID,
        f"Hash chain internally consistent ({len(entries)} entries). "
        "Source authenticity, claim truth, runtime behavior, and production readiness "
        "are not established.",
        previous_hash,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify a G23 SHA-256 hash chain.")
    parser.add_argument("path", help="JSON chain file")
    parser.add_argument(
        "--expected-head",
        help="Trusted SHA-256 hash of the expected final chain entry.",
    )
    args = parser.parse_args(argv)

    result = verify_hash_chain(
        args.path,
        expected_head=args.expected_head,
    )
    print(json.dumps({
        "state": result.state.value,
        "explanation": result.explanation,
        "observed_sha256": result.observed_sha256,
    }, ensure_ascii=False, indent=2))

    return 0 if result.state == State.VALID else 1


if __name__ == "__main__":
    raise SystemExit(main())
