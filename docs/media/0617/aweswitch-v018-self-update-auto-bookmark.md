# aweswitch: Launch It, Bookmarked. Update It, Automatic.

![aweswitch](../../../logo/hero.png)

Last time we covered [how aweswitch lets you run multiple agent endpoints without breaking open sessions](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA). Named profiles, runtime injection, no global config mutation — that solves the switching problem.

But switching is only part of the workflow.

You close a terminal. The next day you need that GLM debugging session again. You scroll through shell history. You check `aweshelf list` and see a wall of entries like "help me fix the bug" and "refactor the auth module." Which one was the GLM session? No idea. Meanwhile, a new version of aweswitch has been sitting on PyPI for weeks. You only find out when a colleague mentions a feature you never knew existed.

These are small frictions. But they add up. Recent updates have been quietly eliminating them.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## Auto-Bookmarks

[aweshelf](https://github.com/wehuman01/aweshelf) is a session bookmark manager for Claude Code and Codex CLI — save, tag, search, and resume past coding sessions. (For a deeper look, see [aweshelf: 像整理抽屉一样轻松收纳agent会话](https://mp.weixin.qq.com/s/ifUFVG3UTOu4PU18wggAqA).)

With aweswitch, aweshelf integration is now seamless. Bookmarking a session used to be a manual step: find the session ID, run `aweshelf bookmark`. In practice, you always forgot.

Now, add `-c` when launching a profile and the bookmark happens automatically:

```bash
aweswitch cc-glm -c backend -t "Refactor auth middleware"
```

That is the entire command. The session starts, the bookmark completes in the background, and you move on.

Later, find it by category or keyword:

```bash
aweshelf list
```

```
REF          TITLE                      CATEGORY   PROFILE    DATE
─────────────────────────────────────────────────────────────────────
a3f2c1       Refactor auth middleware    backend    cc-glm     2026-06-17
b7d9e4       Compare Mimo vs GLM output testing     cc-xiaomi  2026-06-16
e1a5f8       Fix the login bug          backend    cc-glm     2026-06-15
```

```bash
aweshelf search "auth"
aweshelf resume a3f2c1
```

Every entry carries a category, a title, and the profile it ran under. Resume restores the session with the same endpoint, token, and model — your GLM debugging session will not accidentally restart against Gemini.

If aweshelf is not installed, `-c` and `-t` are silently ignored. Claude Code launches normally.

## Self-Update

Finding out about new aweswitch releases used to mean checking PyPI manually or hearing about it from someone else.

Now, aweswitch checks PyPI in the background once per day. If a newer version exists, a reminder prints after your command finishes:

```
⚠  Update available. Run `aweswitch self-update` to update.
```

The reminder appears after your output, not before. It does not interrupt anything. When you are ready:

```bash
aweswitch self-update
```

It detects whether you installed via pipx or pip and runs the right upgrade command. Want to check without installing?

```bash
aweswitch self-update --check
```

Do not want the background reminder at all?

```bash
export AWESWITCH_NO_UPDATE_CHECK=1
```

## A Day in Practice

Morning. You start a debugging session:

```bash
aweswitch cc-glm -c backend -t "Debug payment webhook"
```

GLM endpoint launches, bookmark completes in the background. You work for two hours, find the bug, close the terminal.

Afternoon. You want to compare how GLM and Mimo handle a code review:

```bash
aweswitch cc-glm -c review -t "Code review: PR #247"
aweswitch cc-xiaomi -c review -t "Code review: PR #247"
```

Two sessions, two endpoints, two bookmarks. You compare the outputs, close both terminals.

Next day. You need the payment webhook session back:

```bash
aweshelf search "payment"
```

```
REF          TITLE                  CATEGORY   PROFILE    DATE
─────────────────────────────────────────────────────────────────
a3f2c1       Debug payment webhook  backend    cc-glm     2026-06-17
```

```bash
aweshelf resume a3f2c1
```

Same GLM endpoint, same token, same model. Everything where you left it.

A week later. You run `aweswitch list` and see a new line at the bottom:

```
cc-glm      claude   glm-5.1
cc-xiaomi   claude   mimo-v2.5-pro

⚠  Update available. Run `aweswitch self-update` to update.
```

```bash
aweswitch self-update
```

Done. No manual PyPI checking. No guessing the package name. No stale installations.

## Why It Matters

The core of aweswitch has not changed: named profiles, runtime injection, no global config mutation.

But a switcher is only one part of the workflow. You also need to find your sessions later. You need to know when the tool itself has been updated. Auto-bookmarks turn "launch" and "remember" into a single action. Self-update lets the tool tell you when it needs attention.

These are not flashy features. They do not change how aweswitch switches profiles. They change how aweswitch fits into your daily work — from a command you run to a tool that runs with you.

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
