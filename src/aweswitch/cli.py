#!/usr/bin/env python3
import copy
import json
import os
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote

import click

from aweswitch import __version__
from aweswitch.update_check import check_async, get_pypi_latest, _version_gte


TEMPLATE_PATH = Path(__file__).parent / "default-config.json"

SECRET_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|AUTH)", re.IGNORECASE)
ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
TEMP_SETTINGS_TTL_S = 24 * 60 * 60

# Claude Code reads these env vars to remap each /model tier to a concrete model
# id. Claude Code MERGES the --settings file with ~/.claude/settings.json, so a
# tier var the profile omits would let a stale value from a different provider
# leak through. build_claude_env defaults every unset tier to ANTHROPIC_MODEL to
# keep the --settings file authoritative regardless of which tier is selected.
CLAUDE_TIER_VARS = (
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
)

# Profile kinds stored under `profiles`: "api" (env-based API profiles) and
# "account" (official OAuth logins). Profile names are unique across both.
PROFILE_KINDS = ("api", "account")

# Official-login accounts. Each account stores an opaque copy of the CLI's own
# credentials file and launches through a private config dir (CODEX_HOME /
# CLAUDE_CONFIG_DIR), so different accounts run side by side without touching
# the user's global ~/.codex or ~/.claude.
ACCOUNT_PROVIDERS = ("claude", "codex")
ACCOUNT_BLOB_KEY = {"codex": "auth", "claude": "credentials"}
ACCOUNT_CRED_FILENAME = {"codex": "auth.json", "claude": ".credentials.json"}

# Profile names are invoked as top-level commands, so these names can never
# reach ProfileGroup's fallback launcher. Reject them when creating new
# profiles/accounts instead of saving an unusable entry.
RESERVED_PROFILE_NAMES = {
    "__profile__", "account", "add", "apply", "config", "init", "list",
    "self-update", "show", "usage",
}

# These two credentials are alternative Claude authentication mechanisms.
# An apply must not leave the previous mechanism active when the new profile
# only configures the other one.
CLAUDE_AUTH_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def config_path():
    return Path(os.environ.get("AWESWITCH_CONFIG", "~/.config/aweswitch/config.json")).expanduser()


def claude_settings_path():
    return Path(os.environ.get("CLAUDE_SETTINGS", "~/.claude/settings.json")).expanduser()


def codex_config_path():
    return Path(os.environ.get("CODEX_CONFIG", "~/.codex/config.toml")).expanduser()


def opencode_config_path():
    return Path(os.environ.get("OPENCODE_CONFIG", "~/.config/opencode/opencode.json")).expanduser()


def managed_opencode_path():
    """Sidecar recording provider keys aweswitch may safely prune."""
    return opencode_config_path().with_name(".aweswitch-managed-providers.json")


def accounts_root():
    """Runtime dirs for official accounts live next to the config file."""
    return config_path().parent / "accounts"


def validate_profile_name(name, account=False):
    if not isinstance(name, str) or not name or name.startswith("-"):
        die("profile name must be a non-empty command name and cannot start with '-'")
    if name in RESERVED_PROFILE_NAMES:
        die(f"reserved command name cannot be used as a profile: {name}")
    if account and (name in (".", "..") or "/" in name or "\\" in name):
        die(f"account name must be a single path component, got: {name}")


def account_dir(provider, name):
    if provider not in ACCOUNT_PROVIDERS:
        die(f"official accounts support {', '.join(ACCOUNT_PROVIDERS)}, got: {provider}")
    validate_profile_name(name, account=True)
    provider_root = accounts_root() / provider
    target = provider_root / name
    try:
        target.resolve().relative_to(provider_root.resolve())
    except ValueError:
        die(f"account path escapes its provider directory: {name}")
    return target


def live_credentials_path(provider):
    """Where the CLI itself stores an official login (for account import)."""
    if provider == "codex":
        return codex_config_path().with_name("auth.json")
    return claude_settings_path().with_name(".credentials.json")


def load_opencode_config():
    path = opencode_config_path()
    if not path.exists():
        return {"provider": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Never fall through to write_opencode_config with an empty config:
        # that would silently replace the user's whole opencode.json.
        die(f"invalid JSON in {path}: {exc}\n  Fix or remove the file, then retry.")
    if not isinstance(data, dict):
        die(f"unexpected JSON in {path}: expected an object at the top level")
    provider = data.get("provider")
    if provider is None:
        data["provider"] = {}
    elif not isinstance(provider, dict):
        die(f"'provider' in {path} must be an object")
    return data


def write_opencode_config(data):
    path = opencode_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _read_managed_sidecar(path):
    """Read the managed sidecar, or {} when absent; dies on malformed data."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(f"invalid managed-provider JSON at {path}: {exc}\n  Fix or remove the file, then retry.")
    if not isinstance(data, dict):
        die(f"invalid managed-provider data at {path}: expected an object")
    return data


def _managed_string_list(data, key, path):
    values = data.get(key)
    if values is None:
        return []
    if not isinstance(values, list) or not all(isinstance(name, str) and name for name in values):
        die(f"invalid managed-provider data at {path}: expected a {key} string list")
    return values


def _atomic_write_json(path, data):
    """Atomically persist a small JSON state file with 0600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        if os.name != "nt":
            os.chmod(temp_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def load_managed_opencode_providers():
    path = managed_opencode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "providers", path))


def set_managed_opencode_providers(providers):
    """Rewrite the managed provider list, preserving other sidecar keys."""
    path = managed_opencode_path()
    data = _read_managed_sidecar(path)
    if data.get("providers") == sorted(providers):
        return
    data["providers"] = sorted(providers)
    _atomic_write_json(path, data)


def load_managed_opencode_agents():
    """Agent names whose frontmatter model line aweswitch owns."""
    path = managed_opencode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "agents", path))


def set_managed_opencode_agents(agents):
    path = managed_opencode_path()
    data = _read_managed_sidecar(path)
    if data.get("agents") == sorted(agents):
        return
    data["agents"] = sorted(agents)
    _atomic_write_json(path, data)


def load_created_opencode_agents():
    """Agent names whose whole file aweswitch created from the template."""
    path = managed_opencode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "createdAgents", path))


def set_created_opencode_agents(agents):
    path = managed_opencode_path()
    data = _read_managed_sidecar(path)
    if data.get("createdAgents") == sorted(agents):
        return
    data["createdAgents"] = sorted(agents)
    _atomic_write_json(path, data)


def record_managed_opencode_provider(provider_name):
    set_managed_opencode_providers(load_managed_opencode_providers() | {provider_name})


def opencode_agents_dir():
    """Global agent markdown dir, sibling of opencode.json (follows OPENCODE_CONFIG)."""
    return opencode_config_path().parent / "agents"


def _frontmatter_end(lines):
    """Index of the closing `---` of a frontmatter block, or None."""
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return i
    return None


def _line_eol(line):
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _edit_agent_model_line(path, new_value):
    """Set or remove the frontmatter `model:` line of an agent markdown file.

    A line-level edit: everything outside that one line keeps its exact
    bytes, so a user-authored prompt body is never reformatted. A missing
    line is inserted before the closing `---`; a missing frontmatter block is
    created. new_value=None removes the line, which lets the agent fall back
    to inheriting the primary model — valid under every provider. Returns
    True when the file changed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    lines = text.splitlines(keepends=True)
    end = _frontmatter_end(lines)
    model_idx = None
    if end is not None:
        for i in range(1, end):
            if re.match(r"^model:[ \t]*", lines[i]):
                model_idx = i
                break
    if new_value is None:
        if model_idx is None:
            return False
        del lines[model_idx]
    elif model_idx is not None:
        lines[model_idx] = f"model: {new_value}{_line_eol(lines[model_idx])}"
    elif end is not None:
        # Kept out of the f-string replacement field: a backslash inside an
        # f-string expression is a SyntaxError before Python 3.12.
        eol = _line_eol(lines[end]) or "\n"
        lines.insert(end, f"model: {new_value}{eol}")
    else:
        lines[0:0] = ["---\n", f"model: {new_value}\n", "---\n"]
    new_text = "".join(lines)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


# Generic agent template: every aweswitch-created agent differs only in the
# model line, so config is the single source of truth for the subagent fleet.
OPENCODE_AGENT_TEMPLATE = """---
description: General-purpose subagent ({model})
mode: subagent
model: {ref}
---

Complete the assigned task and report the result concisely.
"""

ZCODE_AGENT_TEMPLATE = """---
name: {name}
description: General-purpose subagent ({model})
model: {value}
---
"""


def ensure_opencode_agents(subagents, release_missing=True):
    """Create, pin, release or delete agent files to match the pin set.

    subagents maps agent name -> "profile/model" (from the config's global
    subagents.opencode section). A declared agent whose file is missing is
    created from the generic template — only the model line differs between
    agents. With release_missing (the apply path) an agent aweswitch
    previously managed but absent from this map is removed: a file created
    from the template is deleted, while a user-authored file only loses its
    model line so the agent survives and inherits the primary model. The
    launch path passes release_missing=False: launching a profile only
    (re)creates and (re)writes the pins the config declares and never
    removes one; the next apply reconciles them. Files never named here are
    never touched. Returns change notes.
    """
    agents_dir = opencode_agents_dir()
    created = load_created_opencode_agents()
    owned = load_managed_opencode_agents()
    changes = []
    if release_missing:
        for agent in sorted(owned - set(subagents)):
            path = agents_dir / f"{agent}.md"
            if agent in created:
                if path.exists():
                    path.unlink()
                    changes.append(f"deleted agent '{agent}' (created by aweswitch)")
                created.discard(agent)
            elif _edit_agent_model_line(path, None):
                changes.append(f"released agent '{agent}' (inherits primary model)")
        owned = set()
    for agent, ref in sorted(subagents.items()):
        path = agents_dir / f"{agent}.md"
        if not path.exists():
            agents_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                OPENCODE_AGENT_TEMPLATE.format(model=ref.split("/", 1)[1], ref=ref),
                encoding="utf-8",
            )
            created.add(agent)
            changes.append(f"created agent '{agent}' from template -> {ref}")
        elif _edit_agent_model_line(path, ref):
            changes.append(f"pinned agent '{agent}' -> {ref}")
    set_created_opencode_agents(created & set(subagents))
    set_managed_opencode_agents(owned | set(subagents))
    return changes


def warn_opencode_stale_agents():
    """Warn about agent files pinned to a provider missing from opencode.json.

    Only user-maintained pins can end up here — aweswitch-owned pins are
    released or repointed by ensure_opencode_agents on every apply — so this
    reports and never repairs.
    """
    agents_dir = opencode_agents_dir()
    if not agents_dir.is_dir():
        return
    providers = set(load_opencode_config()["provider"])
    for md in sorted(agents_dir.glob("*.md")):
        try:
            lines = md.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        end = _frontmatter_end(lines)
        if end is None:
            continue
        for i in range(1, end):
            m = re.match(r"^model:[ \t]*(\S+)$", lines[i])
            if m:
                provider = m.group(1).split("/", 1)[0]
                if provider not in providers:
                    click.echo(
                        f"warning: agent '{md.stem}' pins model '{m.group(1)}' but provider "
                        f"'{provider}' is not in opencode.json; add an entry under "
                        f"subagents.opencode in the aweswitch config to manage it",
                        err=True,
                    )
                break


# The two AI SDK packages aweswitch may write for an opencode provider:
# chat completions by default, or the OpenAI Responses API per model when a
# profile lists that model in OPENCODE_RESPONSES_MODEL. Provider ownership is
# tracked separately; these package names alone are never used as proof.
OPENCODE_NPM_CHAT = "@ai-sdk/openai-compatible"
OPENCODE_NPM_RESPONSES = "@ai-sdk/openai"
OPENCODE_REASONING_VARIANTS = ("low", "medium", "high", "xhigh", "max")


def build_opencode_provider_entry(base_url, api_key, name="aweswitch"):
    return {
        "name": name,
        "npm": OPENCODE_NPM_CHAT,
        "options": {
            "apiKey": api_key,
            "baseURL": base_url,
            "setCacheKey": True,
        },
    }


def _opencode_api_key_ref(raw):
    """Return opencode's env ref syntax for a config ${VAR} API key.

    Allows bare values through with a warning so users aren't blocked from
    using plain strings; the env-ref form is still recommended because it
    keeps the actual key out of the config file.
    """
    if not isinstance(raw, str):
        click.echo(
            "  tip: OPENCODE_API_KEY is not a string — consider ${VAR_NAME} to keep the key out of the config file\n"
            "  Example: \"OPENCODE_API_KEY\": \"${MY_API_KEY}\"",
            err=True,
        )
        return str(raw)
    m = ENV_REF_RE.fullmatch(raw)
    if not m:
        click.echo(
            "  tip: OPENCODE_API_KEY is a plain value — consider ${VAR_NAME} to keep the key out of the config file\n"
            "  Example: \"OPENCODE_API_KEY\": \"${MY_API_KEY}\"",
            err=True,
        )
        return raw
    return f"{{env:{m.group(1)}}}"


def _zcode_api_key_ref(raw):
    """Expand a ${VAR} API key for zcode — its config has no env-ref syntax.

    zcode stores provider keys as plain strings, so the reference is resolved
    from the shell env at apply time and the resolved key lands in the config.
    """
    if not isinstance(raw, str):
        click.echo(
            "  tip: ZCODE_API_KEY is not a string — use a plain value or a ${VAR_NAME} reference\n"
            "  Example: \"ZCODE_API_KEY\": \"${MY_API_KEY}\"",
            err=True,
        )
        return str(raw)
    if ENV_REF_RE.fullmatch(raw):
        return expand_value(raw, dict(os.environ))
    click.echo(
        "  tip: ZCODE_API_KEY is a plain value — consider ${VAR_NAME} so the key lives in your\n"
        "  shell config instead of the aweswitch config",
        err=True,
    )
    return raw


def _parse_responses_models(raw, profile_name, key):
    """Parse OPENCODE/ZCODE_RESPONSES_MODEL: model IDs that use the Responses API.

    Accepts a comma-separated string or a list of IDs. Returns a list of model
    IDs preserving the configured order (deduplicated) so the merged model
    dict — and with it the no-arg default model — is deterministic, or an
    empty list if absent/empty.
    """
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, str):
        ids = raw.split(",")
    elif isinstance(raw, list) and all(isinstance(m, str) for m in raw):
        ids = list(raw)
    else:
        die(f"{key} must be a comma-separated string or a list of "
            f"model IDs for profile: {profile_name}")
    return list(dict.fromkeys(m.strip() for m in ids if m.strip()))


def _merge_opencode_models(env, profile_name):
    """Merge OPENCODE_MODEL and OPENCODE_RESPONSES_MODEL into one {id: name} dict.

    At least one must be non-empty; the two fields have equal standing, so
    either alone is a complete model list. The merged key order is the
    opencode model-picker order (a no-arg launch keeps defaulting to its
    first entry): whichever field is written first in env leads, and within
    each block the configured order is preserved — write
    OPENCODE_RESPONSES_MODEL above OPENCODE_MODEL to list Responses models
    first.
    """
    chat = normalize_models_opt(
        env.get("OPENCODE_MODEL"), profile_name, "OPENCODE_MODEL")
    resp = _parse_responses_models(
        env.get("OPENCODE_RESPONSES_MODEL"), profile_name,
        "OPENCODE_RESPONSES_MODEL")
    if not chat and not resp:
        die(f"OPENCODE_MODEL or OPENCODE_RESPONSES_MODEL is required for {profile_name}")
    duplicate_models = set(chat) & set(resp)
    if duplicate_models:
        die(f"models must not be listed in both OPENCODE_MODEL and "
            f"OPENCODE_RESPONSES_MODEL for {profile_name}: "
            f"{', '.join(sorted(duplicate_models))}")
    resp_dict = {model_id: model_id for model_id in resp}
    keys = list(env)
    responses_leads = ("OPENCODE_MODEL" in keys and "OPENCODE_RESPONSES_MODEL" in keys
                       and keys.index("OPENCODE_RESPONSES_MODEL") < keys.index("OPENCODE_MODEL"))
    if responses_leads:
        merged = {**resp_dict, **chat}
    else:
        merged = {**chat, **resp_dict}
    return merged, resp


def _resolve_zcode_models(chat_raw, responses_raw, profile_name):
    """Resolve the zcode model fields into a model dict and the provider kind.

    zcode supports exactly one API format per provider, so exactly one of
    ZCODE_CHAT_MODEL (chat completions, kind openai-compatible) or
    ZCODE_RESPONSES_MODEL (Responses API, kind openai) must be set.
    """
    chat = normalize_models_opt(chat_raw, profile_name, "ZCODE_CHAT_MODEL")
    resp = _parse_responses_models(
        responses_raw, profile_name, "ZCODE_RESPONSES_MODEL")
    if chat and resp:
        die(f"zcode supports one API format per provider; use ZCODE_CHAT_MODEL or "
            f"ZCODE_RESPONSES_MODEL, not both — split {profile_name} into two profiles")
    if not chat and not resp:
        die(f"ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL is required for {profile_name}")
    if chat:
        return dict(chat), "openai-compatible"
    return {model_id: model_id for model_id in resp}, "openai"


SUBAGENT_TARGETS = ("opencode", "zcode")


def _subagent_profile_models(target, entry, profile_name):
    """A target profile's merged {model_id: name} list."""
    if target == "opencode":
        models, _ = _merge_opencode_models(entry["env"], profile_name)
    else:
        models, _ = _resolve_zcode_models(
            entry["env"].get("ZCODE_CHAT_MODEL"),
            entry["env"].get("ZCODE_RESPONSES_MODEL"), profile_name)
    return models


def parse_subagent_pins(config, target):
    """Parse the top-level subagents.<target> section into {agent: "profile/model"}.

    Subagent pins are global state — the agent files outlive any profile —
    so the section sits beside "profiles", not inside one. Each value is
    the exact "profile/model-id" string an agent file's model line gets:
    split at the first slash (the model id itself may contain slashes), the
    named profile must be a <target> api profile listing that model, so a
    pin always resolves the moment it is written.
    """
    section = config.get("subagents")
    if section is None:
        return {}
    if not isinstance(section, dict):
        die('subagents must be an object: {"opencode": {...}, "zcode": {...}}')
    unknown = [key for key in section if key not in SUBAGENT_TARGETS]
    if unknown:
        die("subagents supports targets 'opencode' and 'zcode' only, got: "
            + ", ".join(sorted(unknown)))
    raw = section.get(target)
    if raw is None or raw == {}:
        return {}
    prefix = "oc" if target == "opencode" else "zc"
    if not isinstance(raw, dict):
        die(
            f"subagents.{target} must be a non-empty {{agent: \"profile/model\"}} object\n"
            f"  Example: \"subagents\": {{\"{target}\": {{\"explore\": \"{prefix}-glm/glm-5.1-flash\"}}}}"
        )
    group = kind_group(config, "api").get(target, {})
    if not isinstance(group, dict):
        die(f"provider entries must be an object: api.{target}")
    pins = {}
    for agent, ref in raw.items():
        if not isinstance(agent, str) or not agent.strip():
            die(f"subagents.{target} agent names must be non-empty strings")
        if not isinstance(ref, str) or not ref.strip() or "/" not in ref:
            die(
                f"subagents.{target}['{agent}'] must be a \"profile/model-id\" reference, got: {ref!r}\n"
                f"  Example: \"{agent}\": \"{prefix}-glm/glm-5.1-flash\""
            )
        ref = ref.strip()
        profile, _, model = ref.partition("/")
        entry = group.get(profile)
        if not isinstance(entry, dict) or not isinstance(entry.get("env"), dict):
            die(f"subagents.{target}['{agent}'] references '{profile}', "
                f"which is not an api profile under profiles.api.{target}")
        if model not in _subagent_profile_models(target, entry, profile):
            die(f"subagents.{target}['{agent}'] model '{model}' is not in "
                f"profile {profile}'s model list")
        pins[agent] = ref
    return pins


