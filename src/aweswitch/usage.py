"""Codex official OAuth quota reader for aweswitch.

Standard-library-only. No speculative GLM/Doubao code paths.
Provides the public API expected by the future ``aweswitch usage`` CLI.
"""

from __future__ import annotations

import json
import pathlib
import socket
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional


class UsageError(Exception):
    """Raised when quota retrieval or credential loading fails.

    Messages are user-actionable and never include credentials.
    """


def load_codex_credentials(
    runtime_path: pathlib.Path,
    fallback_blob: object,
) -> dict:
    """Load Codex credentials from a runtime ``auth.json`` or a fallback mapping.

    Preference order:
    1. ``runtime_path`` when it exists as a regular file.
    2. ``fallback_blob`` (opaque account credential mapping).

    Validates that ``tokens.access_token`` is a non-empty string.
    Returns a minimal safe mapping containing only the access token and an
    optional ``account_id``. Never writes files.
    """
    if runtime_path.exists() and runtime_path.is_file():
        try:
            raw: Any = json.loads(runtime_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise UsageError("Failed to read credentials file.") from exc
    else:
        raw = fallback_blob

    if not isinstance(raw, dict):
        raise UsageError("Credentials must be a JSON object.")

    tokens = raw.get("tokens")
    if not isinstance(tokens, dict):
        raise UsageError("Missing 'tokens' in credentials.")

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise UsageError("Missing or empty 'tokens.access_token' in credentials.")

    result: Dict[str, str] = {"access_token": access_token.strip()}

    account_id = raw.get("account_id") or raw.get("ChatGPT-Account-Id")
    if account_id and isinstance(account_id, str) and account_id.strip():
        result["account_id"] = account_id.strip()

    return result


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_WINDOW_FIELDS = (
    "used_percentage",
    "reset_unix_timestamp",
    "window_minutes",
)

_TOKEN_PROFILE_FIELDS = (
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
    "context_window",
)


def _normalize_usage_response(data: Any) -> dict:
    """Produce a stable normalized mapping from the raw usage payload.

    Raw upstream JSON is never returned directly. Fields are treated as
    optional and unknown keys are silently discarded.
    """
    if not isinstance(data, dict):
        return {}

    result: Dict[str, Any] = {}

    # Plan string, if present.
    if "plan" in data and isinstance(data["plan"], str):
        result["plan"] = data["plan"]

    # Quota windows live under ``quota_windows`` with slots
    # ``primary``, ``secondary``, and ``additional``.
    quota_windows = data.get("quota_windows")
    if isinstance(quota_windows, dict):
        windows: Dict[str, dict] = {}
        for slot in ("primary", "secondary", "additional"):
            raw_win = quota_windows.get(slot)
            if not isinstance(raw_win, dict):
                continue
            normalized: Dict[str, Any] = {}
            used_pct = raw_win.get("used_percentage")
            if isinstance(used_pct, (int, float)):
                normalized["used_percentage"] = used_pct
            reset_at = raw_win.get("reset_at") or raw_win.get("reset_unix_timestamp")
            if isinstance(reset_at, (int, float)):
                normalized["reset_unix_timestamp"] = int(reset_at)
            win_min = raw_win.get("window_minutes")
            if isinstance(win_min, (int, float)):
                normalized["window_minutes"] = int(win_min)
            if normalized:
                windows[slot] = normalized
        if windows:
            result["windows"] = windows

    # Credits (scalar or nested) — pass through as-is when present.
    if "credits" in data:
        result["credits"] = data["credits"]

    # Token profile stats, if provided.
    token_profile = data.get("token_profile")
    if isinstance(token_profile, dict):
        stats: Dict[str, Any] = {}
        for key in _TOKEN_PROFILE_FIELDS:
            if key in token_profile:
                stats[key] = token_profile[key]
        if stats:
            result["token_profile"] = stats

    return result


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request_usage_endpoint(
    url: str,
    headers: Dict[str, str],
    timeout: int = 10,
) -> dict:
    """Issue a GET request and return the parsed JSON body.

    Raises ``UsageError`` on any HTTP, network, timeout, or JSON error.
    The error message never contains credentials.
    """
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        raise UsageError(
            "HTTP error {} fetching quota data.".format(exc.code)
        ) from exc
    except urllib.error.URLError as exc:
        raise UsageError(
            "Network error fetching quota data: {}.".format(exc.reason)
        ) from exc
    except socket.timeout:
        raise UsageError("Request timed out fetching quota data.") from None
    except json.JSONDecodeError:
        raise UsageError("Invalid JSON response from quota endpoint.") from None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_codex_usage(
    credentials: dict,
    get_json: Optional[Callable[[str, dict], dict]] = None,
) -> dict:
    """Fetch Codex quota usage from the official backend.

    Calls ``/backend-api/wham/usage`` and, best-effort,
    ``/backend-api/wham/profiles/me``.
    The profile call must not make a successful quota result fail.
    HTTP, network, timeout, and invalid-JSON errors become ``UsageError``
    without token leaks.

    Returns a normalized stable mapping with optional keys:
    ``plan``, ``windows``, ``credits``, ``token_profile``.
    """
    if not credentials.get("access_token"):
        raise UsageError("Missing 'access_token' in credentials.")

    headers = {
        "Authorization": "Bearer {}".format(credentials["access_token"]),
        "User-Agent": "codex-cli",
    }
    account_id = credentials.get("account_id")
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    usage_url = "https://chatgpt.com/backend-api/wham/usage"
    profile_url = "https://chatgpt.com/backend-api/wham/profiles/me"

    def _request(url: str) -> dict:
        if get_json is None:
            return _request_usage_endpoint(url, headers, timeout=10)
        return get_json(url, credentials)

    # Primary usage endpoint — propagates errors so callers see them.
    usage_raw = _request(usage_url)
    if not isinstance(usage_raw, dict):
        usage_raw = {}
    result = _normalize_usage_response(usage_raw)

    # Best-effort profile fetch; failure must not undo a successful result.
    try:
        _request(profile_url)
    except UsageError:
        pass

    return result
