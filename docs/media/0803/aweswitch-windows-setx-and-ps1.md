# aweswitch: I Asked My Agent to Set Up My Token, and It Worked

![aweswitch](../../../logo/hero.png)

I am on Windows. I open `cmd.exe` and type `aweswitch cc-glm`. I get back: `command not found: claude`. I open PowerShell. I type the same thing. I get back the same error. I close the laptop, get coffee, and tell my agent:

> "My `GLM_ANTHROPIC_AUTH_TOKEN` is not being picked up on Windows. Figure out why and fix it."

When I came back, the token was in the user environment, the profile launched cleanly from both `cmd.exe` and PowerShell, and there was a backup `.ps1` wrapper in the logs explaining what had changed. The agent had diagnosed the problem — `aweswitch` was writing the token to `$PROFILE`, which only PowerShell reads — and rewired the setup to use `setx` so both shells could see it.

That is the new shape of Windows support for an agent tool. The bug is in the docs, not the code. The agent reads the docs. So I gave the task to the agent.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## The Bug: One Shell Sees, the Other Doesn't

Most agent tools treat Windows as an afterthought. The Python package is cross-platform — `subprocess.run`, `os.path.join`, the whole deal — but the *instructions* still say "add this to your `~/.zshrc`." On Windows there is no `~/.zshrc`. There is `$PROFILE` for PowerShell and the user environment store (the thing the System Properties GUI edits) for everything else. They do not overlap.

aweswitch's `README.ai.md` told Windows users to put tokens in `$PROFILE`. PowerShell users were fine. `cmd.exe` users — and that is a lot of Windows users — were not. The same `aweswitch cc-glm` worked in one terminal and failed in the next, with the same token, on the same machine, at the same minute. The setup procedure was lying to half its users.

The fix had two parts, and the second part exposed a second bug.

### Part 1: `setx`, Not `$PROFILE`

The new guidance is to use `setx`, which writes to the user environment store. Both `cmd.exe` and PowerShell read it on the next launch. `$PROFILE` stays documented as the PowerShell-only alternative for users who want it.

```bat
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
setx XIAOMI_ANTHROPIC_AUTH_TOKEN "sk-..."
setx OPENAI_API_KEY "sk-..."
```

The PowerShell equivalent, in case the user prefers it:

```powershell
[Environment]::SetEnvironmentVariable("GLM_ANTHROPIC_AUTH_TOKEN", "sk-...", "User")
```

Read it back or remove it the same way:

```powershell
[Environment]::GetEnvironmentVariable("GLM_ANTHROPIC_AUTH_TOKEN", "User")   # read
[Environment]::SetEnvironmentVariable("GLM_ANTHROPIC_AUTH_TOKEN", $null, "User")   # remove
```

The agent is now allowed to run `setx` on the user's behalf. It is a non-interactive command in the same class as `aweswitch apply` — no shell prompt, no input form, no editor. The user is told to open a new terminal afterwards because `setx` does not affect the current one.

The `SKILL.md` platform table now reads:

| Platform | Target | Scope |
|---|---|---|
| zsh (macOS default) | `~/.zshrc` | all zsh shells |
| bash | `~/.bashrc` or `~/.bash_profile` | all bash shells |
| Windows | `setx` (writes user environment variables) | **cmd and PowerShell both** |
| Windows (PowerShell only) | `$PROFILE` | PowerShell only |

`/M` is not passed to `setx` — that targets machine scope and requires admin. The agent knows this and does not try.

### Part 2: `.ps1` Was Already Broken

The day after the docs went out, a Windows user filed a different bug. `aweswitch <profile>` failed with `command not found: claude` even after the token was set, even from PowerShell, even after restarting. The agent looked at the launch path in `src/aweswitch/cli.py` and spotted it.