def subagent_pin_profiles(pins):
    """The profile names a pin set depends on — the refs' provider parts."""
    return {ref.split("/", 1)[0] for ref in pins.values()}


def _stamp_opencode_responses_models(models_dict, model_ids, responses_models):
    """Add/remove the per-model Responses npm override on the named models.

    Only iterates model_ids (the set this call manages), so an additive launch
    never strips overrides from other models. Removal only deletes an npm value
    aweswitch itself would have written — a hand-set vendor npm stays.
    Returns True when anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        prov = entry.get("provider")
        if model_id in responses_models:
            if not isinstance(prov, dict):
                prov = {}
                entry["provider"] = prov
            if prov.get("npm") != OPENCODE_NPM_RESPONSES:
                prov["npm"] = OPENCODE_NPM_RESPONSES
                changed = True
        elif isinstance(prov, dict) and prov.get("npm") == OPENCODE_NPM_RESPONSES:
            del prov["npm"]
            if not prov:
                del entry["provider"]
            changed = True
    return changed


def _stamp_opencode_model_defaults(models_dict, model_ids):
    """Add the default modalities/attachment declaration to the named models.

    opencode defaults every custom-model capability to false when the field is
    absent, so a bare {"name": ...} entry hides the image-paste/attach
    affordances even for multimodal models. Declaring text+image for all
    models only moves a capability mismatch to the upstream API, which errors
    visibly; the reverse fails silently. Only fills values that are absent —
    a hand-set declaration (e.g. input: ["text"] to keep a model text-only)
    always wins. Returns True when anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        if "attachment" not in entry:
            entry["attachment"] = True
            changed = True
        if "modalities" not in entry:
            entry["modalities"] = {"input": ["text", "image"], "output": ["text"]}
            changed = True
    return changed


def _stamp_opencode_release_dates(models_dict, model_ids):
    """Stamp release_date on the named models in descending config order.

    OpenCode's model picker sorts by release_date (newest first) and then by
    title — it never reads the config's JSON key order, so without dates the
    picker falls back to alphabetical. Mapping config position to descending
    dates (first model = 9999-12-31) makes the picker, and the provider's
    default model, follow the aweswitch config. Unlike the fill-only stamps
    this overwrites: the date IS the order signal, so a hand-set date that
    contradicts the config order is reconciled on apply. apply-only — launch
    never re-stamps, so an additive launch cannot reshuffle the picker.
    Returns True when anything changed.
    """
    changed = False
    newest = date(9999, 12, 31)
    for i, model_id in enumerate(model_ids):
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        want = (newest - timedelta(days=i)).isoformat()
        if entry.get("release_date") != want:
            entry["release_date"] = want
            changed = True
    return changed


def _stamp_opencode_reasoning_variants(models_dict, model_ids):
    """Add default reasoning-effort variants to the named models.

    Each of low/medium/high/xhigh/max is filled only when its key is absent;
    hand-set variants always win, and existing variant keys are never removed.
    Only iterates model_ids (the set this call manages). Returns True when
    anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        if "variants" not in entry:
            entry["variants"] = {}
            changed = True
        variants = entry["variants"]
        if not isinstance(variants, dict):
            continue
        for effort in OPENCODE_REASONING_VARIANTS:
            if effort not in variants:
                variants[effort] = {"reasoningEffort": effort}
                changed = True
    return changed


def opencode_model_display_name(model_id, model_name):
    """Namespaced model IDs (producer/model, e.g. hub/x) display as the full ID.

    When the configured display name is just the ID's last segment, the model
    picker can show identical rows for different producers (hub/x and peng1/x
    both displaying "x"); keeping the full ID keeps them distinguishable.
    Custom display names pass through unchanged.
    """
    if "/" in model_id and model_name == model_id.rsplit("/", 1)[1]:
        return model_id
    return model_name


def ensure_opencode_provider(base_url, api_key_ref, provider_name, models,
                             display_name=None, prune=False,
                             responses_models=None):
    """Ensure provider+models exist in opencode.json, synced to the aweswitch config.

    The provider entry is owned by aweswitch (its name is the profile name), so
    stale credentials and display names are updated to match the config instead
    of rejected. Launch passes only the selected model (additive); `aweswitch
    apply` passes the full list with prune=True so the entry matches the config
    exactly — including key order, and descending release_date stamps that
    make OpenCode's picker follow the config order (the picker sorts by
    release_date, never by key order). `responses_models` stamps a per-model
    Responses npm override on those models and removes stale ones; it only
    touches the models passed in `models`. Every managed model also gets the
    default modalities/attachment declaration (text+image input, attachments
    on) unless the entry already declares one — hand-set values win. The
    provider-level npm stays
    @ai-sdk/openai-compatible by default. Returns "created", "updated", or
    "unchanged".
    """
    name = display_name or provider_name
    responses_models = responses_models or set()
    oc_config = load_opencode_config()
    providers = oc_config["provider"]
    existing = providers.get(provider_name)
    status = "unchanged"

    if existing:
        opts = existing.setdefault("options", {})
        if not isinstance(opts, dict):
            opts = {}
            existing["options"] = opts
        if opts.get("baseURL") != base_url:
            opts["baseURL"] = base_url
            status = "updated"
        if opts.get("apiKey") != api_key_ref:
            opts["apiKey"] = api_key_ref
            status = "updated"
        if existing.get("name") != name:
            existing["name"] = name
            status = "updated"
        if (existing.get("npm") in (OPENCODE_NPM_CHAT, OPENCODE_NPM_RESPONSES)
                and existing.get("npm") != OPENCODE_NPM_CHAT):
            existing["npm"] = OPENCODE_NPM_CHAT
            status = "updated"
        models_dict = existing.setdefault("models", {})
        if not isinstance(models_dict, dict):
            models_dict = {}
            existing["models"] = models_dict
        for model_id, model_name in models.items():
            display = opencode_model_display_name(model_id, model_name)
            entry_model = models_dict.setdefault(model_id, {})
            if not isinstance(entry_model, dict):
                # hand-edited entries may use a plain string; repair in place
                entry_model = {}
                models_dict[model_id] = entry_model
            if entry_model.get("name") != display:
                entry_model["name"] = display
                status = "updated"
        if _stamp_opencode_model_defaults(models_dict, models):
            status = "updated"
        if _stamp_opencode_reasoning_variants(models_dict, models):
            status = "updated"
        if _stamp_opencode_responses_models(models_dict, models, responses_models):
            status = "updated"
        if prune:
            for model_id in [m for m in models_dict if m not in models]:
                del models_dict[model_id]
                status = "updated"
            # Key order is the picker order: a full sync makes the config's
            # order authoritative too, so reorder (per-model entries —
            # including hand-set values — ride along unchanged).
            if list(models_dict) != list(models):
                existing["models"] = {model_id: models_dict[model_id]
                                      for model_id in models}
                status = "updated"
            # OpenCode's picker sorts by release_date (newest first), then
            # title — it never reads key order. The descending stamps are
            # what actually make the picker follow the config; the reorder
            # above keeps the file itself honest.
            if _stamp_opencode_release_dates(existing["models"], models):
                status = "updated"
        if status != "unchanged":
            write_opencode_config(oc_config)
    else:
        entry = build_opencode_provider_entry(base_url, api_key_ref, name=name)
        entry["models"] = {
            model_id: {"name": opencode_model_display_name(model_id, model_name)}
            for model_id, model_name in models.items()
        }
        _stamp_opencode_model_defaults(entry["models"], models)
        _stamp_opencode_reasoning_variants(entry["models"], models)
        _stamp_opencode_responses_models(entry["models"], models, responses_models)
        _stamp_opencode_release_dates(entry["models"], models)
        providers[provider_name] = entry
        write_opencode_config(oc_config)
        status = "created"
    # An unchanged launch historically required no directory write. Preserve
    # that path; apply (prune=True) explicitly opts into tracking even when the
    # provider content already matches.
    if status != "unchanged" or prune:
        record_managed_opencode_provider(provider_name)
    return status


def write_opencode_launch(oc_write_info):
    """Perform the launch-time opencode writes for a prepared profile.

    Dep providers, the session provider with the profile's full model list,
    and the config's global agent pins. Launch is additive: models
    accumulate (pins too — nothing the config still names is released);
    reconciling the agent files with the aweswitch config is apply's job.
    Returns change notes to echo.
    """
    for dep in oc_write_info.get("deps", []):
        ensure_opencode_provider(
            dep["base_url"],
            dep["api_key_ref"],
            dep["provider_name"],
            dep["models"],
            display_name=dep["display_name"],
            responses_models=set(dep["responses_models"]),
        )
    launch_models = dict(oc_write_info.get("models") or {})
    launch_models.setdefault(
        oc_write_info["model"], oc_write_info["model_display_name"])
    ensure_opencode_provider(
        oc_write_info["base_url"],
        oc_write_info["api_key_ref"],
        oc_write_info["provider_name"],
        launch_models,
        display_name=oc_write_info["display_name"],
        responses_models=set(oc_write_info["responses_models"]),
    )
    subagents = oc_write_info.get("subagents") or {}
    if not subagents:
        return []
    return ensure_opencode_agents(subagents, release_missing=False)


def build_opencode_specs(config, names=None):
    """Validate and materialize the sync spec for every (or the named) profile.

    Each spec is (name, base_url, api_key_ref, models, display_name,
    responses_models). Pure: reads the aweswitch config, touches no files,
    so a dry run can preview the exact list a sync would write.
    """
    profiles = kind_group(config, "api").get("opencode", {})
    if not isinstance(profiles, dict):
        die("provider entries must be an object: api.opencode")
    specs = []
    for name in dict.fromkeys(names if names is not None else profiles):
        provider, kind, _ = profile_for(config, name)
        if provider != "opencode" or kind != "api":
            die(f"sync only supports opencode api profiles, got: {name} (provider={provider}, kind={kind})")
        profile_env = profiles.get(name, {}).get("env", {})
        base_url_raw = profile_env.get("OPENCODE_BASE_URL")
        api_key_raw = profile_env.get("OPENCODE_API_KEY")
        if not base_url_raw:
            die(f"OPENCODE_BASE_URL is required for opencode profile: {name}")
        if not api_key_raw:
            die(f"OPENCODE_API_KEY is required for opencode profile: {name}")
        models_dict, responses_models = _merge_opencode_models(profile_env, name)
        specs.append((
            name,
            expand_value(base_url_raw, dict(os.environ)),
            _opencode_api_key_ref(api_key_raw),
            models_dict,
            profile_env.get("OPENCODE_NAME") or name,
            responses_models,
        ))
    return specs


def sync_opencode_profiles(config, names=None):
    """Write every (or the named) opencode profile into opencode.json.

    Unlike a launch, which only adds models, sync replaces each provider
    entry (base URL, API key ref, display name) and its full model list so
    the file matches the aweswitch config — models removed from the config
    disappear from opencode too. Providers the config doesn't know about
    are left alone. All profiles are validated before anything is written.
    Agent pins come from the config's top-level subagents.opencode section
    — global state, not per-profile — so every sync reconciles them: named
    agents get their model line rewritten, agents a previous apply pinned
    but the section no longer names are released, and every referenced
    profile's provider is ensured even when this sync didn't name it.
    Returns (profile, status, model_count, agent_notes) tuples.
    """
    specs = build_opencode_specs(config, names)
    if specs:
        load_opencode_config()
        load_managed_opencode_providers()
    pins = parse_subagent_pins(config, "opencode")
    # The pins must resolve the moment they are written: every referenced
    # profile's provider is ensured even when this sync didn't name it.
    synced_names = {spec[0] for spec in specs}
    dep_names = subagent_pin_profiles(pins) - synced_names
    for name, base_url, api_key_ref, models, display_name, responses_models in \
            build_opencode_specs(config, sorted(dep_names)):
        ensure_opencode_provider(base_url, api_key_ref, name, models,
                                 display_name=display_name, prune=True,
                                 responses_models=responses_models)
    results = []
    for name, base_url, api_key_ref, models, display_name, responses_models in specs:
        results.append((
            name,
            ensure_opencode_provider(base_url, api_key_ref, name, models,
                                     display_name=display_name, prune=True,
                                     responses_models=responses_models),
            len(models),
        ))
    agent_notes = ensure_opencode_agents(pins)
    return [
        (name, status, model_count, agent_notes if name == results[0][0] else [])
        for name, status, model_count in results
    ]


def find_orphan_opencode_providers(config):
    """Return {name: entry} for aweswitch-written providers left in opencode.json.

    An orphan is a provider no opencode profile in the aweswitch config backs
    anymore — typically a renamed or deleted profile. Ownership comes from a
    sidecar written whenever aweswitch manages a provider; shape guessing is
    deliberately avoided so a hand-written provider is never pruned. Old
    sessions pinned to an orphan's models keep sending those model IDs
    upstream, which breaks when the upstream renames them.
    """
    managed = kind_group(config, "api").get("opencode") or {}
    providers = load_opencode_config()["provider"]
    owned = load_managed_opencode_providers()
    orphans = {}
    for name in owned:
        entry = providers.get(name)
        if name not in managed and isinstance(entry, dict):
            orphans[name] = entry
    return orphans


def warn_opencode_orphans(config):
    """Report aweswitch-written providers no profile backs (renamed or deleted)."""
    orphans = find_orphan_opencode_providers(config)
    if not orphans:
        return
    for name, entry in sorted(orphans.items()):
        models = ", ".join(sorted(entry.get("models") or {})) or "no models"
        click.echo(
            f"warning: orphaned aweswitch provider '{name}' in opencode.json ({models})",
            err=True,
        )
    click.echo(
        "  No aweswitch profile backs it (renamed or deleted?); old sessions pinned to its\n"
        "  models keep using them. Prune with: aweswitch apply --opencode --prune orphans",
        err=True,
    )


# --prune accepts a mode keyword or a provider-name list.
PRUNE_ORPHANS = "orphans"
PRUNE_ALL = "all"
ZCODE_BUILTIN_PROVIDER_PREFIX = "builtin:"


def _parse_prune(raw):
    """Resolve a --prune value into 'orphans', 'all', or a name list."""
    if raw is None:
        return None
    value = raw.strip()
    if value == PRUNE_ORPHANS:
        return PRUNE_ORPHANS
    if value == PRUNE_ALL:
        return PRUNE_ALL
    names = _parse_prune_provider_names(value)
    return names


def _parse_prune_provider_names(raw):
    """Split a --prune value into a de-duplicated provider-name list."""
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        die(f"--prune needs 'orphans', 'all', or at least one provider name, got: {raw!r}")
    return list(dict.fromkeys(names))


def _plan_provider_prune(prune, providers, backed, path, label, elsewhere=None):
    """Resolve --prune 'all' or a name list against one provider config. No writes.

    Shared by the opencode and zcode planners so the two stay in step. 'all'
    targets every unbacked provider, hand-written ones included — explicit
    opt-in to full alignment. A name list adds exactly those entries; each
    must exist and must not be profile-backed (a sync would recreate it
    otherwise). A name missing from this config is an error unless another
    config pruned by the same run has it (`elsewhere` holds that config's
    provider names) — a leftover provider only ever exists in one of the two
    files, so a mixed apply must be able to name it once.
    """
    if prune == PRUNE_ALL:
        if not backed:
            die(
                f"--prune all would delete every provider, but the "
                f"aweswitch config has no {label} profiles.\n"
                f"  Add a profile first, or name the providers to prune."
            )
        return {
            name: entry
            for name, entry in providers.items()
            if name not in backed and isinstance(entry, dict)
        }
    targets = {}
    for name in prune:
        entry = providers.get(name)
        if not isinstance(entry, dict):
            if elsewhere and name in elsewhere:
                continue
            available = ", ".join(sorted(providers)) or "(none)"
            die(
                f"--prune: no provider '{name}' in {path}\n"
                f"  Available providers: {available}"
            )
        if name in backed:
            die(
                f"--prune: '{name}' is backed by the aweswitch profile of the "
                "same name; remove that profile from the config instead."
            )
        targets[name] = entry
    return targets


def plan_opencode_prune(config, prune, elsewhere=None):
    """Resolve apply's --prune value into an opencode {name: entry} deletion set.

    'orphans' contributes tracked providers no profile backs. 'all' and name
    lists are resolved by the shared planner; in a run that also prunes zcode,
    a name list entry missing here may resolve there (`elsewhere`) instead of
    erroring. No writes.
    """
    if prune is None:
        return {}
    if prune == PRUNE_ORPHANS:
        return find_orphan_opencode_providers(config)
    return _plan_provider_prune(
        prune,
        providers=load_opencode_config()["provider"],
        backed=kind_group(config, "api").get("opencode") or {},
        path=opencode_config_path(),
        label="opencode",
        elsewhere=elsewhere,
    )


def _describe_provider_models(entry):
    return ", ".join(sorted(entry.get("models") or {})) or "no models"


def default_model_repair_target(config, model, provider_keys):
    """Return what a dangling top-level `model` should become, or None.

    A prune may delete the provider the default model points at; this repair
    keeps the pointer usable. The part before the first "/" names the
    provider. A pointer at a provider that still exists (hand-written ones
    included), a bare model id without "/", or a missing field is left alone.
    With several profiles the alphabetically-first one's first configured
    model (the same no-arg launch default) becomes the target.
    """
    if not isinstance(model, str) or "/" not in model:
        return None
    if model.split("/", 1)[0] in provider_keys:
        return None
    backed = kind_group(config, "api").get("opencode") or {}
    if not backed:
        click.echo(
            f"warning: default model '{model}' points at a missing provider and the "
            "aweswitch config has no opencode profile to repoint it to; leaving it unchanged",
            err=True,
        )
        return None
    profile = sorted(backed)[0]
    profile_env = backed.get(profile, {}).get("env", {})
    models, _ = _merge_opencode_models(profile_env, profile)
    return f"{profile}/{next(iter(models))}"


def preview_opencode_prune(specs, targets, config):
    """Print what a dry-run apply would sync and prune; write nothing."""
    click.echo("Dry run: nothing will be written.")
    for name, _base_url, _api_key_ref, models, _display_name, _responses in specs:
        click.echo(f"{name}: would sync ({len(models)} models)")
    for name in sorted(targets):
        click.echo(f"Would prune provider '{name}' ({_describe_provider_models(targets[name])})")
    if not targets:
        click.echo("Nothing to prune.")
    oc_config = load_opencode_config()
    new_model = default_model_repair_target(
        config, oc_config.get("model"),
        set(oc_config["provider"]) - set(targets),
    )
    if new_model is not None:
        click.echo(f"Default model: {oc_config.get('model')} -> {new_model}")


def execute_opencode_prune(config, targets):
    """Delete the planned providers, then keep the default model usable."""
    oc_config = load_opencode_config()
    for name in sorted(targets):
        if oc_config["provider"].pop(name, None) is None:
            continue
        click.echo(
            f"Pruned provider '{name}' from {opencode_config_path()} "
            f"({_describe_provider_models(targets[name])})"
        )
    new_model = default_model_repair_target(
        config, oc_config.get("model"), set(oc_config["provider"]))
    if new_model is not None:
        click.echo(f"Default model: {oc_config.get('model')} -> {new_model}")
        oc_config["model"] = new_model
    write_opencode_config(oc_config)
    set_managed_opencode_providers(load_managed_opencode_providers() - set(targets))


def zcode_config_path():
    return Path(os.environ.get("ZCODE_CONFIG", "~/.zcode/v2/config.json")).expanduser()


def managed_zcode_path():
    """Sidecar recording provider keys aweswitch may safely prune."""
    return zcode_config_path().with_name(".aweswitch-managed-providers.json")


def load_zcode_config():
    path = zcode_config_path()
    if not path.exists():
        return {"provider": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Never fall through to write_zcode_config with an empty config:
        # that would silently replace the user's whole config.json.
        die(f"invalid JSON in {path}: {exc}\n  Fix or remove the file, then retry.")
    if not isinstance(data, dict):
        die(f"unexpected JSON in {path}: expected an object at the top level")
    provider = data.get("provider")
    if provider is None:
        data["provider"] = {}
    elif not isinstance(provider, dict):
        die(f"'provider' in {path} must be an object")
    return data


def write_zcode_config(data):
    path = zcode_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    secure_config_file(path)


def load_managed_zcode_providers():
    path = managed_zcode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "providers", path))


def set_managed_zcode_providers(providers):
    """Rewrite the managed provider list, preserving other sidecar keys."""
    path = managed_zcode_path()
    data = _read_managed_sidecar(path)
    if data.get("providers") == sorted(providers):
        return
    data["providers"] = sorted(providers)
    _atomic_write_json(path, data)


def load_managed_zcode_agents():
    """Built-in agent names whose model override aweswitch owns."""
    path = managed_zcode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "agents", path))


def set_managed_zcode_agents(agents):
    path = managed_zcode_path()
    data = _read_managed_sidecar(path)
    if data.get("agents") == sorted(agents):
        return
    data["agents"] = sorted(agents)
    _atomic_write_json(path, data)


def load_managed_zcode_user_agents():
    """User-subagent names whose frontmatter model line aweswitch owns."""
    path = managed_zcode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "userAgents", path))


def set_managed_zcode_user_agents(agents):
    path = managed_zcode_path()
    data = _read_managed_sidecar(path)
    if data.get("userAgents") == sorted(agents):
        return
    data["userAgents"] = sorted(agents)
    _atomic_write_json(path, data)


def load_created_zcode_user_agents():
    """User-subagent names whose whole file aweswitch created from the template."""
    path = managed_zcode_path()
    return set(_managed_string_list(_read_managed_sidecar(path), "createdUserAgents", path))


def set_created_zcode_user_agents(agents):
    path = managed_zcode_path()
    data = _read_managed_sidecar(path)
    if data.get("createdUserAgents") == sorted(agents):
        return
    data["createdUserAgents"] = sorted(agents)
    _atomic_write_json(path, data)


def record_managed_zcode_provider(provider_name):
    set_managed_zcode_providers(load_managed_zcode_providers() | {provider_name})


# zcode's built-in agent overrides live in an undocumented app-state file; the
# two names are the complete key space of builtInModelOverrides.
ZCODE_OVERRIDE_AGENTS = ("general-purpose", "Explore")


def zcode_agents_state_path():
    """The desktop app's subagent-state file, sibling of v2/config.json."""
    return zcode_config_path().with_name("agents-state.json")


