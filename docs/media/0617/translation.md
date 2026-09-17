# Aweswitch更新：启动即记录，升级不操心

![aweswitch](../../../logo/hero.png)

上一次我们介绍了 [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)。Named profiles、runtime injection、不修改全局配置——这套机制解决了"切换"的问题。

但切换只是工作流的一部分。

你关掉一个终端，第二天想找回那个 GLM 的调试 session，翻遍 shell history 也想不起来是哪个。你打开 `aweshelf list`，看到一整屏的 "help me fix the bug"、"refactor the auth module"——哪条是 GLM 的？完全分不清。与此同时，aweswitch 的新版本已经在 PyPI 上静静地躺了好几周，你浑然不知，直到同事提起一个你从未听说过的功能。

这些都是小摩擦，但日积月累。最近的几次更新，正在悄悄抹平它们。

GitHub: [github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 自动书签

[aweshelf](https://github.com/wehuman01/aweshelf) 是 Claude Code 和 Codex CLI 的 session 书签管理器——保存、标记、搜索、恢复，管理你的编程 session 历史。（更详细的介绍见 [aweshelf: 像整理抽屉一样轻松收纳agent会话](https://mp.weixin.qq.com/s/ifUFVG3UTOu4PU18wggAqA)。）

现在 aweswitch 与 aweshelf 的集成做到了无缝衔接。以前给 session 加书签是手动操作：找到 session ID，跑一条 `aweshelf bookmark` 命令。实际上，你总是忘。

现在，启动 profile 时加一个 `-c` 参数，书签就自动完成了：

```bash
aweswitch cc-glm -c backend -t "Refactor auth middleware"
```

就这一条。Session 启动，书签在后台搞定，你什么都不用管。

之后想找回来？按类别或关键词搜索：

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

每条记录都带着类别、标题和当时的 profile。Resume 之后，session 以原来的端点、token、模型恢复——你的 GLM 调试不会意外跑到 Gemini 上去。

如果没装 aweshelf，`-c` 和 `-t` 会被安静地忽略，Claude Code 正常启动。

## 自更新

以前想知道 aweswitch 有没有新版本，只能手动去 PyPI 查，或者等别人告诉你。

现在，aweswitch 每天在后台自动检查一次 PyPI。如果有新版本，你的命令结束后会多出一行提醒：

```
⚠  Update available. Run `aweswitch self-update` to update.
```

提醒出现在输出之后，不会打断你的工作流。准备好了，一条命令搞定：

```bash
aweswitch self-update
```

它会自动检测你是用 pipx 还是 pip 安装的，用对应的命令升级。想先看看有没有新版本，但不急着装？

```bash
aweswitch self-update --check
```

根本不想收到后台提醒？

```bash
export AWESWITCH_NO_UPDATE_CHECK=1
```

## 一天的实战

早上，你开始一个调试 session：

```bash
aweswitch cc-glm -c backend -t "Debug payment webhook"
```

GLM 端点启动，书签在后台自动完成。工作两小时，找到 bug，关掉终端。

下午，你想对比 GLM 和 Mimo 做 code review 的效果：

```bash
aweswitch cc-glm -c review -t "Code review: PR #247"
aweswitch cc-xiaomi -c review -t "Code review: PR #247"
```

两个 session，两个端点，两条书签。对比完，关掉终端。

第二天，你想找回昨天的支付 webhook session：

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

同一个 GLM 端点，同一个 token，同一个模型。一切如故。

一周后，你跑 `aweswitch list`，底部多了一行：

```
cc-glm      claude   glm-5.1
cc-xiaomi   claude   mimo-v2.5-pro

⚠  Update available. Run `aweswitch self-update` to update.
```

```bash
aweswitch self-update
```

搞定。不用手动查 PyPI，不用猜包名，不用担心装错环境。

## 为什么这些功能重要

aweswitch 的核心没有变：named profiles、runtime injection、不碰全局配置。

但一个切换器只是工作流的一环。你还需要找回你的 session，需要知道工具本身有没有更新。自动书签把"启动"和"记住"合成了一个动作。自更新让工具自己告诉你什么时候该升级了。

这些功能不炫目。它们不改变 aweswitch 怎么切换 profile，而是改变 aweswitch 怎么融入你的日常工作——从你需要主动去跑的命令，变成陪你一起跑的工具。

## 更多来自 Webioinfo

aweswitch 是 [Webioinfo](https://www.webioinfo.top/) 生态的一部分：

- **[aweskill](https://aweskill.webioinfo.top/)** — 面向 47+ AI 编程 Agent 的 Skill 包管理器
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI 编程 session 管理器，支持 profile 感知的 session 恢复
- **[awescholar](https://github.com/wehuman01/awescholar)** — 自动化科学文献发现
