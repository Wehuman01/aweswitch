# aweswitch: Apply Mode, and Beyond

![aweswitch](../../../logo/hero.png)

aweswitch has evolved from a Claude Code profile switcher into a cross-platform agent profile manager. The latest release introduces a new way to switch profiles without launching a new process, alongside broader platform and provider support.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## Apply Mode

v0.3.0 introduced `apply` and `restore` commands. This is a fundamentally different way to use aweswitch.

### The Problem

Launch mode (`aweswitch <profile>`) starts a new Claude Code session with the profile's environment injected at process level. This works well for parallel terminals and isolated sessions. But it has a limitation: once launched, the session's environment is frozen. You cannot switch models mid-session using `/model`.

If you want to change models without closing the terminal, you need to exit, run aweswitch again, and start a new session. The session context is lost.

### The Solution

Apply mode writes the profile's environment directly to `~/.claude/settings.json`:

```bash
aweswitch apply cc-glm
```

This updates the settings file with the profile's environment variables. The next Claude Code session — or the current one, if you use `/model` — picks up the new values. No new process needed.

### How It Works

When you run `aweswitch apply`:

1. The profile's environment is expanded (including `_NAME` variants for the `/model` picker)
2. A backup of `~/.claude/settings.json` is created (only on first apply)
3. The expanded environment is merged into the settings file
4. The profile's variables are now the default for all Claude Code sessions

The backup is preserved across subsequent applies. Use `--force` to overwrite it:

```bash
aweswitch apply cc-glm --force
```

Restore the original settings at any time:

```bash
aweswitch restore
```

### When to Use Each Mode

**Launch mode** is for isolation:

```bash
aweswitch cc-glm          # Start new session with GLM
aweswitch cc-xiaomi       # Start another with Mimo in parallel
```

- Each session has its own environment
- Multiple profiles run simultaneously in different terminals
- Environment is frozen at launch time
- Use when you need parallel, independent sessions

**Apply mode** is for persistence:

```bash
aweswitch apply cc-glm    # Set GLM as default
claude                    # Start session (uses GLM)
/model                    # Switch model within session
```

- Environment is written to settings.json
- All new sessions use the applied profile
- `/model` works within the session
- Use when you want a single active profile across sessions

### A Typical Workflow

You work with GLM during the day. At night, you want to switch to a cheaper model for quick tasks:

```bash
aweswitch apply cc-haiku
```

Open Claude Code. The session starts with Haiku. You do your quick tasks.

The next morning, switch back:

```bash
aweswitch apply cc-glm
```

Open Claude Code. GLM is the default again. No profile arguments, no launch flags. Just `claude` and go.

### Isolating from cc-switch

If you use [cc-switch](https://github.com/farion1231/cc-switch) alongside aweswitch, be aware that `aweswitch apply` modifies `~/.claude/settings.json`. This can interfere with cc-switch's configuration.

To isolate the two tools, create a dedicated cc-switch profile that preserves your original settings:

```bash
# Save your current settings as a cc-switch profile
cc-switch save baseline

# Use aweswitch apply freely
aweswitch apply cc-glm
aweswitch apply cc-haiku

# Restore cc-switch baseline when needed
cc-switch restore baseline
```

This way, aweswitch apply operates on its own settings state, and cc-switch maintains a separate baseline. The two tools coexist without conflict.

### The Skill

The aweswitch skill for AI assistants defaults to apply mode. If you are using an AI agent to manage your profiles, it will use `aweswitch apply` unless you specify launch mode explicitly.

This makes profile switching seamless when working with AI: the agent can change your active profile without starting a new process.

## A Day in Practice

Morning. You start a debugging session with GLM:

```bash
aweswitch cc-glm -c backend -t "Debug payment webhook"
```

Launch mode, auto-bookmarked. You work for two hours.

Afternoon. You want to compare GLM and Mimo on a code review. Launch both in parallel:

```bash
aweswitch cc-glm -c review -t "Code review: PR #247"
aweswitch cc-xiaomi -c review -t "Code review: PR #247"
```

Two sessions, two endpoints, two bookmarks. You compare, close both.

Evening. You want a cheap model for quick edits. Apply Haiku as default:

```bash
aweswitch apply cc-haiku
```

Open Claude Code. Haiku is active. You use `/model` to switch to Sonnet for one specific task, then back to Haiku.

Next morning. Restore GLM:

```bash
aweswitch apply cc-glm
```

Or, if you are done with apply mode and want your original settings:

```bash
aweswitch restore
```

## Platform and Provider Support

v0.2.0 made aweswitch fully portable. Four Unix-specific calls were replaced with cross-platform alternatives:

- `os.fork()` → `threading.Thread` for auto-bookmark
- `os.execvpe()` → `subprocess.run()` on Windows
- `os.chmod()` skipped on Windows where it has no effect
- `shlex.split()` uses `posix=False` for correct path handling

Windows users can now launch profiles without hitting Unix-only system calls. CI covers Python 3.9 and 3.13 on Linux, macOS, and Windows.

v0.1.9 added OpenAI Codex as a supported provider. Profiles can now target Claude Code or Codex:

```json
{
  "profiles": {
    "claude": {
      "cc-glm": { "env": { "ANTHROPIC_MODEL": "glm-5.1" } }
    },
    "codex": {
      "codex-openai": {
        "env": {
          "OPENAI_BASE_URL": "https://api.openai.com/v1",
          "OPENAI_API_KEY": "$OPENAI_API_KEY"
        }
      }
    }
  }
}
```

When creating a profile with `aweswitch add`, you are prompted to choose a provider. Codex profiles launch with the appropriate CLI flags and environment injection.

## Why It Matters

aweswitch started as a profile switcher. It solved the problem of running multiple agent endpoints without breaking open sessions.

But switching has two dimensions: **process isolation** and **persistent configuration**. Launch mode handles the first. Apply mode handles the second.

With launch mode, each session is independent. You can run five different profiles in five terminals. The environment is frozen, predictable, and isolated.

With apply mode, the profile becomes the default. You set it once, and every new session uses it. You can change models within a session using `/model`. The environment is persistent, flexible, and shared.

These are not competing modes. They solve different problems. Launch mode is for parallel work. Apply mode is for sequential work. Together, they cover the full spectrum of how developers actually use AI coding agents.

Cross-platform support means Windows users are no longer second-class. Codex support means aweswitch is not tied to a single provider. These are foundational changes that make the tool viable for a wider audience.

The core principle remains: named profiles, runtime injection, no global config mutation (unless you explicitly ask for it with `apply`).

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