def load_zcode_agents_state():
    """Read agents-state.json, or {} when absent; dies on a malformed shape.

    The file's structure is undocumented (reverse-engineered from the app),
    so anything unexpected dies instead of risking a write that corrupts app
    state.
    """
    path = zcode_agents_state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(f"invalid JSON in {path}: {exc}\n  Fix or remove the file, then retry.")
    if not isinstance(data, dict):
        die(f"unexpected JSON in {path}: expected an object at the top level")
    overrides = data.get("builtInModelOverrides")
    if overrides is not None and (
            not isinstance(overrides, dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in overrides.items())):
        die(f"'builtInModelOverrides' in {path} must map agent names to model strings")
    return data


def write_zcode_agents_state(data):
    """Atomic write that preserves keys aweswitch does not manage."""
    _atomic_write_json(zcode_agents_state_path(), data)


def zcode_app_running():
    """Best-effort check for a running ZCode desktop app.

    The app rewrites agents-state.json from its Settings UI; a write while
    the Subagents page holds a stale snapshot is lost on save. Only used to
    warn — a lost override self-heals on the next apply.
    """
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ZCode.exe"],
                capture_output=True, text=True, timeout=5)
            return "ZCode.exe" in (result.stdout or "")
        result = subprocess.run(
            ["pgrep", "-f", "ZCode.app/Contents/MacOS"],
            capture_output=True, timeout=5)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _zcode_override_value(ref):
    """Encode a "provider/model" reference the way zcode's settings UI does.

    The app stores custom-provider model references as
    "custom:<encoded-provider>:<encoded-model>" and decodes by splitting at
    the first raw ":" after the prefix, so both parts are percent-encoded —
    a slash-bearing model id (hub/x) becomes hub%2Fx. Profile names cannot
    contain "/" (they are command names), so splitting the reference at its
    first "/" is unambiguous.
    """
    provider, model = ref.split("/", 1)
    return f"custom:{quote(provider, safe='')}:{quote(model, safe='')}"


def ensure_zcode_agent_overrides(subagents):
    """Set or release the built-in agent model overrides.

    subagents maps built-in agent name -> "profile/model" (from the
    config's global subagents.zcode section); the encoded
    custom:<provider>:<model> form lands in builtInModelOverrides per
    agent. An empty map (or None) releases everything aweswitch owns;
    overrides the user set in the app UI on names aweswitch doesn't own
    are preserved — the sidecar records ownership so a later release never
    deletes a hand-set value. Returns change notes.
    """
    owned = load_managed_zcode_agents()
    pins = subagents or {}
    unknown = set(pins) - set(ZCODE_OVERRIDE_AGENTS)
    if unknown:
        die("built-in agent overrides accept names "
            + ", ".join(ZCODE_OVERRIDE_AGENTS)
            + " only, got: " + ", ".join(sorted(unknown)))
    if not pins and not owned:
        return []
    notes = []
    state = None
    if owned - set(pins):
        state = load_zcode_agents_state()
        overrides = state.setdefault("builtInModelOverrides", {})
        for agent in sorted(owned - set(pins)):
            if overrides.pop(agent, None) is not None:
                notes.append(f"released built-in agent '{agent}' (inherits session model)")
    if pins:
        if zcode_app_running():
            click.echo(
                "warning: ZCode appears to be running; if the Settings -> Subagents page is open,\n"
                "  saving there will overwrite this pin (re-run aweswitch apply to restore it)",
                err=True,
            )
        if state is None:
            state = load_zcode_agents_state()
        overrides = state.setdefault("builtInModelOverrides", {})
        for agent, ref in sorted(pins.items()):
            value = _zcode_override_value(ref)
            if overrides.get(agent) != value:
                overrides[agent] = value
                notes.append(f"pinned built-in agent '{agent}' -> {ref}")
    if notes:
        write_zcode_agents_state(state)
    set_managed_zcode_agents(set(pins))
    return notes


def zcode_user_agents_dir():
    """zcode's user-subagent markdown directory, ~/.zcode/agents.

    Derived from the config path the way the app derives it from its
    storage root: both live under the parent of the v2/ dir that holds
    config.json and agents-state.json.
    """
    return zcode_config_path().parent.parent / "agents"


def ensure_zcode_user_agents(subagents, release_missing=True):
    """Create, pin, release or delete user-subagent files to match the pin set.

    subagents maps agent name -> "profile/model" (from the config's global
    subagents.zcode section); the encoded custom:<provider>:<model> form
    zcode itself uses is written to the file's frontmatter model: line and
    nothing else is touched, so a user-authored name, description or
    prompt body is never reformatted. A declared agent whose file is
    missing is created from the generic template — only the model line
    differs between agents. Mirrors ensure_opencode_agents: with
    release_missing (the apply path) an agent aweswitch previously managed
    but absent from this map is removed (template-created file deleted,
    user-authored file only loses its model line and inherits the session
    model); the launch path never removes anything. Returns change notes.
    """
    agents_dir = zcode_user_agents_dir()
    created = load_created_zcode_user_agents()
    owned = load_managed_zcode_user_agents()
    changes = []
    if release_missing:
        for agent in sorted(owned - set(subagents)):
            path = agents_dir / f"{agent}.md"
            if agent in created:
                if path.exists():
                    path.unlink()
                    changes.append(f"deleted agent '{agent}' (created by aweswitch)")
                created.discard(agent)
            elif _edit_agent_model_line(path, None):
                changes.append(f"released agent '{agent}' (inherits session model)")
        owned = set()
    for agent, ref in sorted(subagents.items()):
        path = agents_dir / f"{agent}.md"
        if not path.exists():
            agents_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                ZCODE_AGENT_TEMPLATE.format(
                    name=agent,
                    model=ref.split("/", 1)[1],
                    value=_zcode_override_value(ref),
                ),
                encoding="utf-8",
            )
            created.add(agent)
            changes.append(f"created agent '{agent}' from template -> {ref}")
        elif _edit_agent_model_line(path, _zcode_override_value(ref)):
            changes.append(f"pinned agent '{agent}' -> {ref}")
    set_created_zcode_user_agents(created & set(subagents))
    set_managed_zcode_user_agents(owned | set(subagents))
    return changes


# Default model limits stamped onto entries we manage when the user didn't
# supply them in the profile. Mirrors what zcode writes for its own custom
# providers, so the model picker behaves the same as a hand-added entry.
ZCODE_DEFAULT_LIMIT_CONTEXT = 1000000
ZCODE_DEFAULT_LIMIT_OUTPUT = 128000

# zcode maps a thought-level variant onto request params — chat models send it
# as reasoning_effort, Responses models as reasoning.effort — but only for
# canonical effort names (none/minimal/low/medium/high/xhigh/max); any other
# variant name maps to nothing on the wire. "none" is the working disable: the
# request carries reasoning_effort "none" and the model answers without
# thinking (verified against bigmodel GLM, ark deepseek, sensenova, weixin and
# kimi; stepfun ignores the value and keeps thinking). Plain reasoning blocks
# are also the only form zcode preserves across its own config saves for
# custom providers — catalog-format specs are ignored on load and stripped on
# the next save. So the default fill is a plain block whose variants lead with
# "none"; the picker shows it as "None".
ZCODE_REASONING_VARIANTS = ("none", "low", "medium", "high", "xhigh", "max")
ZCODE_REASONING_DEFAULT_VARIANT = "medium"
# The pre-none fills selected max; the legacy recognizers below must keep
# matching that shape even though the default is now medium.
_LEGACY_DEFAULT_VARIANT = "max"
# The spec-shaped fill an unreleased build wrote under zcode.reasoning; inert
# in zcode and stripped on its next save, so it is migrated to the plain block.
ZCODE_REASONING_SPEC_LEVELS = ("off", "low", "medium", "high", "xhigh", "max")


def build_zcode_provider_entry(base_url, api_key, kind, name):
    """Build a fresh zcode provider entry owned by aweswitch."""
    return {
        "name": name,
        "kind": kind,
        "options": {
            "apiKey": api_key,
            "baseURL": base_url,
        },
        "enabled": True,
        "source": "custom",
    }


def _stamp_zcode_model_defaults(models_dict, model_ids):
    """Add the default limit/modalities stamp to the named models.

    zcode treats absent capability fields as "unsupported", so a bare entry
    hides text/image input even for multimodal models. Stamping
    text+image input, text output, and the default context/output window
    matches what zcode writes for its own custom providers — and only fills
    values the user didn't already set. Returns True when anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        if "limit" not in entry:
            entry["limit"] = {
                "context": ZCODE_DEFAULT_LIMIT_CONTEXT,
                "output": ZCODE_DEFAULT_LIMIT_OUTPUT,
            }
            changed = True
        if "modalities" not in entry:
            entry["modalities"] = {"input": ["text", "image"], "output": ["text"]}
            changed = True
        zcode_meta = entry.get("zcode")
        if not isinstance(zcode_meta, dict):
            zcode_meta = {}
            entry["zcode"] = zcode_meta
        if "modalitiesConfigured" not in zcode_meta:
            zcode_meta["modalitiesConfigured"] = True
            changed = True
    return changed


def _zcode_default_reasoning():
    """Build the plain reasoning block stamped onto managed chat models.

    Variants lead with "none" (the canonical effort name that actually turns
    thinking off on the wire) followed by the effort ladder, medium selected.
    """
    return {
        "enabled": True,
        "variants": list(ZCODE_REASONING_VARIANTS),
        "defaultVariant": ZCODE_REASONING_DEFAULT_VARIANT,
    }


def _legacy_zcode_reasoning_spec():
    """Reconstruct the catalog-format spec the unreleased build wrote under
    zcode.reasoning, so that exact shape can be recognized and migrated."""
    levels = {
        "off": {"openai-compatible": {
            "set": [{"path": ["thinking", "type"], "value": "disabled"}],
            "unset": [{"path": ["reasoningEffort"]}],
        }},
    }
    for effort in ZCODE_REASONING_SPEC_LEVELS[1:]:
        levels[effort] = {"openai-compatible": {
            "set": [{"path": ["reasoningEffort"], "value": effort}],
        }}
    return {
        "defaultLevel": _LEGACY_DEFAULT_VARIANT,
        "levels": levels,
    }


def _is_legacy_default_reasoning(reasoning):
    """Recognize aweswitch's own older plain fill: a block exactly equal to
    the pre-none default (low..max, max selected). Only that shape is
    migrated; anything else is the user's."""
    return (
        isinstance(reasoning, dict)
        and set(reasoning) == {"enabled", "variants", "defaultVariant"}
        and reasoning.get("enabled") is True
        and reasoning.get("variants") == list(ZCODE_REASONING_SPEC_LEVELS[1:])
        and reasoning.get("defaultVariant") == _LEGACY_DEFAULT_VARIANT
    )


def _is_legacy_reasoning_spec(zcode_meta):
    """Recognize the unreleased build's zcode.reasoning spec — inert in zcode
    (custom providers ignore catalog-format specs) and stripped by zcode's
    next config save, so aweswitch migrates its own shape to the plain block.
    A spec that is not exactly this shape is hand-written and stays."""
    return isinstance(zcode_meta, dict) and (
        zcode_meta.get("reasoning") == _legacy_zcode_reasoning_spec()
    )


