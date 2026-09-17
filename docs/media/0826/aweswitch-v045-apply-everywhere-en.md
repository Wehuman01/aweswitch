# aweswitch v0.4.5: Apply Everywhere — One Profile, Three Agents' Defaults

![aweswitch](../../../logo/hero.png)

My daily driver is a GLM profile. But I run three agents — Claude Code, Codex, OpenCode — and each keeps its own config file: `settings.json`, `config.toml`, `opencode.json`. Three files, three formats.

aweswitch's answer used to be launch mode: `aweswitch cc-glm` starts an isolated session, env vars frozen for that session alone. Elegant, until your fingers betray you and you type a bare `codex` — and you're back on last week's provider.

And before v0.4.5, `apply` only served Claude. Wanted your Codex or OpenCode defaults changed? Hand-edit the file yourself.

Before closing my laptop, I left my agent one sentence:

> "Write my common profiles into all three agents' default configs. I don't want to hand-edit another toml."

Then I went downstairs to pick up a package. By the time I climbed back up, I typed a bare `codex` — and it opened on my own model and endpoint. That's what a default feels like.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## v0.4.5: Apply for All Three Agents

aweswitch has two modes:

- **Launch mode** (`aweswitch <profile>`): starts a fresh session with its own env. Different terminals can run different profiles at once.
- **Write mode** (`aweswitch apply <profile>`): makes the profile the agent's persistent default.

As of v0.4.5, write mode covers all three:

```bash
aweswitch apply cc-glm    # Claude: env -> ~/.claude/settings.json
aweswitch apply cx-glm    # Codex: provider+model -> ~/.codex/config.toml
aweswitch apply oc-glm    # OpenCode: provider+models -> ~/.config/opencode/opencode.json
```

Or mix them in a single call — one per agent:

```bash
aweswitch apply cc-glm cx-glm oc-glm
```

The rule is simple: at most one Claude profile and one Codex profile per call (each only has one "active default"), while OpenCode takes as many as you like.

## The Codex TOML Edit Is Surgical

`config.toml` is the most hand-edited file of the three. A whole-file rewrite would be a disaster — comments and formatting gone. So Codex apply is surgical: it only touches the relevant section and leaves everything else intact. A `.toml.bak` is written first, and API keys are resolved from your existing `${VAR}` shell references rather than inlined as plaintext.

## OpenCode: Bulk Apply with Orphan Cleanup

OpenCode's config holds multiple providers side by side, so bulk is the natural shape:

```bash
aweswitch apply                # every OpenCode profile at once
aweswitch apply --prune-orphans
```

The second flag deserves a line of its own: renaming or deleting a profile used to leave orphan providers behind in `opencode.json`. apply now warns about them, and `--prune-orphans` removes the leftovers safely.

There's also a resume warning: `aweswitch oc-glm -s <session-id>` restores a prior session, and OpenCode brings back the model that session last used while ignoring `-m`. When the two don't match, aweswitch tells you so — hit Tab inside the TUI to switch.

## Slipped? Roll Back

Every write has an exit ramp:

- Codex writes a `.toml.bak` before touching anything
- Claude's `settings.json` backup is never silently overwritten — pass `--force` if you mean it
- Since v0.4.1, `aweswitch config backup` snapshots on demand and prints the path; `aweswitch config restore [FILE]` restores from the default backup or any explicit snapshot

| You say | skill runs |
|---|---|
| "Make GLM the default in all three agents." | `aweswitch apply cc-glm cx-glm oc-glm` |
| "Write every OpenCode profile." | `aweswitch apply` |
| "Clean up the orphan providers in opencode.json." | `aweswitch apply --prune-orphans` |
| "Back up settings.json first." | `aweswitch config backup` |
| "I broke it — roll back." | `aweswitch config restore` |
| "Launch that model by its short name." | `aweswitch cx-aihubmix step-router-v1` |

One-line summary: profiles used to take effect only when you launched through aweswitch — now they can be the agent's factory default.

## The Rest of the 0.4.x Line

- **v0.4.0** Official accounts as first-class citizens: Claude Code / Codex OAuth logins can coexist with private per-account dirs (the previous post in this series covers it in depth)
- **v0.4.1** Backup reorganized: new `aweswitch config backup`; `restore` moved to `config restore [FILE]` and can roll back to any explicit snapshot
- **v0.4.2** Launch by display value: when models are configured as a mapping, launch args can use the display name (`step-router-v1` instead of `peng1/step-router-v1`); ambiguous names are rejected with the matching candidates listed

Full details live in the [CHANGELOG](https://github.com/wehuman01/aweswitch/blob/main/docs/CHANGELOG.md).

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

### Or do it yourself

```bash
pip install aweswitch

# Make your common profiles the persistent defaults
aweswitch apply cc-glm cx-glm oc-glm

# Or just sweep OpenCode and prune orphans
aweswitch apply --prune-orphans

# Launching still works the same way
aweswitch cc-glm
```

No more memorizing which config lives in which file. One profile, three agents, and the default just is.

## More from the aweswitch Series

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)
- [aweswitch更新：谁说windows不能有同样丝滑体验](https://mp.weixin.qq.com/s/6PipJIV7aw95cUOtyg5Vmw)

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restore
- **[awerouter](https://github.com/wehuman01/awerouter)** — smart LLM router: splits requests between Flash (cheap) and Pro (capable) providers based on structural signals
- **[awescholar](https://github.com/wehuman01/awescholar)** — automated scientific literature discovery
