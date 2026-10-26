import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(data):
    return json.loads(
        data,
        object_pairs_hook=reject_duplicate_keys,
    )


def safe_repo_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("path must be a non-empty string")

    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("path must be repository-relative")

    resolved = (root / rel).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes repository root")
    return resolved


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python scripts/verify_audit_manifest.py "
            "<repo-root> <manifest-dir> <report-dir>"
        )
        return 2

    root = Path(sys.argv[1]).resolve()

    try:
        manifest_dir = safe_repo_path(root, sys.argv[2])
        report_dir = safe_repo_path(root, sys.argv[3])
    except (ValueError, OSError) as exc:
        print(f"FAIL: invalid directory path: {exc}")
        return 2

    manifest_path = manifest_dir / "manifest.json"
    hash_path = manifest_dir / "manifest.sha256"
    checks = []
    errors = []

    def record(name, ok, detail=""):
        checks.append({
            "check": name,
            "result": "PASS" if ok else "FAIL",
            "detail": detail,
        })
        if not ok:
            errors.append(name)
        print(
            f"{name}: {'PASS' if ok else 'FAIL'}"
            + (f" ({detail})" if detail else "")
        )

    try:
        manifest_bytes = manifest_path.read_bytes()
        hash_fields = hash_path.read_text(
            encoding="utf-8"
        ).split()

        hash_format_ok = (
            bool(hash_fields)
            and HASH_RE.fullmatch(hash_fields[0]) is not None
        )
        actual_manifest_hash = sha256(manifest_bytes)
        manifest_hash_ok = (
            hash_format_ok
            and actual_manifest_hash == hash_fields[0].lower()
        )
        record(
            "manifest_sha256",
            manifest_hash_ok,
            f"actual={actual_manifest_hash}",
        )

        manifest = load_json_bytes(manifest_bytes)
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be a JSON object")

        record(
            "schema_version",
            type(manifest.get("schema_version")) is int
            and manifest["schema_version"] == 1,
            f"value={manifest.get('schema_version')!r}",
        )

        items = manifest.get("items")
        record(
            "items_type",
            isinstance(items, list),
            f"type={type(items).__name__}",
        )
        if not isinstance(items, list):
            items = []

        seen_paths = set()
        valid_items = []

        for index, item in enumerate(items):
            prefix = f"item[{index}]"

            if not isinstance(item, dict):
                record(prefix + ":object", False, "item must be an object")
                continue

            rel = item.get("path")
            try:
                path = safe_repo_path(root, rel)
            except (ValueError, OSError) as exc:
                record(prefix + ":path", False, str(exc))
                continue

            normalized = path.as_posix()
            if normalized in seen_paths:
                record(prefix + ":duplicate_path", False, normalized)
                continue
            seen_paths.add(normalized)

            digest = item.get("sha256")
            digest_ok = (
                isinstance(digest, str)
                and HASH_RE.fullmatch(digest) is not None
            )
            record(
                prefix + ":sha256_format",
                digest_ok,
                f"path={rel}",
            )

            size = item.get("size_bytes")
            size_ok = type(size) is int and size >= 0
            record(
                prefix + ":size_format",
                size_ok,
                f"path={rel}",
            )

            expected_state = item.get("expected_state")
            state_ok = (
                "expected_state" not in item
                or isinstance(expected_state, str)
            )
            record(
                prefix + ":expected_state_format",
                state_ok,
                f"path={rel}",
            )

            valid_items.append((item, path, digest_ok, size_ok))

            if not path.is_file():
                record(f"file:{rel}", False, "missing file")
                continue

            data = path.read_bytes()

            record(
                f"sha256:{rel}",
                digest_ok and sha256(data) == digest.lower(),
                "hash matches manifest" if digest_ok else "invalid hash format",
            )
            record(
                f"size:{rel}",
                size_ok and len(data) == size,
                f"actual={len(data)} bytes",
            )

            if "expected_state" in item:
                try:
                    result = load_json_bytes(data)
                    actual_state = (
                        result.get("state")
                        if isinstance(result, dict)
                        else None
                    )
                    record(
                        f"state:{rel}",
                        state_ok and actual_state == expected_state,
                        f"expected={expected_state!r} "
                        f"actual={actual_state!r}",
                    )
                except (ValueError, UnicodeDecodeError) as exc:
                    record(f"state:{rel}", False, str(exc))

        source_value = manifest.get("source_path")
        source = None
        try:
            source = safe_repo_path(root, source_value)
        except (ValueError, OSError) as exc:
            record("source_path", False, str(exc))

        source_exists = source is not None and source.is_file()
        if not source_exists:
            record("source_file", False, "source missing or invalid")
        else:
            source_bytes = source.read_bytes()
            source_hash = sha256(source_bytes)
            declared_hash = manifest.get("source_sha256")
            source_hash_format_ok = (
                isinstance(declared_hash, str)
                and HASH_RE.fullmatch(declared_hash) is not None
            )
            record(
                "source_sha256",
                source_hash_format_ok
                and source_hash == declared_hash.lower(),
                f"actual={source_hash}",
            )

        recovered_items = [
            item for item in items
            if isinstance(item, dict)
            and isinstance(item.get("path"), str)
            and Path(item["path"]).name == "recovered.json"
        ]

        recovered = None
        if len(recovered_items) != 1:
            record(
                "source_recovery_match",
                False,
                "expected exactly one recovered.json entry",
            )
        else:
            try:
                recovered = safe_repo_path(
                    root, recovered_items[0]["path"]
                )
            except (ValueError, OSError):
                recovered = None

            if (
                source_exists
                and recovered is not None
                and recovered.is_file()
            ):
                actual_match = (
                    source.read_bytes() == recovered.read_bytes()
                )
                record(
                    "source_recovery_match",
                    actual_match,
                    "byte-for-byte comparison",
                )
                declared_match = manifest.get(
                    "recovery_copy_matches_source"
                )
                record(
                    "recovery_metadata",
                    type(declared_match) is bool
                    and declared_match == actual_match,
                    f"declared={declared_match!r} actual={actual_match}",
                )
            else:
                record(
                    "source_recovery_match",
                    False,
                    "source or recovery file missing",
                )
                record(
                    "recovery_metadata",
                    False,
                    "cannot verify recovery metadata",
                )

    except Exception as exc:
        record(
            "manifest_load",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    exit_code = 1 if errors else 0
    report = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path.relative_to(root)),
        "checks": checks,
        "failure_count": len(errors),
        "result": "FAIL" if exit_code else "PASS",
        "exit_code": exit_code,
    }

    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "verification-result.json"
        if report_path.exists():
            print("FAIL: report already exists; refusing to overwrite")
            return 2
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"FAIL: cannot write report: {exc}")
        return 2

    print(f"RESULT={report['result']}")
    print(f"EXIT_CODE={exit_code}")
    print(f"REPORT={report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
