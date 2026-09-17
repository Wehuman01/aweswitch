# aweswitch: OpenCode Agents, and Beyond

![aweswitch](../../../logo/hero.png)

aweswitch has evolved from a profile switcher into a cross-platform agent profile manager. The latest release adds OpenCode as a first-class provider, pairs it with OpenCode's native `@` agent calling, and rounds out the platform with security and portability fixes.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## OpenCode Provider

v0.3.2 adds OpenCode as the third supported provider, joining Claude Code and Codex. aweswitch now manages three agent platforms from a single CLI.

### The Problem

OpenCode uses its own configuration format — `~/.config/opencode/opencode.json` — with provider-specific fields: `npm` package, `baseURL`, model dictionaries. Setting this up by hand means editing JSON, copying API keys into plaintext, and repeating the process for every endpoint. Switching providers means editing files again.

If you use Claude Code, Codex, and OpenCode together, you juggle three separate config systems with no shared tooling.

### The Solution

`aweswitch add` now includes `opencode` as a provider option:

```bash
aweswitch add
# > Provider: claude | codex | opencode
```

Pick `opencode`. Enter the base URL, the API key environment variable name, and the model. aweswitch stores this in its own config at `~/.config/aweswitch/config.json`:

```json
"oc-xiaomi": {
  "env": {
    "OPENCODE_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/v1",
    "OPENCODE_API_KEY": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
    "OPENCODE_MODEL": {
      "mimo-v2.5-pro": "MiMo-v2.5-Pro",
      "mimo-v2.5": "MiMo-v2.5"
    }
  }
}
```

That is all you write. On first launch, aweswitch expands this into the full provider block that OpenCode expects in `~/.config/opencode/opencode.json`:

```json
{
  "provider": {
    "oc-xiaomi": {
      "models": { "mimo-v2.5-pro": { "name": "MiMo-v2.5-Pro" } },
      "name": "oc-xiaomi",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "{env:XIAOMI_ANTHROPIC_AUTH_TOKEN}",
        "baseURL": "https://token-plan-sgp.xiaomimimo.com/v1"
      }
    }
  }
}
```

The verbose part — `npm` package, `options` nesting, `models` dict — is generated automatically. You only manage the flat version: base URL, env var reference, and model names.

Two things matter here:

1. **`{env:VAR}` keeps keys out of the file.** The literal `{env:XIAOMI_ANTHROPIC_AUTH_TOKEN}` is what gets written. OpenCode resolves it from the environment at runtime. The file is safe to commit, share, or diff.
2. **`OPENCODE_MODEL` carries display labels.** The dict format `{"mimo-v2.5-pro": "MiMo-v2.5-Pro"}` maps internal model IDs to human-readable names. aweswitch passes these through to OpenCode's `models` dict.

Launch an OpenCode session:

```bash
aweswitch oc-glm glm-5.1
```

That reads the `oc-glm` profile, expands the environment, and starts OpenCode with `glm-5.1` as the active model. If you omit the model, the first model in `OPENCODE_MODEL` is used.

`OPENCODE_MODEL` also accepts a simple string (`"glm-5.1"`) or a list (`["glm-5.1", "glm-4.6"]`) if you don't need display labels. The dict format shown above is the most explicit.

### When to Use Which Mode

**Launch mode** starts a new OpenCode session with a specific profile:

```bash
aweswitch oc-glm glm-5.1
```

- Each session has its own environment
- Multiple profiles run simultaneously in different terminals
- Use when you need parallel, isolated sessions

**Apply mode** (Claude only) writes the profile to `~/.claude/settings.json`:

```bash
aweswitch apply cc-glm
```

- Environment persists across sessions
- Use when one model dominates your workflow

| Provider | Launch mode | Apply mode |
|----------|------------|------------|
| Claude | supported | supported |
| Codex | supported | not supported |
| OpenCode | supported | not supported |

## Subagents via @

The provider layer gives OpenCode a connection. But a single model per session is limiting. OpenCode's agent directory lets you define multiple models and invoke them with `@` — without leaving the conversation.

### The Problem

Running multiple models usually means multiple terminals, multiple processes, multiple context windows. You switch models by switching windows. Context does not carry over.

### The Solution

