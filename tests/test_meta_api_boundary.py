"""Boundary tests for Meta API failures. No real network calls."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.meta_api import API_URL, MetaAPIError, explain_verification


class MetaAPIBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.key_patch = patch.dict(
            "os.environ", {"MODEL_API_KEY": "boundary-test-secret"}
        )
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    def call_client(self):
        return explain_verification({
            "state": "VALID",
            "explanation": "Hash matches.",
            "observed_sha256": "a" * 64,
        })

    def test_http_429_is_sanitized(self):
        with patch("app.meta_api.urlopen") as mocked:
            mocked.side_effect = HTTPError(
                API_URL, 429, "rate limited", {},
                io.BytesIO(b"private response body")
            )
            with self.assertRaises(MetaAPIError) as caught:
                self.call_client()

        self.assertIn("429", str(caught.exception))
        self.assertNotIn("private response body", str(caught.exception))
        self.assertNotIn("boundary-test-secret", str(caught.exception))

    def test_http_500_is_sanitized(self):
        with patch("app.meta_api.urlopen") as mocked:
            mocked.side_effect = HTTPError(
                API_URL, 500, "server error", {},
                io.BytesIO(b"internal server details")
            )
            with self.assertRaises(MetaAPIError) as caught:
                self.call_client()

        self.assertIn("500", str(caught.exception))
        self.assertNotIn("internal server details", str(caught.exception))
        self.assertNotIn("boundary-test-secret", str(caught.exception))

    def test_timeout_is_sanitized(self):
        with patch("app.meta_api.urlopen") as mocked:
            mocked.side_effect = TimeoutError("private timeout detail")
            with self.assertRaises(MetaAPIError) as caught:
                self.call_client()

        self.assertIn("TimeoutError", str(caught.exception))
        self.assertNotIn("private timeout detail", str(caught.exception))
        self.assertNotIn("boundary-test-secret", str(caught.exception))

    def test_invalid_json_body_is_rejected(self):
        response = io.BytesIO(b"{not valid json")
        response.status = 200

        with patch("app.meta_api.urlopen", return_value=response):
            with self.assertRaisesRegex(
                MetaAPIError, "unexpected format"
            ):
                self.call_client()

    def test_oversized_response_is_rejected(self):
        response = io.BytesIO(b"x" * 1_000_001)
        response.status = 200

        with patch("app.meta_api.urlopen", return_value=response):
            with self.assertRaisesRegex(
                MetaAPIError, "exceeded the size limit"
            ):
                self.call_client()


if __name__ == "__main__":
    unittest.main()
