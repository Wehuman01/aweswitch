"""Tests for aweswitch.usage — standard-library-only Codex OAuth quota reader."""

from __future__ import annotations

import json
import pathlib
import socket
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from aweswitch.usage import UsageError, fetch_codex_usage, load_codex_credentials


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeHTTPResponse:
    """Minimal stand-in for ``http.client.HTTPResponse`` used in urlopen."""

    def __init__(self, data, status=200):
        self._body = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class _RawBodyHTTPResponse:
    """HTTPResponse shim that returns raw bytes without JSON encoding."""

    def __init__(self, body_bytes, status=200):
        self._body = body_bytes
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _fake_response(data, status=200):
    return _FakeHTTPResponse(data, status=status)


def _raw_response(body_bytes, status=200):
    return _RawBodyHTTPResponse(body_bytes, status=status)


# ---------------------------------------------------------------------------
# load_codex_credentials tests
# ---------------------------------------------------------------------------


class LoadCodexCredentialsTests(unittest.TestCase):
    """Tests for load_codex_credentials."""

    def test_fallback_used_when_runtime_missing(self):
        fallback = {"tokens": {"access_token": "tok-123"}, "account_id": "acc-1"}
        creds = load_codex_credentials(pathlib.Path("/nonexistent/auth.json"), fallback)
        self.assertEqual(creds["access_token"], "tok-123")
        self.assertEqual(creds["account_id"], "acc-1")

    def test_runtime_preferred_over_fallback(self):
        runtime_blob = {"tokens": {"access_token": "fresh-tok"}, "account_id": "acc-rt"}
        fallback_blob = {"tokens": {"access_token": "old-tok"}, "account_id": "acc-fb"}

        fake_path = pathlib.Path("/runtime/auth.json")
        with mock.patch.object(
            pathlib.Path, "exists", return_value=True
        ), mock.patch.object(
            pathlib.Path, "is_file", return_value=True
        ), mock.patch.object(
            pathlib.Path,
            "read_text",
            return_value=json.dumps(runtime_blob),
        ):
            creds = load_codex_credentials(fake_path, fallback_blob)

        self.assertEqual(creds["access_token"], "fresh-tok")
        self.assertEqual(creds["account_id"], "acc-rt")

    def test_rejects_non_dict_credentials(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(pathlib.Path("/nonexistent"), [])

    def test_rejects_missing_tokens_key(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(pathlib.Path("/nonexistent"), {})

    def test_rejects_non_dict_tokens(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(pathlib.Path("/nonexistent"), {"tokens": "bad"})

    def test_rejects_missing_access_token_key(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(pathlib.Path("/nonexistent"), {"tokens": {}})

    def test_rejects_empty_access_token(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(
                pathlib.Path("/nonexistent"), {"tokens": {"access_token": ""}}
            )

    def test_rejects_non_string_access_token(self):
        with self.assertRaises(UsageError):
            load_codex_credentials(
                pathlib.Path("/nonexistent"), {"tokens": {"access_token": 42}}
            )

    def test_strips_whitespace_access_token(self):
        creds = load_codex_credentials(
            pathlib.Path("/nonexistent"),
            {"tokens": {"access_token": "  tok  "}},
        )
        self.assertEqual(creds["access_token"], "tok")

    def test_reads_chatgpt_account_id_header_key(self):
        creds = load_codex_credentials(
            pathlib.Path("/nonexistent"),
            {"tokens": {"access_token": "tok"}, "ChatGPT-Account-Id": "acc-2"},
        )
        self.assertEqual(creds["account_id"], "acc-2")

    def test_account_id_key_preferred_over_header_key(self):
        creds = load_codex_credentials(
            pathlib.Path("/nonexistent"),
            {
                "tokens": {"access_token": "tok"},
                "account_id": "acc-a",
                "ChatGPT-Account-Id": "acc-b",
            },
        )
        self.assertEqual(creds["account_id"], "acc-a")

    def test_ignores_non_string_account_id(self):
        creds = load_codex_credentials(
            pathlib.Path("/nonexistent"),
            {"tokens": {"access_token": "tok"}, "account_id": 42},
        )
        self.assertNotIn("account_id", creds)

    def test_invalid_runtime_json_raises(self):
        fake_path = pathlib.Path("/runtime/auth.json")
        with mock.patch.object(pathlib.Path, "exists", return_value=True), \
             mock.patch.object(pathlib.Path, "is_file", return_value=True), \
             mock.patch.object(pathlib.Path, "read_text", return_value="not-json"):
            with self.assertRaises(UsageError):
                load_codex_credentials(fake_path, {"tokens": {"access_token": "x"}})


# ---------------------------------------------------------------------------
# fetch_codex_usage tests
# ---------------------------------------------------------------------------


class FetchCodexUsageTests(unittest.TestCase):
    """Tests for fetch_codex_usage."""

    USAGE_PAYLOAD = {
        "plan": "free",
        "quota_windows": {
            "primary": {
                "used_percentage": 42.5,
                "reset_at": 1700000000,
                "window_minutes": 60,
            },
            "secondary": {
                "used_percentage": 10,
                "reset_at": 1700003600,
                "window_minutes": 60,
            },
            "additional": {
                "used_percentage": 0,
                "reset_at": 1700007200,
                "window_minutes": 30,
            },
        },
        "credits": 100,
        "token_profile": {
            "total_tokens": 5000,
            "prompt_tokens": 3000,
            "completion_tokens": 2000,
        },
    }

    def _side_effect_for(self, *responses):
        """Build a side-effect callable that yields responses in order.

        Each item is either a ``_FakeHTTPResponse`` to return directly or a
        callable that will be invoked with ``(req, timeout=None)`` (e.g. a
        helper that raises).
        """
        it = iter(responses)

        def _se(req, timeout=None):
            val = next(it)
            # Call callables that are not our response shim.
            if callable(val) and not isinstance(val, _FakeHTTPResponse):
                return val(req, timeout=timeout)
            return val

        return _se

    # --- happy path ---

    def test_happy_path_normalizes_all_fields(self):
        creds = {"access_token": "tok", "account_id": "acc-1"}
        usage_resp = _fake_response(self.USAGE_PAYLOAD)
        profile_resp = _fake_response({"plan": "plus"})

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=self._side_effect_for(usage_resp, profile_resp),
        ):
            result = fetch_codex_usage(creds)

        # Usage fields take precedence over profile.
        self.assertEqual(result["plan"], "free")
        self.assertEqual(result["credits"], 100)
        self.assertEqual(result["windows"]["primary"]["used_percentage"], 42.5)
        self.assertEqual(result["windows"]["primary"]["reset_unix_timestamp"], 1700000000)
        self.assertEqual(result["windows"]["primary"]["window_minutes"], 60)
        self.assertEqual(result["windows"]["secondary"]["used_percentage"], 10)
        self.assertIn("additional", result["windows"])
        self.assertEqual(result["token_profile"]["total_tokens"], 5000)

    # --- profile-call failure ---

    def test_profile_failure_does_not_break_quota_result(self):
        creds = {"access_token": "tok"}
        usage_resp = _fake_response(self.USAGE_PAYLOAD)

        def _raise_profile(req, timeout=None):
            raise urllib.error.HTTPError(
                "https://chatgpt.com/backend-api/wham/profiles/me",
                403, "Forbidden", {}, None
            )

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=self._side_effect_for(usage_resp, _raise_profile),
        ):
            result = fetch_codex_usage(creds)

        # Quota data is still present.
        self.assertEqual(result["plan"], "free")
        self.assertEqual(result["credits"], 100)
        self.assertEqual(result["windows"]["primary"]["used_percentage"], 42.5)
        self.assertEqual(result["token_profile"]["total_tokens"], 5000)

    # --- missing credential ---

    def test_missing_access_token_raises(self):
        with self.assertRaises(UsageError):
            fetch_codex_usage({})

    def test_none_access_token_raises(self):
        with self.assertRaises(UsageError):
            fetch_codex_usage({"access_token": None})

    def test_empty_access_token_raises(self):
        with self.assertRaises(UsageError):
            fetch_codex_usage({"access_token": ""})

    # --- response parsing ---

    def test_windows_primary_only(self):
        creds = {"access_token": "tok"}
        payload = {
            "quota_windows": {
                "primary": {
                    "used_percentage": 0,
                    "reset_at": 1700000000,
                    "window_minutes": 60,
                },
            }
        }
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(result["windows"]["primary"]["used_percentage"], 0)
        self.assertEqual(result["windows"]["primary"]["reset_unix_timestamp"], 1700000000)
        self.assertEqual(result["windows"]["primary"]["window_minutes"], 60)
        self.assertNotIn("secondary", result["windows"])
        self.assertNotIn("additional", result["windows"])

    def test_response_parsing_omits_non_numeric_percentage(self):
        creds = {"access_token": "tok"}
        payload = {
            "quota_windows": {
                "primary": {"used_percentage": "unknown", "unknown_field": "x"}
            },
        }
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        # All values are non-numeric; the entire window is omitted.
        self.assertEqual(result, {})

    def test_response_parsing_omits_non_numeric_window_minutes(self):
        creds = {"access_token": "tok"}
        payload = {
            "quota_windows": {
                "primary": {"used_percentage": 50, "window_minutes": "unknown"},
            }
        }
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(result["windows"]["primary"]["used_percentage"], 50)
        self.assertNotIn("window_minutes", result["windows"]["primary"])

    def test_response_parsing_accepts_reset_unix_timestamp_key(self):
        creds = {"access_token": "tok"}
        payload = {
            "quota_windows": {
                "primary": {"reset_unix_timestamp": 1234567890},
            }
        }
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(
            result["windows"]["primary"]["reset_unix_timestamp"], 1234567890
        )

    def test_response_parsing_token_profile_partial(self):
        creds = {"access_token": "tok"}
        payload = {
            "quota_windows": {
                "primary": {"used_percentage": 0},
            },
            "token_profile": {"total_tokens": 999},
        }
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(result["token_profile"]["total_tokens"], 999)
        self.assertNotIn("prompt_tokens", result["token_profile"])

    def test_omits_credits_when_absent(self):
        creds = {"access_token": "tok"}
        payload = {"quota_windows": {"primary": {"used_percentage": 0}}}
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ):
            result = fetch_codex_usage(creds)

        self.assertNotIn("credits", result)

    def test_non_dict_usage_response_returns_empty(self):
        creds = {"access_token": "tok"}
        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=_fake_response("unexpected-list"),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(result, {})

    # --- safe HTTP error behavior ---

    def test_http_error_message_has_no_token_leak(self):
        creds = {"access_token": "super-secret-tok"}

        def _raise(req, timeout=None):
            raise urllib.error.HTTPError(
                "https://chatgpt.com/backend-api/wham/usage",
                500, "Internal Server Error", {}, None
            )

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=_raise,
        ):
            with self.assertRaises(UsageError) as cm:
                fetch_codex_usage(creds)

        msg = str(cm.exception)
        self.assertNotIn("super-secret-tok", msg)
        self.assertIn("HTTP error 500", msg)

    def test_network_error_converts_to_usage_error(self):
        creds = {"access_token": "tok"}

        def _raise(req, timeout=None):
            raise urllib.error.URLError("Name or service not known")

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=_raise,
        ):
            with self.assertRaises(UsageError) as cm:
                fetch_codex_usage(creds)

        self.assertIn("Network error", str(cm.exception))

    def test_timeout_converts_to_usage_error(self):
        creds = {"access_token": "tok"}

        def _raise(req, timeout=None):
            raise socket.timeout()

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=_raise,
        ):
            with self.assertRaises(UsageError) as cm:
                fetch_codex_usage(creds)

        self.assertIn("timed out", str(cm.exception))

    def test_invalid_json_converts_to_usage_error(self):
        creds = {"access_token": "tok"}
        bad_resp = _raw_response(b"not-json")

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            return_value=bad_resp,
        ):
            with self.assertRaises(UsageError) as cm:
                fetch_codex_usage(creds)

        self.assertIn("Invalid JSON", str(cm.exception))

    # --- get_json injection ---

    def test_get_json_callback_receives_correct_urls(self):
        creds = {"access_token": "tok", "account_id": "acc-42"}
        calls = []

        def fake_get_json(url, credentials):
            calls.append(url)
            return {"plan": "plus"}

        result = fetch_codex_usage(creds, get_json=fake_get_json)

        self.assertEqual(result["plan"], "plus")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], "https://chatgpt.com/backend-api/wham/usage")
        self.assertEqual(calls[1], "https://chatgpt.com/backend-api/wham/profiles/me")

    def test_get_json_profile_error_does_not_break_result(self):
        creds = {"access_token": "tok"}
        calls = []

        def fake_get_json(url, credentials):
            calls.append(url)
            if url.endswith("/usage"):
                return {"plan": "free"}
            raise UsageError("profile unavailable")

        result = fetch_codex_usage(creds, get_json=fake_get_json)

        self.assertEqual(result["plan"], "free")
        self.assertEqual(len(calls), 2)

    def test_profile_url_failure_uses_only_usage_data(self):
        """Profile 404 must not make the quota result fail."""
        creds = {"access_token": "tok"}
        usage_resp = _fake_response({"plan": "pro", "credits": 500})

        def _raise_profile(req, timeout=None):
            raise urllib.error.HTTPError(
                "https://chatgpt.com/backend-api/wham/profiles/me",
                404, "Not Found", {}, None
            )

        with mock.patch(
            "aweswitch.usage.urllib.request.urlopen",
            side_effect=self._side_effect_for(usage_resp, _raise_profile),
        ):
            result = fetch_codex_usage(creds)

        self.assertEqual(result["plan"], "pro")
        self.assertEqual(result["credits"], 500)


if __name__ == "__main__":
    unittest.main()
