<div align="center">
  <img src="logo/hero.png" alt="aweswitch" width="860">
  <h1>aweswitch: Agent Profile Switcher <a href="https://github.com/wehuman01/aweskill"><img src="https://raw.githubusercontent.com/wehuman01/aweskill/main/logo/aweskill-badge2.svg" alt="aweskill companion"></a></h1>
  <p><strong>A tiny local launcher for switching AI agent runtime profiles.</strong></p>
<p><strong>One config, one command — works the same on Ubuntu, macOS, and Windows.</strong></p>
  <p>Start different agent sessions with different API endpoints, tokens, and models without rewriting global agent config.</p>
  <p>
    <strong>English</strong> ·
    <a href="./README_cn.md">简体中文</a> ·
    <a href="https://www.webioinfo.top/">Webioinfo</a>
  </p>
  <p>
    <a href="https://ko-fi.com/mugpeng"><img src="https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  </p>
  <p>
    <img src="https://img.shields.io/pypi/v/aweswitch?style=flat-square&color=7C3AED" alt="Version">
    <img src="https://img.shields.io/badge/python-%E2%89%A53.9-0EA5E9?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/license-MPL--2.0-22C55E?style=flat-square" alt="License">
  </p>
  <p>
    <img src="https://img.shields.io/badge/status-beta-c96a3d?style=flat-square" alt="Status">
    <img src="https://img.shields.io/badge/provider-Claude_Code_%7C_Codex_%7C_OpenCode_%7C_zcode-7C3AED?style=flat-square" alt="Provider">
    <img src="https://img.shields.io/badge/install-pip-22C55E?style=flat-square" alt="pip install">
    <img src="https://img.shields.io/badge/platform-ubuntu%20%7C%20macOS%20%7C%20windows-334155?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/pepy/dt/aweswitch?style=flat-square" alt="PyPI downloads">
    <img src="https://img.shields.io/github/stars/wehuman01/aweswitch?style=flat-square" alt="GitHub stars">
  </p>
</div>

> Run different agent profiles side by side without breaking sessions that are already open.

`aweswitch` reads profiles from `~/.config/aweswitch/config.json` and offers two modes:

- **Launch mode** (`aweswitch <profile>`) — starts a new agent session with isolated env. Each session gets its own API endpoint, token, and model. Different terminals can run different profiles simultaneously. Env is frozen at launch time.
- **Write mode** (`aweswitch apply <profile>`) — makes a profile the agent's persistent default: Claude env into `~/.claude/settings.json`, Codex provider+model into `~/.codex/config.toml`, OpenCode provider+models into `~/.config/opencode/opencode.json`, and zcode providers+models into `~/.zcode/v2/config.json`. A bare `aweswitch apply` bulk-syncs every OpenCode and zcode profile; `--opencode` / `--zcode` narrow the bulk to one agent. Claude and Codex keep one active default at a time.

It is intentionally small. Today it supports Claude Code, Codex, OpenCode, and zcode profiles, plus official-login accounts (Claude Code / Codex OAuth).

## Quick Start

`aweswitch` follows the same loop as the rest of the awesome family: hand the bootstrap to an agent once and you land with a working first profile, then manage day-to-day work in natural language. Step 1 covers that bootstrap and gets you using aweswitch right away; steps 2 and 3 are the more advanced operations — equipping the management skill and the daily scenarios in detail. One rule is specific to this tool — the agent never launches a profile for you, because that would nest an agent inside an agent. Applying profiles and managing the config go through the agent; launching stays in your own terminal.

### 1. Install and use aweswitch

If you are working in Claude Code, Codex, Cursor, or another coding agent, hand the whole job to it — the agent installs the CLI, initializes the config, installs the aweswitch skill, and writes your first profile for you: it reads API keys already exported in your shell config (`~/.zshrc`, `~/.bashrc`, or the Windows user environment) and references them directly, asking only for what is missing. The natural-language path alone leaves a working first config. Invoke skills (`/` in Claude Code, `$` in Codex) afterwards to confirm the new skill appears; if not, restart the agent first.

You can tell your agent:

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

Once the bootstrap finishes, aweswitch is ready to use. There are two ways to use a profile:

**Write (apply)** — writes a profile into the agent's own config as the persistent default, so every session you open normally uses it from then on. You can tell your agent:

```text
Add a GLM Claude profile, then write cc-glm into Claude settings.
```

**Launch** — touches no global config: it starts a one-off session with its own API endpoint and model, and different terminals can run different profiles side by side. Run it in your own terminal (the agent will not launch it for you — that would nest an agent):

```bash
aweswitch cc-glm
```

Working outside a coding agent and prefer to do it yourself? Install from PyPI, create the default config, then add your first profile interactively or edit the config directly — the commands and a reference config are in the folded blocks below.

