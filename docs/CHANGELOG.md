# change log

## v0.7.0 - 2026-09-13

OpenCode/zcode subagent pins move out of profile envs into a top-level `subagents` section beside `profiles` — agent files outlive any profile, so their pins no longer hang off one. Each target gets its own map: `subagents.opencode` and `subagents.zcode`, `{agent-name: "profile/model-id"}`. The value is the exact string the agent file's `model:` line gets; the named profile must be a same-target api profile listing that model, and every apply ensures those providers. zcode's two built-in names (`general-purpose`, `Explore`) now take per-agent entries in the same map — pinning them to different models, alongside user subagents, is finally expressible. Old configs keep working: `OPENCODE_SUBAGENT_MODEL` / `ZCODE_SUBAGENT_MODEL` in a profile's env are migrated into the section on first load (config rewritten with a `.json.bak` backup; `@profile/model` refs and the zcode scalar form are expanded). Declared subagents are also fully managed now, the way providers align to profiles: a name whose agent file is missing is created from a generic template (description and prompt body are boilerplate — only the `model:` line differs), and an entry removed from the section deletes a template-created file on the next apply, while user-authored files keep the old contract — only their frontmatter `model:` line is pinned or released, never the rest of the file.

<details><summary>Highlights</summary>

- New top-level `subagents` section: `{"opencode": {agent: "profile/model"}, "zcode": {...}}` — global state, not per-profile; the "single slot / one declaring profile" restriction is gone
- Values split at the first `/` (model ids may contain slashes); referenced profiles are validated and ensured as sync dependencies
- zcode: built-in overrides and user-subagent pins live in one map; removing an entry releases exactly that pin
- Agent files missing on disk are created from a generic template; removing the entry deletes a template-created file (user-authored files are only unpinned, never deleted)
- Launch re-writes the declared pins additively, creating missing declared files (never removes); every apply reconciles the agent files with the section
- Automatic migration of the old env keys on first load, with backup

</details>

## v0.6.9 - 2026-09-12

`ZCODE_SUBAGENT_MODEL` now also accepts a `{agent-name: model}` object. The scalar form still pins zcode's two built-in agents (`general-purpose` + `Explore`) to one model; the object form pins named user subagents — markdown files in `~/.zcode/agents/` — each to its own model, rewriting only the frontmatter `model:` line to the `custom:<provider>:<model>` form zcode itself uses. This keeps zcode subagent rosters aligned with OpenCode's named agents (`OPENCODE_SUBAGENT_MODEL`): the same functional names on both sides, each pinned to its own model. The two forms never mix in one apply, the field stays a single global slot (one declaring profile), and removing the field releases whichever pins the previous apply owned.

<details><summary>Highlights</summary>

- zcode: `ZCODE_SUBAGENT_MODEL` accepts a `{agent-name: model}` object pinning named user subagents in `~/.zcode/agents/*.md` (frontmatter `model:` line only; name/description/body untouched, same contract as OpenCode agent pins)
- Scalar form (both built-in agents, one model) is unchanged; the two forms never mix — switching forms releases the previous apply's pins
- Values are bare same-profile model IDs or `"@profile/model"` cross-profile refs, ensured as sync dependencies like the scalar form
- A named agent without an existing markdown file dies before anything is written, listing the available names

</details>

## v0.6.8 - 2026-09-12

Sessions recorded outside the account pool — by plain `codex` or a `cx-*` api-profile launch — now join `share_sessions` too. With the flag on, the default Codex home's `sessions/` and `archived_sessions/` become links into the same pool on the next Codex launch, after migrating any existing rollout files in. A session started in bare codex is then resumable under every account, and pooled sessions are resumable from bare codex; turning the flag off unlinks the default home along with the accounts, and pooled files stay in the pool.

<details><summary>Highlights</summary>

- `share_sessions` now also pools the default Codex home (`$CODEX_HOME` or `~/.codex`), so sessions recorded by plain `codex` or `cx-*` api-profile launches are shared with every official account
- Existing rollout files in the default home migrate into the pool on the next Codex launch or `account login`
- Disabling the flag unlinks the default home as well; already-pooled files stay in the pool

</details>

## v0.6.7 - 2026-09-12

Codex official-account sessions can now be shared across accounts — a session started on one account is resumable from any other. This release also adopts the awecontrib shared verify entry point, so CI and local `./verify` run the same gate.

### Shared codex sessions across accounts

Setting `"share_sessions": true` at the top level of `config.json` turns every codex account's `sessions/` and `archived_sessions/` into links into a shared pool under `accounts/codex/.shared/`. Existing rollout files are migrated into the pool on the next launch or `account login`. A session recorded by one account can then be resumed under another: `aweswitch cxo-peng resume <id>` finds a session recorded by `cxo-heck`, and the `codex resume` picker lists every account's sessions (`--all` lifts the cwd filter).

- Rollout files carry no account identity and codex hardcodes its session location to `$CODEX_HOME/sessions`, so a filesystem link (symlink, junction on Windows) is the only sharing mechanism
- Off by default; turning the flag off unlinks the accounts again
- Files already in the pool stay there since they cannot be attributed back to an account
- Claude accounts stay isolated for now

### CI: shared awecontrib verify entry point