def _stamp_zcode_reasoning(models_dict, model_ids):
    """Add the default reasoning block to the named models.

    Managed models get a fill-only default: none plus the
    low/medium/high/xhigh/max ladder with medium selected. A chat-completions
    model hides the thought-level picker without a block; a Responses model
    already shows zcode's native picker, and the same plain block is the shape
    zcode itself persists there, so stamping it gives both kinds the same
    think/off ladder. A hand-set block wins
    wholesale — a plain reasoning dict with its own variants list keeps the
    list verbatim (only missing enabled/defaultVariant siblings are filled),
    and a hand-written zcode.reasoning spec is never edited. reasoning: false
    or enabled: false (explicit opt-outs, both honored by zcode) is left
    alone. Two of aweswitch's own older fills are migrated in place: the
    plain low..max default gains the none level, and the unreleased build's
    zcode.reasoning spec is replaced by the plain block zcode actually keeps.
    Returns True when anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if not isinstance(entry, dict):
            continue
        reasoning = entry.get("reasoning")
        if reasoning is False or (
            isinstance(reasoning, dict) and reasoning.get("enabled") is False
        ):
            continue
        if _is_legacy_default_reasoning(reasoning):
            entry["reasoning"] = _zcode_default_reasoning()
            changed = True
            continue
        if isinstance(reasoning, dict) and "variants" in reasoning:
            if "enabled" not in reasoning:
                reasoning["enabled"] = True
                changed = True
            if "defaultVariant" not in reasoning:
                reasoning["defaultVariant"] = ZCODE_REASONING_DEFAULT_VARIANT
                changed = True
            continue
        zcode_meta = entry.get("zcode")
        if isinstance(zcode_meta, dict) and "reasoning" in zcode_meta:
            if _is_legacy_reasoning_spec(zcode_meta):
                del zcode_meta["reasoning"]
                if not zcode_meta:
                    del entry["zcode"]
                entry["reasoning"] = _zcode_default_reasoning()
                changed = True
            continue
        if "reasoningSpec" in entry:
            continue
        entry["reasoning"] = _zcode_default_reasoning()
        changed = True
    return changed


def _strip_zcode_model_kinds(models_dict, model_ids):
    """Drop per-model kind keys written by v0.5.8.

    zcode ignores a model-level kind (the transport kind is provider-level),
    so the keys are dead weight from a scheme that never took effect.
    Returns True when anything changed.
    """
    changed = False
    for model_id in model_ids:
        entry = models_dict.get(model_id)
        if isinstance(entry, dict) and "kind" in entry:
            del entry["kind"]
            changed = True
    return changed


def ensure_zcode_provider(base_url, api_key_ref, provider_name, kind, models,
                          display_name=None, prune=False):
    """Ensure provider+models exist in zcode config.json, synced to aweswitch.

    The provider entry is owned by aweswitch (its name is the profile name), so
    stale credentials, kind, and display names are updated to match the config
    instead of rejected. Launch is N/A (zcode is a desktop app); apply is the
    only call path, so the full model list always overwrites the entry's
    models — same as `sync_opencode_profiles(prune=True)`, including key
    order, which is the model-picker order. The provider's
    enabled flag is set to True and source to "custom" on every managed sync.
    Each managed model gets the default limit/modalities stamp unless the
    entry already declares one, plus the fill-only default reasoning block
    (none + low..max) — a chat model hides the thought-level picker without
    one, and a Responses model gets the same ladder so both kinds offer the
    same think/off control.
    Returns "created", "updated", or "unchanged".
    """
    name = display_name or provider_name
    zc_config = load_zcode_config()
    providers = zc_config["provider"]
    existing = providers.get(provider_name)
    status = "unchanged"

    if existing:
        if not isinstance(existing, dict):
            existing = {}
            providers[provider_name] = existing
        opts = existing.setdefault("options", {})
        if not isinstance(opts, dict):
            opts = {}
            existing["options"] = opts
        if opts.get("baseURL") != base_url:
            opts["baseURL"] = base_url
            status = "updated"
        if opts.get("apiKey") != api_key_ref:
            opts["apiKey"] = api_key_ref
            status = "updated"
        if existing.get("name") != name:
            existing["name"] = name
            status = "updated"
        if existing.get("kind") != kind:
            existing["kind"] = kind
            status = "updated"
        if existing.get("enabled") is not True:
            existing["enabled"] = True
            status = "updated"
        if existing.get("source") != "custom":
            existing["source"] = "custom"
            status = "updated"
        models_dict = existing.setdefault("models", {})
        if not isinstance(models_dict, dict):
            models_dict = {}
            existing["models"] = models_dict
        for model_id in models:
            if model_id not in models_dict:
                models_dict[model_id] = {"name": model_id}
                status = "updated"
            else:
                entry = models_dict[model_id]
                if not isinstance(entry, dict):
                    entry = {"name": model_id}
                    models_dict[model_id] = entry
                    status = "updated"
                elif "name" not in entry:
                    entry["name"] = model_id
                    status = "updated"
        if _stamp_zcode_model_defaults(models_dict, models):
            status = "updated"
        if _strip_zcode_model_kinds(models_dict, models):
            status = "updated"
        if _stamp_zcode_reasoning(models_dict, models):
            status = "updated"
        if prune:
            for model_id in [m for m in models_dict if m not in models]:
                del models_dict[model_id]
                status = "updated"
            # Key order is the picker order: a full sync makes the config's
            # order authoritative too, so reorder (per-model entries —
            # including hand-set values — ride along unchanged).
            if list(models_dict) != list(models):
                existing["models"] = {model_id: models_dict[model_id]
                                      for model_id in models}
                status = "updated"
        if status != "unchanged":
            write_zcode_config(zc_config)
    else:
        entry = build_zcode_provider_entry(base_url, api_key_ref, kind, name=name)
        entry["models"] = {model_id: {"name": model_id} for model_id in models}
        _stamp_zcode_model_defaults(entry["models"], models)
        _stamp_zcode_reasoning(entry["models"], models)
        providers[provider_name] = entry
        write_zcode_config(zc_config)
        status = "created"
    record_managed_zcode_provider(provider_name)
    return status


def build_zcode_specs(config, names=None):
    """Validate and materialize the zcode sync spec for every (or the named) profile.

    Pure: reads the aweswitch config, touches no files. Each spec is (name,
    base_url, api_key_ref, kind, models, display_name).
    """
    profiles = kind_group(config, "api").get("zcode", {})
    if not isinstance(profiles, dict):
        die("provider entries must be an object: api.zcode")
    specs = []
    for name in dict.fromkeys(names if names is not None else profiles):
        provider, kind, _ = profile_for(config, name)
        if provider != "zcode" or kind != "api":
            die(f"sync only supports zcode api profiles, got: {name} (provider={provider}, kind={kind})")
        profile_env = profiles.get(name, {}).get("env", {})
        base_url_raw = profile_env.get("ZCODE_BASE_URL")
        api_key_raw = profile_env.get("ZCODE_API_KEY")
        if not base_url_raw:
            die(f"ZCODE_BASE_URL is required for zcode profile: {name}")
        if not api_key_raw:
            die(f"ZCODE_API_KEY is required for zcode profile: {name}")
        if "ZCODE_KIND" in profile_env:
            die(f"ZCODE_KIND is no longer supported for {name}; use ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL")
        if "ZCODE_MODEL" in profile_env:
            die(f"ZCODE_MODEL is no longer supported for {name}; rename it to ZCODE_CHAT_MODEL")
        models_dict, kind = _resolve_zcode_models(
            profile_env.get("ZCODE_CHAT_MODEL"), profile_env.get("ZCODE_RESPONSES_MODEL"), name)
        specs.append((
            name,
            expand_value(base_url_raw, dict(os.environ)),
            _zcode_api_key_ref(api_key_raw),
            kind,
            list(models_dict),
            profile_env.get("ZCODE_NAME") or name,
        ))
    return specs


def sync_zcode_profiles(config, names=None):
    """Write every (or the named) zcode profile into zcode config.json.

    Replaces each provider entry (base URL, key ref, kind, display name) and
    its full model list so the file matches the aweswitch config — models
    removed from the config disappear from zcode too. Providers the config
    doesn't know about are left alone. All profiles are validated before
    anything is written. Subagent pins come from the config's top-level
    subagents.zcode section — global state, not per-profile — so every
    sync reconciles them: the two built-in names (general-purpose,
    Explore) rewrite the app's builtInModelOverrides, every other name
    rewrites a user-subagent markdown file in ~/.zcode/agents, pins a
    previous apply owned but the section no longer names are released, and
    every referenced profile's provider is ensured even when this sync
    didn't name it. Returns (profile, status, model_count, agent_notes)
    tuples.
    """
    specs = build_zcode_specs(config, names)
    if specs:
        load_zcode_config()
        load_managed_zcode_providers()
    pins = parse_subagent_pins(config, "zcode")
    builtin_pins = {agent: ref for agent, ref in pins.items()
                    if agent in ZCODE_OVERRIDE_AGENTS}
    user_pins = {agent: ref for agent, ref in pins.items()
                 if agent not in ZCODE_OVERRIDE_AGENTS}
    # The pins must resolve the moment they are written: every referenced
    # profile's provider is ensured even when this sync didn't name it.
    synced_names = {spec[0] for spec in specs}
    dep_names = subagent_pin_profiles(pins) - synced_names
    for name, base_url, api_key_ref, kind, models, display_name in \
            build_zcode_specs(config, sorted(dep_names)):
        ensure_zcode_provider(base_url, api_key_ref, name, kind, models,
                              display_name=display_name, prune=True)
    results = []
    for name, base_url, api_key_ref, kind, models, display_name in specs:
        results.append((
            name,
            ensure_zcode_provider(base_url, api_key_ref, name, kind, models,
                                  display_name=display_name, prune=True),
            len(models),
        ))
    agent_notes = (ensure_zcode_agent_overrides(builtin_pins)
                   + ensure_zcode_user_agents(user_pins))
    return [
        (name, status, model_count, agent_notes if name == results[0][0] else [])
        for name, status, model_count in results
    ]


def find_orphan_zcode_providers(config):
    """Return {name: entry} for aweswitch-written providers left in zcode config.

    An orphan is a provider no zcode profile in the aweswitch config backs
    anymore — typically a renamed or deleted profile. Ownership comes from a
    sidecar written whenever aweswitch manages a provider; shape guessing is
    deliberately avoided so a hand-written provider is never pruned.
    """
    managed = kind_group(config, "api").get("zcode") or {}
    providers = load_zcode_config()["provider"]
    owned = load_managed_zcode_providers()
    orphans = {}
    for name in owned:
        entry = providers.get(name)
        if name not in managed and isinstance(entry, dict):
            orphans[name] = entry
    return orphans


def plan_zcode_prune(config, prune, elsewhere=None):
    """Resolve apply's --prune value into a zcode {name: entry} deletion set.

    'orphans' contributes tracked providers no profile backs. 'all' and name
    lists are resolved by the shared planner; in a run that also prunes
    opencode, a name list entry missing here may resolve there (`elsewhere`)
    instead of erroring. No writes.
    """
    if prune is None:
        return {}
    if isinstance(prune, list):
        protected = [name for name in prune if name.startswith(ZCODE_BUILTIN_PROVIDER_PREFIX)]
        if protected:
            die(
                "--prune cannot remove zcode built-in providers: "
                + ", ".join(protected)
            )
    if prune == PRUNE_ORPHANS:
        targets = find_orphan_zcode_providers(config)
    else:
        targets = _plan_provider_prune(
            prune,
            providers=load_zcode_config()["provider"],
            backed=kind_group(config, "api").get("zcode") or {},
            path=zcode_config_path(),
            label="zcode",
            elsewhere=elsewhere,
        )
    for name in sorted(name for name in targets if name.startswith(ZCODE_BUILTIN_PROVIDER_PREFIX)):
        targets.pop(name)
        click.echo(f"Skipping protected zcode built-in provider '{name}'", err=True)
    return targets


def warn_zcode_orphans(config):
    """Report aweswitch-written providers no profile backs (renamed or deleted)."""
    orphans = find_orphan_zcode_providers(config)
    if not orphans:
        return
    for name, entry in sorted(orphans.items()):
        models = ", ".join(sorted(entry.get("models") or {})) or "no models"
        click.echo(
            f"warning: orphaned aweswitch provider '{name}' in zcode config ({models})",
            err=True,
        )
    click.echo(
        "  No aweswitch profile backs it (renamed or deleted?); the zcode GUI will still list it.\n"
        "  Prune with: aweswitch apply --zcode --prune orphans",
        err=True,
    )


def execute_zcode_prune(targets):
    """Delete the planned providers from the zcode config and the sidecar."""
    zc_config = load_zcode_config()
    providers = zc_config["provider"]
    for name in sorted(targets):
        if providers.pop(name, None) is None:
            continue
        click.echo(f"Pruned provider '{name}' from {zcode_config_path()}")
    write_zcode_config(zc_config)
    set_managed_zcode_providers(load_managed_zcode_providers() - set(targets))


def confirm_provider_prune(opencode_targets, zcode_targets):
    """Show every planned provider deletion and require explicit approval."""
    if not opencode_targets and not zcode_targets:
        return
    for name in sorted(opencode_targets):
        click.echo(
            f"Will prune provider '{name}' from {opencode_config_path()} "
            f"({_describe_provider_models(opencode_targets[name])})"
        )
    for name in sorted(zcode_targets):
        click.echo(
            f"Will prune provider '{name}' from {zcode_config_path()} "
            f"({_describe_provider_models(zcode_targets[name])})"
        )
    click.confirm("Continue pruning?", default=False, abort=True)


def opencode_data_path():
    return Path(os.environ.get("OPENCODE_DATA", "~/.local/share/opencode")).expanduser()


def opencode_session_last_model(session_id):
    """Return "provider/model" from a session's last user message in opencode's DB.

    The opencode TUI restores this model when resuming with -s, overriding the
    -m flag aweswitch passes. Best-effort: returns None when the DB, session,
    or model stamp is missing, so the launch path never blocks on it.
    """
    db = opencode_data_path() / "opencode.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.5)
        try:
            # opencode accepts partial session ids; mirror that with a prefix
            # lookup that must resolve to exactly one session.
            rows = conn.execute("SELECT id FROM session WHERE id = ?", (session_id,)).fetchall()
            if not rows:
                rows = conn.execute(
                    "SELECT id FROM session WHERE substr(id, 1, ?) = ?",
                    (len(session_id), session_id),
                ).fetchall()
            if len(rows) != 1:
                return None
            for (data,) in conn.execute(
                "SELECT data FROM message WHERE session_id = ? ORDER BY time_created DESC",
                (rows[0][0],),
            ):
                try:
                    message = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                model = message.get("model")
                if isinstance(model, dict) and model.get("providerID") and model.get("modelID"):
                    return f"{model['providerID']}/{model['modelID']}"
                return None
            return None
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None


def warn_opencode_session_model(user_args, provider_name, model):
    """Warn when -s resumes a session whose stored model differs from the launch model.

    Resuming restores the session's previous model and overrides -m, so the
    requested model only takes effect after switching it inside the TUI.
    """
    session_id = None
    for index, arg in enumerate(user_args):
        if arg in ("-s", "--session") and index + 1 < len(user_args):
            session_id = user_args[index + 1]
            break
        if arg.startswith("--session="):
            session_id = arg.partition("=")[2]
            break
    if not session_id:
        return
    last_model = opencode_session_last_model(session_id)
    if not last_model or last_model == f"{provider_name}/{model}":
        return
    click.echo(
        f"warning: opencode resumes {session_id} with its previous model ({last_model}) and ignores -m.\n"
        f"  To use {provider_name}/{model}, switch models inside the TUI (Tab) after it opens.",
        err=True,
    )


def generate_codex_config(provider_name, base_url):
    """Generate a minimal config.toml for a third-party Codex provider."""
    clean = re.sub(r"[^a-z0-9_]", "_", provider_name.lower()).strip("_") or "custom"
    return (
        f'model_provider = "{clean}"\n'
        f'disable_response_storage = true\n'
        f'\n'
        f'[model_providers.{clean}]\n'
        f'name = "{clean}"\n'
        f'base_url = "{base_url}"\n'
        f'wire_api = "responses"\n'
        f'requires_openai_auth = true\n'
    )


# The provider key codex's config uses for aweswitch-injected endpoints. Launch
# injects the same key via `-c model_providers.custom.*`, so apply keeps the
# two paths interchangeable.
CODEX_PROVIDER_KEY = "custom"

CODEX_CUSTOM_TABLE_RE = re.compile(rf"^\s*\[\s*model_providers\.{CODEX_PROVIDER_KEY}(\.|\s*\])")

# Codex's multi-agent settings live in the [agents] table; aweswitch manages
# only the default_subagent_model key inside it and never touches roles or
# other keys. TOML also allows a top-level dotted `agents.<key> = ...` form,
# so both shapes are handled to avoid leaving duplicates behind.
CODEX_AGENTS_TABLE_RE = re.compile(r"^\s*\[\s*agents\s*\]")
CODEX_AGENTS_KEY_RE = re.compile(r"^\s*default_subagent_model\s*=")
CODEX_AGENTS_DOTTED_KEY_RE = re.compile(r"^\s*agents\s*\.\s*default_subagent_model\s*=")
CODEX_AGENTS_DOTTED_ANY_RE = re.compile(r"^\s*agents\s*\.\s*[A-Za-z_]")


def _codex_header_mask(lines):
    """Per-line True when the line opens a TOML table.

    Lines inside multi-line strings (\"\"\" / ''') never count, so a string
    body that starts with '[' (e.g. config snippets inside
    developer_instructions) can't be mistaken for a table header. Quotes in
    comments and single-line strings are ignored.
    """
    mask, multiline = [], ""
    for line in lines:
        if multiline:
            mask.append(False)
            if multiline in line:
                multiline = ""
            continue
        mask.append(line.lstrip().startswith("["))
        quote, i, n = "", 0, len(line)
        while i < n:
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                if line.startswith(ch * 3, i):
                    if line.count(ch * 3) % 2 == 1:
                        multiline = ch * 3
                    break
                quote = ch
            elif ch == "#":
                break  # comment: the rest of the line is not code
            i += 1
    return mask


def write_codex_config(path, base_url, env_key, model=None):
    """Persist the third-party provider as codex's default in config.toml.

    Line-based TOML edit — the project targets py3.9 with no writer deps: the
    top-level model / model_provider / disable_response_storage assignments
    are updated in the header zone and the [model_providers.custom] table
    (including subtables) is removed and re-appended; everything else
    (mcp_servers, projects, ...) is preserved verbatim.
    """
    path = Path(path)
    top_keys = {
        "model_provider": f'"{CODEX_PROVIDER_KEY}"',
        "disable_response_storage": "true",
    }
    if model:
        top_keys["model"] = f'"{model}"'
    table = (
        f"[model_providers.{CODEX_PROVIDER_KEY}]\n"
        f'name = "{CODEX_PROVIDER_KEY}"\n'
        f'base_url = "{base_url}"\n'
        f'wire_api = "responses"\n'
        f'env_key = "{env_key}"\n'
    )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{k} = {v}\n" for k, v in top_keys.items()) + "\n" + table)
        return

    lines = path.read_text().splitlines(keepends=True)
    headers = _codex_header_mask(lines)

    # Drop the previous [model_providers.custom] block (header through any
    # subtables, stopping at the next unrelated table header).
    kept, skipping_custom = [], False
    for line, is_header in zip(lines, headers):
        if is_header:
            skipping_custom = bool(CODEX_CUSTOM_TABLE_RE.match(line))
            if skipping_custom:
                continue
        if not skipping_custom:
            kept.append(line)
    headers = _codex_header_mask(kept)

    # Update the top-level assignments inside the header zone; collect the
    # missing ones so they can be inserted before the first table.
    result, updated, header_zone, insert_at = [], set(), True, None
    for line, is_header in zip(kept, headers):
        if header_zone and is_header:
            header_zone = False
            insert_at = len(result)
        matched = False
        if header_zone:
            for key, value in top_keys.items():
                if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                    result.append(f"{key} = {value}\n")
                    updated.add(key)
                    matched = True
                    break
        if not matched:
            result.append(line)
    if header_zone:
        insert_at = len(result)
    missing = [f"{k} = {top_keys[k]}\n" for k in top_keys if k not in updated]
    if missing:
        result[insert_at:insert_at] = missing
    text = "".join(result)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + table)


def codex_subagent_model(profile_env, profile_name):
    """Return the profile's CODEX_SUBAGENT_MODEL pin (str) or None."""
    raw = profile_env.get("CODEX_SUBAGENT_MODEL")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        die(f"CODEX_SUBAGENT_MODEL must be a non-empty string for {profile_name}")
    value = raw.strip()
    if value.startswith("@"):
        die(
            f"CODEX_SUBAGENT_MODEL does not support @profile/model references for {profile_name}\n"
            f"  codex serves sub-agents through the profile's own endpoint — use a model id it serves"
        )
    return value


def _codex_key_value(line):
    return line.split("=", 1)[1].strip() if "=" in line else ""


def edit_codex_subagent_model(lines, value):
    """Insert, replace, or release agents.default_subagent_model in TOML lines.

    Companion to write_codex_config's line-based editing: everything outside
    the managed key is preserved verbatim. `value` (str) pins the key; None
    releases it, dropping an [agents] table that becomes empty. Returns
    (lines, note) where note describes the change or is None when the file
    already reflects the request.
    """
    headers = _codex_header_mask(lines)
    table_start = next(
        (i for i, (line, is_header) in enumerate(zip(lines, headers))
         if is_header and CODEX_AGENTS_TABLE_RE.match(line)),
        None)

    if table_start is not None:
        span_end = next((j for j in range(table_start + 1, len(lines)) if headers[j]), len(lines))
        key_idx = next(
            (j for j in range(table_start + 1, span_end) if CODEX_AGENTS_KEY_RE.match(lines[j])),
            None)
        if value is not None:
            wanted = f'default_subagent_model = "{value}"\n'
            if key_idx is not None:
                if lines[key_idx].strip() == wanted.strip():
                    return lines, None
                old = _codex_key_value(lines[key_idx])
                lines[key_idx] = wanted
                return lines, f"agents.default_subagent_model = {value} (overwrote {old})"
            lines[table_start + 1:table_start + 1] = [wanted]
            return lines, f"agents.default_subagent_model = {value} (sub-agents spawn on this model)"
        if key_idx is None:
            return lines, None
        del lines[key_idx]
        span_end -= 1
        if all(not lines[j].strip() for j in range(table_start + 1, span_end)):
            del lines[table_start]
        return lines, "released agents.default_subagent_model (sub-agents inherit the primary model)"

    # No [agents] table: handle the top-level dotted form, then create one.
    # Dotted keys only make sense in the header zone — an `agents.x = ...` line
    # inside another table belongs to that table and must not be touched.
    header_zone_end = next((j for j, is_header in enumerate(headers) if is_header), len(lines))
    dotted_idx = next(
        (i for i in range(header_zone_end) if CODEX_AGENTS_DOTTED_KEY_RE.match(lines[i])),
        None)
    if dotted_idx is not None:
        if value is None:
            del lines[dotted_idx]
            return lines, "released agents.default_subagent_model (sub-agents inherit the primary model)"
        wanted = f'agents.default_subagent_model = "{value}"\n'
        if lines[dotted_idx].strip() == wanted.strip():
            return lines, None
        old = _codex_key_value(lines[dotted_idx])
        lines[dotted_idx] = wanted
        return lines, f"agents.default_subagent_model = {value} (overwrote {old})"

    if value is None:
        return lines, None
    dotted_siblings = [
        i for i in range(header_zone_end) if CODEX_AGENTS_DOTTED_ANY_RE.match(lines[i])]
    if dotted_siblings:
        # Other dotted agents.* keys already define the table implicitly, so a
        # new [agents] header would be invalid TOML — stay in dotted form.
        insert_at = dotted_siblings[-1] + 1
        lines[insert_at:insert_at] = [f'agents.default_subagent_model = "{value}"\n']
        return lines, f"agents.default_subagent_model = {value} (sub-agents spawn on this model)"

    if lines and lines[-1].strip():
        lines.append("\n")
    lines.append(f"[agents]\ndefault_subagent_model = \"{value}\"\n")
    return lines, f"agents.default_subagent_model = {value} (sub-agents spawn on this model)"


def set_codex_subagent_model(path, value):
    """Apply an agents.default_subagent_model edit to config.toml; returns the note."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines, note = edit_codex_subagent_model(lines, value)
    path.write_text("".join(lines), encoding="utf-8")
    return note


def die(message) -> NoReturn:
    raise SystemExit(f"aweswitch: {message}")


def init_config(path):
    path = Path(path).expanduser()
    if path.exists():
        die(f"config already exists: {path}")
    if not TEMPLATE_PATH.exists():
        die(f"template not found: {TEMPLATE_PATH}")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE_PATH, path)


def load_config(path):
    path = Path(path).expanduser()
    if not path.exists():
        die(f"config not found: {path}\nrun: aweswitch config init")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(f"invalid config JSON at {path}: {exc}")
    if not isinstance(data.get("profiles"), dict):
        die("config must contain a profiles object")
    changed = migrate_profiles(data)
    changed |= migrate_subagents(data)
    if changed:
        backup = path.with_suffix(".json.bak")
        try:
            shutil.copy2(path, backup)
        except OSError as exc:
            die(f"failed to back up config before migration: {exc}")
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


# Pre-0.7 subagent pins lived in a profile's env under these keys.
SUBAGENT_ENV_KEYS = (
    ("opencode", "OPENCODE_SUBAGENT_MODEL"),
    ("zcode", "ZCODE_SUBAGENT_MODEL"),
)


def migrate_subagents(data):
    """Fold profile-env subagent pins into the top-level subagents section.

    Old pins lived in a profile's env (OPENCODE_SUBAGENT_MODEL /
    ZCODE_SUBAGENT_MODEL) as bare own-profile model IDs, "@profile/model"
    refs, or — zcode only — a scalar pinning both built-in agents to one
    model. Agent files outlive profiles, so the pins move to a section
    beside "profiles", each value rewritten as the explicit
    "profile/model-id" form the section uses. Returns True when the config
    changed (caller persists it).
    """
    api = data.get("profiles", {}).get("api")
    if not isinstance(api, dict):
        return False
    changed = False
    for target, key in SUBAGENT_ENV_KEYS:
        group = api.get(target)
        if not isinstance(group, dict):
            continue
        for profile_name, entry in group.items():
            env = entry.get("env") if isinstance(entry, dict) else None
            if not isinstance(env, dict) or env.get(key) is None:
                continue
            raw = env.pop(key)
            if isinstance(raw, dict):
                items = list(raw.items())
            elif target == "zcode" and isinstance(raw, str) and raw.strip():
                items = [(agent, raw) for agent in ZCODE_OVERRIDE_AGENTS]
            else:
                die(f"cannot migrate {key} for {profile_name}: expected a "
                    f"{{agent: model}} object"
                    + (" or a model ID" if target == "zcode" else ""))
            pins = {}
            for agent, ref in items:
                if (not isinstance(agent, str) or not agent.strip()
                        or not isinstance(ref, str) or not ref.strip()):
                    die(f"cannot migrate {key} entry for {profile_name}: "
                        f"{agent!r}: {ref!r}")
                ref = ref.strip()
                if ref.startswith("@"):
                    dep, _, model = ref[1:].partition("/")
                    if not dep or not model:
                        die(f"cannot migrate {key} entry for {profile_name}: {ref!r}")
                else:
                    dep, model = profile_name, ref
                pins[agent] = f"{dep}/{model}"
            section = data.setdefault("subagents", {})
            if not isinstance(section, dict):
                die('subagents must be an object: {"opencode": {...}, "zcode": {...}}')
            target_section = section.setdefault(target, {})
            if not isinstance(target_section, dict):
                die(f"subagents.{target} must be an object")
            target_section.update(pins)
            changed = True
    return changed


def migrate_profiles(data):
    """Fold the pre-0.4 provider-first layout into profiles.api, in place.

    v1: {"profiles": {"claude": {...}, "codex": {...}}}
    v2: {"profiles": {"api": {...}, "accounts": {...}}}

    Returns True when the config was rewritten (caller persists it). A file
    that mixes both layouts is rejected instead of guessed at.
    """
    profiles = data["profiles"]
    if not profiles:
        return False
    if not any(key in profiles for key in ("api", "accounts")):
        data["profiles"] = {"api": profiles}
        return True
    stale = [key for key in profiles if key not in ("api", "accounts")]
    if stale:
        die(
            "config mixes old and new profile layouts under 'profiles': "
            + ", ".join(sorted(stale))
            + "\n  Expected only 'api' and 'accounts'. Fix or remove the file, then retry."
        )
    return False


def kind_group(config, kind):
    """Return the provider->entries mapping for a profile kind."""
    key = "accounts" if kind == "account" else kind
    group = config.get("profiles", {}).get(key, {})
    if not isinstance(group, dict):
        die(f"profiles.{key} must be an object")
    return group


def load_claude_settings_env(path=None):
    path = claude_settings_path() if path is None else Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    env = data.get("env", {})
    if not isinstance(env, dict):
        return {}
    return {key: value for key, value in env.items() if isinstance(value, str)}


def expand_value(value, env):
    if not isinstance(value, str):
        return value

    def replace(match):
        name = match.group(1)
        if name not in env:
            die(
                f"required environment variable not set: {name}\n"
                f"  Add it to your shell config (e.g. ~/.zshrc or ~/.bashrc), then reload your shell."
            )
        return env[name]

    return ENV_REF_RE.sub(replace, value)


def profile_for(config, name):
    """Resolve a profile name to (provider, kind, entry).

    kind is "api" or "account". Names must be unique across both kinds and
    all providers; a name found twice is ambiguous.
    """
    matches = []
    for kind in PROFILE_KINDS:
        for provider, provider_entries in kind_group(config, kind).items():
            if not isinstance(provider_entries, dict):
                die(f"provider entries must be an object: {kind}.{provider}")
            entry = provider_entries.get(name)
            if entry is not None:
                matches.append((provider, kind, entry))

    if not matches:
        die(f"unknown profile: {name}\nrun: aweswitch list  # view available profiles")
    if len(matches) > 1:
        die(f"ambiguous profile: {name}")

    provider, kind, entry = matches[0]
    if not isinstance(entry, dict):
        die(f"profile must be an object: {provider}.{name}")
    return provider, kind, entry


def write_settings_file(data):
    settings_dir = Path(tempfile.gettempdir()) / "aweswitch"
    settings_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - TEMP_SETTINGS_TTL_S
    for old_path in settings_dir.glob("aweswitch-settings-*.json"):
        try:
            if old_path.stat().st_mtime < cutoff:
                old_path.unlink()
        except OSError:
            pass

    fd, path = tempfile.mkstemp(prefix="aweswitch-settings-", suffix=".json", dir=settings_dir)
    if os.name != "nt":
        os.chmod(path, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return Path(path)


def read_json_object(path, what):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(f"invalid JSON in {path} ({what}): {exc}")
    if not isinstance(data, dict):
        die(f"unexpected JSON in {path} ({what}): expected an object")
    return data


def write_secret_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)


def seed_claude_settings(source, destination):
    """Copy settings while dropping API-provider overrides for an OAuth account."""
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        shutil.copy2(source, destination)
        return
    if not isinstance(data, dict):
        shutil.copy2(source, destination)
        return
    env = data.get("env")
    if isinstance(env, dict):
        data = copy.deepcopy(data)
        data["env"] = {key: value for key, value in env.items() if not key.startswith("ANTHROPIC_")}
    destination.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def seed_codex_config(source, destination):
    """Copy config.toml without the selected third-party model provider."""
    text = source.read_text(encoding="utf-8")
    match = re.search(r'^\s*model_provider\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    if not match:
        shutil.copy2(source, destination)
        return

    provider = re.escape(match.group(1))
    provider_table = re.compile(rf"^\s*\[\s*model_providers\.{provider}(?:\.|\s*\])")
    table_header = re.compile(r"^\s*\[")
    model_provider = re.compile(r"^\s*model_provider\s*=")
    filtered = []
    skipping_provider_table = False
    for line in text.splitlines(keepends=True):
        if model_provider.match(line):
            continue
        if table_header.match(line):
            skipping_provider_table = bool(provider_table.match(line))
        if not skipping_provider_table:
            filtered.append(line)
    destination.write_text("".join(filtered), encoding="utf-8")


def ensure_account_dir(provider, name, blob, force=False):
    """Materialize an official account's runtime dir and return its path.

    Once the dir exists it is the source of truth: the CLI refreshes OAuth
    tokens in place, so an existing credentials file is never overwritten by
    the (possibly stale) config blob unless force=True. Companion config
    files (codex config.toml / claude settings.json) are seeded once from the
    user's live files so model and MCP settings carry over.
    """
    d = account_dir(provider, name)
    d.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(d, 0o700)
    cred_path = d / ACCOUNT_CRED_FILENAME[provider]
    if (force or not cred_path.exists()) and isinstance(blob, dict) and blob:
        write_secret_json(cred_path, blob)
    if provider == "codex":
        seed, src, seed_config = d / "config.toml", codex_config_path(), seed_codex_config
    else:
        seed, src, seed_config = d / "settings.json", claude_settings_path(), seed_claude_settings
    if not seed.exists() and src.exists():
        seed_config(src, seed)
    return d


CODEX_SESSION_SUBDIRS = ("sessions", "archived_sessions")


def share_sessions_enabled(config):
    value = config.get("share_sessions", False)
    if not isinstance(value, bool):
        die("config 'share_sessions' must be true or false")
    return value


def shared_sessions_root(provider):
    """Session pool shared by all of one provider's official accounts."""
    return accounts_root() / provider / ".shared"


