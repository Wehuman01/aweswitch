"""Codex official OAuth quota reader for aweswitch."""

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

    account_id = (
        tokens.get("account_id")
        or raw.get("account_id")
        or raw.get("ChatGPT-Account-Id")
    )
    if account_id and isinstance(account_id, str) and account_id.strip():
        result["account_id"] = account_id.strip()

    return result


_TOKEN_PROFILE_FIELDS = (
    "lifetime_tokens",
    "peak_daily_tokens",
    "longest_running_turn_sec",
    "current_streak_days",
    "longest_streak_days",
    "daily_usage_buckets",
)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_window(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    result = {}
    used = data.get("used_percent", data.get("used_percentage"))
    if _is_number(used):
        result["used_percentage"] = used
    reset_at = data.get("reset_at", data.get("resets_at"))
    if _is_number(reset_at):
        result["reset_unix_timestamp"] = int(reset_at)
    window_seconds = data.get("limit_window_seconds")
    if _is_number(window_seconds):
        result["window_minutes"] = int(window_seconds / 60)
    elif _is_number(data.get("window_minutes")):
        result["window_minutes"] = int(data["window_minutes"])
    return result


def _normalize_credits(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    result = {}
    for key in ("has_credits", "unlimited", "balance"):
        value = data.get(key)
        if isinstance(value, bool) or _is_number(value):
            result[key] = value
    return result


def _normalize_token_profile(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    result = {}
    for key in _TOKEN_PROFILE_FIELDS:
        value = data.get(key)
        if key == "daily_usage_buckets" and isinstance(value, list):
            buckets = []
            for bucket in value:
                if not isinstance(bucket, dict):
                    continue
                normalized = {
                    field: bucket[field]
                    for field in ("start_date", "tokens")
                    if field in bucket and isinstance(bucket[field], (str, int, float))
                }
                if normalized:
                    buckets.append(normalized)
            if buckets:
                result[key] = buckets
        elif _is_number(value):
            result[key] = value
    return result


def _normalize_usage_response(data: Any) -> dict:
    """Produce a stable normalized mapping from the raw usage payload.

    Raw upstream JSON is never returned directly. Fields are treated as
    optional and unknown keys are silently discarded.
    """
    if not isinstance(data, dict):
        return {}

    result: Dict[str, Any] = {}

    plan = data.get("plan_type", data.get("plan"))
    if isinstance(plan, str):
        result["plan"] = plan

    windows = {}
    rate_limit = data.get("rate_limit")
    if isinstance(rate_limit, dict):
        for label, field in (("primary", "primary_window"), ("secondary", "secondary_window")):
            window = _normalize_window(rate_limit.get(field))
            if window:
                windows[label] = window
    # Kept for compatibility with early backend responses and fixtures.
    quota_windows = data.get("quota_windows")
    if isinstance(quota_windows, dict):
        for label in ("primary", "secondary", "additional"):
            window = _normalize_window(quota_windows.get(label))
            if window:
                windows.setdefault(label, window)
    additional = data.get("additional_rate_limits")
    if isinstance(additional, list):
        for index, item in enumerate(additional, 1):
            if not isinstance(item, dict):
                continue
            label = item.get("limit_id") or item.get("name") or str(index)
            if not isinstance(label, str):
                label = str(index)
            nested = item.get("rate_limit") if isinstance(item.get("rate_limit"), dict) else item
            window = _normalize_window(nested.get("primary_window", nested))
            if window:
                windows[f"additional:{label}"] = window
    if windows:
        result["windows"] = windows

    credits = _normalize_credits(data.get("credits"))
    if credits:
        result["credits"] = credits

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
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        raise UsageError("Request timed out fetching quota data.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
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
        return get_json(url, headers)

    # Primary usage endpoint — propagates errors so callers see them.
    usage_raw = _request(usage_url)
    if not isinstance(usage_raw, dict):
        usage_raw = {}
    result = _normalize_usage_response(usage_raw)

    # Best-effort profile fetch; failure must not undo a successful result.
    try:
        profile_raw = _request(profile_url)
    except UsageError:
        pass
    else:
        if isinstance(profile_raw, dict):
            token_profile = _normalize_token_profile(profile_raw.get("stats"))
            if token_profile:
                result["token_profile"] = token_profile

    return result