Each agent is a markdown file in `~/.config/opencode/agents/`. The filename becomes the agent name. YAML frontmatter defines the configuration.

Create three agents:

`~/.config/opencode/agents/glm.md`

```markdown
---
description: General assistant
mode: subagent
model: oc-glm/glm-5.1
---
```

`~/.config/opencode/agents/step.md`

```markdown
---
description: General assistant
mode: subagent
model: stepfun/step-3.7-flash
---
```

`~/.config/opencode/agents/xiaomi.md`

```markdown
---
description: General assistant
mode: subagent
model: oc-xiaomi/mimo-v2.5-pro
---
```

Three fields. That is the entire file.

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | Agent label shown in the `@` picker |
| `mode` | Yes | `subagent` for invocable child agents |
| `model` | Yes | `provider/model` — matches the provider key in `opencode.json` |

Any text below the frontmatter becomes the agent's system prompt. You can specialize agents without touching provider config:

```markdown
---
description: Code reviewer
mode: subagent
model: oc-glm/glm-5.1
---

You are a senior code reviewer. Focus on correctness, performance, and security.
```

### How @ Works

In an OpenCode conversation, call any agent by name:

```
@glm Create a REST endpoint for user profile updates
@step Review the validation middleware for edge cases
@xiaomi Write API documentation describing this endpoint's request and response format
```

Each `@` invocation routes to the model defined in that agent's config. No new terminal. No profile switch. No lost context. The main thread stays put while the sub-agent runs on its own model and hands the result back.

### aweswitch and OpenCode: The Division of Labor

aweswitch manages the infrastructure. OpenCode manages the orchestration.

| Layer | Tool | Responsibility |
|-------|------|----------------|
| Provider config (`opencode.json`) | aweswitch | API key, base URL, model definitions |
| Agent routing (`agents/*.md`) | OpenCode | Which model each `@`-agent uses, system prompts |

Keep them separate and they compose cleanly. Change a key in aweswitch and every agent on that provider picks it up. Add a new agent file and it works with whatever providers aweswitch has already configured.

### A Day in Practice

Morning. You set up providers with aweswitch and create three agent files. You launch with GLM as the default:

```bash
aweswitch oc-glm glm-5.1
```

You start a new API route. GLM generates the handler and validation middleware.

Mid-morning. You want a second opinion on the validation logic:

```
@step Review the validation middleware for edge cases
```

Step catches an unhandled case: partial updates with null fields. You fix it, still in the same thread.

Afternoon. You're writing documentation. You want a concise Chinese summary:

```
@xiaomi Write API documentation describing this endpoint's request and response format
```

MiMo produces the documentation. You paste it into the README.

Evening. A teammate asks which model wrote a given function. It doesn't matter — every `@`-call is logged in the thread. You can see exactly where GLM ended and Step began.

## Other Updates

### v0.3.3 — Security Hardening

`OPENCODE_API_KEY` must now use `{env:VAR}` syntax. Plain-text keys are rejected at startup with a clear error message. This prevents accidental secret writes to `opencode.json`.

Temporary settings files in `/tmp/aweswitch/` are now garbage-collected on each launch. Files older than 24 hours are removed before creating a new one.

`aweswitch apply` now fails with a clear message if the settings backup cannot be created (e.g. disk full), instead of silently continuing.

## Why It Matters

aweswitch started as a profile switcher for one agent. Adding OpenCode makes it a switcher for three — Claude Code, Codex, and OpenCode — all from the same `aweswitch add` / `aweswitch <profile>` interface.

OpenCode adds something the other two do not: a native way to run multiple models *inside one conversation*. The agents directory plus `@` invocation turns a single session into a team of specialists. One writes, one reviews, one summarizes — each on the model that fits the job.

The split between aweswitch and OpenCode is deliberate. aweswitch manages connections — API keys, base URLs, which models exist. OpenCode manages orchestration — which agent runs which model, and when. The `{env:VAR}` boundary is the contract between them: secrets live in the environment, config lives in files, and nothing sensitive ever touches disk.

The core principle carries over from day one: named profiles, runtime injection, no secrets on disk. OpenCode support just extends it to a third platform — and to a new way of working where the right model is always one `@` away.

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