def _points_at_session_pool(link, target):
    """True when LINK is a directory link (symlink, or Windows junction) to TARGET."""
    try:
        return link.exists() and Path(os.path.realpath(link)) == Path(os.path.realpath(target))
    except OSError:
        return False


def _is_dir_link(link):
    """True for a symlink, or a Windows junction (reparse point)."""
    if link.is_symlink():
        return True
    if os.name == "nt":
        try:
            return bool(os.lstat(link).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except OSError:
            return False
    return False


def _make_session_link(target, link):
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def _remove_session_link(link):
    # A junction reports is_symlink() False; os.rmdir removes the reparse
    # point without ever touching the target.
    if link.is_symlink():
        link.unlink()
    else:
        os.rmdir(link)


def _migrate_into_session_pool(src_dir, pool_dir):
    """Move every rollout file from SRC_DIR into POOL_DIR, date layout kept.

    Raises on the first OS error; the caller only replaces SRC_DIR with a link
    after a clean pass, so a partial migration simply retries on the next
    launch. Returns notes for the caller to print.
    """
    notes = []
    moved = 0
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_dir)
        dest = pool_dir / rel
        if dest.exists():
            if dest.stat().st_size == path.stat().st_size:
                path.unlink()
                notes.append(f"dropped duplicate session file {rel}")
            else:
                candidate, n = dest, 1
                while candidate.exists():
                    n += 1
                    candidate = dest.with_name(f"{dest.stem}-duplicate-{n}{dest.suffix}")
                shutil.move(str(path), str(candidate))
                notes.append(f"merged colliding session file as {candidate.name}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))
        moved += 1
    if moved:
        notes.append(f"moved {moved} session file(s) into the shared pool")
    for root, dirs, _files in os.walk(src_dir, topdown=False):
        for name in dirs:
            (Path(root) / name).rmdir()
    src_dir.rmdir()
    return notes


def _sync_session_dir_to_pool(home, subdir, pool, enabled, context):
    """Point HOME/subdir at POOL/subdir, or unlink again when disabled.

    One rollout dir of one codex home — an account dir, or codex's own
    default home. An existing real dir is migrated into the pool once, before
    it is replaced by the link; a link already pointing at the pool is left
    quiet. With the flag off, only links pointing at the pool are removed and
    pooled files stay there. Returns notes for the caller to print.
    """
    notes = []
    link = Path(home) / subdir
    target = pool / subdir
    if not enabled:
        if _points_at_session_pool(link, target):
            _remove_session_link(link)
            notes.append(
                f"share_sessions is off: unlinked {subdir}; pool files stay in {target}"
            )
        return notes
    if _points_at_session_pool(link, target):
        return notes
    target.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(pool, 0o700)
    if _is_dir_link(link):
        _remove_session_link(link)
        notes.append(f"replaced foreign {subdir} link")
    elif link.is_dir():
        try:
            notes += _migrate_into_session_pool(link, target)
        except OSError as exc:
            die(f"failed to share sessions for {context}: {exc}")
    link.parent.mkdir(parents=True, exist_ok=True)
    _make_session_link(target, link)
    notes.append(f"sharing {subdir} via {target}")
    return notes


def sync_account_session_dirs(provider, account_home, config):
    """Point an official account's rollout dirs at the provider-wide pool.

    With 'share_sessions' on, every codex account reads and writes the same
    pool, so a session recorded by one account can be resumed under another —
    rollout files carry no account identity, and codex hardcodes its session
    location to $CODEX_HOME/sessions, so a filesystem link is the only way to
    share. Claude accounts are left isolated for now (their session layout is
    not verified). Returns notes for the caller to print.
    """
    if provider != "codex":
        return []
    enabled = share_sessions_enabled(config)
    pool = shared_sessions_root(provider)
    notes = []
    for subdir in CODEX_SESSION_SUBDIRS:
        notes += _sync_session_dir_to_pool(account_home, subdir, pool, enabled, account_home)
    return notes


def codex_default_home():
    """Where codex records sessions outside an aweswitch account dir."""
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()


def sync_default_codex_sessions(config):
    """Point codex's own default home at the account session pool.

    Sessions recorded by plain `codex` or an api-profile launch land in the
    default home, not in any account dir; linking it into the pool makes
    those sessions resumable under every account — and pooled sessions
    resumable from plain codex. Same link/migrate/unlink contract as
    accounts. Returns notes for the caller to print.
    """
    enabled = share_sessions_enabled(config)
    pool = shared_sessions_root("codex")
    home = codex_default_home()
    notes = []
    for subdir in CODEX_SESSION_SUBDIRS:
        notes += _sync_session_dir_to_pool(home, subdir, pool, enabled, home)
    return notes


def profile_name_taken(config, name, ignore=None):
    """True when NAME is used by any profile other than `ignore` (kind, provider)."""
    for kind in PROFILE_KINDS:
        for provider, entries in kind_group(config, kind).items():
            if (kind, provider) == ignore:
                continue
            if isinstance(entries, dict) and name in entries:
                return True
    return False


def secure_config_file(path):
    if os.name != "nt":
        os.chmod(path, 0o600)


def save_account(path, provider, name, blob):
    """Store an account's credential blob under profiles.accounts.<provider>.<name>."""
    validate_profile_name(name, account=True)
    path = Path(path).expanduser()
    data = load_config(path)
    if profile_name_taken(data, name, ignore=("account", provider)):
        die(f"name already used: {name}")
    first_account = not kind_group(data, "account")
    accounts = data["profiles"].setdefault("accounts", {})
    accounts.setdefault(provider, {})[name] = {ACCOUNT_BLOB_KEY[provider]: blob}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    secure_config_file(path)
    if first_account:
        click.echo(
            f"Note: {path} now contains login credentials — keep it private "
            f"(permissions set to 600; do not commit or sync it publicly).",
            err=True,
        )


def build_claude_env(config, profile_name, base_env=None, claude_settings_env=None):
    """Build expanded env dict for a Claude profile, including _NAME variants.

    Every model-tier var (OPUS/SONNET/HAIKU/FABLE) the profile does not set is
    defaulted to ANTHROPIC_MODEL, and each gets a matching _NAME label. Without
    explicit values, Claude Code merges --settings with ~/.claude/settings.json
    and a stale tier->model mapping from a previous provider wins, so /model can
    resolve to a model the current provider doesn't serve (e.g. a minimax profile
    erroring with "selected model (mimo-v2.5)").
    """
    base_env = dict(os.environ if base_env is None else base_env)
    provider, kind, profile = profile_for(config, profile_name)
    if provider != "claude" or kind != "api":
        die(f"only claude api profiles are supported, got: provider={provider}, kind={kind}")
    profile_env = profile.get("env", {})
    if not profile_env.get("ANTHROPIC_BASE_URL"):
        die("ANTHROPIC_BASE_URL is required for claude profile")
    auth_token_raw = profile_env.get("ANTHROPIC_AUTH_TOKEN")
    if auth_token_raw and not ENV_REF_RE.fullmatch(auth_token_raw):
        click.echo(
            "  tip: ANTHROPIC_AUTH_TOKEN is a plain value — consider ${VAR_NAME} to keep the key out of the config file\n"
            "  Example: \"ANTHROPIC_AUTH_TOKEN\": \"${MY_API_KEY}\"",
            err=True,
        )
    settings_env = load_claude_settings_env() if claude_settings_env is None else claude_settings_env
    expansion_env = {**settings_env, **base_env}
    result = {key: expand_value(value, expansion_env) for key, value in profile_env.items()}

    # Default every unset tier to the main model so /model always resolves to a
    # model this provider serves, no matter which tier is selected.
    main_model = result.get("ANTHROPIC_MODEL")
    if main_model:
        for tier in CLAUDE_TIER_VARS:
            result.setdefault(tier, main_model)

    # Ensure _NAME variants are set so Claude Code /model picker shows the
    # correct label instead of a stale value from base settings.
    for tier in CLAUDE_TIER_VARS:
        name_key = f"{tier}_NAME"
        if tier in result:
            result.setdefault(name_key, result[tier])
        else:
            result[name_key] = "Not set"

    # CLAUDE_CODE_SUBAGENT_MODEL is the global default for Task-tool
    # subagents (and agent-teams teammates) and outranks per-agent
    # frontmatter. It merges like the tier vars, so an omitted key would let
    # a pin from a different provider leak through. "inherit" is Claude
    # Code's own fall-through value (normal per-agent resolution), so
    # emitting it keeps the profile authoritative without changing behavior.
    result.setdefault("CLAUDE_CODE_SUBAGENT_MODEL", "inherit")
    return result


def _normalize_models(raw, profile_name, key, required):
    """Normalize supported model shapes and reject entries selectors cannot use."""
    if isinstance(raw, dict) and raw:
        if not all(
            isinstance(model_id, str) and model_id.strip()
            and isinstance(display_name, str) and display_name.strip()
            for model_id, display_name in raw.items()
        ):
            die(f"{key} model IDs and display names must be non-empty strings for {profile_name}")
        return raw
    if isinstance(raw, list) and raw:
        if not all(isinstance(model_id, str) and model_id.strip() for model_id in raw):
            die(f"{key} model IDs and display names must be non-empty strings for {profile_name}")
        return {model_id: model_id for model_id in raw}
    if isinstance(raw, str) and raw.strip():
        return {model_id.strip(): model_id.strip() for model_id in raw.split(",") if model_id.strip()}
    if required:
        die(f"{key} is required for {profile_name}")
    return {}


def normalize_models(raw, profile_name, key):
    """Normalize a required model list (dict, list, or comma-separated str)."""
    return _normalize_models(raw, profile_name, key, required=True)


def normalize_models_opt(raw, profile_name="profile", key="OPENCODE_MODEL"):
    """Like normalize_models but returns {} instead of dying on empty/missing input."""
    return _normalize_models(raw, profile_name, key, required=False)


def select_model(models_dict, user_args, profile_name):
    """Select a model ID from the first positional arg or the first configured entry.

    Exact ID and exact display-name matches win first. If neither matches, IDs
    and display names are compared case-insensitively, then as case-insensitive
    substrings so short inputs like `GPT` can select `gpt-5.2-codex`.
    """
    if user_args:
        model = user_args[0]
        user_args = user_args[1:]
    else:
        model = next(iter(models_dict))
    if model in models_dict:
        return model, user_args

    matching_ids = [model_id for model_id, display_name in models_dict.items() if display_name == model]
    if not matching_ids:
        lowered = model.casefold()
        exact_matches = [
            model_id
            for model_id, display_name in models_dict.items()
            if model_id.casefold() == lowered or display_name.casefold() == lowered
        ]
        if len(exact_matches) == 1:
            return exact_matches[0], user_args
        if exact_matches:
            available = ", ".join(sorted(exact_matches))
            die(f"ambiguous model '{model}' for {profile_name}\n  Matching IDs: {available}")

        matching_ids = [
            model_id
            for model_id, display_name in models_dict.items()
            if lowered in model_id.casefold() or lowered in display_name.casefold()
        ]
    if len(matching_ids) == 1:
        return matching_ids[0], user_args
    if matching_ids:
        available = ", ".join(sorted(matching_ids))
        die(f"ambiguous model '{model}' for {profile_name}\n  Matching IDs: {available}")

    available = ", ".join(sorted(models_dict))
    die(f"unknown model '{model}' for {profile_name}\n  Available: {available}")


def prepare_run(config, profile_name, user_args, base_env=None, claude_settings_env=None, oc_providers=None):
    base_env = dict(os.environ if base_env is None else base_env)
    provider, kind, profile = profile_for(config, profile_name)
    profile_env = profile.get("env", {})
    env = dict(base_env)
    expansion_env = dict(base_env)
    oc_write_info = None
    account_info = None
    if kind == "account":
        if provider == "codex":
            env["CODEX_HOME"] = str(account_dir("codex", profile_name))
            argv = ["codex"]
        elif provider == "claude":
            env["CLAUDE_CONFIG_DIR"] = str(account_dir("claude", profile_name))
            # Claude Code defaults to the macOS Keychain on macOS; force file
            # credentials inside the account dir so the snapshot round-trips.
            env["CLAUDE_CODE_DONT_USE_KEYCHAIN"] = "1"
            argv = ["claude"]
        else:
            die(f"official accounts are not supported for {profile_name}: {provider}")
        argv += user_args
        account_info = {
            "provider": provider,
            "name": profile_name,
            "blob": profile.get(ACCOUNT_BLOB_KEY[provider]),
        }
    elif provider == "claude":
        argv = ["claude"]
        settings_env = build_claude_env(config, profile_name, base_env, claude_settings_env)
        if settings_env:
            settings_path = write_settings_file({"env": settings_env})
            argv += ["--settings", str(settings_path)]
        argv += user_args
    elif provider == "codex":
        base_url_raw = profile_env.get("OPENAI_BASE_URL")
        api_key_raw = profile_env.get("OPENAI_API_KEY")
        if not base_url_raw:
            die(f"OPENAI_BASE_URL is required for codex profile: {profile_name}")
        if not api_key_raw:
            die(f"OPENAI_API_KEY is required for codex profile: {profile_name}")
        # OPENAI_MODEL is optional: without it the profile only switches the API
        # source (legacy behavior). With it, the first positional arg selects the
        # model, same convention as opencode profiles.
        model = None
        if profile_env.get("OPENAI_MODEL"):
            models_dict = normalize_models(profile_env["OPENAI_MODEL"], profile_name, "OPENAI_MODEL")
            model, user_args = select_model(models_dict, user_args, profile_name)
        base_url = expand_value(base_url_raw, expansion_env)
        api_key = expand_value(api_key_raw, expansion_env)
        argv = ["codex"]
        if model:
            argv += ["-c", f'model="{model}"']
        argv += ["-c", f'model_provider="custom"']
        # codex >= 0.150 rejects providers without a non-empty name.
        argv += ["-c", f'model_providers.custom.name="{CODEX_PROVIDER_KEY}"']
        argv += ["-c", f'model_providers.custom.base_url="{base_url}"']
        argv += ["-c", f'model_providers.custom.wire_api="responses"']
        argv += ["-c", f'model_providers.custom.env_key="OPENAI_API_KEY"']
        argv += ["-c", f'disable_response_storage=true']
        subagent = codex_subagent_model(profile_env, profile_name)
        if subagent:
            argv += ["-c", f'agents.default_subagent_model="{subagent}"']
        env["OPENAI_API_KEY"] = api_key
        argv += user_args
    elif provider == "opencode":
        base_url_raw = profile_env.get("OPENCODE_BASE_URL")
        api_key_raw = profile_env.get("OPENCODE_API_KEY")
        if not base_url_raw:
            die(f"OPENCODE_BASE_URL is required for opencode profile: {profile_name}")
        if not api_key_raw:
            die(f"OPENCODE_API_KEY is required for opencode profile: {profile_name}")
        models_dict, responses_models = _merge_opencode_models(profile_env, profile_name)
        # First positional arg is the model name; default to first in dict
        model, user_args = select_model(models_dict, user_args, profile_name)
        warn_opencode_session_model(user_args, profile_name, model)
        base_url = expand_value(base_url_raw, expansion_env)
        # Keep an env reference in opencode.json so the actual key is never written to disk.
        api_key_ref = _opencode_api_key_ref(api_key_raw)
        # Agent pins are global config state (subagents.opencode), not
        # per-profile: launch writes them additively — release is apply's
        # job — so they resolve the moment the session starts.
        subagents = parse_subagent_pins(config, "opencode")
        dep_names = sorted(subagent_pin_profiles(subagents) - {profile_name})
        oc_write_info = {
            "base_url": base_url,
            "api_key_ref": api_key_ref,
            "provider_name": profile_name,
            "model": model,
            # The full model list: the launch write registers every model the
            # profile serves, so a subagent pin on a non-session model (e.g.
            # primary glm-5.2, explore pinned to glm-5.1) resolves even when
            # the user never ran apply.
            "models": models_dict,
            "display_name": profile_env.get("OPENCODE_NAME") or profile_name,
            "model_display_name": models_dict.get(model, model),
            "responses_models": list(responses_models),
            "subagents": subagents,
            # Pins may reference other profiles' providers; carry their full
            # write specs so run_profile can ensure them before the pins are
            # applied.
            "deps": [
                {
                    "base_url": dep_base_url,
                    "api_key_ref": dep_api_key_ref,
                    "provider_name": dep_name,
                    "models": dict(dep_models),
                    "display_name": dep_display_name,
                    "responses_models": list(dep_responses),
                }
                for dep_name, dep_base_url, dep_api_key_ref, dep_models,
                    dep_display_name, dep_responses
                in (build_opencode_specs(config, dep_names) if dep_names else [])
            ],
        }
        argv = ["opencode", "-m", f"{profile_name}/{model}"]
        argv += user_args
    elif provider == "zcode":
        die(
            f"zcode is a desktop GUI app and does not support launch mode.\n"
            f"  Use 'aweswitch apply {profile_name}' to write the profile into\n"
            f"  ~/.zcode/v2/config.json, then open the zcode app to activate it."
        )
    else:
        die(f"unsupported provider for {profile_name}: {provider}")

    return argv, env, oc_write_info, account_info


def redact(data):
    redacted = copy.deepcopy(data)

    # Account blobs are live OAuth tokens: mask them whole rather than hoping
    # every nested key matches the secret-name heuristic below.
    accounts = redacted.get("profiles", {}).get("accounts")
    if isinstance(accounts, dict):
        for provider_accounts in accounts.values():
            if isinstance(provider_accounts, dict):
                for entry in provider_accounts.values():
                    if isinstance(entry, dict):
                        for key in ACCOUNT_BLOB_KEY.values():
                            if key in entry:
                                entry[key] = "<redacted>"

    def walk(value, key=""):
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                if SECRET_RE.search(child_key) and isinstance(child_value, str):
                    value[child_key] = "<redacted>"
                else:
                    walk(child_value, child_key)
        elif isinstance(value, list):
            for item in value:
                walk(item, key)

    walk(redacted)
    return redacted


def _format_usage_timestamp(value):
    """Format a Unix timestamp as a local datetime string, or pass through."""
    if isinstance(value, (int, float)) and value > 1_000_000_000:
        from datetime import datetime
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _format_usage_value(value):
    """Recursively format usage data, turning reset timestamps into local time."""
    if isinstance(value, dict):
        return {
            key: (_format_usage_timestamp(val) if key == "reset_unix_timestamp"
                  else _format_usage_value(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_format_usage_value(item) for item in value]
    return _format_usage_timestamp(value)


def _render_usage_block(key, value, indent=2):
    """Render a single usage field for human output."""
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return f"{prefix}{key}: {{}}"
        lines = [f"{prefix}{key}:"]
        for child_key, child_value in value.items():
            lines.append(_render_usage_block(child_key, child_value, indent + 2))
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{prefix}{key}: []"
        lines = [f"{prefix}{key}:"]
        for i, item in enumerate(value):
            lines.append(_render_usage_block(f"[{i}]", item, indent + 2))
        return "\n".join(lines)
    return f"{prefix}{key}: {value}"


def _usage_progress(used_percent, width=20):
    """Return ``(bar, remaining_percent)`` where the bar reflects remaining quota."""
    remaining = 100.0 - float(used_percent)
    remaining = max(0.0, min(100.0, remaining))
    filled = int(round((remaining / 100.0) * width))
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return bar, int(round(remaining))


def _usage_window_label(label, window):
    """Derive a friendly limit name from the window label and its span."""
    span = window.get("window_minutes")
    base = label
    if isinstance(base, str) and base.startswith("additional:"):
        base = base.split(":", 1)[1]
    if isinstance(scan := span, (int, float)) and not isinstance(scan, bool):
        if scan >= 43200:
            return "30-day limit"
        if scan >= 10080:
            return "Weekly limit"
        if scan >= 1440:
            return "Daily limit"
        hours = round(scan / 60.0)
        if hours < 1:
            return f"{round(scan / 60.0, 1)}h limit"
        return f"{hours}h limit"
    if base:
        return base[:1].upper() + base[1:]
    return "limit"


def _usage_reset_text(reset_ts):
    """Format a reset Unix timestamp as a compact local time hint."""
    if not (isinstance(reset_ts, (int, float)) and not isinstance(reset_ts, bool)):
        return None
    if reset_ts <= 1_000_000_000:
        return None
    from datetime import datetime
    target = datetime.fromtimestamp(reset_ts)
    clock = target.strftime("%H:%M")
    if target.date() == datetime.now().date():
        return f"resets {clock}"
    return f"resets {clock} on {target.day} {target.strftime('%b')}"


def _render_usage_window_bar(label, window):
    """Render one quota window as a labeled progress bar."""
    name = _usage_window_label(label if isinstance(label, str) else str(label), window or {})
    used = (window or {}).get("used_percentage")
    prefix = f"{name}:".ljust(14)
    if isinstance(used, (int, float)) and not isinstance(used, bool):
        bar, remaining = _usage_progress(used)
        body = f"[ {bar} ] {remaining}% left"
    else:
        body = "[ .... ]"
    line = f"  {prefix} {body}"
    reset_text = _usage_reset_text((window or {}).get("reset_unix_timestamp"))
    if reset_text:
        line += f" ({reset_text})"
    return line


def _render_usage_visual(account_name, usage):
    """Render a normalized usage payload with progress bars."""
    lines = [f"{account_name}:"]
    plan = usage.get("plan")
    if isinstance(plan, str) and plan.strip():
        lines.append(f"  Plan: {plan}")
    for label, window in usage.get("windows", {}).items():
        lines.append(_render_usage_window_bar(label, window if isinstance(window, dict) else {}))
    for key, value in usage.items():
        if key in ("plan", "windows"):
            continue
        if value in ({}, [], None):
            continue
        lines.append(_render_usage_block(key, value, 2))
    return "\n".join(lines)


def _format_human_usage(account_name, usage_data):
    """Render usage data as human-readable lines.

    A normalized quota payload (dict with a ``windows`` mapping) is drawn as
    labeled progress bars; any other shape falls back to the generic nested
    renderer so unusual payloads still surface their fields.
    """
    if isinstance(usage_data, dict) and isinstance(usage_data.get("windows"), dict):
        return _render_usage_visual(account_name, usage_data)
    formatted = _format_usage_value(usage_data)
    lines = [f"{account_name}:"]
    for key, value in formatted.items():
        lines.append(_render_usage_block(key, value, 2))
    return "\n".join(lines)


def _render_usage_error(account_name, error):
    """Render a per-account usage error for human output."""
    return f"{account_name}: error: {error}"


def _redact_usage_data(data):
    """Redact sensitive fields from usage data for JSON output."""
    if not isinstance(data, dict):
        return data
    result = {}
    for key, value in data.items():
        if SECRET_RE.search(key) and isinstance(value, str):
            result[key] = "<redacted>"
        elif isinstance(value, dict):
            result[key] = _redact_usage_data(value)
        elif isinstance(value, list):
            result[key] = [
                _redact_usage_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _get_usage_module():
    """Lazily load the usage module so command tests can replace its transport."""
    import importlib
    return importlib.import_module("aweswitch.usage")


def command_list(config):
    providers = set()
    for kind in PROFILE_KINDS:
        for provider, provider_entries in kind_group(config, kind).items():
            if not isinstance(provider_entries, dict):
                die(f"provider entries must be an object: {kind}.{provider}")
            providers.add(provider)
    for provider in sorted(providers):
        for kind in PROFILE_KINDS:
            entries = kind_group(config, kind).get(provider, {})
            for name in sorted(entries):
                if kind == "api":
                    label = profile_model_label(provider, entries[name])
                else:
                    label = "official login"
                print(f"{name}\t{provider}\t{kind}\t{label}")


def profile_model_label(provider, profile):
    env = profile.get("env", {})
    if provider == "claude":
        return env.get("ANTHROPIC_MODEL", "?")
    if provider == "codex":
        models = env.get("OPENAI_MODEL")
        if isinstance(models, dict):
            return ", ".join(sorted(models)) if models else env.get("OPENAI_BASE_URL", "?")
        if isinstance(models, list):
            return ", ".join(models) if models else env.get("OPENAI_BASE_URL", "?")
        if isinstance(models, str) and models.strip():
            return models.strip()
        return env.get("OPENAI_BASE_URL", "?")
    if provider == "opencode":
        models = env.get("OPENCODE_MODEL") or env.get("OPENCODE_RESPONSES_MODEL")
        if isinstance(models, dict):
            return ", ".join(sorted(models)) if models else "?"
        if isinstance(models, list):
            return ", ".join(models) if models else "?"
        if isinstance(models, str):
            parts = [m.strip() for m in models.split(",")]
            return ", ".join(p for p in parts if p) or "?"
        return "?"
    if provider == "zcode":
        models = env.get("ZCODE_CHAT_MODEL") or env.get("ZCODE_RESPONSES_MODEL")
        if isinstance(models, dict):
            return ", ".join(sorted(models)) if models else "?"
        if isinstance(models, list):
            return ", ".join(models) if models else "?"
        if isinstance(models, str):
            parts = [m.strip() for m in models.split(",")]
            return ", ".join(p for p in parts if p) or "?"
        return "?"
    return "?"


def command_show(config, name):
    _, kind, profile = profile_for(config, name)
    if kind == "account":
        # The whole entry is an OAuth credential blob; mask it entirely.
        print(json.dumps({key: "<redacted>" for key in profile}, indent=2))
        return
    print(json.dumps(redact(profile), indent=2))


def editor_argv(editor, path):
    return [*shlex.split(editor, posix=(os.name != "nt")), str(path)]


CLAUDE_PROJECTS_DIR = Path("~/.claude/projects").expanduser()


def _bookmark_worker(start_time, category, profile, title):
    """Poll for a new session file and bookmark it."""
    try:
        aweshelf_bin = shutil.which("aweshelf")
        if not aweshelf_bin:
            return

        for _ in range(30):
            time.sleep(2)
            if not CLAUDE_PROJECTS_DIR.exists():
                continue

            for jsonl_path in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
                if "subagents" in jsonl_path.parts:
                    continue
                try:
                    if jsonl_path.stat().st_mtime < start_time:
                        continue
                except OSError:
                    continue

                session_id = jsonl_path.stem
                cmd = [aweshelf_bin, "bookmark", session_id, "-c", category, "--profile", profile]
                if title:
                    cmd += ["-t", title]
                try:
                    subprocess.run(cmd, timeout=10, capture_output=True)
                except Exception:
                    pass
                return
    except Exception:
        pass


def _auto_bookmark(category, profile, title=None):
    """Spawn a detached worker to auto-bookmark the session after Claude creates it.

    On POSIX the launch path os.execvpe()s the agent, which destroys every
    thread in the process — a background thread would die before its first
    poll. Fork a detached child instead; it survives the exec. On Windows the
    agent runs via subprocess.run(), which keeps this process (and its
    threads) alive, so a daemon thread is enough.
    """
    start = time.time()
    if os.name == "nt":
        threading.Thread(
            target=_bookmark_worker,
            args=(start, category, profile, title),
            daemon=True,
        ).start()
        return
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            _bookmark_worker(start, category, profile, title)
        except BaseException:
            pass
        finally:
            os._exit(0)


def exec_agent(argv, env):
    if os.name == "nt":
        # On Windows, CreateProcess (which subprocess.run uses) does not
        # perform PATHEXT resolution for a bare command name, and it
        # cannot execute .ps1 scripts directly. Resolve the command via
        # shutil.which (which honors PATHEXT), then re-route .ps1 hits
        # through PowerShell. .exe / .cmd / .bat can be exec'd as-is.
        resolved = shutil.which(argv[0], path=env.get("PATH"))
        if resolved:
            if resolved.lower().endswith(".ps1"):
                pwsh = (
                    shutil.which("powershell", path=env.get("PATH"))
                    or shutil.which("powershell.exe", path=env.get("PATH"))
                    or "powershell.exe"
                )
                argv = [pwsh, "-NoLogo", "-ExecutionPolicy", "Bypass",
                        "-File", resolved, *argv[1:]]
            else:
                argv = [resolved, *argv[1:]]
        try:
            result = subprocess.run(argv, env=env)
            sys.exit(result.returncode)
        except FileNotFoundError:
            die(f"command not found: {argv[0]}")
        except OSError as exc:
            die(f"failed to run {argv[0]}: {exc}")
    else:
        try:
            os.execvpe(argv[0], argv, env)
        except FileNotFoundError:
            die(f"command not found: {argv[0]}")
        except OSError as exc:
            die(f"failed to run {argv[0]}: {exc}")


def save_profile(path, name, env_vars, provider="claude"):
    validate_profile_name(name)
    path = Path(path).expanduser()
    data = load_config(path)
    if profile_name_taken(data, name):
        die(f"profile already exists: {name}")
    profile = {"env": {k: v for k, v in env_vars.items() if v}}
    data["profiles"].setdefault("api", {}).setdefault(provider, {})[name] = profile
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def command_config(argv):
    path = config_path()
    subcommand = argv[0] if argv else "path"

    if subcommand == "path":
        print(path)
    elif subcommand == "show":
        print(json.dumps(redact(load_config(path)), indent=2))
    elif subcommand == "init":
        init_config(path)
        print(path)
    elif subcommand == "edit":
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            init_config(path)
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or shutil.which("nano")
        if not editor:
            die(f"no EDITOR set; edit config manually: {path}")
        argv = editor_argv(editor, path)
        if os.name == "nt":
            result = subprocess.run(argv)
            sys.exit(result.returncode)
        else:
            try:
                os.execvp(argv[0], argv)
            except FileNotFoundError:
                die(f"editor not found: {argv[0]}")
    else:
        die(f"unknown config command: {subcommand}")


class ProfileGroup(click.Group):
    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if not args:
                raise
            profile_name = args[0]
            ctx.meta["profile_name"] = profile_name
            command = self.get_command(ctx, "__profile__")
            return profile_name, command, args[1:]


@click.group(
    cls=ProfileGroup,
    name="aweswitch",
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Agent profile switcher for launching isolated runtime configs.\n\nSupported providers: claude, codex, opencode, zcode. Official accounts\n(claude/codex OAuth logins) are managed with `aweswitch account` and launch\nthrough private per-account config dirs.\n\nLaunch: aweswitch <profile> [-c CATEGORY] [-t TITLE] [extra args...]\n\nApply: aweswitch apply [profiles...] writes persistent defaults into each\nagent's own config (claude settings.json / codex config.toml / opencode\nopencode.json / zcode config.json). A bare `aweswitch apply` bulk-syncs\nevery opencode and zcode profile; --opencode / --zcode narrow it to one.\n\nBookmark (requires aweshelf): -c tags the session with a category and -t sets\na custom title. A background process auto-bookmarks the session once it starts.\nInstall aweshelf: pip3 install aweshelf. If aweshelf is not installed,\n-c and -t are ignored with a warning.",
)
@click.version_option(__version__, "-v", "--version", message="%(version)s")
def cli():
    pass


@cli.command("list")
def list_profiles():
    """List configured profiles."""
    command_list(load_config(config_path()))


@cli.command()
@click.argument("profile")
def show(profile):
    """Show one profile with secrets redacted."""
    command_show(load_config(config_path()), profile)


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
def config():
    """Manage aweswitch config."""


@config.command("path")
def config_path_command():
    """Print config path."""
    click.echo(config_path())


@config.command("show")
def config_show_command():
    """Show config with secrets redacted."""
    click.echo(json.dumps(redact(load_config(config_path())), indent=2))


@config.command("edit")
def config_edit_command():
    """Open config in $VISUAL, $EDITOR, or nano."""
    command_config(["edit"])


@config.command("init")
def config_init_command():
    """Create the default config."""
    init_config(config_path())
    click.echo(config_path())


@config.command("backup")
@click.option("--force", "-f", is_flag=True, help="Overwrite an existing backup.")
def config_backup_command(force):
    """Back up ~/.claude/settings.json and print the backup path.

    The printed path can be passed to `aweswitch config restore` later.
    """
    settings_path = claude_settings_path()
    backup_path = settings_path.with_suffix(".json.bak")
    if not settings_path.exists():
        die(f"no settings file found: {settings_path}")
    if backup_path.exists() and not force:
        click.echo("Note: backup already exists, not overwritten. Use --force to overwrite.")
    else:
        try:
            shutil.copy2(settings_path, backup_path)
        except OSError as exc:
            die(f"failed to create backup {backup_path}: {exc}")
    click.echo(backup_path)


@config.command("restore")
@click.argument("backup_file", required=False)
def config_restore_command(backup_file):
    """Restore ~/.claude/settings.json from BACKUP_FILE (default: settings.json.bak)."""
    settings_path = claude_settings_path()
    backup_path = Path(backup_file) if backup_file else settings_path.with_suffix(".json.bak")
    if not backup_path.exists():
        die(f"no such backup file: {backup_path}")
    shutil.copy2(backup_path, settings_path)
    click.echo(f"Restored {settings_path} from {backup_path}.")
    click.echo("Restart your session for changes to take effect.")


@cli.command("init")
def init_command():
    """Create the default config."""
    init_config(config_path())
    click.echo(config_path())


@cli.command("self-update")
@click.option("--check", is_flag=True, help="Show versions without updating.")
def self_update_command(check):
    """Update aweswitch to the latest version."""
    try:
        latest = get_pypi_latest()
    except Exception as e:
        raise SystemExit(f"Failed to check PyPI: {e}")
    if _version_gte(__version__, latest):
        click.echo(f"aweswitch is up to date ({__version__}).")
        return
    click.echo(f"Current: {__version__}  Latest: {latest}")
    if check:
        return

    if Path(sys.prefix, "pyvenv.cfg").exists() and "pipx" in sys.prefix:
        cmd = [shutil.which("pipx") or "pipx", "upgrade", "aweswitch"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "aweswitch"]

    click.echo(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        click.echo("Done. Restart aweswitch to use the new version.")
    else:
        raise SystemExit(result.returncode)


@cli.command("add")
def add_command():
    """Interactively add a new profile."""
    path = config_path()
    load_config(path)

    kind = click.prompt("Type", type=click.Choice(["api", "official"]))
    if kind == "official":
        provider = click.prompt("Provider", type=click.Choice(ACCOUNT_PROVIDERS))
        name = click.prompt("Account name")
        method = click.prompt(
            "Method",
            type=click.Choice(["login", "import"]),
            default="login",
        )
        if method == "login":
            login_account(path, provider, name)
        else:
            import_account(path, provider, name)
        return

    provider = click.prompt("Provider", type=click.Choice(["claude", "codex", "opencode", "zcode"]))
    name = click.prompt("Profile name")

    if provider == "opencode":
        base_url = click.prompt("OPENCODE_BASE_URL")
        auth_var = click.prompt("OPENCODE_API_KEY env var name (saved as ${VAR_NAME})")
        auth_token = f"${{{auth_var}}}"
        models_str = click.prompt("OPENCODE_MODEL (comma-separated, e.g. glm-5.1,glm-5.2)")
        models_dict = {m.strip(): m.strip() for m in models_str.split(",") if m.strip()}

        env_vars = {
            "OPENCODE_BASE_URL": base_url,
            "OPENCODE_API_KEY": auth_token,
            "OPENCODE_MODEL": models_dict,
        }
        save_profile(path, name, env_vars, provider=provider)
        click.echo(f"Profile '{name}' added.")
    elif provider == "zcode":
        base_url = click.prompt("ZCODE_BASE_URL")
        auth_var = click.prompt("ZCODE_API_KEY env var name (saved as ${VAR_NAME})")
        auth_token = f"${{{auth_var}}}"
        chat_str = click.prompt("ZCODE_CHAT_MODEL chat models (comma-separated, optional)", default="", show_default=False)
        responses_str = click.prompt("ZCODE_RESPONSES_MODEL response models (comma-separated, optional)", default="", show_default=False)
        models_dict = {m.strip(): m.strip() for m in chat_str.split(",") if m.strip()}
        responses = [m.strip() for m in responses_str.split(",") if m.strip()]
        if not models_dict and not responses:
            die("ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL is required")
        if models_dict and responses:
            die("zcode supports one API format per provider; use ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL, not both")
        name_val = click.prompt("ZCODE_NAME (display name, optional, Enter to skip)", default="", show_default=False)

        env_vars = {
            "ZCODE_BASE_URL": base_url,
            "ZCODE_API_KEY": auth_token,
        }
        if models_dict:
            env_vars["ZCODE_CHAT_MODEL"] = models_dict
        else:
            env_vars["ZCODE_RESPONSES_MODEL"] = responses
        if name_val.strip():
            env_vars["ZCODE_NAME"] = name_val.strip()
        save_profile(path, name, env_vars, provider=provider)
        click.echo(f"Profile '{name}' added.")
    elif provider == "claude":
        base_url = click.prompt("ANTHROPIC_BASE_URL")
        auth_var = click.prompt("ANTHROPIC_AUTH_TOKEN env var name (saved as ${VAR_NAME})")
        auth_token = f"${{{auth_var}}}"
        model = click.prompt("ANTHROPIC_MODEL")
        haiku_model = click.prompt("ANTHROPIC_DEFAULT_HAIKU_MODEL (optional, press Enter to skip)", default="", show_default=False)
        sonnet_model = click.prompt("ANTHROPIC_DEFAULT_SONNET_MODEL (optional, press Enter to skip)", default="", show_default=False)

        env_vars = {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
            "ANTHROPIC_MODEL": model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": haiku_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": sonnet_model,
        }
        save_profile(path, name, env_vars, provider=provider)
        click.echo(f"Profile '{name}' added.")
    else:
        base_url = click.prompt("OPENAI_BASE_URL")
        auth_var = click.prompt("OPENAI_API_KEY env var name (saved as ${VAR_NAME})")
        auth_token = f"${{{auth_var}}}"
        models_str = click.prompt("OPENAI_MODEL (comma-separated, Enter to skip)", default="", show_default=False)

        env_vars = {
            "OPENAI_BASE_URL": base_url,
            "OPENAI_API_KEY": auth_token,
        }
        if models_str.strip():
            env_vars["OPENAI_MODEL"] = {m.strip(): m.strip() for m in models_str.split(",") if m.strip()}
        save_profile(path, name, env_vars, provider=provider)
        click.echo(f"Profile '{name}' added.")



def _mask_value(key, value):
    """Mask values that look like secrets for display."""
    if not isinstance(value, str):
        return value
    if SECRET_RE.search(key) and len(value) > 8:
        return value[:4] + "***"
    return value


def apply_claude_profile(config, profile, force, prepared=None):
    """Write a claude profile's env into ~/.claude/settings.json (one active at a time)."""
    settings_path = claude_settings_path()
    if prepared is not None:
        settings_data = copy.deepcopy(prepared["settings_data"])
        expanded_env = prepared["expanded_env"]
    elif settings_path.exists():
        try:
            settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            die(f"invalid JSON in {settings_path}")
        if not isinstance(settings_data, dict):
            die(f"unexpected JSON in {settings_path}: expected an object at the top level")
        if not isinstance(settings_data.get("env", {}), dict):
            die(f"'env' in {settings_path} must be an object")
        expanded_env = build_claude_env(config, profile)
    else:
        settings_data = {}
        expanded_env = build_claude_env(config, profile)

    # Backup: only on first apply, or when --force is used.
    backup_path = settings_path.with_suffix(".json.bak")
    backed_up = False
    if settings_path.exists():
        if not backup_path.exists() or force:
            try:
                shutil.copy2(settings_path, backup_path)
            except OSError as exc:
                die(f"failed to create backup {backup_path}: {exc}")
            backed_up = True

    current_env = dict(settings_data.get("env", {}))
    for key in CLAUDE_AUTH_KEYS:
        if key not in expanded_env and key in current_env:
            click.echo(f"  Removed stale {key} (not in new profile)", err=True)
            current_env.pop(key)
    settings_data["env"] = {**current_env, **expanded_env}
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings_data, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(settings_path, 0o600)

    click.echo(f"Applied {profile} to {settings_path}")
    for key, value in sorted(expanded_env.items()):
        click.echo(f"  {key:42s} → {_mask_value(key, value)}")
    if backed_up:
        click.echo(f"Backup: {backup_path}")
    elif backup_path.exists():
        click.echo(f"Note: backup already exists, not overwritten. Use --force to overwrite.")
    click.echo("Restart your session or use /model to pick the new model.")


def apply_codex_profile(config, profile_name, force):
    """Write a codex profile's provider and model into ~/.codex/config.toml."""
    _, _, entry = profile_for(config, profile_name)
    profile_env = entry.get("env", {})
    base_url_raw = profile_env.get("OPENAI_BASE_URL")
    api_key_raw = profile_env.get("OPENAI_API_KEY")
    if not base_url_raw:
        die(f"OPENAI_BASE_URL is required for codex profile: {profile_name}")
    if not api_key_raw:
        die(f"OPENAI_API_KEY is required for codex profile: {profile_name}")
    base_url = expand_value(base_url_raw, dict(os.environ))
    # Point env_key at the referenced shell variable when the profile uses a
    # ${VAR} ref, so codex reads the key the user already exports. Plain keys
    # can't be persisted safely — fall back to OPENAI_API_KEY and warn.
    ref = ENV_REF_RE.fullmatch(api_key_raw) if isinstance(api_key_raw, str) else None
    if ref:
        env_key = ref.group(1)
    else:
        env_key = "OPENAI_API_KEY"
        click.echo(
            "  tip: OPENAI_API_KEY is a plain value — export $OPENAI_API_KEY for codex, or use a\n"
            "  ${VAR_NAME} reference in the profile so codex reads the key from that variable.",
            err=True,
        )
    model = None
    if profile_env.get("OPENAI_MODEL"):
        models_dict = normalize_models(profile_env["OPENAI_MODEL"], profile_name, "OPENAI_MODEL")
        model = next(iter(models_dict))
    subagent = codex_subagent_model(profile_env, profile_name)

    settings_path = codex_config_path()
    backup_path = settings_path.with_suffix(".toml.bak")
    backed_up = False
    if settings_path.exists():
        if not backup_path.exists() or force:
            try:
                shutil.copy2(settings_path, backup_path)
            except OSError as exc:
                die(f"failed to create backup {backup_path}: {exc}")
            backed_up = True

    write_codex_config(settings_path, base_url, env_key, model)
    note = set_codex_subagent_model(settings_path, subagent)

    click.echo(f"Applied {profile_name} to {settings_path}")
    click.echo(f"  model_provider = {CODEX_PROVIDER_KEY} ({base_url})")
    if model:
        click.echo(f"  model = {model}")
    else:
        click.echo("  model = (unchanged — profile has no OPENAI_MODEL)")
    if note:
        click.echo(f"  {note}")
    click.echo(f"  env_key = {env_key} (codex reads this env var at runtime)")
    if backed_up:
        click.echo(f"Backup: {backup_path}")
    elif backup_path.exists():
        click.echo("Note: backup already exists, not overwritten. Use --force to overwrite.")
    click.echo("Restart codex for changes to take effect.")


def preflight_apply(config, resolved):
    """Validate every requested apply before the first target file is changed."""
    prepared = {}
    has_opencode = False
    has_zcode = False
    for name, provider, kind, entry in resolved:
        if kind == "account":
            die(f"accounts are launch-only: {name}")
        if provider not in ("claude", "codex", "opencode", "zcode"):
            die(f"unsupported provider for {name}: {provider}")
        profile_env = entry.get("env", {})
        if not isinstance(profile_env, dict):
            die(f"profile env must be an object: {provider}.{name}")

        if provider == "claude":
            expanded_env = build_claude_env(config, name)
            settings_path = claude_settings_path()
            if settings_path.exists():
                try:
                    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    die(f"invalid JSON in {settings_path}")
                if not isinstance(settings_data, dict):
                    die(f"unexpected JSON in {settings_path}: expected an object at the top level")
                if not isinstance(settings_data.get("env", {}), dict):
                    die(f"'env' in {settings_path} must be an object")
            else:
                settings_data = {}
            prepared[name] = {
                "expanded_env": expanded_env,
                "settings_data": settings_data,
            }
        elif provider == "codex":
            base_url = profile_env.get("OPENAI_BASE_URL")
            api_key = profile_env.get("OPENAI_API_KEY")
            if not base_url:
                die(f"OPENAI_BASE_URL is required for codex profile: {name}")
            if not api_key:
                die(f"OPENAI_API_KEY is required for codex profile: {name}")
            expand_value(base_url, dict(os.environ))
            if profile_env.get("OPENAI_MODEL"):
                normalize_models(profile_env["OPENAI_MODEL"], name, "OPENAI_MODEL")
            codex_subagent_model(profile_env, name)
            path = codex_config_path()
            if path.exists():
                try:
                    path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    die(f"invalid UTF-8 in {path}")
        elif provider == "opencode":
            base_url = profile_env.get("OPENCODE_BASE_URL")
            api_key = profile_env.get("OPENCODE_API_KEY")
            if not base_url:
                die(f"OPENCODE_BASE_URL is required for opencode profile: {name}")
            if not api_key:
                die(f"OPENCODE_API_KEY is required for opencode profile: {name}")
            oc_models, _ = _merge_opencode_models(profile_env, name)
            parse_subagent_pins(config, "opencode")
            expand_value(base_url, dict(os.environ))
            has_opencode = True
        else:
            base_url = profile_env.get("ZCODE_BASE_URL")
            api_key = profile_env.get("ZCODE_API_KEY")
            if not base_url:
                die(f"ZCODE_BASE_URL is required for zcode profile: {name}")
            if not api_key:
                die(f"ZCODE_API_KEY is required for zcode profile: {name}")
            if "ZCODE_KIND" in profile_env:
                die(f"ZCODE_KIND is no longer supported for {name}; use ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL")
            if "ZCODE_MODEL" in profile_env:
                die(f"ZCODE_MODEL is no longer supported for {name}; rename it to ZCODE_CHAT_MODEL")
            zc_models, _kind = _resolve_zcode_models(
                profile_env.get("ZCODE_CHAT_MODEL"),
                profile_env.get("ZCODE_RESPONSES_MODEL"), name,
            )
            parse_subagent_pins(config, "zcode")
            expand_value(base_url, dict(os.environ))
            expand_value(api_key, dict(os.environ))
            has_zcode = True

    if has_opencode:
        load_opencode_config()
        load_managed_opencode_providers()
    if has_zcode:
        load_zcode_config()
        load_managed_zcode_providers()
    return prepared


@cli.command("apply")
@click.argument("profiles", nargs=-1)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing backup.")
@click.option("--opencode", is_flag=True,
              help="Apply every OpenCode profile (bulk only makes sense there).")
@click.option("--zcode", is_flag=True,
              help="Apply every zcode profile (bulk only — zcode is a desktop app).")
@click.option("--prune", "prune_raw", default=None,
              metavar="orphans|all|NAME[,NAME...]",
              help="Remove providers no aweswitch profile backs: 'orphans' "
                   "removes tracked leftovers only; 'all' removes every "
                   "unbacked provider (hand-written ones included); or list "
                   "provider names to remove exactly those. Applies to "
                   "opencode and zcode.")
@click.option("--dry-run", is_flag=True,
              help="Preview the OpenCode sync and prune plan without "
                   "writing (requires a prune flag).")
def apply_command(profiles, force, opencode, zcode, prune_raw, dry_run):
    """Apply profiles as persistent defaults in each agent's config.

    Claude -> env in ~/.claude/settings.json. Codex -> provider and model in
    ~/.codex/config.toml. OpenCode -> provider entry with its full model list
    in ~/.config/opencode/opencode.json (overwritten if the provider exists,
    added if missing). zcode -> provider entry with its full model list in
    ~/.zcode/v2/config.json (zcode is a desktop GUI app; no launch mode).

    Claude and Codex keep a single active default, so at most one profile of
    each may be applied per call; OpenCode and zcode profiles coexist, so
    several may be applied at once — or every one of them in one bulk sync:
    a bare `aweswitch apply` does every OpenCode profile then every zcode
    profile, and --opencode / --zcode narrow the bulk to one agent.

    OpenCode/zcode prunes are opt-in via --prune: 'orphans' removes tracked
    providers no profile backs, 'all' removes every unbacked provider
    (hand-written ones included), or a name list removes exactly those;
    --dry-run previews the plan (OpenCode side only). A prune never leaves
    the default model pointing at a deleted provider.

    Subagent model pins live in the config's top-level "subagents" section
    ({"opencode": {...}, "zcode": {...}}) as {agent: "profile/model"} and
    ride along with every sync: opencode rewrites the named agents'
    frontmatter model line; zcode routes its two built-in names
    (general-purpose, Explore) to the app's builtInModelOverrides and every
    other name to a user-subagent markdown file in ~/.zcode/agents. Pins a
    previous apply owned but the section no longer names are released —
    the agent falls back to inheriting the session/primary model.
    """
    config = load_config(config_path())
    names = list(profiles)

    # A bare `apply` defaults to the both-agents bulk sync: every OpenCode
    # profile, then every zcode profile.
    if not names and not opencode and not zcode:
        opencode = zcode = True
    if (opencode or zcode) and names:
        die("pick one: --opencode/--zcode (bulk) or explicit profile names, not both")
    prune = _parse_prune(prune_raw)
    prune_requested = prune is not None
    if dry_run and not prune_requested:
        die("--dry-run previews pruning; add --prune orphans|all|NAME,...")
    if dry_run and zcode and not opencode:
        die("--dry-run previews OpenCode pruning only (this run has no OpenCode part)")

    if opencode or zcode:
        # Bulk sync. Plan every prune before the first write so a bad --prune
        # name dies with nothing on disk changed; in a both-agents run a name
        # may live in either config, so each plan skips names the other one
        # owns. An empty side dies in a one-agent run but is skipped with a
        # note in a both-agents run; nothing at all on either side dies here.
        both = opencode and zcode
        oc_profiles = kind_group(config, "api").get("opencode", {})
        zc_profiles = kind_group(config, "api").get("zcode", {})
        if both and not oc_profiles and not zc_profiles:
            die(
                "nothing to apply\n"
                "run: aweswitch apply <profile> ... | --opencode | --zcode"
            )
        oc_targets = {}
        zc_targets = {}
        if opencode:
            oc_targets = plan_opencode_prune(
                config, prune,
                elsewhere=load_zcode_config()["provider"] if zcode else None)
        if zcode:
            zc_targets = plan_zcode_prune(
                config, prune,
                elsewhere=load_opencode_config()["provider"] if opencode else None)

        if not dry_run:
            confirm_provider_prune(oc_targets, zc_targets)

        if opencode:
            if not oc_profiles:
                if not both:
                    die("no opencode profiles found\nrun: aweswitch apply <profile>")
                click.echo("no opencode profiles found, skipping")
            elif dry_run:
                preview_opencode_prune(build_opencode_specs(config), oc_targets, config)
            else:
                for name, status, model_count, agent_notes in sync_opencode_profiles(config):
                    click.echo(f"{name}: {status} ({model_count} models)")
                    for note in agent_notes:
                        click.echo(f"  {note}")
                click.echo(f"Synced to {opencode_config_path()}")
                if oc_targets:
                    execute_opencode_prune(config, oc_targets)
                elif not prune_requested:
                    warn_opencode_orphans(config)
                warn_opencode_stale_agents()

        if zcode:
            if dry_run:
                # Reached only in a both-agents run (a lone --zcode --dry-run
                # died above): the prune plan was validated, but the preview
                # renderer is OpenCode-only.
                if zc_profiles:
                    click.echo("no zcode prune preview; run without --dry-run to prune zcode")
                else:
                    click.echo("no zcode profiles found, skipping")
            elif not zc_profiles:
                if not both:
                    die("no zcode profiles found\nrun: aweswitch apply <profile>")
                click.echo("no zcode profiles found, skipping")
            else:
                for name, status, model_count, agent_notes in sync_zcode_profiles(config):
                    click.echo(f"{name}: {status} ({model_count} models)")
                    for note in agent_notes:
                        click.echo(f"  {note}")
                click.echo(f"Synced to {zcode_config_path()}")
                if zc_targets:
                    execute_zcode_prune(zc_targets)
                elif not prune_requested:
                    warn_zcode_orphans(config)
        return

    resolved = [(name, *profile_for(config, name)) for name in names]
    if sum(1 for _, provider, kind, _ in resolved if (provider, kind) == ("claude", "api")) > 1:
        die("apply one claude profile at a time (settings.json holds a single active profile)")
    if sum(1 for _, provider, kind, _ in resolved if (provider, kind) == ("codex", "api")) > 1:
        die("apply one codex profile at a time (config.toml holds a single active provider)")
    oc_names = [name for name, provider, _, _ in resolved if provider == "opencode"]
    zc_names = [name for name, provider, _, _ in resolved if provider == "zcode"]
    if prune is not None and not oc_names and not zc_names:
        die("--prune needs an opencode or zcode profile in this apply run")
    if dry_run and not oc_names:
        die("--dry-run previews OpenCode pruning only (this run has no OpenCode profile)")
    # Plan every prune before the first write so a bad --prune name dies with
    # nothing on disk changed. A --prune name list may resolve in either
    # participating config, so each plan skips names the other one owns.
    opencode_prune_targets = {}
    zcode_prune_targets = {}
    if oc_names:
        elsewhere = load_zcode_config()["provider"] if zc_names else None
        opencode_prune_targets = plan_opencode_prune(config, prune, elsewhere=elsewhere)
    if zc_names:
        elsewhere = load_opencode_config()["provider"] if oc_names else None
        zcode_prune_targets = plan_zcode_prune(config, prune, elsewhere=elsewhere)
    if dry_run:
        preview_opencode_prune(
            build_opencode_specs(config, oc_names),
            opencode_prune_targets,
            config)
        return
    confirm_provider_prune(opencode_prune_targets, zcode_prune_targets)
    prepared = preflight_apply(config, resolved)
    applied_opencode = False
    applied_zcode = False
    for name, provider, kind, _ in resolved:
        if provider == "claude":
            apply_claude_profile(config, name, force, prepared=prepared.get(name))
        elif provider == "codex":
            apply_codex_profile(config, name, force)
        elif provider == "opencode":
            _, status, model_count, agent_notes = sync_opencode_profiles(config, [name])[0]
            click.echo(f"{name}: {status} ({model_count} models) -> {opencode_config_path()}")
            for note in agent_notes:
                click.echo(f"  {note}")
            applied_opencode = True
        elif provider == "zcode":
            _, status, model_count, agent_notes = sync_zcode_profiles(config, [name])[0]
            click.echo(f"{name}: {status} ({model_count} models) -> {zcode_config_path()}")
            for note in agent_notes:
                click.echo(f"  {note}")
            applied_zcode = True
        else:
            die(f"unsupported provider for {name}: {provider}")
    if applied_opencode:
        if opencode_prune_targets:
            execute_opencode_prune(config, opencode_prune_targets)
        elif not prune_requested:
            warn_opencode_orphans(config)
        warn_opencode_stale_agents()
    if applied_zcode:
        if zcode_prune_targets:
            execute_zcode_prune(zcode_prune_targets)
        elif not prune_requested:
            warn_zcode_orphans(config)


@cli.command("usage", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("accounts", nargs=-1)
@click.option("--all-codex", is_flag=True, help="Select every Codex official account.")
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON.")
@click.pass_context
def usage_command(ctx, accounts, all_codex, json_output):
    """Show quota usage for Codex official accounts.

    ACCOUNTS are one or more Codex official account names. Combine with
    --all-codex to include every configured Codex official account.
    """
    config = load_config(config_path())

    if accounts and all_codex:
        die("pass account names or --all-codex, not both")

    resolved = []
    if all_codex:
        codex_accounts = kind_group(config, "account").get("codex", {})
        for name in sorted(codex_accounts):
            resolved.append((name, "codex", "account", codex_accounts[name]))
        if not resolved:
            click.echo(
                "No Codex official accounts found. Add one with: "
                "aweswitch account login codex <name>"
            )
            ctx.exit(0)
    else:
        if not accounts:
            click.echo(
                "No account selector given.\n"
                "\n"
                "Usage examples:\n"
                "  aweswitch usage work              # show usage for one Codex official account\n"
                "  aweswitch usage --all-codex       # show usage for every Codex official account\n"
            )
            ctx.exit(0)
        seen = set()
        for name in accounts:
            if name in seen:
                continue
            seen.add(name)
            provider, kind, entry = profile_for(config, name)
            if kind != "account":
                die(f"'{name}' is an API profile; usage reads Codex official accounts only")
            if provider != "codex":
                die(
                    f"'{name}' is a {provider} official account; "
                    "usage reads Codex official accounts only"
                )
            resolved.append((name, provider, kind, entry))

    if not resolved:
        click.echo("No Codex official accounts selected.")
        ctx.exit(0)

    usage_mod = _get_usage_module()
    results = []
    any_failed = False

    for name, provider, kind, entry in resolved:
        blob = entry.get(ACCOUNT_BLOB_KEY["codex"], {})
        runtime_path = account_dir("codex", name) / ACCOUNT_CRED_FILENAME["codex"]
        try:
            credentials = usage_mod.load_codex_credentials(runtime_path, blob)
            usage_data = usage_mod.fetch_codex_usage(credentials)
            results.append({"account": name, "usage": usage_data})
        except usage_mod.UsageError as exc:
            results.append({"account": name, "error": str(exc)})
            any_failed = True
        except Exception:
            results.append({"account": name, "error": "Unexpected error fetching quota data."})
            any_failed = True

    if json_output:
        output = []
        for item in results:
            obj = {"account": item["account"]}
            if "error" in item:
                obj["error"] = item["error"]
            else:
                obj["usage"] = _redact_usage_data(item["usage"])
            output.append(obj)
        click.echo(json.dumps(output, indent=2))
    else:
        for item in results:
            if "error" in item:
                click.echo(_render_usage_error(item["account"], item["error"]))
            else:
                click.echo(_format_human_usage(item["account"], item["usage"]))

    if any_failed:
        ctx.exit(1)


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
def account():
    """Manage official-login accounts (Claude Code / Codex OAuth).

    Accounts launch like profiles (aweswitch <name>) but run through a
    private config dir, so several official accounts can be used side by
    side. See `aweswitch account login` to add one.
    """


def import_account(path, provider, name):
    """Save an official account from the CLI's live credentials."""
    load_config(path)
    live = live_credentials_path(provider)
    if not live.exists():
        die(
            f"no live credentials found at {live}\n"
            f"  Log in with the CLI first, or use: aweswitch account login {provider} {name}"
        )
    save_account(path, provider, name, read_json_object(live, "live credentials"))
    click.echo(f"Account '{name}' added ({provider}). Launch it with: aweswitch {name}")


def login_account(path, provider, name):
    """Run the CLI's own OAuth login inside the account dir and capture it."""
    data = load_config(path)
    existing = kind_group(data, "account").get(provider, {}).get(name)
    if existing is None and profile_name_taken(data, name):
        die(f"name already used: {name}")
    blob = existing.get(ACCOUNT_BLOB_KEY[provider]) if isinstance(existing, dict) else None
    d = ensure_account_dir(provider, name, blob)
    for note in sync_account_session_dirs(provider, d, data):
        click.echo(note)
    if provider == "codex":
        for note in sync_default_codex_sessions(data):
            click.echo(note)
    cred_path = d / ACCOUNT_CRED_FILENAME[provider]
    backup_path = cred_path.with_name(f".{cred_path.name}.login-backup")
    if cred_path.exists():
        if backup_path.exists():
            backup_path.unlink()
        cred_path.replace(backup_path)

    def restore_previous_credentials():
        if cred_path.exists():
            cred_path.unlink()
        if backup_path.exists():
            backup_path.replace(cred_path)

    env = dict(os.environ)
    if provider == "codex":
        env["CODEX_HOME"] = str(d)
        argv = ["codex", "login"]
        click.echo(f"Starting codex login for account '{name}' ...")
    else:
        env["CLAUDE_CONFIG_DIR"] = str(d)
        env["CLAUDE_CODE_DONT_USE_KEYCHAIN"] = "1"
        argv = ["claude"]
        click.echo(f"Starting claude for account '{name}' — run /login inside, then exit.")
    try:
        try:
            result = subprocess.run(argv, env=env)
        except FileNotFoundError:
            die(f"command not found: {argv[0]}")
        except OSError as exc:
            die(f"failed to run {argv[0]}: {exc}")
        if result.returncode != 0 or not cred_path.exists():
            die(f"no credentials captured at {cred_path} (login exited with code {result.returncode})")
        captured = read_json_object(cred_path, "captured credentials")
        save_account(path, provider, name, captured)
    except BaseException:
        restore_previous_credentials()
        raise
    if backup_path.exists():
        backup_path.unlink()
    click.echo(f"Account '{name}' saved. Launch it with: aweswitch {name}")


@account.command("add")
@click.argument("provider", type=click.Choice(ACCOUNT_PROVIDERS))
@click.argument("name")
def account_add_command(provider, name):
    """Save the currently logged-in official account as NAME.

    Imports the CLI's live credentials (~/.codex/auth.json or
    ~/.claude/.credentials.json). Claude Code on macOS usually keeps login
    in the Keychain instead; use `aweswitch account login` there.
    """
    import_account(config_path(), provider, name)


@account.command("login")
@click.argument("provider", type=click.Choice(ACCOUNT_PROVIDERS))
@click.argument("name")
def account_login_command(provider, name):
    """Log in to an official account NAME and capture its credentials.

    Runs the CLI's own login flow inside the account's private config dir,
    then stores the resulting credentials in the aweswitch config.
    """
    login_account(config_path(), provider, name)


@account.command("sync")
@click.argument("provider", type=click.Choice(ACCOUNT_PROVIDERS))
@click.argument("name")
def account_sync_command(provider, name):
    """Refresh NAME's stored credentials from its runtime dir.

    The CLI refreshes OAuth tokens inside the account dir at launch; sync
    copies the refreshed credentials back into the config file.
    """
    path = config_path()
    data = load_config(path)
    entry = kind_group(data, "account").get(provider, {}).get(name)
    if not isinstance(entry, dict):
        die(f"unknown account: {name}\nrun: aweswitch list  # view available profiles")
    cred_path = account_dir(provider, name) / ACCOUNT_CRED_FILENAME[provider]
    if not cred_path.exists():
        die(
            f"no runtime credentials at {cred_path}\n"
            f"  Launch or log in to the account first: aweswitch account login {provider} {name}"
        )
    save_account(path, provider, name, read_json_object(cred_path, "runtime credentials"))
    click.echo(f"Account '{name}' synced from {cred_path}")


@account.command("remove")
@click.argument("provider", type=click.Choice(ACCOUNT_PROVIDERS))
@click.argument("name")
@click.option("--purge", is_flag=True, help="Also delete the account's runtime directory.")
def account_remove_command(provider, name, purge):
    """Remove account NAME from the config."""
    path = config_path()
    data = load_config(path)
    provider_accounts = kind_group(data, "account").get(provider, {})
    if name not in provider_accounts:
        die(f"unknown account: {name}\nrun: aweswitch list  # view available profiles")
    # Resolve and validate before mutating config: an unsafe legacy name must
    # never turn a failed purge into a partially removed account entry.
    d = account_dir(provider, name)
    del provider_accounts[name]
    if not provider_accounts:
        kind_group(data, "account").pop(provider, None)
        if not kind_group(data, "account"):
            data["profiles"].pop("accounts", None)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if purge and d.exists():
        shutil.rmtree(d)
        click.echo(f"Removed account '{name}' and deleted {d}")
    else:
        click.echo(f"Removed account '{name}' (runtime dir kept: {d}; use --purge to delete)")


@click.command(
    "__profile__",
    hidden=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("-c", "--category", default=None, help="Bookmark category.")
@click.option("-t", "--title", default=None, help="Bookmark title.")
@click.pass_context
def run_profile(ctx, category, title):
    profile_name = ctx.parent.meta.get("profile_name")
    if not profile_name:
        die("missing profile name")
    if category:
        if not shutil.which("aweshelf"):
            click.echo("warning: aweshelf not found; -c/-t ignored. Install: pip3 install aweshelf (https://github.com/wehuman01/aweshelf)", err=True)
        else:
            _auto_bookmark(category, profile_name, title=title)
    config = load_config(config_path())
    run_argv, run_env, oc_write_info, account_info = prepare_run(config, profile_name, ctx.args)
    if oc_write_info is not None:
        for note in write_opencode_launch(oc_write_info):
            click.echo(note)
    provider, _, _ = profile_for(config, profile_name)
    if provider == "codex":
        for note in sync_default_codex_sessions(config):
            click.echo(note)
    if account_info is not None:
        d = ensure_account_dir(account_info["provider"], account_info["name"], account_info["blob"])
        for note in sync_account_session_dirs(account_info["provider"], d, config):
            click.echo(note)
    exec_agent(run_argv, run_env)


cli.add_command(run_profile)


def main(argv=None):
    get_reminder = check_async(sys.argv[1:] if argv is None else argv)
    try:
        return cli.main(args=argv, prog_name="aweswitch")
    finally:
        reminder = get_reminder()
        if reminder:
            click.echo(f"⚠  {reminder}", err=True)


if __name__ == "__main__":
    raise SystemExit(main())