The repository now uses the shared `./verify` entry point from awecontrib, and CI calls it directly. This keeps local and CI gates in sync and makes the repo consistent with other awesome/* projects.

<details><summary>Highlights</summary>

- codex: `"share_sessions": true` pools `sessions/` and `archived_sessions/` across all official-account codex profiles via symlinks under `accounts/codex/.shared/`
- `codex resume` picker and `aweswitch <profile> resume <id>` see all shared sessions regardless of which account recorded them
- Shared sessions work because rollout files have no account identity and codex's session path is fixed — filesystem links are the only mechanism
- Off by default; disabling unlinks the accounts, and already-pooled sessions stay in the pool
- CI and local `./verify` both run the awecontrib shared gate

</details>

## v0.6.6 - 2026-09-11

zcode models managed by aweswitch — chat and Responses — can now have thinking turned off from zcode's picker: the fill-only default leads with a working `None` level, no hand-editing of `~/.zcode/v2/config.json`. This release also fixes a syntax error that made 0.6.2 through 0.6.5 fail to import on Python 3.9-3.11, and gates the release on that same interpreter so it cannot happen again.

### Working off via the `none` thought level for all zcode models

- The fill-only default is a plain `reasoning: {enabled, variants, defaultVariant}` block again, now `variants: [none, low, medium, high, xhigh, max]` with `medium` selected — zcode's picker shows the first level as "None". zcode maps only canonical effort names onto request params, and `none` is one: the request carries `reasoning_effort: "none"`, verified to return answers without thinking through bigmodel GLM, ark deepseek, sensenova, weixin and kimi endpoints (stepfun ignores the value and keeps thinking). Any other non-canonical variant name — including `off` — maps to nothing on the wire
- Plain blocks are also the only reasoning form zcode keeps for custom providers: a catalog-format spec under `zcode.reasoning` is ignored on load and silently stripped on zcode's next config save (found by watching a spec-filled config lose every spec at the first settings write). The previous plain fill is kept precisely because it survives
- aweswitch's own older fills are migrated on the next apply: the exact plain `low..max` block gains the `none` level, and the unreleased build's `zcode.reasoning` spec (exact-shape match only) is replaced by the plain block
- Hand-written config still wins wholesale: a plain reasoning dict with its own variants list keeps the list verbatim (only missing `enabled`/`defaultVariant` siblings are filled), and a `zcode.reasoning` spec that isn't aweswitch's own shape is never edited. `reasoning: false` or `enabled: false` remain explicit opt-outs
- Responses-API models (kind `openai`) now get the same default block — it is the exact plain shape zcode itself persists on them after a picker selection, so chat and Responses profiles offer the same think/off ladder with no extra setup

### Fixed: aweswitch failed to import on Python 3.9-3.11

`_edit_agent_model_line` built its inserted line as `f"model: {new_value}{_line_eol(lines[end]) or '\n'}"`. The `'\n'` sits inside the f-string's replacement field, and a backslash there is a `SyntaxError` before PEP 701 (Python 3.12) — so the whole module failed to import on 3.9, 3.10 and 3.11 even though the wheel advertises `requires-python >=3.9`. Introduced by the per-profile subagent pins in v0.6.2, it shipped in 0.6.2 through 0.6.5: installing aweswitch on those interpreters and running any command raised `SyntaxError` at import time. The fallback newline is now hoisted into a local so the f-string expression is backslash-free; behavior is unchanged.

- The Release workflow tested Python 3.13 only, which is why the broken wheels cleared the gate. It now runs the suite on 3.9 first (`test-min`) and the `release` job depends on it, so the oldest interpreter the wheel claims is exercised before anything is published

<details><summary>Highlights</summary>

- zcode: every managed model — chat or Responses — gets a fill-only `reasoning` block whose variants lead with `none`, a canonical effort name that sends `reasoning_effort: "none"` so the picker has a working off switch
- aweswitch's own older reasoning fills (the plain `low..max` block, or the unreleased `zcode.reasoning` spec) are migrated on the next apply; hand-written reasoning config is never edited
- Fix: the f-string in `_edit_agent_model_line` was a `SyntaxError` below Python 3.12, which made 0.6.2-0.6.5 uninstallable on 3.9-3.11
- The Release workflow is now gated on Python 3.9, so a wheel that cannot be imported on its declared minimum can no longer reach PyPI

</details>

## v0.6.5 - 2026-09-09

zcode models managed by aweswitch now receive a fill-only default reasoning block, so the thought-level picker shows for every managed chat model. Previously a `ZCODE_CHAT_MODEL` model like `stepfun-2/step-router-v1` showed no picker at all while `ZCODE_RESPONSES_MODEL` models (e.g. `codex/gpt-5.6-luna`) always did — the Responses protocol carries its own effort parameter, and zcode hides the picker for a chat model whose entry has no reasoning block.

### Default reasoning block for zcode chat models

Every managed chat-completions model (`ZCODE_CHAT_MODEL`, provider `kind: openai-compatible`) gets `reasoning: {enabled, variants: [low, medium, high, xhigh, max], defaultVariant: max}` — the same fill-only default OpenCode models get, restricted to the canonical effort names zcode itself maps onto request params (`reasoning_effort` for chat, `reasoning.effort` for Responses). A hand-written block wins wholesale: an existing variants list is never edited, appended to, or reordered, and `reasoning: false` is an explicit opt-out. Responses providers (kind `openai`) are untouched — zcode already shows its own effort picker for them, and a stamped block would override the app's native defaults.

<details><summary>Highlights</summary>

- Every managed zcode chat model gets the fill-only `low` / `medium` / `high` / `xhigh` / `max` reasoning block (`max` selected), so the thought-level picker shows
- Hand-written blocks win wholesale; `reasoning: false` opts out
- Responses-API providers keep zcode's native effort picker and its defaults

</details>

## v0.6.4 - 2026-09-06

Model order is user-configurable by editing order: the model key order in the aweswitch config is the model-picker order in OpenCode and zcode, and reshuffling the picker is a config edit + `aweswitch apply`, no hand-editing of agent configs.

### Features
- OpenCode: apply now stamps each managed model a descending `release_date` following the config's key order (first model = `9999-12-31`). OpenCode's picker sorts models by release date and then by title — it never reads JSON key order, so without the stamps the picker fell back to alphabetical. The stamps also make the first configured model the provider's default. A hand-set `release_date` that contradicts the config order is reconciled on apply; launch stays additive and never re-stamps, and favorites/recents still float to the top (app behavior)
- apply (prune=True) also rebuilds the provider's model key order to match the config: whichever of `OPENCODE_MODEL` / `OPENCODE_RESPONSES_MODEL` is written first in `env` leads the list (zcode unchanged — its picker order follows the key order as before)

## v0.6.3 - 2026-09-06

### Features
- Claude Code: manage `CLAUDE_CODE_SUBAGENT_MODEL` like the tier vars — every launch/apply emits it, writing `inherit` when the profile omits it, so a pin left by a different provider can never leak through
- Codex: manage `agents.default_subagent_model` per profile — launch injects `-c agents.default_subagent_model=...`, apply manages the `[agents]` key in `config.toml` (releasing it when the profile omits the field, dropping a now-empty table, preserving hand-written roles and other keys)

### Fixes
- OpenCode/zcode subagent pin sync is now config-authoritative and launch is additive: applying a profile that omits the pin field no longer wipes a pin another profile still declares (the slot is released only when no profile declares it, and the holder's provider is ensured even when not synced), and launching writes the profile's full model list so a pinned non-session model resolves without a prior apply


### Features
- Add per-profile subagent model pins for OpenCode and zcode, with `@profile/model` cross-profile references

### Fixes
- `--prune` now lists every provider it would remove and requires explicit confirmation; zcode `builtin:*` providers are protected
- Encode zcode built-in agent override values with percent-encoding to match the app's settings UI

## v0.6.1

OpenCode models managed by aweswitch now receive fill-only `low`, `medium`, `high`, `xhigh`, and `max` reasoning-strength variants. Switch variants with `ctrl+t` in OpenCode; hand-written variants remain unchanged. OpenAI's official Responses endpoint may reject `max`, in which case switch back to a valid variant.

### Fill-only reasoning-strength variants for OpenCode models

Every managed OpenCode model gets `low`, `medium`, `high`, `xhigh`, and `max` reasoning-effort variants by default. Each variant is stamped as `{"reasoningEffort": effort}` and is fill-only: existing variant keys are never removed or overridden, so hand-written variants always win. The variants appear in OpenCode's model picker and can be switched with `ctrl+t`. OpenAI's official Responses endpoint may reject `max`; if that happens, switch back to a valid variant.

<details><summary>Highlights</summary>

- Every managed OpenCode model receives `low` / `medium` / `high` / `xhigh` / `max` reasoning-strength variants
- Fill-only: existing variant keys are never removed or overridden
- Variants switchable with `ctrl+t` in OpenCode
- OpenAI Responses endpoint may reject `max`; switch back to a valid variant

</details>

## v0.6.0

A bare `aweswitch apply` used to refuse with "nothing to apply" and demand profile names or a bulk flag. It now defaults to the both-agents bulk sync: every OpenCode profile, then every zcode profile.

### Bare `apply` bulk-syncs OpenCode and zcode

`aweswitch apply` with no arguments and no flags syncs all OpenCode profiles into `opencode.json` and all zcode profiles into zcode's `config.json` in one run. An agent with no profiles on one side is skipped with a note instead of aborting the run; only a config with no OpenCode and no zcode profiles at all keeps the "nothing to apply" error. `--opencode` / `--zcode` still narrow the bulk to one agent, and giving both flags is now equivalent to the bare default (the flags are no longer mutually exclusive). `--prune` applies to both sides of a both-agents run, with a name list resolving across the two configs — a leftover only ever lives in one of them, so a mixed run can name it once, and every prune is planned before the first write. `--dry-run` still previews the OpenCode side only; the zcode side prints a note that it has no preview.

<details><summary>Highlights</summary>

- Bare `aweswitch apply` = OpenCode bulk then zcode bulk; empty side skipped with a note
- `--opencode --zcode` accepted (same as the bare default); flag + explicit names still rejected
- `--prune` name lists resolve across both agent configs in one run
- Docs, READMEs and the aweswitch skill updated for the new default

</details>

## v0.5.9

v0.5.8 wrote per-model `kind` keys and deleted the provider-level kind — but zcode ignores a model-level kind entirely: the desktop app resolves one transport kind per provider (from the provider's own `kind` field), so every model in a mixed profile actually went out over the same protocol. The kind is now provider-level again, set by which model field the profile declares.

### Provider-level kind for zcode

zcode profiles take `ZCODE_CHAT_MODEL` (chat completions → provider `kind: "openai-compatible"`) or `ZCODE_RESPONSES_MODEL` (Responses API → provider `kind: "openai"`) — exactly one of the two; declaring both is rejected with a prompt to split into two profiles, since one provider carries one API format. The provider-level `kind` is written into `~/.zcode/v2/config.json` and stale values are updated on sync. Stale per-model `kind` keys left by v0.5.8 are stripped on the next sync. A profile that still declares `ZCODE_MODEL` (v0.5.8 naming) is rejected with instructions to rename it to `ZCODE_CHAT_MODEL`.

<details><summary>Highlights</summary>

- Provider-level `kind` restored; per-model kinds never took effect in zcode and are cleaned up
- `ZCODE_CHAT_MODEL` / `ZCODE_RESPONSES_MODEL` are mutually exclusive — one API format per provider
- Legacy `ZCODE_MODEL` rejected with a rename hint
- Default config's zcode profiles use the BigModel coding-plan chat endpoint

</details>

## v0.5.8

zcode profile model configuration is now split by API mode, matching OpenCode. `ZCODE_KIND` (the provider-level `anthropic` / `openai` / `openai-compatible` setting) is removed; each model declares its own transport kind.

### Per-model kind for zcode

zcode profiles use `ZCODE_MODEL` for chat models and `ZCODE_RESPONSES_MODEL` for Responses-API models. The merged models map onto per-model `kind` entries in `~/.zcode/v2/config.json`: models in `ZCODE_MODEL` get `kind: "openai-compatible"`, models in `ZCODE_RESPONSES_MODEL` get `kind: "openai"`. At least one of the two fields is required; a model may not appear in both — duplicate model IDs error out instead of silently overriding. `ZCODE_MODEL` leads the model order (and the label shown by `aweswitch list`); responses-only models are appended after it. A profile that still declares `ZCODE_KIND` is rejected with instructions to migrate to the model fields.

<details><summary>Highlights</summary>

- `ZCODE_KIND` removed; `ZCODE_MODEL` / `ZCODE_RESPONSES_MODEL` define each model's kind
- Duplicate model IDs across the two zcode fields are rejected
- OpenCode `OPENCODE_MODEL` and `OPENCODE_RESPONSES_MODEL` now also reject overlapping model IDs
- Stale model-level kinds are pruned on the next sync when a model stops being Responses-only

</details>

## v0.5.7

`--prune-orphans` and `--prune-providers` are replaced by a single `--prune` flag on `aweswitch apply`. It takes a value instead of being a bare switch: `--prune orphans` removes tracked leftovers no profile backs, `--prune all` removes every unbacked provider (hand-written ones included), and `--prune name1,name2` removes exactly those named entries. The flag works for both OpenCode and zcode — previously `--prune-providers` was OpenCode-only and zcode cleanup required the separate `--prune-orphans` switch.

### Highlights

- `--prune orphans` / `--prune all` / `--prune NAME[,NAME...]` replace `--prune-orphans` and `--prune-providers`
- zcode accepts the same `--prune` values as OpenCode
- `--dry-run` now needs `--prune orphans|all|NAME,...`

## v0.5.6

`v0.5.6` fixes two correctness gaps in `aweswitch apply` introduced by the v0.5.5 OpenCode prune work and the new zcode provider support.

### OpenCode prune safety

Named-form `apply <profile> --prune-providers ...` now validates the requested prune set before any profile sync writes, matching the bulk `--opencode` behavior. Previously the named form synced first and only then died on an unknown or profile-backed provider name, leaving `opencode.json` partially modified.

### ZCODE_MODEL preflight

A zcode profile with missing `ZCODE_MODEL` no longer slips through `preflight_apply`. Mixed apply commands like `apply cx-test zc-x` now abort before writing any target file, instead of writing `codex.toml` and failing midway through the zcode sync.

### Highlights

- Named-form OpenCode prune guards run before any `opencode.json` write
- ZCODE_MODEL is required during preflight for zcode profiles
- Regression tests cover both atomicity fixes

## v0.5.5

`v0.5.5` adds zcode as a supported provider alongside Claude Code, Codex, and OpenCode. zcode is a desktop GUI app; profiles are apply-only — `aweswitch apply --zcode` upserts provider entries and full model lists into `~/.zcode/v2/config.json`, same ownership and orphan tracking as OpenCode.

### zcode provider support

zcode profiles live under `profiles.api.zcode` and use `ZCODE_BASE_URL`, `ZCODE_API_KEY`, `ZCODE_KIND`, and `ZCODE_MODEL` env vars. `ZCODE_KIND` accepts `anthropic`, `openai`, or `openai-compatible` (defaults to `anthropic`). Like OpenCode, every managed model gets default limit (`1M` context, `128K` output) and modalities (`text+image` input, `text` output) stamps unless the entry already declares them — zcode hides image-paste and other affordances when these fields are absent. Apply is the only interaction mode: `aweswitch <profile>` is rejected with a clear message telling the user to use apply instead.

Orphan detection works the same as OpenCode: a `.aweswitch-managed-providers.json` sidecar tracks which providers aweswitch owns, so hand-written entries are never pruned. `aweswitch apply --zcode --prune-orphans` removes leftover providers from renamed or deleted profiles.

### Bulk apply flags are now mutually exclusive

`--opencode` and `--zcode` are mutually exclusive flags; passing both is rejected with an actionable error. Bare `aweswitch apply` with no arguments was already rejected since v0.4.6; the error message now lists both `--opencode` and `--zcode` as options.

### Highlights

- New zcode provider with `ZCODE_BASE_URL` / `ZCODE_API_KEY` / `ZCODE_KIND` / `ZCODE_MODEL` support
- `aweswitch apply --zcode` bulk-upserts zcode profiles into `~/.zcode/v2/config.json`
- `aweswitch add` now supports zcode profiles (prompts for ZCODE fields)
- Orphan tracking via `.aweswitch-managed-providers.json` sidecar; `--prune-orphans` removes leftovers
- Managed model entries get default limit and modalities stamps on first apply
- `--opencode` and `--zcode` are mutually exclusive (previously could be combined silently)
- SKILL.md documents zcode workflows, config structure, and naming conventions
- Default config includes `zc-bigmodel` and `zc-bai` example profiles
- Launch mode rejects zcode profiles with a clear apply-only message
- `aweswitch list` shows zcode profiles with their model list

## v0.5.4

Safety and compatibility hardening for profile application, official-account paths, and OpenCode provider ownership.

### Highlights

- Validate every profile in a mixed `apply` command before writing any target config
- Reject unsafe account paths and top-level command names; restore previous login credentials after any login-flow failure
- Preserve unrelated Claude settings while removing a stale alternative auth key, and support first apply when the settings directory does not exist
- Track aweswitch-managed OpenCode provider keys in a sidecar so `--prune-orphans` never infers ownership from a hand-written provider's shape
- Reject malformed model ID/display-name mappings with an actionable config error

## v0.5.3

`v0.5.3` stamps default `modalities` and `attachment` declarations on every aweswitch-managed OpenCode model entry so image-paste and attach affordances are not silently hidden.

### Default modalities/attachment for OpenCode models

opencode defaults every custom-model capability to `false` when the field is absent, which hides the image-paste and attach affordances even for models that support them. aweswitch now writes `"attachment": true` and `"modalities": {"input": ["text", "image"], "output": ["text"]}` on every managed model unless the entry already declares one — a hand-set value (for example `input: ["text"]` to keep a model text-only) always wins.

### Highlights

- New `_stamp_opencode_model_defaults` helper: fills `attachment` and `modalities` only when absent
- Backfill on every apply: entries written before v0.5.3 pick up the declaration on the next sync
- Hand-set values are never clobbered
- SKILL.md documents the new default behavior and the override path

## v0.5.2

`v0.5.2` simplifies OpenCode Responses configuration to a single knob: `OPENCODE_RESPONSES_MODEL` now works on its own, and the provider-wide `OPENCODE_RESPONSES` flag is gone.

### `OPENCODE_RESPONSES_MODEL` stands alone, `OPENCODE_RESPONSES` removed

`OPENCODE_MODEL` is no longer required when `OPENCODE_RESPONSES_MODEL` is set — the two fields have equal standing, so the responses list becomes the profile's full model list, with every model running on the Responses API (`@ai-sdk/openai`). Mixing is still supported: set both fields to keep the rest of the models on chat completions. A profile with neither field is rejected. Model order is deterministic: `OPENCODE_MODEL`'s order leads the merged list when present, responses-only models are appended in configured order, and the no-arg launch default follows that order.

The `OPENCODE_RESPONSES` boolean is removed. Profiles that set it no longer switch the whole provider to `@ai-sdk/openai`; a provider entry still carrying the responses npm from an older version is reset to `@ai-sdk/openai-compatible` on the next launch or `aweswitch apply`, and per-model overrides from `OPENCODE_RESPONSES_MODEL` are stamped on top. Hand-set vendor npm values are never touched.

### Highlights

- `OPENCODE_MODEL` is optional when `OPENCODE_RESPONSES_MODEL` lists the models (Responses-only profiles need one field)
- `OPENCODE_RESPONSES` boolean removed — use `OPENCODE_RESPONSES_MODEL` per model, or omit `OPENCODE_MODEL` to run everything on Responses
- Stale provider-level `@ai-sdk/openai` npm from v0.5.1 configs is reverted to the chat package automatically

## v0.5.1

`v0.5.1` lets OpenCode profiles speak the OpenAI Responses API: some backends only accept `/responses`, and until now every aweswitch-managed provider was pinned to chat completions.

### Responses API support for OpenCode profiles

`OPENCODE_RESPONSES` switches the provider's npm package between the default `@ai-sdk/openai-compatible` (chat completions, `/chat/completions`) and `@ai-sdk/openai` (Responses API, `/responses`) when set to true. Backends whose models only speak the Responses protocol now work without hand-editing `opencode.json`. The flag is owned by aweswitch like the other provider fields: launch and `aweswitch apply` both rewrite it when it differs, so clearing it reverts the provider to the chat package, and hand-set vendor SDK npm values are never touched.

`OPENCODE_RESPONSES_MODEL` is the mixed-protocol escape hatch: a comma-separated string or list of model IDs that get a per-model Responses override (`"provider": {"npm": "@ai-sdk/openai"}` on that model entry) while the rest of the provider stays on chat. Every ID must exist in `OPENCODE_MODEL` — a mismatch is rejected as a config typo. Clearing the list removes the stale overrides on the next sync. Orphan detection now recognizes both openai packages, so providers created in Responses mode are still reported and pruned correctly after a profile is renamed or deleted.

### Highlights

- New `OPENCODE_RESPONSES` env var: switch a whole OpenCode provider between chat completions and the Responses API
- New `OPENCODE_RESPONSES_MODEL` env var: per-model Responses overrides for mixed-protocol backends
- Both flags sync on launch and `aweswitch apply`; clearing them reverts cleanly
- Hand-written provider/model entries with a vendor npm are never modified

## v0.5.0

`v0.5.0` restores compatibility with codex 0.150+: launching any codex profile (`aweswitch cx-...`) failed with `model_providers.custom: provider name must not be empty` because the launch path injected the provider without a `name`.

### Codex 0.150 compatibility

codex 0.150 added a validation requiring every `model_providers` entry to carry a non-empty `name`. The apply path already wrote `name = "custom"` into `config.toml`, but the launch path's `-c` injection only carried `base_url` / `wire_api` / `env_key`, so every launch died at config load. Launches now inject `model_providers.custom.name="custom"` as well — the field is a long-standing provider key, so older codex versions accept it unchanged.

### Highlights

- Codex profile launches work again on codex 0.150+ (provider `name` injected via `-c`, matching what apply writes)
- Test suite runs on Python 3.9 without `tomllib`

## v0.4.8

`v0.4.8` completes the v0.4.7 model-matching promise: typing `aweswitch cx-aihubmix GPT` now actually finds `gpt-5.2-codex`. Short inputs match as case-insensitive substrings of model IDs and display names, instead of demanding a full exact replica.

### Case-insensitive substring matching

v0.4.7 shipped case-insensitive comparison, but it only matched when the input equaled a full model ID or display name — so the changelog example (`GPT` → `gpt-5.2-codex`) still failed. `select_model` now adds a third pass: after exact and case-insensitive matches miss, the input is matched as a case-insensitive substring of both IDs and display names.

Matching order: exact ID → exact display name → case-insensitive full match → case-insensitive substring. A unique match wins; multiple candidates fail with the same actionable error listing them.

### Highlights

- Launch args now resolve as case-insensitive substrings, so `GPT` selects `gpt-5.2-codex`
- Exact-match-first behavior unchanged; substring is the last fallback
- Ambiguous substring matches are rejected with the list of matching candidates

## v0.4.7

`v0.4.7` adds case-insensitive model matching: typing `aweswitch cx-aihubmix GPT` now finds `gpt-5.2-codex` instead of demanding an exact replica of the ID or display name.

### Case-insensitive model matching

When launching with a model argument, `select_model` first tries an exact match against model IDs and display names (unchanged). If nothing matches exactly, a case-insensitive comparison runs as a fallback across both model IDs and display names. This lets users type model names the way they'd naturally say them — `GPT-5.2-CODEX`, `doubao-seed-evolving`, `SEED` — without needing to match the exact casing configured in the profile.

Ambiguous case-insensitive matches still fail with the same actionable error as before, listing the candidates that matched.

### Highlights

- Launch args match model IDs and display names case-insensitively as a fallback after exact match fails
- No change to exact-match-first behavior; case-insensitive is a second pass
- Ambiguous case-insensitive matches are rejected with the list of candidates

## v0.4.6

`v0.4.6` makes bulk OpenCode apply explicit: bare `aweswitch apply` no longer implicitly writes every OpenCode profile — use `aweswitch apply --opencode` instead, so the default behavior is always intentional.

### Explicit bulk OpenCode apply

The old behavior of `aweswitch apply` with no arguments was to silently apply every OpenCode profile, which surprised users who forgot they had multiple OpenCode profiles. The new `--opencode` flag makes bulk write opt-in. Calling `aweswitch apply` with no arguments now prints a clear error showing both options.

### Highlights

- New `--opencode` flag: `aweswitch apply --opencode` writes every OpenCode profile
- `aweswitch apply` with no arguments now errors with a helpful usage hint instead of silently bulk-applying
- Passing both `--opencode` and explicit profile names is rejected with an actionable error

## v0.4.5

`v0.4.5` extends `apply` to all three agents — Claude, Codex, and OpenCode — so a profile's provider settings can be written directly into each agent's live config, and hardens the apply paths against hand-edited configs.

### Apply for all three agents

`aweswitch apply` now covers Claude (`settings.json`), Codex (`config.toml` via a surgical TOML edit with a `.toml.bak` backup, `env_key` resolved from `${VAR}` references), and OpenCode (provider upsert carrying the full model list; an existing provider is overwritten, a missing one is added). Bare `aweswitch apply` applies every OpenCode profile in bulk, while at most one Claude and one Codex profile per call. Launching an OpenCode profile with `-s` warns when the session's stored model differs from the requested one, since OpenCode restores the session model and ignores `-m`.

OpenCode profiles that were renamed or deleted could leave stale provider entries behind: apply now warns about these orphans and supports `--prune-orphans` to remove them safely. Namespaced model IDs (for example `hub/x`) are shown in full to avoid ambiguous picker rows from different producers.

### Hardening

- Hand-edited OpenCode entries (plain-string model values, non-object options/models) are repaired instead of crashing with `AttributeError`
- Codex table-header detection skips lines inside multi-line strings, so a `developer_instructions` body starting with `[` can no longer misplace top-level keys
- `sync_opencode_profiles --names ""` no longer falls back to applying all profiles
- SQLite read-only open uses `Path.as_uri` so Windows drive-letter paths form a valid URI
- Internal: removed an unreachable return after `die()` in `select_model`

### Highlights

- `apply` writes provider settings for all three agents: Claude, Codex, and OpenCode
- Bare `aweswitch apply` bulk-applies every OpenCode profile
- `apply --prune-orphans` removes stale OpenCode provider entries left by renames or deletes
- Warn when resuming an OpenCode session whose stored model differs from the requested one
- Apply paths tolerate hand-edited configs instead of crashing

## v0.4.2

`v0.4.2` lets launch arguments use a configured model's display value while preserving the full model ID passed to the agent.

### Model selection by display value

When a profile defines model IDs and display values as a mapping, the launch argument may use either form. The full model ID remains the value passed to the underlying agent, and duplicate display values fail with an actionable error.

### Highlights

- OpenCode and Codex launch commands can select a model by its configured display value, such as `step-router-v1` for `peng1/step-router-v1`
- Ambiguous display values are rejected with the matching model IDs instead of selecting one silently

## v0.4.1

`v0.4.1` reorganizes settings backup handling under `config`: a new `aweswitch config backup` command creates a settings backup and prints its path, and `restore` moves under `config` while gaining the ability to restore from an explicit backup file.

### Backup and restore under `config`

`aweswitch config backup` copies `~/.claude/settings.json` to `settings.json.bak` and prints the backup path. Like `apply`, an existing backup is not overwritten unless `--force` is given. The top-level `aweswitch restore` command is replaced by `aweswitch config restore [FILE]`: without arguments it restores from the default `settings.json.bak`; with a file argument it restores from that snapshot, so older timestamped backups can be rolled back to explicitly.

### Highlights

- New `aweswitch config backup`: back up settings on demand and print the backup path (`--force` to overwrite)
- `restore` moved to `config restore [FILE]`: restore from the default backup or any explicit snapshot file
- Internal: `die()` typed as NoReturn, clearing type-checker false positives

## v0.4.0

`v0.4.0` adds official-login accounts: multiple Claude Code and Codex OAuth logins can now be saved as accounts and launched side by side, each through a private config dir. The config schema gains an `api`/`accounts` split under `profiles`; old configs are migrated automatically on first load.

### Official accounts (Claude Code / Codex OAuth)

`aweswitch account login codex work` runs `codex login` inside a per-account runtime dir and captures the resulting credentials; `aweswitch account add codex work` imports the currently logged-in account from the live `~/.codex/auth.json` / `~/.claude/.credentials.json`. Launching works like any profile: `aweswitch cxo-work` starts the CLI with `CODEX_HOME` (codex) or `CLAUDE_CONFIG_DIR` plus `CLAUDE_CODE_DONT_USE_KEYCHAIN=1` (claude) pointed at the account dir, so several official accounts can run simultaneously without touching the global `~/.codex` or `~/.claude`.

Credentials are stored as opaque blobs in `config.json` (`profiles.accounts.<provider>.<name>`), treated as unreadable by aweswitch, and masked entirely in `show` / `config show`. Once an account dir exists it is the source of truth (the CLI refreshes OAuth tokens there); `aweswitch account sync` copies refreshed tokens back into the config, and an existing credentials file is never overwritten by a stale blob. The config file is chmod 600 when the first account is added.

### Config schema v2

Profiles now live under `profiles.api.<provider>` and accounts under `profiles.accounts.<provider>`, with names unique across both trees. Loading a pre-0.4 config transparently moves it to the new layout (a `.json.bak` backup is written first); configs that mix both layouts are rejected with a clear error. `aweswitch list` prints a kind column (`api` / `account`).

### Highlights

- Official-login accounts for Claude Code and Codex with per-account private config dirs
- `aweswitch account add / login / sync / remove [--purge]` command group
- Side-by-side official accounts: launch isolation via `CODEX_HOME` / `CLAUDE_CONFIG_DIR`
- Config schema v2 (`profiles.api` + `profiles.accounts`) with automatic migration and backup
- Account credential blobs masked entirely in `show` / `config show`; config chmod 600 on first account
- `list` output gains an api/account kind column
- `apply` restricted to claude **api** profiles (accounts are launch-only)

## v0.3.9

`v0.3.9` hardens the runtime against corrupt configs and fixes the auto-bookmark worker so it survives agent launches on POSIX. Editable installs now report the correct version after bumps.

### Version detection

`aweswitch.__version__` now reads from `pyproject.toml` when running from source, instead of relying on `importlib.metadata` which freezes the installed dist-info version at install time. This fixes stale version reports after bumps in editable installs.

### Config parsing

JSON loading now uses explicit `encoding="utf-8"` across the config, OpenCode, and update-check paths, and handles `UnicodeDecodeError` alongside `JSONDecodeError`.

`load_opencode_config` now validates the top-level structure and the `provider` key before returning. Corrupt or unexpected JSON causes a loud exit instead of silently falling through to `write_opencode_config`, which could otherwise clobber the user's `opencode.json`.

### Auto-bookmark worker

The background bookmark worker now runs in a detached forked child on POSIX. The previous daemon-thread approach died before its first poll because `os.execvpe()` destroys every thread in the process during agent launch. On Windows the launch path uses `subprocess.run()`, which keeps this process alive, so the daemon thread is retained there.

### Editor fallback

`aweswitch config edit` now reports a clear error when the configured editor binary is not found, instead of raising an unhandled `FileNotFoundError`.

### Highlights

- Read version from `pyproject.toml` for editable installs
- Harden JSON loading with explicit UTF-8 and `UnicodeDecodeError` handling
- Fail loudly on corrupt `opencode.json` instead of silently overwriting it
- Fork detached bookmark worker on POSIX to survive `execvpe()`
- Clear error when editor binary is missing in `config edit`
- Skip PyPI update check on bare invocation

## v0.3.8

`v0.3.8` softens auth-token validation across Claude and OpenCode profiles: plaintext values are now allowed with a tip instead of a hard error, reducing friction for users who don't need `${VAR}` references.

### Highlights
- **Plaintext API keys allowed with a tip**: `OPENCODE_API_KEY` and `ANTHROPIC_AUTH_TOKEN` now emit a warning when the value is not a `${VAR_NAME}` env reference, but no longer block launch. The env-ref form is still recommended to keep keys out of the config file.
- **Claude auth validation aligned with Codex/OpenCode**: `ANTHROPIC_BASE_URL` is now required (existence check), and `ANTHROPIC_AUTH_TOKEN` format is checked with the same warn-only policy.
- **Model list display**: `aweswitch list` now renders `OPENAI_MODEL` / `OPENCODE_MODEL` correctly when they are dicts, lists, or comma-separated strings.

### Docs
- README: added `awerouter` to the companion tools list.

## v0.3.7

`v0.3.7` lets Codex profiles select a model at launch, and keeps OpenCode provider entries in sync when their credentials change.

### Third-party models for Codex profiles

Codex profiles now support an optional `OPENAI_MODEL` (dict, list, or comma-separated string), following the same convention as OpenCode profiles: `aweswitch cx-<name> [model]` picks the model at launch, defaulting to the first entry. The model is injected via Codex `-c` config overrides, so nothing is written to `~/.codex/`. Without the key, the profile keeps the legacy behavior of only switching the API source.

### Sync stale OpenCode provider entries

When an OpenCode profile's `OPENCODE_BASE_URL` or `OPENCODE_API_KEY` changes, `aweswitch` now updates the existing provider entry in `~/.config/opencode/opencode.json` to match instead of erroring with "different credentials". The entry is owned by aweswitch (its name is the profile name), so the aweswitch config is the source of truth. The API key is always stored as an `{env:VAR}` reference — the resolved key is no longer passed through internal launch state.

### Highlights

- Add optional `OPENAI_MODEL` for Codex profiles: `aweswitch cx-<name> [model]`
- Support dict/list/string model formats for Codex, same as OpenCode
- Update stale OpenCode provider credentials instead of failing
- Drop internal plaintext API key from launch state; only `{env:VAR}` refs are written

## v0.3.6

`v0.3.6` fixes a profile-switching bug where a Claude profile could launch against the wrong model.

### Default unset model tiers to ANTHROPIC_MODEL

When launching a Claude profile, `aweswitch` now defaults every model-tier env var it does not explicitly set — `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL` — to the profile's `ANTHROPIC_MODEL`.

Previously only the OPUS tier was defaulted. Claude Code merges the `--settings` file with `~/.claude/settings.json`, so a tier the profile left unset inherited a stale model mapping from a previous provider. If the selected `/model` tier was one of those, the request resolved to a model the current provider does not serve (for example, a minimax profile erroring with "selected model (mimo-v2.5)"). Explicit per-tier overrides in a profile are preserved.

### Highlights

- Default all unset Claude model tiers (OPUS/SONNET/HAIKU/FABLE) to `ANTHROPIC_MODEL`
- Prevent stale tier→model mappings from leaking across providers via settings merge
- Preserve explicit per-tier model overrides in profiles

## v0.3.5

`v0.3.5` improves the Windows experience with PowerShell-first agent launcher routing and updated documentation. Windows users can now run `aweswitch` against PowerShell-installed agent binaries without manual script invocation.

### Windows PowerShell support

When resolving the agent command on Windows, `aweswitch` now prefers `shutil.which` with PATHEXT resolution (`.cmd`, `.exe`, `.bat`, `.ps1`). `.ps1` scripts are automatically routed through `powershell.exe -ExecutionPolicy Bypass -File`, matching how users typically install Claude Code and other agent CLIs on Windows.

### PowerShell env-var documentation

Setup docs in both READMEs and the bundled skill now document `setx` for persisting tokens on Windows, so `cmd` and PowerShell agree on the same persistent environment without requiring shell-specific rc files.

### OpenCode documentation

The READMEs and AI bootstrap guide now include full OpenCode provider examples, covering the three supported `OPENCODE_MODEL` formats and the `{env:VAR}` key storage policy.

### Cross-platform README updates

Both READMEs now advertise cross-platform support explicitly with updated badges and a one-line positioning statement.

### Highlights

- Route `.ps1` agent binaries through PowerShell automatically on Windows
- Prefer `setx` for persistent Windows env vars in setup docs
- Documented PowerShell env-var setup in READMEs and skill
- Added OpenCode provider documentation with model format examples
- Updated README badges to show `ubuntu | macOS | windows`
- Added cross-platform positioning line to both READMEs

## v0.3.3

`v0.3.3` hardens several runtime paths and cleans up version management.

### OpenCode API key validation

`OPENCODE_API_KEY` must now be an environment variable reference (`${VAR_NAME}`). Plain-text keys are rejected at startup with a clear error message, preventing accidental secret writes to `opencode.json`.

### Temp settings cleanup

Temporary settings files in `/tmp/aweswitch/` are now garbage-collected on each launch. Files older than 24 hours are removed before creating a new one, preventing unbounded accumulation.

### Backup error handling

`aweswitch apply` now fails with a clear message if the settings backup cannot be created (e.g. disk full), instead of silently continuing and overwriting the original.

### Highlights

- Reject plain-text `OPENCODE_API_KEY`; require `${VAR}` env-ref syntax
- Auto-clean temp settings files older than 24h
- Die with clear message if settings backup fails
- Parse pre-release version suffixes (e.g. `0.3.0a1`) correctly
- Use `pyproject.toml` as single version source; `__init__.py` reads via `importlib.metadata`
- Switch README version badges to PyPI dynamic badge

## v0.3.2

`v0.3.2` adds OpenCode as a supported provider, alongside Claude Code and Codex. Profiles targeting OpenCode are written to `~/.config/opencode/opencode.json` and launched via `opencode -m <provider>/<model>`. This release also refreshes documentation for the new provider and normalizes model handling across formats.

### OpenCode provider support

Profiles can now target OpenCode. Set `"provider": "opencode"` in a profile (or select "opencode" in `aweswitch add`) and provide `OPENCODE_BASE_URL`, `OPENCODE_API_KEY`, and `OPENCODE_MODEL`. aweswitch writes the provider entry to `~/.config/opencode/opencode.json` on first launch, using `{env:VAR}` syntax so the API key is never stored on disk. The model is passed as a positional argument: `aweswitch oc-<profile> <model>`. If no model is given, the first model in `OPENCODE_MODEL` is used.

### Model format normalization

`OPENCODE_MODEL` now accepts three formats and normalizes them consistently:

- **Dict** — `{"glm-5.1": "GLM-5.1"}` — model `name` uses the display value
- **List** — `["glm-5.1", "glm-5.2"]` — model `name` uses the list key
- **String** — `"glm-5.1,glm-5.2"` — model `name` uses the first key

### Documentation refresh

Both READMEs and the bundled skill (`resources/skills/aweswitch/SKILL.md`) now document all three providers (Claude, Codex, OpenCode), with provider-specific config examples, model selection syntax, and a mode-availability table.

### Highlights

- Added OpenCode provider with `OPENCODE_BASE_URL` / `OPENCODE_API_KEY` / `OPENCODE_MODEL` support
- `aweswitch add` now prompts for provider (`claude`, `codex`, or `opencode`)
- First launch writes provider entry to `~/.config/opencode/opencode.json`; subsequent launches reuse it
- API key written as `{env:VAR}` — actual key never stored on disk
- Model specified as first positional argument; defaults to first model in list
- Normalized `OPENCODE_MODEL` dict/list/string formats with consistent label resolution
- Updated README, README_cn, and SKILL.md with OpenCode examples and provider table
- Removed `cc-gemini` and `cx-aihubmix` example profiles from default config

## v0.3.0

`v0.3.0` adds `apply` and `restore` commands for writing profiles directly to `~/.claude/settings.json`, and restructures documentation around the two switching modes.

### Apply and restore commands

`aweswitch apply <profile>` writes a Claude profile's expanded env (including `_NAME` variants for the `/model` picker) directly to `~/.claude/settings.json`. A backup is created on first apply; subsequent applies skip the backup to preserve the original. Use `--force` to overwrite the backup. `aweswitch restore` reverts settings from the backup.

This enables a new workflow: start claude normally, then apply a profile from another terminal (or via the aweswitch skill), and use `/model` to switch models within the session — without launching a new process.

### Two modes documentation

README and SKILL.md now clearly distinguish two modes:

- **Launch mode** (`aweswitch <profile>`) — isolated sessions, env frozen at launch, multiple profiles in parallel terminals.
- **Apply mode** (`aweswitch apply <profile>`) — persistent default via settings.json, `/model` works within session.

Install and Usage sections were merged into a single "Install & Usage" section to eliminate duplication. The AI agent bootstrap guide (README.ai.md) now installs the skill early so the agent has profile knowledge during setup.

### Highlights

- New `aweswitch apply <profile>` command (Claude only)
- New `aweswitch restore` command
- `--force` flag to overwrite existing backup
- Backup only created on first apply to preserve original settings
- Extracted `build_claude_env()` from `prepare_run()` for reuse
- Merged Install and Usage sections in both READMEs
- Skill installation moved to Step 2 in AI bootstrap guide
- SKILL.md defaults to apply mode; launch mode marked as user-only

## v0.2.1

`v0.2.1` improves the missing-environment-variable error message and fixes README skill references.

### Better error messages

When a profile references an environment variable that is not set, aweswitch now prints a clear hint telling the user to add it to their shell config and reload — instead of a bare "missing environment variable" message. The hint is cross-platform and does not hardcode any specific shell or rc file.

### Docs fixes

Updated README skill references to point to the GitHub-hosted `SKILL.md` instead of a local `.aweskill` path, so the link works for all users.

### Highlights

- Improved missing env var error message with actionable reload hint
- Fixed `SKILL.md` links in README.md and README_cn.md to use GitHub URL

## v0.2.0

`v0.2.0` makes aweswitch fully cross-platform. Windows users can now launch profiles without hitting Unix-only system calls.

### Cross-platform support

Four Unix-specific calls were replaced with portable alternatives. `os.fork()` (used for auto-bookmark background polling) is now a `threading.Thread`. `os.execvpe()` / `os.execvp()` (used to hand off to `claude` or `codex`) fall back to `subprocess.run()` on Windows. `os.chmod(0o600)` is skipped on Windows where it has no effect. `shlex.split()` uses `posix=False` on Windows to preserve backslash paths.

### Highlights

- Replaced `os.fork()` with `threading.Thread` for auto-bookmark
- `exec_agent` uses `subprocess.run` on Windows instead of `os.execvpe`
- `config edit` uses `subprocess.run` on Windows instead of `os.execvp`
- Skipped `os.chmod(0o600)` on Windows
- `editor_argv` uses `posix=False` on Windows for correct path splitting
- CI already covers `windows-latest` with Python 3.9 and 3.13

## v0.1.9

`v0.1.9` adds Codex as a supported provider alongside Claude Code, and ships an AI guide and skill for aweswitch.

### Codex provider support

Profiles can now target OpenAI Codex. Set `"provider": "codex"` on a profile (or select "codex" in `aweswitch add`) and provide `OPENAI_BASE_URL` and `OPENAI_API_KEY`. aweswitch launches `codex` with the base URL, wire API, and auth injected via `-c` flags and environment variables. The default config includes a `codex-openai` example profile.

### AI guide and skill

A new `README.ai.md` documents how to use aweswitch from AI agents. A bundled skill file (`resources/skills/aweswitch/SKILL.md`) lets AI assistants discover and invoke aweswitch directly.

### Highlights

- Added Codex provider with `OPENAI_BASE_URL` / `OPENAI_API_KEY` support
- `aweswitch add` now prompts for provider (claude or codex) before profile fields
- Default config includes `codex-openai` example profile
- Added `README.ai.md` for AI agent integration
- Added bundled aweswitch skill for AI assistants
- Clarified Codex profile behavior in both READMEs

## v0.1.8

`v0.1.8` adds a self-update command and background update checking.

### Self-update

`aweswitch self-update` upgrades to the latest PyPI release, automatically detecting whether to use `pipx upgrade` or `pip install --upgrade`. A `--check` flag shows available updates without installing.

### Background update reminder

Each run now checks PyPI in the background (once per 24h) and prints a reminder to stderr when a newer version exists. Set `AWESWITCH_NO_UPDATE_CHECK=1` to disable.

### Highlights

- Added `aweswitch self-update` command with `--check` flag
- Background update check on each run with 24h cooldown
- Robust pipx detection using `sys.prefix` instead of path substring matching
- Error handling for network failures during update checks

## v0.1.7

`v0.1.7` improves model picker display for unset tiers and auto-populates the Opus model fallback.

### Model picker "Not set" display

When a profile does not define `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `SONNET_MODEL`, or `OPUS_MODEL`, the corresponding `_NAME` variant is now set to `"Not set"`. This prevents Claude Code's `/model` picker from showing a stale label inherited from `~/.claude/settings.json`.

### Highlights

- Show "Not set" in `/model` picker for unset model tiers instead of stale values
- Auto-populate `ANTHROPIC_DEFAULT_OPUS_MODEL` from `ANTHROPIC_MODEL` when not explicitly set
- Added aweshelf companion section and race condition notes to both READMEs
- Added `docs/CONTRIBUTING.md`

## v0.1.6

`v0.1.6` adds auto-bookmark support via [aweshelf](https://github.com/wehuman01/aweshelf). Sessions can now be tagged with a category and custom title at launch time, without requiring a separate bookmark step.

### Auto-bookmark with aweshelf

When launching a profile with `-c` (category), aweswitch forks a background process before exec that waits for the new session JSONL file to appear, then calls `aweshelf bookmark` to record it automatically. An optional `-t` flag sets the bookmark title; if omitted, aweshelf uses the session's first message. If aweshelf is not installed, `-c` and `-t` are ignored with a warning printed to stderr.

### Highlights

- Added `-c` / `--category` option to profile launch for auto-bookmarking
- Added `-t` / `--title` option to set a custom bookmark title
- Background fork process polls `~/.claude/projects/` for up to 60s
- Graceful degradation when aweshelf is not installed
- Updated help text with bookmark feature description and install instructions
- Updated both READMEs with aweshelf integration docs

## v0.1.5

`v0.1.5` fixes a model picker display issue when switching profiles and improves unknown-profile error messages.

### Model picker label fix

When a profile sets `ANTHROPIC_DEFAULT_HAIKU_MODEL` (or `SONNET`/`OPUS`), Claude Code's `/model` picker uses the corresponding `_NAME` variant as the display label. If `~/.claude/settings.json` already defines a `_NAME` variant for a different provider, the profile's model value alone wouldn't override the label, causing stale names to appear. aweswitch now automatically sets `_NAME` variants to match the model value at launch time, so users only need to configure the model itself.

### Highlights

- Auto-sync `ANTHROPIC_DEFAULT_*_MODEL_NAME` with the model value on profile launch
- Suggest `aweswitch list` when an unknown profile name is used
- Bumped `__version__` to stay in sync with `pyproject.toml`

## v0.1.4

`v0.1.4` replaces the `help` subcommands with an interactive `add` command for creating new profiles, and improves test coverage and documentation.

### Interactive profile creation

The `help` and `config help` subcommands have been removed. In their place, `aweswitch add` walks through an interactive prompt to create a new profile: name, base URL, auth token variable, model, and optional haiku/sonnet model overrides. Empty optional fields are skipped automatically, and duplicate profile names are rejected.

### Highlights

- Added `aweswitch add` command for interactive profile creation
- Added `save_profile()` helper with duplicate detection and empty-value filtering
- Removed `help` and `config help` subcommands
- Updated README version badges and install examples to v0.1.4

## v0.1.3

`v0.1.3` adds the GitHub Actions release path for aweswitch. The repository now has the same basic CI and tag-driven release structure used by aweskill, adapted for Python packaging and PyPI publishing.

### GitHub Actions release automation

Pushing a `v*` tag now runs the release workflow: it verifies the tag matches the package version, runs the test suite, builds the wheel and source distribution, checks package metadata, extracts release notes from this changelog, creates the GitHub Release, and publishes to PyPI with the configured `PYPI_API_TOKEN` secret.

### Highlights

- Added CI workflow for Python 3.9 and 3.13 across Linux, macOS, and Windows
- Added package build and `twine check` validation to CI
- Added tag-triggered release workflow for GitHub Releases and PyPI publishing
- Added a tag/package version consistency check before publishing
- Updated release-sensitive README version references

## v0.1.2

`v0.1.2` switches Claude profile settings injection from inline JSON to a temporary file. This keeps API tokens out of the process listing.

### Settings file injection

Previously, `aweswitch` passed `--settings '{"env": {...}}'` directly on the command line, which meant tokens were visible in `ps` output. Now it writes the settings object to a temporary file with `0o600` permissions and passes the file path to Claude Code instead.

### Highlights

- Settings written to a temporary file instead of inline JSON
- Temp file created with `0o600` permissions
- Tests updated for the new settings file approach
- Added PyPI downloads and GitHub stars badges to both READMEs

## v0.1.1

`v0.1.1` merges the `dev` branch into `main`. Profiles are now grouped under provider keys, the default config is Claude-only, and both README files include a hero image.

### Provider-grouped profiles

Profiles now live under provider groups:

```json
{
  "profiles": {
    "claude": {
      "cc-glm": {
        "env": {
          "ANTHROPIC_MODEL": "glm-5.1"
        }
      }
    }
  }
}
```

Profile names are still invoked directly with `aweswitch <profile>`, so existing command usage stays short. If a profile name appears under multiple providers, aweswitch reports it as ambiguous.

### Claude-only default config

The default config now contains only Claude Code profiles. Codex and Hermes are reserved for future provider support and are not executable in the current CLI.

### Documentation refresh

The README files were reworked around the same structure used by the larger aweskill project: concise positioning, install steps, FAQ, quick start, config rules, and development notes. Contributor guidance now lives in `docs/CONTRIBUTING.md`. Both READMEs now show a hero image at the top.

### Highlights

- Grouped config under `profiles.claude`
- Removed per-profile `provider` fields
- Removed `codex-mini` from the default config
- Kept direct `aweswitch <profile>` invocation
- Added duplicate profile-name detection
- Added contributor documentation
- Refreshed English and Chinese READMEs
- Added hero image to README headers

## initial line

Earlier commits introduced the single-file Python launcher, externalized the default config template, added tests, inherited token values from Claude settings when needed, switched Claude profile env injection to runtime `--settings`, and documented Claude model override behavior.

## v0.1.0

`v0.1.0` is the first package-oriented release line for aweswitch. The project now installs as a Python package with a console-script entry point, while keeping the CLI intentionally small and dependency-free at runtime.

### Python package installation

aweswitch now uses a `pyproject.toml` package definition with a `src/aweswitch/` layout. The command is exposed through the package entry point:

```toml
[project.scripts]
aweswitch = "aweswitch.cli:main"
```

The default config template is bundled as package data, so `aweswitch config init` works after `pip install aweswitch` without copying files by hand.

### Agent profile switcher positioning

The project positioning was broadened from a Claude Code-only profile switcher to an agent profile switcher. The executable provider set remains intentionally limited to Claude Code for now.

### Similar tools

The README now calls out [cc-switch](https://github.com/farion1231/cc-switch) as a similar Claude Code switching tool and explains how aweswitch currently differs: smaller Python package, local JSON profiles, runtime-only Claude Code `--settings`, and redacted inspection commands.

### Highlights

- Started versioning at `v0.1.0`
- Added `pyproject.toml`
- Moved implementation into `src/aweswitch/cli.py`
- Added the `aweswitch = "aweswitch.cli:main"` console script
- Bundled `default-config.json` as package data
- Updated README badges in the aweskill style
- Repositioned aweswitch as an agent profile switcher
- Added a similar-tools note for `cc-switch`
