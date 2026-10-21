#!/usr/bin/env python3
"""G23 simulated failure demo; original fixture is never modified."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/hash-chain-demo.json"

def run_case(label, path, expected, head=None):
    cmd = [sys.executable, "-m", "app.hash_chain", str(path)]
    if head is not None:
        cmd += ["--expected-head", head]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    try:
        result = json.loads(proc.stdout)
        state = result.get("state")
    except (ValueError, AttributeError):
        state = None
    expected_exit = 0 if expected == "VALID" else 1
    passed = state == expected and proc.returncode == expected_exit
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: "
          f"expected={expected}, observed={state}, exit={proc.returncode}")
    return passed, (
        f"CASE={label}\nEXPECTED={expected}\nOBSERVED={state}\n"
        f"EXIT_CODE={proc.returncode}\nPASS={passed}\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n"
    )

def main():
    if not FIXTURE.is_file():
        print("STOP: fixture missing", file=sys.stderr)
        return 2

    original_bytes = FIXTURE.read_bytes()
    try:
        doc = json.loads(original_bytes)
        head = doc["entries"][-1]["entry_hash"]
        if not isinstance(head, str) or len(head) != 64:
            raise ValueError("invalid chain head")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"STOP: invalid fixture: {exc}", file=sys.stderr)
        return 2

    results = []
    all_passed = True
    with tempfile.TemporaryDirectory(prefix="g23-demo-", dir=Path.home()) as td:
        td = Path(td)
        work = td / "working.json"
        missing = td / "missing.json"
        malformed = td / "malformed.json"
        work.write_bytes(original_bytes)

        for label, path, expected, trusted_head in [
            ("baseline", work, "VALID", head),
        ]:
            ok, log = run_case(label, path, expected, trusted_head)
            all_passed = all_passed and ok
            results.append(log)

        altered = json.loads(work.read_text(encoding="utf-8"))
        altered["entries"][0]["payload"]["artifact"] = "tampered.txt"
        work.write_text(json.dumps(altered), encoding="utf-8")
        ok, log = run_case("tamper", work, "MISMATCH")
        all_passed = all_passed and ok
        results.append(log)

        work.write_bytes(original_bytes)
        ok, log = run_case("restore", work, "VALID", head)
        all_passed = all_passed and ok
        results.append(log)

        ok, log = run_case("missing-file", missing, "UNKNOWN")
        all_passed = all_passed and ok
        results.append(log)

        malformed.write_text("{ invalid json", encoding="utf-8")
        ok, log = run_case("malformed-json", malformed, "CORRUPTED")
        all_passed = all_passed and ok
        results.append(log)

        restore_match = work.read_bytes() == original_bytes
        fixture_match = FIXTURE.read_bytes() == original_bytes
        print(f"[{'PASS' if restore_match else 'FAIL'}] restore bytes unchanged")
        print(f"[{'PASS' if fixture_match else 'FAIL'}] source fixture unchanged")
        all_passed = all_passed and restore_match and fixture_match
        results.append(f"RESTORE_BYTES_MATCH={restore_match}\n")
        results.append(f"SOURCE_FIXTURE_UNCHANGED={fixture_match}\n")

    print("\n=== SCENARIO LOG ===")
    print("\n".join(results))
    print("FIXTURE_SHA256=" + hashlib.sha256(original_bytes).hexdigest())
    print("OVERALL=" + ("PASS" if all_passed else "FAIL"))
    print("CLAIM_LIMIT=Local demo only; not proof of production readiness.")
    return 0 if all_passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
