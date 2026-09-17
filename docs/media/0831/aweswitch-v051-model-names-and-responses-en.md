# aweswitch v0.5.1: Stop Memorizing Model Names — OpenCode Speaks Responses Now

![aweswitch](../../../logo/hero.png)

My model list is full of names like `peng1/step-router-v1`, `gpt-5.2-codex`, `Doubao-Seed-Evolving`. Every launch meant reciting one verbatim — one wrong character, one missing prefix, one capital letter off, and it just errors out.

The other annoyance is sneakier: some backends' models only speak OpenAI's Responses protocol, and the providers aweswitch writes into `opencode.json` have always been chat completions. Want to use them? Hand-edit the file and pray the next sync doesn't overwrite it back.

Before closing my laptop, I left my agent one sentence:

> "At launch I just want to type roughly — `GPT` should find `gpt-5.2-codex`. And that backend that only speaks Responses? I'm done hand-editing opencode.json."

I went downstairs for a coffee. Back at my desk I typed `aweswitch cx-aihubmix GPT`, hit enter — and it landed on `gpt-5.2-codex`.

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## Type Roughly, Land Exactly: Model Matching in Three Steps

This experience came together in three releases:

- **v0.4.2 Short names**: when models are configured as a mapping (`"peng1/step-router-v1": "step-router-v1"`), launch args can use the display value directly
- **v0.4.7 Case-insensitive**: `GLM-5.1`, `Glm-5.1`, `glm-5.1` — any casing works
- **v0.4.8 Substring matching**: a fragment of the ID or display name is enough to hit

The matching order matters: exact ID → exact display name → case-insensitive full match → case-insensitive substring. Narrowest first, widening as it goes; a unique match wins on the spot.

```bash
aweswitch cx-aihubmix GPT        # -> gpt-5.2-codex
aweswitch cc-glm glm-5.2         # exact when exact is what you mean
```

Ambiguity is never guessed. If your list has both `glm-5.1` and `glm-5.2` and you type `glm`, aweswitch refuses to launch and lists the candidates so you can pick. Two extra keystrokes beat silently starting the wrong model.

## v0.5.1: OpenCode Can Speak Responses Now

One sentence of background: within the OpenAI ecosystem there are two "dialects" — the mainstream Chat Completions (`/chat/completions`) and the newer Responses (`/responses`). OpenCode picks its dialect by npm package: `@ai-sdk/openai-compatible` is chat, `@ai-sdk/openai` is Responses.

aweswitch always hardcoded the former. As of v0.5.1, one env var switches it:

```json
"oc-glm": {
  "env": {
    "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
    "OPENCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
    "OPENCODE_RESPONSES": "true",
    "OPENCODE_MODEL": {
      "glm-5.1": "GLM-5.1",
      "glm-5.2": "GLM-5.2"
    }
  }
}
```

Set it to `true` and the provider's npm becomes `@ai-sdk/openai` — the whole profile goes Responses. Like every aweswitch-owned field, launch and `aweswitch apply` both sync it: delete the line someday and the next sync reverts the provider to the chat package, no leftovers.

Hand-written parts stay untouched as always: if you manually swapped in another SDK (say `@ai-sdk/anthropic`), aweswitch only rewrites between the two openai packages — yours is never modified.

## One Provider, Two Protocols

The more common case is mixed: most of a backend's models speak chat, a few only speak Responses. You shouldn't have to split that into two profiles.

`OPENCODE_RESPONSES_MODEL` exists for exactly this:

```json
"OPENCODE_RESPONSES_MODEL": "glm-5.2"
```

The listed models get a per-model override, which lands in `opencode.json` like this:

```json
"models": {
  "glm-5.1": { "name": "GLM-5.1" },
  "glm-5.2": { "name": "GLM-5.2", "provider": { "npm": "@ai-sdk/openai" } }
}
```

The provider overall stays on the chat package while `glm-5.2` goes Responses on its own. Clear the list someday and the next sync sweeps the stale overrides away. Every ID in the list must actually exist in `OPENCODE_MODEL` — a typo errors out, no guessing.

| You say | skill runs |
|---|---|
| "Launch that model by its short name." | `aweswitch cx-aihubmix step-router-v1` |
| "The GPT one — I forgot the full name." | `aweswitch cx-aihubmix GPT` |
| "Switch oc-glm entirely to Responses." | add `"OPENCODE_RESPONSES": "true"` to env, then `aweswitch apply oc-glm` |
| "Only glm-5.2 goes Responses, rest unchanged." | add `"OPENCODE_RESPONSES_MODEL": "glm-5.2"` to env |
| "Back to chat." | delete those two lines, `aweswitch apply oc-glm` again |

One-line summary: type model names loosely, dial the protocol per need, and hand-written config is still nobody's to touch.

## While We're Here

- **v0.4.6** A bare `aweswitch apply` no longer silently writes every OpenCode profile — bulk is explicit via `--opencode` (covered in the previous post)
- **v0.5.0** codex 0.150 compatibility fix: an upstream provider `name` validation broke every launch; the launch path now injects it too

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

# Type a rough model name — it still launches
aweswitch cx-aihubmix GPT

# Switch OpenCode to Responses: add one line to the profile env
#   "OPENCODE_RESPONSES": "true"
# then sync
aweswitch apply oc-glm
```

No more memorizing model names, no more hand-editing config files to switch protocols.



## More from the aweswitch Series

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)
- [aweswitch更新：谁说windows不能有同样丝滑体验](https://mp.weixin.qq.com/s/6PipJIV7aw95cUOtyg5Vmw)
- [aweswitch更新：官方账号也能多开了，不同账号直接切](https://mp.weixin.qq.com/s/HwBu2gjGNj8sc6lvAMnl8w)
<!-- TODO: after publishing, add the previous post (apply everywhere) link here, and add this post's link to the next one -->



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
