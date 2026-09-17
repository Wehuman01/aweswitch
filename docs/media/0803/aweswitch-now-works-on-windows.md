# aweswitch: Who Says Windows Can't Be Just as Smooth

![aweswitch](../../../logo/hero.png)

I finally got on Windows. I open `cmd.exe` and type `aweswitch cc-glm`. I open PowerShell and type the same thing. It comes back just as smooth. I close the laptop, get coffee, and tell my agent:

> "My `GLM_ANTHROPIC_AUTH_TOKEN` is not being picked up on Windows. Figure out why and fix it."

When I came back, the token was in the user environment, the profile launched cleanly from both `cmd.exe` and PowerShell, and the agent had a one-paragraph summary of what it changed. The setup that worked on macOS for months now works on Windows. Same command, same result, both shells.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## Two Bugs, Fixed

Windows support had been "shipped" since v0.2.0. The Python code ran. The CLI worked. What did not work was the setup, and the setup is the part users actually hit first.

**Bug 1: the docs were PowerShell-only.** `aweswitch` told Windows users to put tokens in `$PROFILE`, which only PowerShell reads. `cmd.exe` users — a lot of Windows users — would set the token, restart their terminal, run `aweswitch <profile>`, and watch the same `command not found: claude` come back. The same machine, the same token, the same minute, two different answers depending on which window you opened.

**Bug 2: `.ps1` shims were invisible to the launcher.** Even after the docs got fixed, some Windows users were still hitting `command not found`. Their `claude` was installed as a `.ps1` script — the default way npm-on-Windows installs Node CLIs — and `aweswitch`'s launch path could not find it. The user-visible symptom was the same: a profile that worked on macOS would not launch on Windows. The cause was completely different: a code path that did not know how to ask Windows to run a PowerShell script.

v0.3.5 fixes both.

## What Changed

### `setx` instead of `$PROFILE`

`setx` writes to the user environment store — the same place the System Properties GUI edits. Both `cmd.exe` and PowerShell read it on the next launch. `$PROFILE` is still supported, but only as a PowerShell-only alternative.

The new setup on Windows:

```bat
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
```

Open a new terminal afterwards (`setx` does not affect the current one), then `aweswitch cc-glm` works the same way it does on macOS. The agent handles this for you if you ask: it runs `setx`, checks the value back, and tells you to open a new terminal.

The platform table in the skill now reads:

| Platform | Target | Scope |
|---|---|---|
| zsh (macOS default) | `~/.zshrc` | all zsh shells |
| bash | `~/.bashrc` or `~/.bash_profile` | all bash shells |
| Windows | `setx` | **cmd and PowerShell both** |
| Windows (PowerShell only) | `$PROFILE` | PowerShell only |

### `.ps1` agent binaries now launch

If your `claude` or `codex` is installed as a `.ps1` shim (the npm-on-Windows default), `aweswitch <profile>` now finds it and launches it. The launcher does the obvious thing: when the binary resolves to a `.ps1` file, it routes through `powershell.exe -File` with `-ExecutionPolicy Bypass` so the script runs without prompting. `.exe`, `.cmd`, and `.bat` keep working as before.

You do not see any of this. You just see `aweswitch cc-glm` start Claude Code from `cmd.exe` on a Windows machine for the first time and work.

## A Day on Windows

It is Wednesday. You are on a Windows machine with `cmd.exe` open in one window and PowerShell in another.

**9:00 AM.** First time install:

```cmd
pip install aweswitch
aweswitch -v
```

You try `aweswitch cc-glm` to test the bundled profile. `command not found: claude`. You paste the error to your agent. It runs `setx` for you, tells you to open a new terminal, and walks away. You do. `aweswitch cc-glm` now launches Claude Code against the GLM proxy. The same command also works in PowerShell in the other window.

**10:30 AM.** You want a second profile for Mimo:

> "Add a Mimo profile. I have `XIAOMI_ANTHROPIC_AUTH_TOKEN` in my env already."

The agent runs `aweswitch add`, picks `claude` as the provider, names the profile `cc-mimo`, wires it to the Xiaomi base URL and `${XIAOMI_ANTHROPIC_AUTH_TOKEN}`. It does not run `setx` because you said the token was already in your env. It checks first, to be sure.

```bash
aweswitch cc-mimo
```

