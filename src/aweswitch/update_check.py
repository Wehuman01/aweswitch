"""Post-command update reminder for aweswitch."""

# Vendored across the awe series: awerouter, aweswitch, aweshelf, and awewarm each
# carry a near-identical copy (no shared runtime dependency, by design). Keep
# behavioral fixes in sync manually across the four copies. Last synced: 2026-09-19.

import json
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

from aweswitch import __version__

CHECK_INTERVAL_S = 24 * 60 * 60
REMIND_INTERVAL_S = 24 * 60 * 60


def _parse_version(v):
    try:
        parts = re.findall(r"\d+", v)
        return tuple(int(x) for x in parts[:3]) if parts else (0,)
    except (ValueError, AttributeError):
        return (0,)


def _version_gte(a, b):
    return _parse_version(a) >= _parse_version(b)


def _cache_path():
    return Path(os.environ.get("AWESWITCH_CONFIG", "~/.config/aweswitch/config.json")).expanduser().parent / "update-check.json"


def _load_cache(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _save_cache(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass


def get_pypi_latest():
    url = "https://pypi.org/pypi/aweswitch/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    return data["info"]["version"]


def _should_skip(args):
    if not args:
        return True  # bare invocation only prints help; don't hit PyPI
    if "-h" in args or "--help" in args or "-v" in args or "-V" in args or "--version" in args:
        return True
    return args[0] == "self-update"


def check_async(args):
    """Start an update check in a background thread. Returns a callable that yields a reminder string or None."""
    if os.environ.get("AWESWITCH_NO_UPDATE_CHECK") == "1":
        return lambda: None
    if _should_skip(args):
        return lambda: None

    result = [None]
    done = threading.Event()

    def _run():
        try:
            result[0] = _check(args)
        except Exception:
            pass
        finally:
            done.set()

    threading.Thread(target=_run, daemon=True).start()

    def get_result():
        done.wait(timeout=10)
        return result[0]

    return get_result


def _check(args):
    cache_path = _cache_path()
    cache = _load_cache(cache_path)
    now = time.time()

    latest = None
    if cache and now - cache.get("lastChecked", 0) < CHECK_INTERVAL_S:
        latest = cache.get("latestVersion")
    else:
        latest = get_pypi_latest()
        _save_cache(cache_path, {
            "lastChecked": now,
            "latestVersion": latest,
            "lastReminded": cache.get("lastReminded", 0) if cache else 0,
        })

    if not latest or _version_gte(__version__, latest):
        return None

    last_reminded = cache.get("lastReminded", 0) if cache else 0
    if now - last_reminded < REMIND_INTERVAL_S:
        return None

    _save_cache(cache_path, {
        "lastChecked": now,
        "latestVersion": latest,
        "lastReminded": now,
    })

    return f"Update available: {__version__} → {latest}. Run `aweswitch self-update` to update."