The Windows branch of `exec_agent` was passing `argv[0]` directly to `subprocess.run`, which uses `CreateProcessW`. `CreateProcess` does not do PATHEXT resolution for a bare command name, and it cannot execute `.ps1` scripts at all. The user had `claude` installed via npm, which on Windows drops a `claude.ps1` shim into `AppData\Roaming\npm\`. `aweswitch` was looking for `claude.exe`, not finding it, and giving up.

The fix is the part of v0.3.5 that is actually code, not docs:

```python
resolved = shutil.which(argv[0], path=env.get("PATH"))
if resolved:
    if resolved.lower().endswith(".ps1"):
        pwsh = (shutil.which("powershell", path=env.get("PATH"))
                or shutil.which("powershell.exe", path=env.get("PATH"))
                or "powershell.exe")
        argv = [pwsh, "-NoLogo", "-ExecutionPolicy", "Bypass",
                "-File", resolved, *argv[1:]]
    else:
        argv = [resolved, *argv[1:]]
```

`shutil.which` honors `PATHEXT`, so it finds `.cmd`, `.bat`, `.exe`, and `.ps1` in one call. For `.ps1` hits, the command is re-routed through `powershell.exe -NoLogo -ExecutionPolicy Bypass -File`, which is how the user would have invoked it by hand. `.exe`, `.cmd`, and `.bat` run as-is — the Go-binary case (`opencode.exe`) and the npm shim case (`claude.cmd`) both go through the same path.

Three new unit tests cover the three cases by mocking `os.name == "nt"` and patching `shutil.which`. The real Windows path is exercised by CI on `windows-latest`.

The macOS and Linux branches are unchanged.

## A Day on Windows

It is Wednesday. You are on a Windows machine, dual-booted, with `cmd.exe` open in one window and PowerShell in another. (You switched a month ago after `bash` on Windows got weirder than you wanted to debug.)

**9:00 AM.** You install aweswitch for the first time:

```cmd
pip install aweswitch
aweswitch -v
```

The install works. You try `aweswitch cc-glm` to test the bundled profile. `command not found: claude`. You paste the error to your agent. It reads `README.ai.md`, spots the Windows section, and runs `setx` for you:

```cmd
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
```

It tells you to open a new terminal. You do. `aweswitch cc-glm` now launches Claude Code against the GLM proxy. No `command not found`. The same command also works in PowerShell in the other window.

**10:30 AM.** You want a second profile for Mimo. You tell the agent:

> "Add a Mimo profile. I have `XIAOMI_ANTHROPIC_AUTH_TOKEN` in my env already."

The agent runs `aweswitch add`, picks `claude` as the provider, names the profile `cc-mimo`, wires it to the Xiaomi base URL and `${XIAOMI_ANTHROPIC_AUTH_TOKEN}`. It does not run `setx` because you said the token was already in your env. It checks with `[Environment]::GetEnvironmentVariable("XIAOMI_ANTHROPIC_AUTH_TOKEN", "User")` to be sure, and it is.

```bash
aweswitch cc-mimo
```

A second terminal, a second session, a different model. The first session is still on GLM.

**1:00 PM.** You need to compare GLM and Mimo on a code review. Two parallel sessions:

```bash
aweswitch cc-glm -c review -t "PR #247 review"      # terminal 1 (cmd.exe)
aweswitch cc-mimo -c review -t "PR #247 review"     # terminal 2 (PowerShell)
```

Both bookmarked. The cmd.exe one resolves `claude.cmd` via `shutil.which` and execs it as-is. The PowerShell one resolves `claude.ps1` and gets routed through `powershell.exe -ExecutionPolicy Bypass -File`. Neither fails. You flip between them with `aweshelf browse` to compare outputs.

**3:00 PM.** You notice a typo in your codex profile. You tell the agent:

> "Fix the base URL in `cx-aihubmix` to `https://aihubmix.com/v1`."

The agent reads the config, makes the edit, runs `aweswitch show cx-aihubmix` to verify, and reports back. No restart needed. Next time you run `aweswitch cx-aihubmix`, the new URL is in effect.

**5:00 PM.** You are done. Three profiles, two parallel sessions, one config edit, two bookmarks. You never opened `$PROFILE`. You never pasted a token into a JSON file. The Windows setup is the same as the macOS setup: install, set env, launch. That is the goal.

## What Changed in v0.3.5

For users, the visible changes are two:

1. **`setx` is now the recommended way to set tokens on Windows.** The PowerShell-only `$PROFILE` flow is still supported, but it is no longer the default. Both `cmd.exe` and PowerShell users now get the same result from the same setup.