A second terminal, a second session, a different model. The first session is still on GLM.

**1:00 PM.** You need to compare GLM and Mimo on a code review. Two parallel sessions:

```bash
aweswitch cc-glm -c review -t "PR #247 review"      # terminal 1 (cmd.exe)
aweswitch cc-mimo -c review -t "PR #247 review"     # terminal 2 (PowerShell)
```

Both bookmarked. The cmd.exe one finds `claude.cmd` and runs it. The PowerShell one finds `claude.ps1` and runs it through `powershell.exe -File`. Neither fails. You flip between them with `aweshelf browse` to compare outputs.

**3:00 PM.** You notice a typo in your codex profile:

> "Fix the base URL in `cx-aihubmix` to `https://aihubmix.com/v1`."

The agent reads the config, makes the edit, runs `aweswitch show cx-aihubmix` to verify, and reports back. No restart needed.

**5:00 PM.** You are done. Three profiles, two parallel sessions, one config edit, two bookmarks. You never opened `$PROFILE`. You never pasted a token into a JSON file. The Windows setup is the same as the macOS setup: install, set env, launch.

## What the Agent Now Reaches on Windows

The skill picked up two new powers in v0.3.5:

| You say | The skill runs |
|---|---|
| "Set up `OPENAI_API_KEY` for Windows." | `setx OPENAI_API_KEY "..."` |
| "Switch to cc-mimo." | `aweswitch cc-mimo` — finds and runs `.ps1`, `.cmd`, or `.exe` automatically |
| "Read my current Windows env." | `[Environment]::GetEnvironmentVariable("VAR", "User")` |
| "Remove `OLD_TOKEN`." | `setx OLD_TOKEN ""` |
| "List my aweswitch profiles." | `aweswitch list` |
| "Show me cc-glm." | `aweswitch show cc-glm` |
| "Add a codex profile for AiHubMix." | edits `~/.config/aweswitch/config.json` |

Before v0.3.5, the agent had a Windows-shaped hole in its toolbelt: it could edit the config (cross-platform), launch profiles (cross-platform after v0.2.0), and apply them (cross-platform after v0.3.0), but it had no safe way to *set the env vars the profiles referenced* without lying to half the shells on the system. The `setx` / `[Environment]::SetEnvironmentVariable` pair closes that gap.

## The Same Experience

For Windows users, the flow is now identical to macOS. Install. Set the token. Launch. The shell is `cmd.exe` instead of `zsh`, the env-var command is `setx` instead of `export`, and nothing else changes. `aweswitch cc-glm` does the same thing it does everywhere else. So does `aweswitch apply cc-glm`, `aweswitch list`, `aweswitch add`, `aweswitch show`, and `aweswitch restore`. Same config file, same command names, same behavior.

That sameness extends to the `/aweswitch` skill. Windows users get the same natural-language interface that macOS and Linux users have had since v0.1.9. The skill reads the same `README.ai.md`, walks through the same `aweswitch add` flow, edits the same `~/.config/aweswitch/config.json`, and routes the setup through `setx` instead of `~/.zshrc` when it detects Windows. The agent does not need a separate "Windows mode" — it picks the right command for the platform and runs it.

> "Add a codex profile for AiHubMix. I have `AIHUBMIX_OPENAI_KEY` in my user env."

That prompt works the same way on a Windows laptop as it does on a Mac. The agent runs `aweswitch add`, picks the provider, names the profile, wires it to the token, and verifies with `aweswitch show`. No shell-specific incantations on your part. The setup is a task. The agent does tasks. So I gave the task to the agent.

## Try It on Windows

### Let the agent set it up

If you are in Claude Code, Codex, Cursor, or another coding agent, tell it:

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

The agent installs the CLI, runs `setx GLM_ANTHROPIC_AUTH_TOKEN "..."` for you, checks the value back, and tells you to open a new terminal. From there `aweswitch cc-glm` works the same way it does on macOS.

### Or do it by hand

```cmd
pip install aweswitch
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
aweswitch -v
aweswitch cc-glm
```

Open a new terminal after `setx`. `.ps1`, `.cmd`, and `.exe` shims all work.

That is the whole Windows experience now. Same config, same command, same `/aweswitch` skill, same agent managing it for you.

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.wehuman.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
