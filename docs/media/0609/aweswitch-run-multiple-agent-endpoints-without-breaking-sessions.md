# aweswitch: Run Multiple Agent Endpoints Without Breaking Open Sessions

![aweswitch](../../../logo/hero.png)

Claude Code developers are using more endpoints than ever. The official Anthropic API. Zhipu GLM's Anthropic-compatible layer. A Gemini proxy. Xiaomi Mimo. Each endpoint has its own token, its own model name, its own pricing. You might use the official API during the day for deep debugging, switch to GLM at night for long-running tasks, and occasionally spin up Mimo for comparison testing.

That sounds reasonable. In practice, switching between endpoints is painful.

You open `~/.claude/settings.json`. You change `ANTHROPIC_BASE_URL`. You change `ANTHROPIC_AUTH_TOKEN`. You change `ANTHROPIC_MODEL`. You save the file. And then that Claude Code session you had open — the one running a refactoring — suddenly has a different API endpoint underneath it. The next request might fail outright because it is hitting the wrong endpoint.

Worse, you have three terminal windows open, each running Claude Code against a different endpoint. You change the global config. All three windows are affected.

That is the problem `aweswitch` solves — named profiles for multiple endpoints, with configuration injected only at launch time and never written to global settings.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## The Old Workflow: Edit Config, Hope for the Best

Without aweswitch, switching endpoints looks something like this:

1. Open `~/.claude/settings.json`
2. Find `ANTHROPIC_BASE_URL`, change it to the new endpoint
3. Find `ANTHROPIC_AUTH_TOKEN`, change it to the matching token
4. Find `ANTHROPIC_MODEL`, change it to the model the new endpoint supports
5. Save the file
6. Start a new Claude Code session
7. Hope the session you already had open does not break

Three fields to change every time. If you have four or five endpoints, remembering the triple (URL, token, model) for each one is a burden in itself.

Some people use shell aliases as a partial workaround:

```bash
alias cc-glm='ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=... ANTHROPIC_MODEL=... claude'
```

This works, but aliases cannot handle complex configuration well. Model overrides (haiku, sonnet) are awkward to set up. Token referencing and redaction do not happen. And the configuration is scattered across `.zshrc`, getting harder to maintain over time.

Other switching tools take the direct route: they rewrite the global agent settings file when you switch. This is simple, but it has a fatal flaw — all running sessions share the same configuration. Change it once, and they all break.

## The aweswitch Workflow: Named Profiles, Runtime Injection

`aweswitch` organizes endpoint configurations into named profiles, stores them in its own JSON file, and injects settings only when launching a new process.

Install:

```bash
pip install aweswitch
aweswitch config init
```

Add a profile:

```bash
aweswitch add
```

An interactive prompt asks for the profile name, endpoint URL, token environment variable name, and model. Or edit the config file directly:

```bash
aweswitch config edit
```

The config looks like this — grouped by provider, clean and readable:

```json
{
  "profiles": {
    "claude": {
      "cc-glm": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
          "ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "glm-5.1"
        }
      },
      "cc-gemini": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://generativelanguage.googleapis.com",
          "ANTHROPIC_AUTH_TOKEN": "${GEMINI_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "gemini-3.1-pro-preview"
        }
      },
      "cc-xiaomi": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
          "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "mimo-v2.5-pro"
        }
      }
    }
  }
}
```

Launch with a single command:

```bash
aweswitch cc-glm
```

That is it. No global files modified. No URLs or tokens to remember. No hoping.

## The Core Principle: Never Touch Global Config

The most important design decision in `aweswitch` is: **never mutate global agent configuration**.

It injects environment variables through Claude Code's runtime `--settings` argument, scoped to the child process being launched. Other sessions that are already open are completely unaffected.

This means you can do this simultaneously:

- Terminal 1: `aweswitch cc-glm` — running Zhipu GLM for a code review
- Terminal 2: `aweswitch cc-gemini` — running Gemini for documentation generation
- Terminal 3: `aweswitch cc-xiaomi` — running Mimo for comparison testing

Three sessions, three endpoints, three models, zero interference. Close one, and the other two keep working.

This is not just convenience — it is correctness. Global config mutation is a source of hard-to-reproduce bugs. Your session starts returning errors for no apparent reason, and you spend half an hour realizing it was because you changed the global settings the last time you switched endpoints. `aweswitch` eliminates this class of problem entirely.

## Use Case 1: Daily Multi-Endpoint Switching

You have three endpoints. During the day, you use the official Claude API for important work — it is the most reliable. At night, you run long tasks on GLM — better cost-efficiency. Occasionally, you experiment with Mimo.

Without aweswitch, every switch means manually editing config or maintaining a pile of brittle aliases.

With aweswitch:

```bash
aweswitch list
```

```
cc-glm      glm-5.1        https://open.bigmodel.cn/api/anthropic
cc-xiaomi   mimo-v2.5-pro  https://token-plan-sgp.xiaomimimo.com/anthropic
```

```bash
aweswitch cc-glm
```

One command to launch. Close the terminal when you are done. Next time, launch whichever profile you need. No URLs to remember, no token variable names to look up, no model names to memorize.

## Use Case 2: Side-by-Side Sessions for Comparison Testing

You are evaluating how different models handle the same task. You want to know how GLM, Gemini, and Mimo compare on code review quality.

You launch three terminal windows:

```bash
# Terminal 1
aweswitch cc-glm

# Terminal 2
aweswitch cc-gemini

# Terminal 3
aweswitch cc-xiaomi
```

All three sessions run simultaneously, each with its own endpoint and model. You give each one the same prompt and compare the output.

This is impossible with global-config switching tools — change the global config once, and all sessions are affected. `aweswitch`'s runtime injection makes parallel testing possible.

