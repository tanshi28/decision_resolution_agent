"""Small standard-library HTTP client for Gemini's generateContent API."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


class GeminiAPIError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key=None, model=None, timeout=30):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.timeout = timeout
        if not self.api_key:
            raise GeminiAPIError(
                "GEMINI_API_KEY is not set. Add your Google AI Studio API key to the environment."
            )

    def generate(self, contents, function_declarations, system_instruction):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + quote(self.model, safe="")
            + ":generateContent"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "tools": [{"functionDeclarations": function_declarations}],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"temperature": 0.2},
        }
        for attempt in range(MAX_ATTEMPTS):
            request = Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS - 1:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        delay = min(max(float(retry_after), 0), 10) if retry_after else 2**attempt
                    except ValueError:
                        delay = 2**attempt
                    exc.close()
                    time.sleep(delay)
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise GeminiAPIError(
                    "Gemini API returned HTTP {}: {}".format(exc.code, detail[:1000])
                ) from exc
            except URLError as exc:
                raise GeminiAPIError("Could not reach the Gemini API: {}".format(exc.reason)) from exc
            except TimeoutError as exc:
                raise GeminiAPIError("The Gemini API request timed out.") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GeminiAPIError("Gemini API returned an invalid JSON response.") from exc
