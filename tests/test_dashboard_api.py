import hashlib
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import dashboard


class DashboardAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            dashboard.Handler,
        )
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.server_thread.start()
        cls.base_url = (
            f"http://127.0.0.1:{cls.server.server_address[1]}"
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=3)

    def post_verify(self, payload):
        request = Request(
            self.base_url + "/api/verify",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as error:
            try:
                body = error.read().decode(
                    "utf-8", errors="replace"
                )
                return error.code, body
            finally:
                error.close()

    def test_valid_artifact_returns_valid(self):
        path = dashboard.ROOT / "app" / "verifier.py"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()

        status, body = self.post_verify({
            "path": "app/verifier.py",
            "sha256": digest,
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "VALID")
        self.assertEqual(body["observed_sha256"], digest)
        self.assertIn("does not establish", body["scope_limit"])

    def test_mismatched_digest_returns_mismatch(self):
        status, body = self.post_verify({
            "path": "app/verifier.py",
            "sha256": "0" * 64,
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "MISMATCH")

    def test_missing_reference_returns_unknown(self):
        status, body = self.post_verify({
            "path": "app/verifier.py",
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "UNKNOWN")

    def test_path_traversal_is_rejected(self):
        status, body = self.post_verify({
            "path": "../outside.txt",
            "sha256": "0" * 64,
        })

        self.assertEqual(status, 403)
        self.assertIn("Artifact path must stay inside project", body)

    def test_missing_artifact_returns_unknown(self):
        status, body = self.post_verify({
            "path": "app/__g23_missing_test_artifact__.bin",
            "sha256": "0" * 64,
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
