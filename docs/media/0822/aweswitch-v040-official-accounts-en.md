# aweswitch v0.4.0: Official Logins, Side by Side

![aweswitch](../../../logo/hero.png)

I have two Claude Code accounts: one from work, one my own. Running both at once used to be impossible — there is only one `~/.claude`, so switching meant logging out, running `/login` again, waiting through the browser redirect, and praying I ended up on the right account this time. Codex was no different.

And "two terminals, two accounts, running in parallel"? That used to be fantasy.

Before closing my laptop, I left my agent one sentence:

> "Put all of my official accounts into aweswitch. I want to launch any of them with one command, and run them at the same time."

Then I went downstairs to pick up a package, taking out the trash on the way. By the time I climbed back up with the box under my arm, `aweswitch list` already showed a few new rows with `account` in the kind column. Work account and personal account, both in there, neither stepping on the other's login state.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## v0.4.0: Official Accounts Are First-Class Citizens

aweswitch has solved one problem since day one: switching between multiple API sources without breaking sessions. But officially logged-in OAuth accounts were always no-man's-land — cc-switch doesn't touch them, env-var schemes can't reach them, and your only option was manually logging in and out.

v0.4.0 brings official accounts in as peers of API profiles. The config now has two kinds under `profiles`: `api` (env-based profiles) and `account` (official OAuth logins), managed under one namespace, with a kind column making everything obvious in `aweswitch list`:

```text
NAME         PROVIDER   KIND      DETAIL
cco-work     claude     account   official login
cxo-team     codex      account   official login
cc-glm       claude     api       glm-5.1
cx-aihubmix  codex      api       gpt-5.2-codex, kimi-k2.7
```

## It Takes Two Commands

**Import an already-logged-in account** (the CLI must be currently logged in):

```bash
aweswitch account add codex cxo-work
```

**Or let aweswitch walk you through the login flow** — it runs the official `codex login` inside the account's own private directory (for claude, it starts a session where you run `/login`, then exit), and captures the credentials:

```bash
aweswitch account login claude cco-personal
```

macOS users, note: Claude Code stores credentials in the Keychain on macs, which `account add` cannot read — use `account login` for claude accounts.

**Then launch it like any profile**:

```bash
aweswitch cxo-work        # terminal 1: the work Codex account
aweswitch cco-personal    # terminal 2: the personal Claude account, running at the same time
```

Two terminals, two accounts, zero interference. Your global `~/.codex` and `~/.claude` are not touched by a single byte.

## How the Isolation Works

Every account gets its own private config directory. Codex accounts launch through `CODEX_HOME`; claude accounts through `CLAUDE_CONFIG_DIR` (plus an env var that disables Keychain access). When an OAuth token expires, the CLI refreshes it inside its own private directory — aweswitch never reads these credentials; it stores them as opaque blobs.

Security got real attention too:

- Credential blobs are fully masked — `aweswitch show` and `config show` only ever show `<redacted>`
- Adding the first account tightens the config file's permissions to `600`
- Tokens in the private dir are always the freshest; `aweswitch account sync` copies refreshed tokens back into the config, and a stale snapshot can never overwrite fresh credentials

Existing users don't need to migrate anything: old configs upgrade automatically on first load, with a `.json.bak` backup written beforehand.

| You say | skill runs |
|---|---|
| "Add my work account to aweswitch." | `aweswitch account add codex cxo-work` |
| "Also add my personal Claude account." | `aweswitch account login claude cco-personal` |
| "Start a session on the work account." | `aweswitch cxo-work` |
| "Run both accounts side by side." | `aweswitch cxo-work` and `aweswitch cco-personal` in two terminals |
| "The token probably needs a refresh?" | `aweswitch account sync codex cxo-work` |
| "I don't use that account anymore." | `aweswitch account remove codex cxo-work --purge` |

One-line summary: whatever you could do with API profiles, you can now do with official logins.

## Oh, and the Backlog

The updates from v0.3.7 through v0.3.9 ship with this release too — in one sentence: Codex profiles can now pick a third-party model at launch (`aweswitch cx-aihubmix kimi-k2.7`), changed OpenCode credentials sync automatically instead of erroring, plaintext API keys went from hard error to a warning tip, plus a round of hardening against corrupt configs and background-process edge cases.

Details live in the [CHANGELOG](https://github.com/wehuman01/aweswitch/blob/main/docs/CHANGELOG.md).

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

### Or do it yourself

```bash
pip install aweswitch

# Bring in the official accounts you already use
aweswitch account login codex cxo-work
aweswitch account login claude cco-personal

# Launch both
aweswitch cxo-work &
aweswitch cco-personal
```

No more logging out just to log back in. No more counting browser authorization redirects. Work account and personal account, one terminal each, everyone back in their own home.

## More from the aweswitch Series

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)



## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restore
- **[awerouter](https://github.com/wehuman01/awerouter)** — smart LLM router: splits requests between Flash (cheap) and Pro (capable) providers based on structural signals
- **[awescholar](https://github.com/wehuman01/awescholar)** — automated scientific literature discovery
