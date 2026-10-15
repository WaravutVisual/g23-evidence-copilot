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