## Use Case 3: Token Security Without Plaintext

Each endpoint uses a different token. You do not want tokens sitting in plaintext inside config files.

`aweswitch` handles this with environment variable references. In the config, tokens use the `${VAR_NAME}` syntax:

```json
"ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}"
```

The actual token values live in shell environment variables:

```bash
export GLM_ANTHROPIC_AUTH_TOKEN="your-secret-token"
```

Put them in `~/.zshrc` and they are available in every new terminal. The config file contains only variable names — no plaintext tokens.

Beyond that, `aweswitch`'s inspection commands automatically redact sensitive fields:

```bash
aweswitch show cc-glm
```

In the output, fields matching token, key, secret, password, or auth are replaced with `***`. You can safely paste the `show` output into a chat for help without worrying about leaking credentials.

## Use Case 4: Tiered Model Configuration

Claude Code uses different models for different scenarios — the primary model for complex tasks, a lighter model for background work. You might want the primary model on `mimo-v2.5-pro` but lightweight tasks on `mimo-v2.5` to reduce cost.

`aweswitch` supports Claude model overrides:

```json
{
  "profiles": {
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
```

The primary model stays on `mimo-v2.5-pro`. Haiku-tier tasks automatically use `mimo-v2.5`. One profile handles the tiering — no extra configuration needed.

## Use Case 5: Pair with aweshelf and aweskill

`aweswitch` works well on its own. But in the [Webioinfo](https://www.webioinfo.top/) ecosystem, two companion tools make the workflow more complete:

- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager. When bookmarking a session, it records the aweswitch profile that was active. When restoring, the session restarts with the same endpoint, model, and token. Your GLM debugging session will not accidentally resume against the Gemini endpoint.
- **[aweskill](https://github.com/wehuman01/aweskill)** — Skill package manager for 47+ AI coding agents. Install `aweswitch` as a skill once, and any agent you use can read the SKILL.md and operate the CLI without manual setup.

The three tools have clear roles: **aweskill** installs skills, **aweswitch** manages runtime configuration, and **aweshelf** persists sessions. The agent handles all three — you focus on the code.

## Use Case 6: Add a New Endpoint Interactively

You just got access to a new endpoint. You do not want to edit a JSON file by hand.

```bash
aweswitch add
```

An interactive prompt walks you through:

1. Profile name (e.g., `cc-deepseek`)
2. Base URL
3. Auth token environment variable name
4. Model name
5. Optional haiku/sonnet model overrides

Once you fill in the fields, the profile is written to the config automatically. No manual JSON editing, no risk of format errors.

```bash
aweswitch cc-deepseek
```

Ready to use immediately.

## How It Differs from cc-switch

[cc-switch](https://github.com/farion1231/cc-switch) is another tool in the same space. It is a Tauri-based desktop application (Rust + React) with a graphical interface, system tray, database, and support for managing configurations across Claude Desktop, Codex, Gemini, Hermes, and other providers.

The core difference is **how switching works**:

**cc-switch** rewrites the agent's global configuration file when you switch profiles. This is straightforward — after switching, the next agent you launch picks up the new config. The trade-off is that all already-open sessions sharing that same configuration file are also affected. If you have Claude Code running in one terminal and switch to a different profile, that running session may start failing because the endpoint underneath it changed.

**aweswitch** never touches global configuration. It injects settings through runtime arguments, scoped to the new process being launched. Sessions that are already open are completely unaffected. You can run three Claude Code sessions against three different endpoints in three terminals, with zero interference.

This difference shapes when each tool is the right choice:

### When to use aweswitch

- You need to **run multiple Claude Code sessions with different endpoints simultaneously** — for example, comparing model outputs side by side
- You work primarily in the **CLI and terminal**, and do not need a graphical interface
- You want your **agent to operate the switcher automatically** — aweswitch's CLI can be registered as a Skill via aweskill, so agents can switch profiles through natural language
- You work on **remote servers, CI pipelines, or headless environments** where a GUI is not available
- You need **profile-aware session restoration** with aweshelf

### When to use cc-switch

- You prefer a **graphical interface** — one-click switching from the system tray, no commands to remember
- You use **Claude Desktop, Codex, Gemini CLI, Hermes**, and other agents — not just Claude Code
- You need to **manage MCP servers** — cc-switch has built-in MCP configuration management
- You want to **track usage and costs** — cc-switch includes usage tracking features
- You only **use one profile at a time** and do not need to run multiple endpoints in parallel

The two tools are not mutually exclusive. If you use Claude Code and need parallel multi-endpoint sessions, use aweswitch. If you use multiple agents and prefer a GUI, use cc-switch.

## Why This Matters

The AI coding agent ecosystem is diversifying fast. Developers no longer use a single endpoint. Official APIs, self-hosted proxies, third-party compatibility layers — each has its own strengths and use cases.

But the tooling has not kept up. Switching endpoints is still a manual, error-prone operation that breaks existing sessions. Many switching tools choose to rewrite global config because it is simple — but it is not correct.

`aweswitch` holds one principle: **every session keeps the configuration it started with**.

This is not a technical detail — it is a correctness guarantee. When you run `aweswitch cc-glm`, you know that session will keep using the GLM endpoint, no matter how many other profile sessions you launch afterwards. Your configuration will not be silently changed. Your sessions will not suddenly fail because global settings shifted underneath them.

It does not try to be a platform. It does not require an account. It does not sync anything to the cloud. Configuration lives on local disk in plain JSON. Five endpoints or fifty — the management workflow is the same.

## Awesome Ecosystem

aweshare is part of a growing family of "awesome" tools — CLI-first, local-first, and operable by AI agents.

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

