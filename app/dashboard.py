"""Local G23 dashboard. Polling is not a production monitoring service."""
import json
import os
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.verifier import verify_artifact

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("G23_DASHBOARD_PORT", "8765"))

HTML = r"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>G23 Evidence Copilot</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif}
body{margin:0;background:#0b1020;color:#e7edf7}
main{max-width:900px;margin:auto;padding:24px}
h1{margin-bottom:4px} .muted{color:#9aa9c0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:20px}
.card{background:#141d31;border:1px solid #293650;border-radius:14px;padding:18px;overflow-wrap:anywhere}
.label{font-size:13px;color:#9aa9c0;margin-bottom:10px}
.value{font-size:20px;font-weight:700}
.good{color:#62e6a7}.warn{color:#ffd166}.bad{color:#ff8585}
code{font-size:13px} footer{margin-top:20px;font-size:13px;color:#9aa9c0}
button{background:#253653;color:white;border:1px solid #526681;padding:9px 13px;border-radius:8px}
input{box-sizing:border-box;width:100%;padding:10px;border-radius:8px;
border:1px solid #526681;background:#0b1020;color:#e7edf7}
label{font-size:13px;color:#9aa9c0}

</style>
</head>
<body><main>
<h1>G23 Evidence Copilot</h1>
<div class="muted">Local status dashboard · refresh every 5 seconds</div>
<div class="grid">
<section class="card"><div class="label">LATEST COMMIT</div><div id="commit" class="value">LOADING</div><p id="subject" class="muted">Waiting for status…</p></section>
<section class="card"><div class="label">GIT STATUS</div><div id="git" class="value">NOT_RUN</div><p id="branch" class="muted">Branch not checked</p><p id="files" class="muted"></p></section>
<section class="card"><div class="label">EVIDENCE VERIFICATION</div><div id="evidence" class="value">NOT_RUN</div><p id="explanation" class="muted">No verification result yet</p><p id="digest" class="muted"></p></section>
<section class="card"><div class="label">LAST CHECK (UTC)</div><div id="checked" class="value">NOT_RUN</div><p id="error" class="muted"></p></section>
</div>

<p><button id="refresh">Check now</button></p>

<section class="card">
<h2>Verify an Artifact</h2>
<p class="muted">ตรวจไฟล์ภายในโฟลเดอร์โปรเจกต์นี้เท่านั้น</p>
<form id="verifyForm">
<label for="artifactPath">Artifact path (relative to project)</label>
<p><input id="artifactPath" required placeholder="examples/sample.bin"></p>
<label for="referenceSha256">Reference SHA-256</label>
<p><input id="referenceSha256" placeholder="64 hexadecimal characters"></p>
<button type="submit">Verify artifact</button>
</form>
<p id="verifyState" class="value">NOT_RUN</p>
<p id="verifyExplanation" class="muted">ยังไม่ได้ตรวจ Artifact</p>
<p id="verifyDigest" class="muted"></p>
</section>

<footer>VALID proves only the defined check passed. It does not prove runtime correctness or production readiness. A missing artifact/reference remains UNKNOWN.</footer>
</main>
<script>
const el = id => document.getElementById(id);
function setText(id, value) { el(id).textContent = value ?? ""; }
function setState(id, value) {
  setText(id, value);
  el(id).className = "value " +
    (value === "VALID" || value === "CLEAN" ? "good" :
     value === "UNKNOWN" || value === "NOT_RUN" || value === "DIRTY" ? "warn" :
     value === "MISMATCH" || value === "CORRUPTED" || value === "ERROR" ? "bad" : "");
}
async function refreshStatus() {
  try {
    const response = await fetch("/api/status", {cache:"no-store"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    const s = await response.json();
    setText("commit", s.git.commit || "UNKNOWN");
    setText("subject", s.git.subject || "Commit message unavailable");
    setState("git", s.git.state);
    setText("branch", "Branch: " + (s.git.branch || "UNKNOWN"));
    setText("files", s.git.changed_files.length
      ? s.git.changed_files.join(", ") : "No changed paths reported");
    setState("evidence", s.evidence.state);
    setText("explanation", s.evidence.explanation);
    setText("digest", s.evidence.observed_sha256
      ? "Observed SHA-256: " + s.evidence.observed_sha256 : "");
    setText("checked", s.last_checked_utc);
    setText("error", s.errors.length ? s.errors.join(" | ") : "");
  } catch (e) {
    setState("git", "ERROR");
    setText("error", "Status request failed: " + e.message);
  }
}
el("refresh").addEventListener("click", refreshStatus);
el("verifyForm").addEventListener("submit", async event => {
  event.preventDefault();
  setText("verifyState", "CHECKING");
  setText("verifyExplanation", "กำลังตรวจไฟล์...");
  setText("verifyDigest", "");
  try {
    const response = await fetch("/api/verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        path: el("artifactPath").value.trim(),
        sha256: el("referenceSha256").value.trim()
      })
    });
    const result = await response.json();
    setState("verifyState", result.state || "ERROR");
    setText("verifyExplanation", result.explanation || result.error || "No explanation");
    setText("verifyDigest", result.observed_sha256
      ? "Observed SHA-256: " + result.observed_sha256 : "");
  } catch (error) {
    setState("verifyState", "ERROR");
    setText("verifyExplanation", "Verification request failed: " + error.message);
  }
});

refreshStatus();
setInterval(refreshStatus, 5000);
</script></body></html>"""


def git_value(*args):
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            check=True, capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def build_status():
    errors = []
    commit = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    subject = git_value("log", "-1", "--format=%s")
    porcelain = git_value("status", "--porcelain")

    if commit is None or branch is None or porcelain is None:
        git_state = "UNKNOWN"
        errors.append("Git status could not be fully checked.")
        changed_files = []
    else:
        changed_files = [line[3:] for line in porcelain.splitlines() if line]
        git_state = "DIRTY" if changed_files else "CLEAN"

    artifact = os.environ.get("G23_ARTIFACT")
    expected = os.environ.get("G23_SHA256")
    if not artifact or not expected:
        evidence = {
            "state": "UNKNOWN",
            "explanation": (
                "Artifact path or reference SHA-256 is not configured; "
                "evidence has not been verified."
            ),
            "observed_sha256": None,
        }
    else:
        path = Path(artifact)
        if not path.is_absolute():
            path = ROOT / path
        result = verify_artifact(str(path), expected)
        evidence = {
            "state": result.state.value,
            "explanation": result.explanation,
            "observed_sha256": result.observed_sha256,
        }

    return {
        "service": "G23 Evidence Copilot Local Dashboard",
        "last_checked_utc": datetime.now(timezone.utc).isoformat(),
        "refresh_interval_seconds": 5,
        "git": {
            "commit": commit,
            "branch": branch,
            "subject": subject,
            "state": git_state,
            "changed_files": changed_files,
        },
        "evidence": evidence,
        "errors": errors,
        "claim_limits": [
            "A hash match proves byte equality against the supplied reference only.",
            "Runtime correctness is not established.",
            "Production readiness is not established.",
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/":
            body = HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif route == "/api/status":
            body = json.dumps(
                build_status(), ensure_ascii=False
            ).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


    def do_POST(self):
        route = urlparse(self.path).path
        if route != "/api/verify":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16384:
                self.send_error(400, "Invalid request size")
                return

            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                self.send_error(400, "JSON object required")
                return

            raw_path = payload.get("path")
            expected = payload.get("sha256")

            if not isinstance(raw_path, str) or not raw_path.strip():
                self.send_error(400, "Artifact path is required")
                return
            if expected is not None and not isinstance(expected, str):
                self.send_error(400, "SHA-256 must be a string")
                return

            candidate = (ROOT / raw_path).resolve()
            if not candidate.is_relative_to(ROOT.resolve()):
                self.send_error(403, "Artifact path must stay inside project")
                return

            result = verify_artifact(
                str(candidate),
                expected.strip() if expected and expected.strip() else None,
            )
            body = json.dumps({
                "state": result.state.value,
                "explanation": result.explanation,
                "observed_sha256": result.observed_sha256,
                "scope_limit": (
                    "Hash equality alone does not establish source authenticity, "
                    "runtime correctness, or production readiness."
                ),
            }, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_error(400, "Invalid verification request")

    def log_message(self, fmt, *args):
        print("[dashboard] " + (fmt % args))


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"G23 Dashboard: http://{HOST}:{PORT}")
    print("Polling interval: 5 seconds. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
