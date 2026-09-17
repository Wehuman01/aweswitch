# aweswitch: I Asked My Agent to Read a README

![aweswitch](../../../logo/hero.png)

I told my coding agent one sentence: *"Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it."* Then I went to get a coffee.

When I came back, aweswitch was installed, the skill was registered, the config was initialized, and three profiles were ready: `cc-glm`, `cc-xiaomi`, and `cx-openai`. It had also noticed my `~/.zshrc` was missing `OPENAI_API_KEY`, asked me to paste the token, and added the export line in the right place.

That is the new shape of installing an agent tool. The install is a task. The agent does tasks. So I gave the task to the agent.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## The Install: A README the Agent Reads

Most agent tools ship a `README.md` for humans and a separate `README.ai.md` for agents. The split is honest: humans want a marketing story, agents want a procedure. aweswitch leans into this.

The `README.ai.md` is a six-step install contract written for the agent, not the user:

1. `pip3 install aweswitch` and verify with `aweswitch -v`
2. Install the `aweswitch` skill via [aweskill](https://aweskill.webioinfo.top/) (Option A) or direct copy of `SKILL.md` (Option B)
3. `aweswitch config init` to create `~/.config/aweswitch/config.json`
4. Read the existing config, add profiles under `profiles.claude` or `profiles.codex`
5. Append the matching `export` lines to `~/.zshrc` (or `~/.bashrc`)
6. Tell the user to type `/` and look for `aweswitch` in the skill list

### The 30-Second Version

In Claude Code, Codex, Cursor, or any of the 47+ agents supported by aweskill, the prompt is the same:

> "Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch."

The agent does the rest. It runs `pip3 install`, sets up the skill, initializes the config, edits `~/.zshrc`, and reports back. If something fails — Node.js missing, Python too old, an existing config with profiles you care about — it stops and asks, instead of silently breaking things.

### What the Agent Will Not Do

This is the part most people miss. aweswitch has two modes: **launch** (`aweswitch <profile>`) and **apply** (`aweswitch apply <profile>`).

The agent will never run launch mode. Launch mode uses `os.execvpe` to replace the current shell with a fresh Claude Code session, which would nest an agent inside the agent. The `README.ai.md` says so explicitly, and the agent respects it.

Apply mode is different. It writes the profile's env into `~/.claude/settings.json` and exits. No interactive sub-process. The agent can run this safely. So the day-to-day profile management — list, show, add, edit, apply, restore — is all agent-runnable. Only the actual launch is yours to do in your own terminal.

## A Day in Practice

It is Tuesday. You are on a deadline.

**7:42 AM.** You open Claude Code. The default profile is whatever was last applied. You want GLM for the morning batch of small refactors:

```
/aweswitch apply cc-glm
```

`/aweswitch` is the skill the agent installed yesterday. The slash menu shows it because the SKILL.md landed in `~/.claude/skills/aweswitch/`. The skill parses the intent ("switch to cc-glm"), confirms the profile exists, runs `aweswitch apply cc-glm`, and reports the change. The current session does not restart, but `/model` now lists GLM-5.2 at the top.

**9:15 AM.** You hit a tricky concurrency bug. GLM is fine for refactors but you want a second opinion from a stronger model. You open a second terminal:

```bash
aweswitch cc-xiaomi
```

Launch mode. New Claude Code session. Mimo is now the model, the token is sourced from `XIAOMI_ANTHROPIC_AUTH_TOKEN`, the base URL is the Xiaomi proxy. The first session is still on GLM. Two profiles, two terminals, no interference.

**11:30 AM.** You need a codex profile for AiHubMix. You tell the agent:

> "Add a codex profile for AiHubMix. I have `AIHUBMIX_OPENAI_KEY` in my zshrc."

The agent reads the current config, computes the diff, adds the profile under `profiles.codex.cx-aihubmix`, and reports the new block:

```json
"cx-aihubmix": {
  "env": {
    "OPENAI_BASE_URL": "https://aihubmix.com/v1",
    "OPENAI_API_KEY": "${AIHUBMIX_OPENAI_KEY}"
  }
}
```

No copy-paste. No "let me find the docs." The agent did the part you do not enjoy.

**1:00 PM.** You test the new profile. A third terminal:

```bash
aweswitch cx-aihubmix --model gpt-5.6-sol
```

Codex launches against AiHubMix with `gpt-5.6-sol` as the model. The `-c` and `-t` flags bookmark the session under `infra` with the title "Test AiHubMix gpt-5.6-sol" via aweshelf. If you lose the terminal, you can find it later with `aweshelf search "AiHubMix"`.

**3:00 PM.** You want to compare GLM and Mimo on a code review. Two parallel sessions:

```bash
aweswitch cc-glm -c review -t "PR #247 review"    # terminal 1
aweswitch cc-xiaomi -c review -t "PR #247 review" # terminal 2
```

Both bookmarked under `review`. Both running side by side. You flip between them with `aweshelf browse` to compare outputs.

**6:00 PM.** You are done. Three profiles, two parallel sessions, one new profile added during the day, four bookmarks. Tomorrow you can resume any of them with `aweshelf resume`. None of this required editing `~/.claude/settings.json` by hand.

## Companion Tool: aweshelf

The [aweshelf](https://github.com/wehuman01/aweshelf) name that keeps showing up across the day above is aweswitch's companion: a session bookmark manager for Claude Code and Codex. The split of labor is simple — aweswitch handles the **launch** (getting the provider, key, and model in place), aweshelf handles the **memory** (bookmarking, categorizing, searching, and resuming sessions, with the original profile restored when you resume). The two work standalone but are best together.

Installing it is the same one line:

```bash
pip3 install aweshelf
```

How it composes with the launch flags (`-c` / `-t`) is covered later in "The Other Half: Session Memory."

## The Stack: What the Skill Can Reach

The `aweswitch` skill is intentionally small. It does not try to be a general agent framework. It is a thin procedural layer over the `aweswitch` CLI, with an intent router that maps natural language to commands.

| You say | The skill runs |
|---|---|
| "List my aweswitch profiles." | `aweswitch list` |
| "Show me cc-glm." | `aweswitch show cc-glm` |
| "Add a codex profile for AiHubMix." | edits `~/.config/aweswitch/config.json` |
| "Change cc-glm to glm-5.2." | edits the profile, verifies with `aweswitch show` |
| "Write cc-glm to settings so I can switch with /model." | `aweswitch apply cc-glm` |
| "Restore my original settings." | `aweswitch restore` |
| "Set up `OPENAI_API_KEY` in my zshrc." | appends `export` line, asks you to paste the token |

The last row is the one that gets the most surprise. Most users have at least one token sitting in their head — not in any file — because they set it up once, on a different machine, and never quite got around to persisting it. The agent will read `~/.zshrc`, identify what's missing, and walk you through adding it. Token stays in the env var. Never in the config file.

## OpenCode, Codex, and the Long Tail

The same pattern works across providers.

**OpenCode** profiles use the same `aweswitch add` flow, with `opencode` as the provider. aweswitch writes the provider entry to `~/.config/opencode/opencode.json` on first launch, using `{env:VAR}` syntax so the key never lands on disk. OpenCode's `@`-agent calling then lets you route sub-tasks to different models in the same conversation:

```
@glm   Write the validation middleware
@step  Review it for edge cases
@mimo  Write the API docs in Chinese
```

aweswitch does not manage the agent files. That is OpenCode's job. aweswitch manages the *connections* — base URL, key, models. The split is intentional: changing a key in aweswitch flows through to every `@`-agent on that provider. Adding a new agent file picks up whatever aweswitch has already configured.

**Codex** profiles use `OPENAI_BASE_URL` and `OPENAI_API_KEY`. aweswitch injects them via the `-c` flag and environment, never writes to `~/.codex/`. Launch mode works the same as for Claude Code: `aweswitch cx-aihubmix --model gpt-5.6-sol`.

**Claude Code** is the only provider that supports apply mode. OpenCode and Codex do not have a writable global config that an in-place switch would make sense for — they are launched fresh each time anyway, so launch mode is the natural fit.

## The Other Half: Session Memory

Profiles are half the problem. The other half is remembering which session was on which profile.

[aweshelf](https://github.com/wehuman01/aweshelf) is the session-bookmark companion. The `-c` and `-t` flags at launch time hand the bookmark off to aweshelf automatically:

```bash
aweswitch cc-glm -c backend -t "Fix auth bug"
aweswitch cx-aihubmix -c research -t "Compare gpt-5.6-sol vs o4-mini"
aweswitch oc-glm glm-5.2 -c docs -t "Translate README to Chinese"
```

When the day is done, `aweshelf browse` opens an interactive TUI. Pick a bookmark, resume the session, and it comes back with the original profile intact. The two tools are designed to compose: aweswitch handles the *launch*, aweshelf handles the *memory*. Together they answer the question "what was I doing last Thursday on the Mimo proxy?" in one keystroke.

## Why It Matters

The first wave of agent tools assumed a human operator. Install meant `pip install`, `npm install -g`, or "clone this repo and run the script." Configure meant editing JSON. Most users tolerated it because they only had one tool to install.

The second wave assumes an agent operator. Install is a task. Configure is a task. Both can be delegated. The artifact that gets delegated is not the binary — it is a *readable spec the agent can execute*.

`README.ai.md` is that spec. It is written for the agent to read and follow, with explicit "do not run this command" boundaries, fallback paths for missing dependencies, and verification steps at every stage. The user does not need to understand it. The agent does.

This is the test I now apply to every agent tool I evaluate:

1. **Can another agent install it from a single prompt?**
2. **Can another agent use it from natural language after install?**
3. **Does the install require changes to my shell or global config that I have to maintain by hand?**

aweswitch passes all three. The first prompt is the README. The second is the skill. The third is non-existent: `aweswitch add` writes to its own config file at `~/.config/aweswitch/config.json`, and `${VAR_NAME}` references keep secrets out of the file. The agent can move it, back it up, or read it back. None of it touches `~/.claude/settings.json` unless you explicitly run `aweswitch apply`.

The future of agent tooling is not "tools that work well with agents." It is "tools that the agent itself can install, configure, and operate on your behalf." aweswitch is one of the first to ship with that as the primary install path, not a workaround.

## Try It

Tell your agent:

> "Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it."

Then check that `/aweswitch` appears in the skill list. If it does, you are thirty seconds away from a new profile. If it does not, restart the agent.

From there, the questions become ordinary:

- "Add a codex profile for AiHubMix."
- "Show me which profile is active."
- "Switch to cc-xiaomi so I can use /model."

The agent already knows the answers. You just had not given it the README yet.

## More from Webioinfo

aweswitch is part of the [Webioinfo](https://www.webioinfo.top/) ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first Skill package manager for 47+ AI coding agents
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awescholar](https://github.com/wehuman01/awescholar)** — Automated scientific literature discovery
