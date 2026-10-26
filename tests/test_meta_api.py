"""Mock-only tests for the Meta API client. No network calls or API credits."""

import io
import json
import os
import unittest
from unittest.mock import patch

from urllib.error import HTTPError, URLError

from app.meta_api import (
    API_URL,
    MetaAPIError,
    explain_verification,
)


def fake_response(payload, status=200):
    response = io.BytesIO(json.dumps(payload).encode("utf-8"))
    response.status = status
    return response


class MetaAPITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MODEL_API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch("app.meta_api.urlopen")
    def test_valid_response_returns_text(self, mocked):
        mocked.return_value = fake_response({
            "choices": [{"message": {"content": "A cautious explanation."}}]
        })

        result = explain_verification({
            "state": "MISMATCH",
            "explanation": "Hash mismatch",
            "observed_sha256": "a" * 64,
            "extra_untrusted_field": "must not be sent",
        })

        self.assertEqual(result, "A cautious explanation.")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, API_URL)
        self.assertEqual(
            request.get_header("Authorization"), "Bearer test-key"
        )
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("extra_untrusted_field", body["messages"][1]["content"])
        self.assertEqual(mocked.call_args.kwargs["timeout"], 15)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_fails_without_network(self):
        with patch("app.meta_api.urlopen") as mocked:
            with self.assertRaisesRegex(MetaAPIError, "not configured"):
                explain_verification({"state": "UNKNOWN"})
            mocked.assert_not_called()

    @patch("app.meta_api.urlopen")
    def test_http_401_is_sanitized(self, mocked):
        mocked.side_effect = HTTPError(
            API_URL, 401, "Unauthorized", {}, io.BytesIO(b"secret response")
        )
        with self.assertRaisesRegex(MetaAPIError, "HTTP error: 401"):
            explain_verification({"state": "UNKNOWN"})

    @patch("app.meta_api.urlopen")
    def test_network_failure_is_sanitized(self, mocked):
        mocked.side_effect = URLError("simulated offline")
        with self.assertRaisesRegex(MetaAPIError, "request failed"):
            explain_verification({"state": "UNKNOWN"})

    @patch("app.meta_api.urlopen")
    def test_malformed_response_is_rejected(self, mocked):
        mocked.return_value = io.BytesIO(b'{"unexpected": true}')
        mocked.return_value.status = 200
        with self.assertRaisesRegex(MetaAPIError, "unexpected format"):
            explain_verification({"state": "UNKNOWN"})

    @patch("app.meta_api.urlopen")
    def test_empty_text_is_rejected(self, mocked):
        mocked.return_value = fake_response({
            "choices": [{"message": {"content": "   "}}]
        })
        with self.assertRaisesRegex(MetaAPIError, "no usable text"):
            explain_verification({"state": "UNKNOWN"})

    def test_invalid_context_is_rejected(self):
        with self.assertRaisesRegex(MetaAPIError, "dictionary"):
            explain_verification("not a dictionary")


if __name__ == "__main__":
    unittest.main()
