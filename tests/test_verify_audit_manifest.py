import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_audit_manifest.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_case(tmp_path, *, source_hash=None, recovery_flag=True):
    repo = tmp_path / "repo"
    manifest_dir = repo / "audit"
    source_dir = repo / "data"
    manifest_dir.mkdir(parents=True)
    source_dir.mkdir()

    source_bytes = b'{"state":"VALID"}\n'
    (source_dir / "source.json").write_bytes(source_bytes)
    (source_dir / "recovered.json").write_bytes(source_bytes)

    items = []
    for path in (
        "data/source.json",
        "data/recovered.json",
    ):
        data = (repo / path).read_bytes()
        items.append({
            "path": path,
            "sha256": digest(data),
            "size_bytes": len(data),
        })

    manifest = {
        "schema_version": 1,
        "source_path": "data/source.json",
        "source_sha256": source_hash or digest(source_bytes),
        "recovery_copy_matches_source": recovery_flag,
        "items": items,
    }
    manifest_bytes = (
        json.dumps(manifest, separators=(",", ":")) + "\n"
    ).encode()
    (manifest_dir / "manifest.json").write_bytes(manifest_bytes)
    (manifest_dir / "manifest.sha256").write_text(
        digest(manifest_bytes) + "  manifest.json\n",
        encoding="utf-8",
    )
    return repo, manifest_dir


def run_verifier(repo, manifest_dir, report_dir):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(repo),
            str(manifest_dir.relative_to(repo)),
            str(report_dir.relative_to(repo)),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_valid_manifest_passes(tmp_path):
    repo, manifest_dir = make_case(tmp_path)
    result = run_verifier(repo, manifest_dir, repo / "reports" / "run1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT=PASS" in result.stdout


def test_wrong_source_sha256_fails(tmp_path):
    repo, manifest_dir = make_case(
        tmp_path, source_hash="0" * 64
    )
    result = run_verifier(repo, manifest_dir, repo / "reports" / "run2")
    assert result.returncode == 1
    assert "source_sha256: FAIL" in result.stdout


def test_wrong_recovery_boolean_fails(tmp_path):
    repo, manifest_dir = make_case(tmp_path, recovery_flag=False)
    result = run_verifier(repo, manifest_dir, repo / "reports" / "run3")
    assert result.returncode == 1
    assert "recovery_metadata: FAIL" in result.stdout


def test_duplicate_json_key_fails(tmp_path):
    repo, manifest_dir = make_case(tmp_path)
    manifest_path = manifest_dir / "manifest.json"
    malformed = (
        b'{"schema_version":1,"schema_version":1,'
        b'"source_path":"data/source.json","source_sha256":"'
        + b"0" * 64
        + b'","recovery_copy_matches_source":true,"items":[]}\n'
    )
    manifest_path.write_bytes(malformed)
    (manifest_dir / "manifest.sha256").write_text(
        digest(malformed) + "  manifest.json\n",
        encoding="utf-8",
    )
    result = run_verifier(repo, manifest_dir, repo / "reports" / "run4")
    assert result.returncode == 1
    assert "duplicate JSON key" in result.stdout


def test_wrong_item_size_type_fails(tmp_path):
    repo, manifest_dir = make_case(tmp_path)
    manifest_path = manifest_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["size_bytes"] = True
    data = (json.dumps(manifest, separators=(",", ":")) + "\n").encode()
    manifest_path.write_bytes(data)
    (manifest_dir / "manifest.sha256").write_text(
        digest(data) + "  manifest.json\n",
        encoding="utf-8",
    )
    result = run_verifier(repo, manifest_dir, repo / "reports" / "run5")
    assert result.returncode == 1
    assert "size_format: FAIL" in result.stdout