2. **`.ps1` agent binaries are now routed through PowerShell automatically.** If your `claude` or `codex` is installed as a `.ps1` shim (the npm-on-Windows default), `aweswitch <profile>` finds it and launches it without any extra configuration.

Behind the scenes, three documentation files were updated — `README.md`, `README_cn.md`, and `README.ai.md` — plus the bundled `SKILL.md` for AI agents. The platform badge in the README is now `ubuntu | macOS | windows`, and the tagline on both READMEs now reads: *"One config, one command — works the same on Ubuntu, macOS, and Windows."* The README had been claiming "works the same on Windows" since v0.2.0. v0.3.5 is the release where that is actually true.

The OpenCode provider got a documentation refresh in the same release — full provider examples covering the three `OPENCODE_MODEL` formats and the `{env:VAR}` key storage policy — but that is a separate story.

## The Stack: What the Agent Now Reaches on Windows

The `aweswitch` skill picked up two new powers in v0.3.5:

| You say | The skill runs |
|---|---|
| "Set up `OPENAI_API_KEY` for Windows." | `setx OPENAI_API_KEY "..."` (or reads `$PROFILE` if you say PowerShell-only) |
| "Switch to cc-mimo." | `aweswitch cc-mimo` — resolves `claude.ps1` via `shutil.which`, routes through PowerShell automatically |
| "Read my current Windows env." | `[Environment]::GetEnvironmentVariable("VAR", "User")` |
| "Remove `OLD_TOKEN`." | `setx OLD_TOKEN ""` or `[Environment]::SetEnvironmentVariable(..., $null, "User")` |
| "List my aweswitch profiles." | `aweswitch list` |
| "Show me cc-glm." | `aweswitch show cc-glm` |
| "Add a codex profile for AiHubMix." | edits `~/.config/aweswitch/config.json` |

The new rows are the first three. Before v0.3.5, the agent had a Windows-shaped hole in its toolbelt: it could edit `~/.config/aweswitch/config.json` (cross-platform), launch profiles (cross-platform after v0.2.0), and apply them to `~/.claude/settings.json` (cross-platform after v0.3.0), but it had no safe way to *set the env vars the profiles referenced* without lying to half the shells on the system. The `setx` / `[Environment]::SetEnvironmentVariable` pair closes that gap.

## Why It Matters

There are two ways to ship a cross-platform tool. The first is to make the code portable and call it done. The second is to make the *setup* portable too.

The first version is what most tools ship. The Python runs on Windows. The CLI works. The README has a section at the bottom titled "Windows" that says "use PowerShell" and moves on. The user who actually follows the instructions discovers, three months later, that their `cmd.exe` scripts broke because the token was never in the env.

The second version is harder because the Windows setup is not just a port — it is a different mental model. macOS users think in shell config files. Windows users think in the System Properties GUI, or in PowerShell profiles, or in nothing at all. The `setx` command is the bridge: it writes to the same store the GUI writes to, and both shells read it. It is the only Windows-specific concept aweswitch now needs.

The `.ps1` shim fix is the same kind of work, one level down. `subprocess.run` does not speak PowerShell natively, but Windows does — it just routes through `powershell.exe -File`. The fix is six lines of Python that say "if the thing we are about to launch ends in `.ps1`, wrap it." That is the whole Windows support story for code execution: the OS already knows how to run it; we just have to ask correctly.

The v0.2.0 release was the headline "Windows support" because the code path stopped crashing. The v0.3.5 release is the quieter one where the setup actually works the same way. Same config, same command, same token, same result — whether you open `cmd.exe`, PowerShell, or neither.

## Try It on Windows

```cmd
pip install aweswitch
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
aweswitch -v
aweswitch cc-glm
```

If `claude` is installed as a `.ps1` shim, the third command works. If it is installed as a `.cmd` or `.exe`, it also works. If the token is set in `cmd.exe` and you switch to PowerShell, it still works. Open a new terminal first — `setx` does not affect the current one.

Then ask the agent:

> "Add a codex profile for AiHubMix. I have `AIHUBMIX_OPENAI_KEY` in my user env."

The agent reads the config, makes the edit, verifies with `aweswitch show`, and reports back. No shell-specific incantations on your part.

The setup is a task. The agent does tasks. So I gave the task to the agent.

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
