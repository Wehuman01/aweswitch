# aweswitch：我让 agent 替我读了一份 README

![aweswitch](../../../logo/hero.png)

我对我的编码 agent 说了一句话："读一下 https://github.com/wehuman01/aweswitch/blob/main/README.ai.md，按里面的步骤来。"然后我去泡了杯咖啡。

等我回来，aweswitch 已经装好了，技能也注册上了，配置初始化完成，三条 profile 已经就位：`cc-glm`、`cc-xiaomi`、`cx-openai`。它还发现我的 `~/.zshrc` 里没有 `OPENAI_API_KEY`，问我要了令牌，并把它写到了正确的位置。

这就是安装一个 agent 工具的新形态。安装本身是一项任务。agent 干任务。所以我把任务派给了 agent。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 安装：一份给 agent 读的 README

大多数 agent 工具同时发一份 `README.md`（写给人看）和一份 `README.ai.md`（写给 agent 看）。这种拆分很诚实：人想要的是一个有故事性的介绍，agent 想要的是一份可执行的操作清单。aweswitch 选择了把这一点做实。

`README.ai.md` 是一份六步的安装契约，写给 agent 而不是写给用户：

1. `pip3 install aweswitch`，然后用 `aweswitch -v` 验证
2. 通过 [aweskill](https://aweskill.webioinfo.top/) 安装 `aweswitch` 技能（方式 A），或者直接复制 `SKILL.md`（方式 B）
3. 运行 `aweswitch config init` 创建 `~/.config/aweswitch/config.json`
4. 读取已有配置，在 `profiles.claude` 或 `profiles.codex` 下添加 profile
5. 把对应的 `export` 行追加到 `~/.zshrc`（或 `~/.bashrc`）
6. 提示用户在 Claude Code 中输入 `/` 并在技能列表里找到 `aweswitch`

### 三十秒版本

在 Claude Code、Codex、Cursor 或 aweskill 支持的 47+ agent 中，提示语都是同一句：

> "读一下 https://github.com/wehuman01/aweswitch/blob/main/README.ai.md，按里面的步骤安装并配置 aweswitch。"

agent 会做剩下的事。它会跑 `pip3 install`、装好技能、初始化配置、改 `~/.zshrc`，然后汇报结果。如果中间出问题——Node.js 没装、Python 版本太老、已有配置里有你不想覆盖的 profile——它会停下来问你，而不是悄悄搞坏什么。

### agent 不会做的事

这一点是大部分人会忽略的。aweswitch 有两种模式：**启动模式**（`aweswitch <profile>`）和**应用模式**（`aweswitch apply <profile>`）。

agent 永远不会跑启动模式。启动模式会通过 `os.execvpe` 把当前 shell 替换成一个全新的 Claude Code 会话——那等于在 agent 里再嵌一个 agent。`README.ai.md` 把这一点写得很清楚，agent 会照做。

应用模式不一样。它会把 profile 的环境变量写入 `~/.claude/settings.json` 然后退出。不会启动交互式子进程。agent 可以安全地跑这条命令。所以日常的配置管理——list、show、add、edit、apply、restore——全都可以让 agent 代劳。只有真正"启动"这件事，得你自己在终端里做。

## 一天的实际用法

周二的早上。你在赶一个 deadline。

**7:42 AM。** 你打开 Claude Code。默认 profile 是上次最后 apply 的那个。上午有一批小重构，你想用 GLM：

```
/aweswitch apply cc-glm
```

`/aweswitch` 就是昨天 agent 帮你装好的那个技能。斜杠菜单里能看到它，是因为 `SKILL.md` 已经落在了 `~/.claude/skills/aweswitch/`。技能解析意图（"切到 cc-glm"），确认 profile 存在，跑 `aweswitch apply cc-glm`，然后报告变更。当前会话不会重启，但 `/model` 列表里 GLM-5.1 已经排在最前面。

**9:15 AM。** 你撞上了一个棘手的并发 bug。GLM 做重构够用，但你想要一个更强的模型给点第二意见。你开了第二个终端：

```bash
aweswitch cc-xiaomi
```

启动模式。一个新的 Claude Code 会话启动。Mimo 成了当前模型，令牌从 `XIAOMI_ANTHROPIC_AUTH_TOKEN` 取，base URL 是 Xiaomi 的代理。第一个会话还跑在 GLM 上。两个 profile、两个终端，互不打架。

**11:30 AM。** 你需要给 AiHubMix 加一条 codex profile。你对 agent 说：

> "加一条 AiHubMix 的 codex profile。我的 zshrc 里有 `AIHUBMIX_OPENAI_KEY`。"

agent 读当前的配置，算出 diff，在 `profiles.codex.cx-aihubmix` 下加了 profile，并报回来这块新内容：

```json
"cx-aihubmix": {
  "env": {
    "OPENAI_BASE_URL": "https://aihubmix.com/v1",
    "OPENAI_API_KEY": "${AIHUBMIX_OPENAI_KEY}"
  }
}
```

没有复制粘贴，没有"让我翻一下文档"。agent 替你做了你最不想做的那部分。

**1:00 PM。** 你测试新加的 profile。开第三个终端：

```bash
aweswitch cx-aihubmix --model o3
```

Codex 在 AiHubMix 后端启动，模型是 `o3`。`-c` 和 `-t` 标志会通过 aweshelf 给这条会话打上 `infra` 分类的"测试 AiHubMix o3"书签。如果之后终端丢了，你随时可以用 `aweshelf search "AiHubMix"` 找回来。

**3:00 PM。** 你想对比 GLM 和 Mimo 跑同一个代码评审。两个会话并行：

```bash
aweswitch cc-glm -c review -t "PR #247 评审"      # 终端 1
aweswitch cc-xiaomi -c review -t "PR #247 评审"   # 终端 2
```

都打上 `review` 分类。两个会话同时跑。你用 `aweshelf browse` 在它们之间切换，对比输出。

**6:00 PM。** 收工。一天下来：三个 profile、两个并行会话、新加了一条 profile、四条书签。明天任意一条都可以用 `aweshelf resume` 续上。整个过程没碰过一次 `~/.claude/settings.json`。

## 技能栈：它能触达什么

`aweswitch` 技能刻意做得很小。它不打算变成一个通用的 agent 框架。它只是 `aweswitch` CLI 之上一层薄薄的过程化封装，配一个把自然语言路由到命令的意图识别器。

| 你说什么 | 技能跑什么 |
|---|---|
| "列出我的 aweswitch profile。" | `aweswitch list` |
| "给我看看 cc-glm。" | `aweswitch show cc-glm` |
| "加一条 AiHubMix 的 codex profile。" | 编辑 `~/.config/aweswitch/config.json` |
| "把 cc-glm 的模型改成 glm-5.2。" | 编辑 profile，用 `aweswitch show` 验证 |
| "把 cc-glm 写到 settings 里，我用 /model 切。" | `aweswitch apply cc-glm` |
| "恢复我原来的 settings。" | `aweswitch restore` |
| "把 `OPENAI_API_KEY` 加到我的 zshrc 里。" | 追加 `export` 行，请你贴令牌 |

最后一行最让人意外。多数用户脑子里都至少存着一个令牌——不在任何文件里——因为当初是在另一台机器上设的，后来一直没真正"持久化"过。agent 会读 `~/.zshrc`，找出缺什么，然后引导你把它加上。令牌留在环境变量里，永远不进配置文件。

## OpenCode、Codex，以及长尾

同一个套路在所有 provider 上都成立。

**OpenCode** profile 用的是同一种 `aweswitch add` 流程，provider 选 `opencode` 即可。aweswitch 在首次启动时把 provider 条目写到 `~/.config/opencode/opencode.json`，用的是 `{env:VAR}` 语法，所以密钥永远不会落盘。OpenCode 自带的 `@`-agent 调用让同一个会话里可以路由子任务到不同模型：

```
@glm   写一下校验中间件
@step  帮我审一下边界情况
@mimo  把这份接口文档翻成中文
```

aweswitch 不管 agent 文件本身——那是 OpenCode 的事。aweswitch 管的是**连接**——base URL、密钥、模型列表。这种拆分是刻意的：在 aweswitch 里改一个密钥，所有用这个 provider 的 `@`-agent 都跟着生效。新加一个 agent 文件，会自动用上 aweswitch 已经配好的 provider。

**Codex** profile 用 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。aweswitch 通过 `-c` 标志和环境变量注入，从不写 `~/.codex/`。启动模式跟 Claude Code 完全一样：`aweswitch cx-aihubmix --model o3`。

**Claude Code** 是唯一支持应用模式的 provider。OpenCode 和 Codex 没有"原地切换"这种语义——它们反正都是每次重新启动，所以启动模式就是最自然的方式。

## 另一半：会话记忆

profile 只是问题的一半。另一半是记住"哪条会话当时跑在哪个 profile 上"。

[aweshelf](https://github.com/wehuman01/aweshelf) 是会话书签的配套工具。启动时的 `-c` 和 `-t` 标志会自动把书签交给 aweshelf：

```bash
aweswitch cc-glm -c backend -t "修复 auth bug"
aweswitch cx-aihubmix -c research -t "对比 o3 和 o4-mini"
aweswitch oc-glm glm-5.1 -c docs -t "把 README 翻成中文"
```

一天结束的时候，`aweshelf browse` 打开一个交互式 TUI。选一条书签，续上会话，原来的 profile 还在。两个工具是配套设计的：aweswitch 管**启动**，aweshelf 管**记忆**。合起来回答的就是"上周四我在 Mimo 代理上到底在干嘛"这种问题，一个键就能答上来。

## 为什么这很重要

第一波 agent 工具假设操作者是人。安装意味着 `pip install`、`npm install -g`、或者"克隆这个 repo 然后跑脚本"。配置意味着改 JSON。多数用户忍着这些，因为只装一两个工具。

第二波假设操作者是 agent。安装是一项任务。配置是一项任务。两者都可以被委托。被委托出去的那个东西不是二进制包——它是一份**agent 能读、能执行的说明文档**。

`README.ai.md` 就是那份说明文档。它写给 agent 读、写给 agent 跟，每一步都标了"不要跑这条命令"的边界、依赖缺失时的备选路径、以及每一步的验证。用户不需要懂它。agent 需要。

这是我评估每一个 agent 工具时会用的一套标准：

1. **另一个 agent 能用一句话把它装好吗？**
2. **装完之后，另一个 agent 能用自然语言使用它吗？**
3. **安装是否需要改我的 shell 或全局配置，让我不得不手动维护？**

aweswitch 三条都过。第一条是 README.ai.md，第二条是技能，第三条不存在：`aweswitch add` 写到的是它自己的配置文件 `~/.config/aweswitch/config.json`，`${VAR_NAME}` 引用让密钥不进文件。agent 可以搬它、备份它、回读它。除非你显式跑 `aweswitch apply`，否则它完全不会碰 `~/.claude/settings.json`。

agent 工具的未来不是"对 agent 友好的工具"。是"agent 自己能装、能配、能替你用的工具"。aweswitch 是第一批把这件事当作主安装路径（而不是变通方案）来发布的工具之一。

## 试试看

对你的 agent 说：

> "读一下 https://github.com/wehuman01/aweswitch/blob/main/README.ai.md，按里面的步骤来。"

然后在技能列表里看看 `/aweswitch` 有没有出现。如果出现了，离加一条新 profile 就剩三十秒。如果没有，重启 agent。

接下来你要问的就都是些普通的问题了：

- "加一条 AiHubMix 的 codex profile。"
- "看看我现在跑的是哪个 profile。"
- "切到 cc-xiaomi，我用 /model。"

agent 已经知道答案。你只是还没把那份 README 递给它。

## Webioinfo 出品

aweswitch 是 [Webioinfo](https://www.webioinfo.top/) 生态的一部分：

- **[aweskill](https://aweskill.webioinfo.top/)** — 面向 47+ AI 编码 agent 的 CLI 优先技能管理器
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — 带 profile 感知恢复的 AI 编码会话管理器
- **[awescholar](https://github.com/wehuman01/awescholar)** — 自动化科学文献发现
