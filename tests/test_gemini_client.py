import io
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from decision_resolution_agent.gemini_client import GeminiAPIError, GeminiClient


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.client = GeminiClient(api_key="test-key")

    @patch("decision_resolution_agent.gemini_client.time.sleep")
    @patch("decision_resolution_agent.gemini_client.urlopen")
    def test_retries_temporary_service_unavailable(self, urlopen, sleep):
        unavailable = HTTPError(
            "https://example.test",
            503,
            "UNAVAILABLE",
            {},
            io.BytesIO(b'{"error":"busy"}'),
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"candidates":[]}'
        urlopen.side_effect = [unavailable, response]

        result = self.client.generate([], [], "test")

        self.assertEqual(result, {"candidates": []})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("decision_resolution_agent.gemini_client.time.sleep")
    @patch("decision_resolution_agent.gemini_client.urlopen")
    def test_does_not_retry_non_transient_http_error(self, urlopen, sleep):
        unauthorized = HTTPError(
            "https://example.test",
            401,
            "UNAUTHORIZED",
            {},
            io.BytesIO(b'{"error":"bad key"}'),
        )
        urlopen.side_effect = unauthorized

        with self.assertRaisesRegex(GeminiAPIError, "HTTP 401"):
            self.client.generate([], [], "test")

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