Package page: [pypi.org/project/aweswitch](https://pypi.org/project/aweswitch/)

<details>
<summary>Install and bootstrap CLI commands</summary>

```bash
# Install from PyPI
pip3 install aweswitch
aweswitch --help

# Create the default config, then align it with your real providers
aweswitch config init
aweswitch config edit

# Or add a profile / official account interactively (api or official)
aweswitch add

# Verify the configured profiles (secrets redacted)
aweswitch list
aweswitch show cc-glm
```

</details>

<details>
<summary>Reference config and token variables</summary>

The default config shape splits profiles by kind (`api` for env-based API profiles, `accounts` for official logins) and then by provider. This is a reference config you can adapt:

```json
{
  "profiles": {
    "api": {
      "claude": {
        "cc-glm": {
          "env": {
            "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "ANTHROPIC_MODEL": "glm-5.1"
          }
        },
        "cc-xiaomi": {
          "env": {
            "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
            "ANTHROPIC_MODEL": "mimo-v2.5-pro"
          }
        }
      },
      "codex": {
        "cx-openai": {
          "env": {
            "OPENAI_BASE_URL": "https://api.openai.com",
            "OPENAI_API_KEY": "${OPENAI_API_KEY}"
          }
        }
      },
      "opencode": {
        "oc-glm": {
          "env": {
            "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "OPENCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "OPENCODE_NAME": "Zhipu GLM",
            "OPENCODE_MODEL": {
              "glm-5.1": "GLM-5.1",
              "glm-5.2": "GLM-5.2"
            }
          }
        }
      },
      "zcode": {
        "zc-glm": {
          "env": {
            "ZCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "ZCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "ZCODE_NAME": "BigModel - Coding Plan",
            "ZCODE_CHAT_MODEL": {
              "GLM-5.3-Flash": "GLM-5.3-Flash",
              "GLM-5-Turbo": "GLM-5-Turbo"
            }
          }
        }
      }
    },
    "accounts": {}
  }
}
```

Configs from before v0.4 (profiles grouped directly by provider) are migrated automatically on first load, with a `config.json.bak` backup written next to the config.

Configure the token variables referenced by your profiles:

```bash
# Claude / OpenCode profiles
export GLM_ANTHROPIC_AUTH_TOKEN="..."
export XIAOMI_ANTHROPIC_AUTH_TOKEN="..."

# Codex profiles
export OPENAI_API_KEY="..."

# zcode profiles
export ZCODE_API_KEY="..."
```

Put long-lived variables in your shell config file if you want them available in every shell — `~/.zshrc` on macOS, `~/.bashrc` or `~/.bash_profile` on bash, or `$PROFILE` on PowerShell.

</details>

<details>
<summary>Example: list configured profiles</summary>

![image-20260622102235441](assets/images/image-20260622102235441.png)

</details>

<details>
<summary>Example: apply profile and switch model</summary>

![image-20260622100567](assets/images/image-20260622100567.png)

</details>

### 2. Equip your agent

The bootstrap prompt in step 1 usually installs the `aweswitch` skill along the way (`README.ai.md` installs it as its own step 2), so most users arrive already equipped. If you installed by hand or the skill is missing, project it once — it teaches the agent to list, inspect, add, edit, and delete profiles, apply them to settings (`aweswitch apply`), restore from backup (`aweswitch config restore`), and read existing API keys from your shell config when writing profiles.

You can tell your agent:

```text
Install the aweswitch skill into this agent so you can manage my aweswitch profiles in natural language.
```

<details>
<summary>Equivalent CLI commands</summary>

```bash
# Via aweskill (recommended): install from GitHub and project into this agent
aweskill install wehuman01/aweswitch
aweskill agent add skill aweswitch --global --agent codex
aweskill agent list --global --agent codex   # expect aweswitch shown as linked

# Without aweskill: copy SKILL.md directly into the agent's skill directory
mkdir -p ~/.claude/skills/aweswitch
curl -fsSL https://raw.githubusercontent.com/wehuman01/aweswitch/main/resources/skills/aweswitch/SKILL.md -o ~/.claude/skills/aweswitch/SKILL.md
```

</details>

### 3. Manage profiles through natural language

From here on, profile management needs no memorized commands: state the intent and the agent reads the config, makes the change, and verifies the result. It can run `aweswitch apply`, `aweswitch config backup`, and `aweswitch config restore` directly; the one thing it will not do is launch a profile (that would nest an agent). The scenarios below cover day-to-day use; expand the folded blocks to run the CLI by hand or verify exactly what happens.

Which mode you need stays a human decision:

| Scenario | Mode |
|---|---|
| Run multiple profiles side by side | Launch (your terminal) |
| Switch model with `/model` inside a session | Write (agent can run it) |
| Quickly try different APIs | Launch |
| Set a persistent default profile | Write |
| Push edited OpenCode profiles into opencode.json | Write (`aweswitch apply`) |
| Push edited zcode profiles into zcode config.json | Write (`aweswitch apply`) |

> **Note:** The two modes do not interfere with each other. `aweswitch cc-glm` does not read or modify settings.json. `aweswitch apply cc-glm` does not affect running sessions.

#### List and inspect profiles

Profiles live in one local config file, and the inspection commands redact secrets. Ask the agent what exists before changing anything.

You can tell your agent:

```text
List all my aweswitch profiles and show what cc-glm points to.
```

<details>
<summary>Equivalent CLI commands</summary>

```bash
aweswitch list                        # list all profiles (api + account kinds)
aweswitch show cc-glm                 # inspect one profile (secrets redacted)
aweswitch usage cxo-work              # show quota usage for a Codex official account
aweswitch config path                 # print config file path
aweswitch config show                 # full config (secrets redacted)
aweswitch config edit                 # open the config in an editor
```

</details>

#### Add or edit a profile

Adding a profile means one entry under `profiles.api.<provider>` with `${VAR_NAME}` token references. The agent reads the current config first, then scans your shell config (`~/.zshrc`, `~/.bashrc`, or the Windows user environment) for API keys you already export and writes the profile referencing them directly — only a missing key needs your input, and the agent can persist it into your shell config for you. Editing works the same way: rename a profile, change the model in `cc-glm` to `glm-5.2`, or add a lighter haiku-tier model for background tasks.

You can tell your agent:

```text
Add an AiHubMix codex profile named cx-aihubmix; reuse the API key I already have in my shell, and ask me only if it is missing.
```

<details>
<summary>Equivalent CLI commands</summary>

```bash
aweswitch add                         # add a profile or official account interactively
# Provider: codex
# Profile name: cx-myprovider
# OPENAI_BASE_URL: https://myprovider.com/v1
# OPENAI_API_KEY env var name: MY_PROVIDER_KEY

aweswitch config edit                 # or edit ~/.config/aweswitch/config.json directly
```

Per-provider env keys, model formats, and naming rules are summarized in [Profile Rules](#profile-rules).

</details>

#### Set a persistent default profile

`aweswitch apply <profile>` writes a profile into the agent's own config so it becomes the persistent default — Claude env into `~/.claude/settings.json`, Codex provider+model into `~/.codex/config.toml`, OpenCode and zcode provider+model lists into their config files. Claude and Codex keep one active default at a time; OpenCode and zcode profiles coexist, so a bare `aweswitch apply` bulk-syncs both sides. First writes back up the originals, and `aweswitch config restore` undoes Claude changes.

You can tell your agent:

```text
Write cc-glm into Claude settings so I can switch models with /model.
```

<details>
<summary>Equivalent CLI commands</summary>

```bash
aweswitch apply cc-glm                # Claude: env -> ~/.claude/settings.json
aweswitch apply cx-glm                # Codex: provider+model -> ~/.codex/config.toml
aweswitch apply oc-glm                # OpenCode: provider+models -> ~/.config/opencode/opencode.json
aweswitch apply zc-glm                # zcode: provider+models -> ~/.zcode/v2/config.json
aweswitch apply                       # bulk: every OpenCode profile, then every zcode profile
aweswitch apply --opencode            # OpenCode bulk only
aweswitch apply --zcode               # zcode bulk only
aweswitch apply cc-glm cx-glm oc-glm  # mixed: one per agent in a single call
aweswitch apply cc-glm --force        # overwrite existing backup

# Prune managed OpenCode / zcode providers left without a backing profile
aweswitch apply --prune orphans             # bulk both agents, remove tracked providers no profile backs
aweswitch apply --opencode --prune all      # also remove every provider no profile backs (hand-written included)
aweswitch apply --opencode --prune old-a,old-b --dry-run  # preview named removals, write nothing

# Back up and restore Claude settings
aweswitch config backup               # back up on demand and print the backup path
aweswitch config restore              # restore settings from default backup
aweswitch config restore <file>       # restore settings from an explicit backup file
```

Every non-dry-run prune prints its targets and requires a `y` confirmation before any config is written. zcode's `builtin:*` providers are always protected, including with `--prune all`; aweswitch refuses named requests for them.

Per-agent write semantics:

- **Claude** — env is merged into `~/.claude/settings.json`; unrelated settings are preserved, while a stale `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` alternative is removed when the new profile does not declare it. Restart the session or use `/model` to pick the new model.
- **Codex** — the provider table and default model are written into `~/.codex/config.toml` (existing content like `mcp_servers` is preserved; first apply creates a `.toml.bak` backup). The API key stays in the environment: `env_key` points at the `${VAR_NAME}` the profile references, so codex reads the key from your shell.
- **OpenCode** — the provider entry (base URL, key ref, display name) and its **full model list** are upserted into `~/.config/opencode/opencode.json`: overwritten if the provider exists, added if missing. Every managed model also gets `low` / `medium` / `high` / `xhigh` / `max` reasoning-strength variants by default; use `ctrl+t` in OpenCode to switch them. Hand-written variants win; if OpenAI's official Responses endpoint rejects `max`, simply switch back to a valid variant. Launching a profile writes the profile's full model list additively (nothing is removed); apply reconciles it exactly, including model key order and the descending `release_date` stamps that make OpenCode's picker follow the configured order — the picker sorts by release date and ignores key order (favorites and recents always float to the top; see below). aweswitch records managed provider keys in `.aweswitch-managed-providers.json`; after a tracked profile is renamed or deleted, apply warns about the orphan (old sessions are pinned to those model IDs), and `aweswitch apply --opencode --prune orphans` removes it. Ownership for that mode is never inferred from configuration shape, so hand-written entries stay put unless you opt in: `--prune old-a,old-b` removes exactly the named entries (they must exist and must not be profile-backed), `--prune all` removes every provider no profile backs — full alignment, hand-written ones included; `--prune orphans` removes only tracked leftovers. Pruning refuses to run when the config has no OpenCode profiles at all. A prune never leaves the file's top-level `model` dangling: if the provider it points at was deleted, it is repointed to the alphabetically-first profile's first configured model. `--dry-run` previews the sync and prune plan without writing anything (in a both-agents run the OpenCode side is previewed; zcode pruning has no preview). Model IDs that contain a `/` (e.g. `hub/seed-evolving`) are displayed with the full ID in the model picker, keeping entries from different producers distinguishable.
- **zcode** — the provider entry (base URL, env key reference, display name) and its **full model list** are upserted into `~/.zcode/v2/config.json`. zcode supports exactly one API format per provider, so a profile takes `ZCODE_CHAT_MODEL` (chat completions, provider `kind: openai-compatible`) **or** `ZCODE_RESPONSES_MODEL` (Responses API, provider `kind: openai`) — never both; split them into two profiles instead. The key order of the model field is the picker order and is rewritten on every apply. Every managed model — chat (`ZCODE_CHAT_MODEL`) or Responses (`ZCODE_RESPONSES_MODEL`) — also gets a fill-only default reasoning block — `variants: [none, low, medium, high, xhigh, max]`, `medium` selected — so the thought-level picker shows up with a working off switch: `none` is a canonical effort name, so selecting it sends `reasoning_effort: "none"` and the model answers without thinking (verified on bigmodel GLM, ark deepseek, sensenova, weixin and kimi; stepfun ignores the value and keeps thinking). zcode hides the picker for a chat model with no reasoning block, and only canonical effort names reach the wire — a plain variant named `off` would send nothing, which is why the default leads with `none` instead. Plain blocks are also the only reasoning form zcode keeps for custom providers: a catalog-format spec under `zcode.reasoning` is ignored on load and stripped on zcode's next config save. aweswitch's own older fills (the exact plain `low..max` block, or an unreleased build's `zcode.reasoning` spec) are migrated on the next apply; other hand-written reasoning config wins wholesale (an existing variants list or a foreign `zcode.reasoning` spec is never edited), and `"reasoning": false` or `enabled: false` opts out. Responses-API models get the same block — it is the exact plain shape zcode itself persists on them after a picker selection, so both kinds offer the same think/off ladder with no extra setup. zcode is a desktop GUI app, so zcode profiles are apply-only and do not support launch mode. `--zcode` syncs every zcode profile; managed providers are tracked in `.aweswitch-managed-providers.json`, with orphan warnings by default and opt-in cleanup via `--prune` (`orphans`, `all`, or names; `--dry-run` has no zcode preview).

Claude and Codex keep a single active default, so at most one profile of each may be applied per call. OpenCode and zcode profiles coexist side by side, so several can be applied at once — a bare `aweswitch apply` bulk-syncs all of them (an agent with no profiles on one side is skipped with a note), and `--opencode` / `--zcode` narrow the bulk to one agent.

</details>

#### Pin subagent models

Subagents (OpenCode `task` agents, zcode's built-in Explore / general-purpose, Claude Code `Task` agents) normally inherit the primary model, so they already follow the profile you launch or apply. Agent files outlive any profile, so OpenCode/zcode pins live in a top-level `subagents` section beside `profiles` — one map per target, each value naming both the provider and the model. The typical case is a cheap model for read-only scouting while the primary stays on a pro model:

```json
{
  "profiles": {
    "api": {
      "opencode": {
        "oc-glm": {"env": {
          "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
          "OPENCODE_API_KEY": "${GLM_API_KEY}",
          "OPENCODE_MODEL": {"glm-5.2": "GLM-5.2", "glm-5.1-flash": "GLM-5.1-Flash"}
        }}
      },
      "zcode": {
        "zc-bigmodel": {"env": {
          "ZCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
          "ZCODE_API_KEY": "${GLM_API_KEY}",
          "ZCODE_CHAT_MODEL": {"GLM-5.3-Flash": "GLM-5.3-Flash"}
        }}
      }
    }
  },
  "subagents": {
    "opencode": {
      "explore": "oc-glm/glm-5.1-flash",
      "review": "oc-step/step-3.7-flash"
    },
    "zcode": {
      "general-purpose": "zc-bigmodel/GLM-5.3-Flash",
      "Explore": "zc-bigmodel/GLM-5.3-Flash",
      "review": "zc-bigmodel/GLM-5.3-Flash"
    }
  }
}
```

- `subagents.opencode` — a `{agent-name: "profile/model"}` map. A name whose markdown file is missing in `~/.config/opencode/agents/` is **created from the generic template** (description and prompt body are boilerplate — only the model line differs); an existing file only gets its frontmatter `model:` line rewritten (the prompt body is never touched) to the exact `profile/model` string you wrote.
- `subagents.zcode` — same shape, same create-from-template rule for `~/.zcode/agents/`. The two built-in names (`general-purpose`, `Explore`) are written into zcode's built-in agent overrides (`~/.zcode/v2/agents-state.json`); every other name pins a user subagent by rewriting only its frontmatter `model:` line to the `custom:<provider>:<model>` form zcode itself uses. Built-ins and user agents can be pinned in the same map, each to its own model.
- Each value is the exact string the agent file gets: `profile/model-id`, split at the first slash (the model id itself may contain slashes, e.g. `hub/seed-evolving`). The named profile must be a same-target api profile listing that model, and every apply ensures those providers, so pins always resolve. Borrowing another profile's provider is just writing its name — `"review": "oc-step/step-3.7-flash"` keeps the primary on GLM while review runs on StepFun.
- Configs from before this section existed keep working: `OPENCODE_SUBAGENT_MODEL` / `ZCODE_SUBAGENT_MODEL` in a profile's env are migrated into the section on first load (the config is rewritten with a `.json.bak` backup; `@profile/model` refs and zcode's scalar form are expanded).
- **Claude** needs no section entry: set `CLAUDE_CODE_SUBAGENT_MODEL` in the profile env — Claude Code's global default for `Task` subagents and agent-teams teammates, outranking per-agent `model:` frontmatter. The model must be served by the profile's own `ANTHROPIC_BASE_URL` (one endpoint per session, so cross-provider references don't apply). aweswitch manages the key like the tier vars: every launch and apply emits it, writing `inherit` — Claude Code's explicit fall-through value — when the profile omits it, so a pin left by a different provider can never leak through; a hand-set value in `~/.claude/settings.json` is overwritten the same way.
- **Claude, per-alias alternative**: set `ANTHROPIC_DEFAULT_HAIKU_MODEL` (or any OPUS/SONNET/HAIKU/FABLE tier var) in the profile env and `model: haiku` in the agent frontmatter — tier remaps keep per-agent distinctions instead of one flat default.
- **Codex** — set `CODEX_SUBAGENT_MODEL` in the profile env (a model id the profile's endpoint serves). Launch injects it as `-c agents.default_subagent_model=...`; apply manages the same key inside `~/.codex/config.toml`'s `[agents]` table — codex's default for `spawn_agent` sub-agents, which an explicit spawn model chosen by the agent still overrides. A profile without the field releases the key on apply (an empty `[agents]` table disappears with it); hand-written `[agents]` roles and other keys are preserved verbatim. Cross-profile references aren't supported — codex serves sub-agents through the session's single endpoint.

Pins follow the config, not the last profile applied: every apply converges the pins to what the section declares — agents a previous apply managed but the section no longer names are removed: a file aweswitch created from the template is **deleted**, a user-authored file only loses its `model:` line and falls back to inheriting the primary/session model, valid under any provider. Launching a profile re-writes the declared pins additively (creating any missing declared files) and never removes anything. Agent files aweswitch never pinned are never touched, and apply warns about user-pinned agents whose provider no longer exists.

#### Launch profiles side by side

Launching is the one action that stays yours: an agent refuses to run `aweswitch <profile>` because it would nest an agent inside an agent. Each launch starts a fresh session with its own frozen env, so different terminals can run different profiles at the same time without rewriting global agent config.

Run it in your own terminal:

```bash
aweswitch cc-glm                      # launch Claude Code profile
aweswitch cx-openai                   # launch Codex profile
aweswitch oc-glm glm-5.2              # launch OpenCode profile with a specific model
aweswitch cxo-work                    # launch Codex official account (see below)
```

<details>
<summary>Extra arguments and auto-bookmark</summary>

```bash
# Pass extra arguments through to the agent
aweswitch cc-glm --dangerously-skip-permissions
aweswitch cx-openai --model o3
aweswitch oc-glm glm-5.1 --mini

# Auto-bookmark the session with aweshelf
aweswitch cc-glm -c backend -t "Fix auth bug"
```

See [aweshelf Integration](#aweshelf-integration) for details.

</details>

#### Run multiple official accounts side by side

Official-login accounts (OAuth) are saved as accounts and launched through a private per-account config dir, so several Claude Code or Codex logins run side by side without touching your global `~/.claude` or `~/.codex`. The OAuth login flow is interactive and runs in your terminal; importing the current login and syncing refreshed tokens back can go through the agent.

You can tell your agent:

```text
Import the Claude account I am currently logged in with as an account named team-a.
```

<details>
<summary>Account CLI commands and how they work</summary>

```bash
aweswitch account login codex work    # run codex login and capture it as account "work"
aweswitch account add claude team-a   # import the currently logged-in claude account
aweswitch cxo-work                    # launch codex with the "work" account
aweswitch account sync codex work     # copy refreshed tokens back into the config
aweswitch account remove codex work --purge
aweswitch usage cxo-work              # show quota usage for a Codex official account
aweswitch usage --all-codex           # show quota usage for every Codex official account
```

`aweswitch add` → type `official` is the interactive route to the same two flows: it asks for provider, account name, and method (`login` runs the OAuth flow, `import` reads the current CLI login).

How it works:

- Launching an account sets `CODEX_HOME` (codex) or `CLAUDE_CONFIG_DIR` + `CLAUDE_CODE_DONT_USE_KEYCHAIN=1` (claude) to a private dir under `~/.config/aweswitch/accounts/<provider>/<name>/`. Credentials are opaque blobs stored in `config.json` and masked in `show` / `config show`; the config file is chmod 600 once it contains an account.
- The account dir is the source of truth once it exists — the CLI refreshes OAuth tokens there, and an existing credentials file is never overwritten by the stored blob. Run `aweswitch account sync` to refresh the config copy for backup/portability.
- On macOS, Claude Code keeps its login in the Keychain by default; `account login` / launches force file-based credentials inside the account dir so accounts stay isolated. `account add` reads `~/.claude/.credentials.json` and only works when that file exists — prefer `account login` on macOS.
- Accounts are launch-only: they don't participate in `apply` mode.
- `aweswitch usage <codex-account>` reads the Codex official account's quota usage. Only Codex official accounts expose a compatible quota API; GLM and Doubao remain dashboard-only. API-key Codex profiles are not supported.
- Sessions are isolated per account by default: each account dir keeps its own `sessions/`, so `codex resume` only finds sessions recorded by that account. Set `"share_sessions": true` (top level of `config.json`) to pool Codex sessions across accounts. On the next launch, each Codex account's `sessions/` and `archived_sessions/` become links into a shared pool under `~/.config/aweswitch/accounts/codex/.shared/`, and existing rollout files are migrated in automatically. Any account can then resume any session — `aweswitch cxo-peng resume <id>` works for a session recorded by `cxo-heck` — and the `codex resume` picker lists every account's sessions (use `--all` to lift the cwd filter). The default Codex home joins the pool too: sessions recorded by plain `codex` or a `cx-*` api-profile launch land in `~/.codex/sessions`, which becomes a pool link on the next Codex launch, so those sessions are resumable under every account — and pooled sessions under plain codex. Turning the flag off unlinks the accounts and the default home again; files already in the pool stay there, since rollout files carry no account identity. Claude accounts are not pooled yet.

</details>

## Support Tools

aweswitch is powered by three companion tools:

- **[aweskill](https://github.com/wehuman01/aweskill)** — CLI skill package manager for AI agents. Handles skill installation, updates, and projection across 47+ coding agents.
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — Session bookmark manager for Claude Code and Codex. Bookmark, categorize, and restore sessions with aweswitch profiles.
- **[awerouter](https://github.com/wehuman01/awerouter)** — Smart LLM router: routes agent requests to flash (cheap) or pro (strong) providers based on structural signals.

aweswitch manages how you **launch** sessions; aweshelf manages how you **remember** them. Use `aweswitch -c` to auto-bookmark at launch, and `aweshelf resume` to restore with the same profile later. And awerouter pairs just as smoothly: point a profile's `BASE_URL` at the awerouter daemon (`ANTHROPIC_MODEL=auto`), and every session you launch goes through its flash/pro routing.

## Self-Update

aweswitch checks PyPI for newer versions in the background on each run. If an update is available, a reminder is printed to stderr after the session ends.

<details>
<summary>self-update commands</summary>

```bash
aweswitch self-update                 # update manually
aweswitch self-update --check         # check without updating
export AWESWITCH_NO_UPDATE_CHECK=1    # disable the background check
```

</details>

## aweshelf Integration

[aweshelf](https://github.com/wehuman01/aweshelf) is a session bookmark manager for Claude Code and Codex CLI. It lets you save, tag, search, and resume past coding sessions.

aweswitch integrates with aweshelf so you can bookmark a session at launch time, without a separate step:

```bash
aweswitch cc-glm -c backend -t "Fix auth bug"
```

### Options

| Flag | Description |
|------|-------------|
| `-c`, `--category` | Category to tag the bookmark with (e.g. `backend`, `research`, `infra`). |
| `-t`, `--title` | Custom bookmark title. If omitted, aweshelf uses the session's first message. |

Both options require aweshelf to be installed. If aweshelf is not found, they are ignored with a warning printed to stderr. Claude Code launches normally regardless.

> **Note**: launching multiple `aweswitch -c` sessions simultaneously in the same project may result in incorrect bookmark assignment. Sequential launches are safe — as long as the previous session's JSONL file has been created before starting the next one (typically a few seconds). See [CONTRIBUTING.md](./docs/CONTRIBUTING.md#known-limitation-concurrent-launch-race-condition) for details.

### Install aweshelf

```bash
pip3 install aweshelf
```

<details>
<summary>What aweshelf does on its own</summary>

Even without aweswitch's `-c`/`-t` flags, aweshelf is useful independently:

```bash
aweshelf bookmark               # bookmark a session interactively
aweshelf bookmark --current     # bookmark the most recent session in this project
aweshelf list                   # list all bookmarks
aweshelf search "auth"          # full-text search across bookmarks
aweshelf resume BOOKMARK_ID     # resume a saved session
aweshelf browse                 # interactive TUI browser
```

</details>

See the [aweshelf README](https://github.com/wehuman01/aweshelf) for full documentation.

## FAQ

### Why aweswitch, and who is it for?

`aweswitch` is for people who use AI coding agents with more than one runtime endpoint, model, or token source and want a repeatable local command instead of editing settings by hand.

- **One local config file** at `~/.config/aweswitch/config.json`
- **Named agent profiles** such as `cc-glm`, `cc-gemini`, `cc-xiaomi`, `cx-openai`, or `oc-glm`
- **Side-by-side sessions** where different terminals can launch different API/model combinations
- **Runtime-only injection** through provider-specific arguments
- **No mutation of global agent config**, so already-open agent sessions keep working with the settings they started with
- **Token references** through shell variables or `~/.claude/settings.json`
- **Readable JSON** with `profiles.api` (env-based profiles) and `profiles.accounts` (official logins) grouping

<details>
<summary>More FAQ</summary>

### Where does aweswitch store profiles?

By default, profiles live in:

```bash
~/.config/aweswitch/config.json
```

You can override that path with `AWESWITCH_CONFIG`.

### Does aweswitch modify Claude settings?

**Launch mode** does not — it only reads the aweswitch config and passes runtime settings to the Claude Code process being launched. Already-running sessions are not affected.

**Write mode** does — `aweswitch apply <profile>` writes the profile into the agent's own config (Claude env into `~/.claude/settings.json`, Codex provider+model into `~/.codex/config.toml`, OpenCode provider+models into `~/.config/opencode/opencode.json`). An automatic backup is created on first write for Claude and Codex. Use `aweswitch config restore` to undo Claude changes.

### Does aweswitch support Codex?

Yes. Codex profiles use `OPENAI_BASE_URL` and `OPENAI_API_KEY` in their `env` block, plus an optional `OPENAI_MODEL` to choose a model at launch. aweswitch injects the base URL and model via Codex's `-c` config overrides and the API key via environment variable, so launches write nothing to `~/.codex/`. `aweswitch apply cx-glm` persists the provider and model into `~/.codex/config.toml` instead.

### Does aweswitch support OpenCode?

Yes. OpenCode profiles use `OPENCODE_BASE_URL`, `OPENCODE_API_KEY`, and `OPENCODE_MODEL` (or `OPENCODE_RESPONSES_MODEL`) in their `env` block (plus the optional `OPENCODE_NAME`). On launch, aweswitch writes the provider entry to `~/.config/opencode/opencode.json` (using `{env:VAR}` syntax so the actual key is never stored on disk), then runs `opencode -m <provider>/<model>`.

The profile name (e.g. `oc-glm`) becomes the provider key in `opencode.json`. Models are specified at launch time: `aweswitch oc-glm glm-5.1`. If no model is given, the first one in the list is used. Launching writes the profile's full model list additively (so a subagent pin on a non-session model resolves too); after editing the config, `aweswitch apply oc-glm` upserts the provider exactly (`aweswitch apply --opencode` does every OpenCode profile).

Resuming a session (`-s <session-id>`) restores the model that session last used, and opencode ignores `-m` in that case — aweswitch warns when the two differ so you know to switch models inside the TUI (Tab) after it opens.

### Does aweswitch support official (OAuth) logins?

Yes — Claude Code and Codex official accounts are saved via `aweswitch account login` (or `account add` to import the current login) and launched like profiles: `aweswitch <account-name>`. Each account runs in its own config dir (`CODEX_HOME` / `CLAUDE_CONFIG_DIR`), so multiple official accounts work side by side. See [Official accounts](#run-multiple-official-accounts-side-by-side).

### Does aweswitch support Hermes?

Not yet. The config format groups profiles by provider so future support can fit naturally.

</details>

## Similar Tools

### [cc-switch](https://github.com/farion1231/cc-switch)

`cc-switch` is an adjacent Claude Code switching tool. It is useful reference material for the same problem space: making Claude Code provider/model switching easier from the command line.

The key difference is that `aweswitch` avoids global config mutation. Many switching tools work by changing the agent's shared API/model settings; that can make already-open agent sessions unreliable because the global API endpoint changed underneath them. `aweswitch` keeps profiles in its own JSON file and injects settings only when launching a new process, so each session keeps the API and model it started with.

`aweswitch` currently takes a smaller Python-package approach: local JSON profiles, runtime-only injection (Claude Code `--settings`, Codex `-c` flags and env vars), secret redaction for inspection commands, and provider grouping that leaves room for future agent support.

## Profile Rules

- Profiles live under `profiles.api.<provider>.<profileName>`; official accounts under `profiles.accounts.<provider>.<accountName>`.
- Supported providers: `claude`, `codex`, `opencode` (accounts: `claude`, `codex`).
- Profile and account names must be unique across the whole `profiles` tree and cannot reuse a top-level aweswitch command name; account names must also be a single path component.
- `env` values only apply to the launched process.
- `${VAR_NAME}` values are expanded from the current shell environment.
- `show` and `config show` redact keys matching token, key, secret, password, or auth; account credential blobs are masked entirely.
- `aweswitch usage` reads quota usage for Codex official accounts only. GLM and Doubao do not expose a compatible quota API and remain dashboard-only. API-key Codex profiles are not supported.

### Claude Profiles

- Pass `env` through runtime `--settings '{"env": ...}'`.
- Set the model with `env.ANTHROPIC_MODEL`.
- Token values can also expand from `~/.claude/settings.json` when they are missing from the shell.

`ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, and `ANTHROPIC_DEFAULT_OPUS_MODEL` are not configured by default. If you want Claude Code to use a lighter model for lightweight or background tasks, add `ANTHROPIC_DEFAULT_HAIKU_MODEL` to the profile:

<details>
<summary>Example Claude profile JSON</summary>

```json
{
  "profiles": {
    "api": {
      "claude": {
        "cc-xiaomi": {
          "env": {
            "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
            "ANTHROPIC_MODEL": "mimo-v2.5-pro",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "mimo-v2.5"
          }
        }
      }
    }
  }
}
```

</details>

This keeps the main model on `mimo-v2.5-pro` while allowing Claude Code to use `mimo-v2.5` for lighter work.

### Codex Profiles

- Requires `OPENAI_BASE_URL` and `OPENAI_API_KEY` in `env`.
- Optionally set `OPENAI_MODEL` (dict, list, or comma-separated string) to pick a model at launch: `aweswitch <profile> [model]`. The first entry is the default; matching is case-insensitive. Without the key, the profile only switches the API source and the first positional argument passes through to `codex` as usual.
- Base URL is injected via `-c model_providers.custom.base_url=...`, the model via `-c model=...` (no file writes).
- API key is injected via environment variable (no writes to `~/.codex/auth.json`).
- Extra arguments are passed through to the `codex` CLI.

Note that Codex has no model-tier system like Claude's OPUS/SONNET/HAIKU slots — only one model is active at a time, and `OPENAI_MODEL` selects it per launch. In practice, Codex works best with OpenAI's own models — using third-party providers as a relay is the common use case, while switching to entirely different model providers tends to give a poor experience.

<details>
<summary>Example Codex profile JSON</summary>

```json
{
  "profiles": {
    "api": {
      "codex": {
        "cx-aihubmix": {
          "env": {
            "OPENAI_BASE_URL": "https://aihubmix.com/v1",
            "OPENAI_API_KEY": "${AIHUBMIX_OPENAI_KEY}"
          }
        }
      }
    }
  }
}
```

</details>

aweswitch does not write to `~/.codex/`. The base URL is passed via Codex's `-c` flag and the API key via environment variable. This keeps your global Codex config untouched.

To add a Codex profile interactively:

```bash
aweswitch add
# Provider: codex
# Profile name: cx-myprovider
# OPENAI_BASE_URL: https://myprovider.com/v1
# OPENAI_API_KEY env var name: MY_PROVIDER_KEY
```

### OpenCode Profiles

- Requires `OPENCODE_BASE_URL`, `OPENCODE_API_KEY`, and `OPENCODE_MODEL` in `env`.
- The profile name (e.g. `oc-glm`) is used as the provider key in `~/.config/opencode/opencode.json`.
- `OPENCODE_MODEL` supports three formats: dict, list, or comma-separated string.
- **Model order is the picker order.** OpenCode's picker sorts models by `release_date` (newest first) and then by title — it never reads key order. On apply, aweswitch stamps each managed model a descending `release_date` following the config's key order, so the picker, and the provider's default model, follow the config: reorder the model keys in the aweswitch config and run `aweswitch apply oc-aweshare` — no hand-editing of `opencode.json`. Launch stays additive and never re-stamps. Favorites and recents always float above the stamped order (app behavior).
- Model is specified as the first positional argument: `aweswitch oc-glm glm-5.1`. Matching is case-insensitive against both model IDs and display names (e.g. `doubao-seed-evolving` selects `Doubao-Seed-Evolving`).
- If no model is given, the first model in the list is used as default.
- Extra arguments are passed through to the `opencode` CLI.
- API key is written to `opencode.json` as `{env:VAR}` — the actual key is never stored on disk.

<details>
<summary>Example OpenCode profile JSON</summary>

```json
{
  "profiles": {
    "api": {
      "opencode": {
        "oc-glm": {
          "env": {
            "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "OPENCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "OPENCODE_NAME": "Zhipu GLM",
            "OPENCODE_MODEL": {
              "glm-5.1": "GLM-5.1",
              "glm-5.2": "GLM-5.2"
            }
          }
        }
      }
    }
  }
}
```

</details>

`OPENCODE_MODEL` formats (optional when `OPENCODE_RESPONSES_MODEL` is set — at least one of the two is required):

| Format | Example | Model `name` in opencode.json |
|--------|---------|-------------------------------|
| Dict | `{"glm-5.1": "GLM-5.1"}` | Uses the value (`GLM-5.1`) |
| List | `["glm-5.1", "glm-5.2"]` | Uses the key (`glm-5.1`) |
| String | `"glm-5.1,glm-5.2"` | Uses the key (`glm-5.1`) |

`OPENCODE_NAME` (optional) sets the display name for the provider in `opencode.json`. Defaults to the profile name.

`OPENCODE_RESPONSES_MODEL` (optional) is a comma-separated string or list of model IDs that get a per-model Responses override (`"provider": {"npm": "@ai-sdk/openai"}` on that model entry) while the rest of the provider stays on chat (`@ai-sdk/openai-compatible`). It has equal standing with `OPENCODE_MODEL`: when `OPENCODE_MODEL` is omitted, this list is the profile's full model list and every model runs on the Responses API. A model may not appear in both fields — an overlap is rejected with an error. Model order — and with it the no-arg default launch model — is block-level: whichever field is written first in `env` leads, and responses models not in `OPENCODE_MODEL` follow the chat block (so writing `OPENCODE_RESPONSES_MODEL` above `OPENCODE_MODEL` lists Responses models first). Clearing the list removes the stale overrides on the next sync; a hand-set vendor npm on a model not listed here is never touched.

Launch:

```bash
aweswitch oc-glm                      # default: first model (glm-5.1)
aweswitch oc-glm glm-5.2              # specific model
aweswitch oc-glm glm-5.1 --mini       # pass extra args
```

On first launch, aweswitch writes the provider entry to `~/.config/opencode/opencode.json`. Subsequent launches reuse the existing entry and only add new models if needed.

To add an OpenCode profile interactively:

```bash
aweswitch add
# Provider: opencode
# Profile name: oc-myprovider
# OPENCODE_BASE_URL: https://myprovider.com/v1
# OPENCODE_API_KEY env var name: MY_API_KEY
# OPENCODE_MODEL: model-1,model-2
```

## Support

If aweswitch saves you time, consider supporting it:

- ⭐ Star the repo — it helps others find it.
- ☕ [Ko-fi](https://ko-fi.com/mugpeng) — buy me a coffee.
- 💬 WeChat — scan the QR code below.

<p align="center">
  <img src="assets/images/wechat-pay.jpg" alt="WeChat Pay" width="240">
</p>

> aweswitch is free and open source. Sponsors keep it maintained — thank you.

## Development

See [Contributing](./docs/CONTRIBUTING.md) for setup, testing, branching, and release workflow.

- [Contributing](./docs/CONTRIBUTING.md)
- [Changelog](./docs/CHANGELOG.md)

## Awesome Ecosystem

aweswitch is part of a growing family of "awesome" tools — CLI-first, local-first, and operable by AI agents.

### CLI Tools

- **[aweskill](https://aweskill.wehuman.top/)** — CLI-first skill package manager supporting 47+ AI coding agents.
- **[aweswitch](https://github.com/wehuman01/aweswitch)** — Agent profile switcher for Claude Code, Codex, and OpenCode.
- **[awerouter](https://github.com/wehuman01/awerouter)** — Smart router that splits requests between Flash and Pro models using structural signals, cutting unnecessary model spend.
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — Bookmark, categorize, and restore AI coding sessions; pairs with aweswitch to save profiles and launch with one command.
- **[aweshare](https://github.com/wehuman01/aweshare)** — Share local Ollama/vLLM backends, domestic coding plans, or authorized OpenAI/Anthropic subscriptions through a self-hosted hub — a sharing economy for tokens.
- **[awewarm](https://github.com/wehuman01/awewarm)** — Subscription window warmer that keeps AI coding-plan windows active, for local setups and through a remote hub server.
- **[awescholar](https://github.com/wehuman01/awescholar)** — AI-agent-operable scientific literature discovery and curation.

### Desktop Apps

- **[awedot](https://awedot.wehuman.top/)** — A floating orb at your screen edge keeps track of the current AI session: bookmark it in one click, resume anytime, and pair with aweswitch to pin the agent's config (e.g., relaunch with the GLM model).

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — A curated survey of AI applications in biology, bioinformatics, and biomedical research. Powered by awescholar.
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — A curated collection of state-of-the-art AI systems for virtual tumor modeling and simulation: static models, dynamic models, agents, benchmarks, and reviews.
