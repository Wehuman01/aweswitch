# aweswitch：环境不重启，平台全覆盖

![aweswitch](../../../logo/hero.png)

上一次我们介绍了 [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)，解决了 session 丢失和版本感知的问题。切换只是工作流的一部分——今天我们继续。

你正在用 Claude Code 调试一个棘手的并发 bug，上下文铺满了半个屏幕——三轮对话、五个文件、一个还没验证的假设。突然想试试 GLM 对这个问题的理解。按 aweswitch 的逻辑，你得退出当前会话，跑一条 `aweswitch cc-glm --resume session-id`。能恢复上下文，但你得先找到 session ID，退出当前会话，再拼一条长命令。你犹豫了三秒，算了，继续用当前的模型。

与此同时，你的同事在 Windows 上想试 aweswitch，装好一看：`os.fork()` 报错。他给你发了个截图，你只能说"暂时只支持 macOS 和 Linux"。

这些摩擦，aweswitch 的最新更新正在逐个消除。

aweswitch 已经从 Claude Code 配置切换工具，进化为跨平台的 AI 编码代理配置管理器。最新版本引入了一种无需启动新进程即可切换配置的方式，同时扩展了平台和提供商支持。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 应用模式

v0.3.0 引入了 `apply` 和 `restore` 命令。这是一种全新的 aweswitch 使用方式。

### 问题

启动模式（`aweswitch <profile>`）会在进程级别注入配置环境，启动一个新的 Claude Code 会话。这种方式适合并行终端和隔离会话。但它有一个限制：一旦启动，会话的环境就被冻结了。会话中无法用 `/model` 切换模型。

如果想在不关闭终端的情况下切换模型，需要退出、重新运行 aweswitch、启动新会话。会话上下文随之丢失。

### 解决方案

应用模式将配置的环境变量直接写入 `~/.claude/settings.json`：

```bash
aweswitch apply cc-glm
```

这会将配置的环境变量更新到 settings 文件中。下一个 Claude Code 会话——或者当前会话，如果你使用 `/model`——会读取新的值。无需启动新进程。

### 工作原理

运行 `aweswitch apply` 时：

1. 配置的环境变量被展开（包括用于 `/model` 选择器的 `_NAME` 变体）
2. 创建 `~/.claude/settings.json` 的备份（仅首次 apply 时）
3. 展开的环境变量合并到 settings 文件
4. 配置的变量成为所有 Claude Code 会话的默认值

后续 apply 操作会保留备份。使用 `--force` 覆盖：

```bash
aweswitch apply cc-glm --force
```

随时恢复原始设置：

```bash
aweswitch restore
```

### 何时使用哪种模式

**启动模式**用于隔离：

```bash
aweswitch cc-glm          # 启动 GLM 新会话
aweswitch cc-xiaomi       # 在另一个终端并行启动 Mimo
```

- 每个会话有独立的环境
- 多个配置可在不同终端同时运行
- 环境在启动时冻结
- 适合需要并行独立会话的场景

**应用模式**用于持久化：

```bash
aweswitch apply cc-glm    # 设置 GLM 为默认
claude                    # 启动会话（使用 GLM）
/model                    # 在会话中切换模型
```

- 环境写入 settings.json
- 所有新会话使用已应用的配置
- `/model` 在会话中可用
- 适合跨会话使用单一活跃配置

### 典型工作流

白天用 GLM 工作。晚上想切换到更便宜的模型处理简单任务：

```bash
aweswitch apply cc-haiku
```

打开 Claude Code。会话以 Haiku 启动。处理简单任务。

第二天早上，切回来：

```bash
aweswitch apply cc-glm
```

打开 Claude Code。GLM 又成为默认值。无需配置参数，无需启动标志。直接 `claude` 就行。

### 与 cc-switch 隔离

如果同时使用 [cc-switch](https://github.com/farion1231/cc-switch) 和 aweswitch，注意 `aweswitch apply` 会修改 `~/.claude/settings.json`。这可能干扰 cc-switch 的配置。

要隔离两个工具，创建一个专门的 cc-switch 配置来保存原始设置：

```bash
# 将当前设置保存为 cc-switch 配置
cc-switch save baseline

# 自由使用 aweswitch apply
aweswitch apply cc-glm
aweswitch apply cc-haiku

# 需要时恢复 cc-switch 基线
cc-switch restore baseline
```

这样，aweswitch apply 在自己的设置状态下运行，cc-switch 维护独立的基线。两个工具共存无冲突。

### Skill 集成

AI 助手的 aweswitch skill 默认使用应用模式。如果用 AI 代理管理配置，它会使用 `aweswitch apply`，除非明确指定启动模式。

这让与 AI 协作时的配置切换无缝衔接：代理可以更改你的活跃配置，无需启动新进程。

## 一天的实践

早上。启动一个 GLM 调试会话：

```bash
aweswitch cc-glm -c backend -t "Debug payment webhook"
```

启动模式，自动书签。工作两小时。

下午。想比较 GLM 和 Mimo 的代码审查效果。并行启动两个：

```bash
aweswitch cc-glm -c review -t "Code review: PR #247"
aweswitch cc-xiaomi -c review -t "Code review: PR #247"
```

两个会话，两个端点，两个书签。比较后关闭。

晚上。想用便宜模型做快速编辑。应用 Haiku 为默认：

```bash
aweswitch apply cc-haiku
claude
```

打开 Claude Code。Haiku 生效。用 `/model` 切换到 Sonnet 处理特定任务，再切回 Haiku。

第二天早上。恢复 GLM：

```bash
aweswitch apply cc-glm
```

直接`/model` 切换glm5.2 即可。

或者，如果不再需要应用模式，想恢复原始设置：

```bash
aweswitch restore
```

## 平台和提供商支持

v0.2.0 让 aweswitch 完全跨平台。四个 Unix 专用调用被替换为跨平台方案：

- `os.fork()` → `threading.Thread`（用于自动书签）
- `os.execvpe()` → `subprocess.run()`（Windows）
- `os.chmod()` 在 Windows 上跳过
- `shlex.split()` 使用 `posix=False` 处理路径

Windows 用户现在可以启动配置，不再遇到 Unix 专用系统调用。CI 覆盖 Linux、macOS 和 Windows 上的 Python 3.9 和 3.13。

v0.1.9 添加了 OpenAI Codex 作为支持的提供商。配置现在可以指向 Claude Code 或 Codex：

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

使用 `aweswitch add` 创建配置时，会提示选择提供商。Codex 配置会使用相应的 CLI 标志和环境注入启动。

## 为什么重要

aweswitch 最初是配置切换工具。解决了在不破坏打开会话的情况下运行多个 AI 编码代理端点的问题。

但切换有两个维度：**进程隔离**和**持久化配置**。启动模式处理前者。应用模式处理后者。

使用启动模式，每个会话是独立的。可以在五个终端运行五个不同的配置。环境是冻结的、可预测的、隔离的。

使用应用模式，配置成为默认值。设置一次，所有新会话都使用它。可以在会话中使用 `/model` 切换模型。环境是持久的、灵活的、共享的。

这两种模式不是竞争关系。它们解决不同的问题。启动模式用于并行工作。应用模式用于顺序工作。它们共同覆盖了开发者实际使用 AI 编码代理的全场景。

跨平台支持意味着 Windows 用户不再是二等公民。Codex 支持意味着 aweswitch 不再绑定单一提供商。这些是基础性变化，让工具能服务更广泛的用户。

核心原则不变：命名配置、运行时注入、不修改全局配置（除非明确要求 `apply`）。

## aweswitch 系列文章

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)

## 更多来自 Webioinfo

aweswitch 是 [Webioinfo](https://www.webioinfo.top/) 生态系统的一部分：

- **[aweskill](https://aweskill.wehuman.top/)** — 面向 47+ AI 编码代理的 CLI 优先 Skill 包管理器
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — 支持配置感知恢复的 AI 编码会话管理器
- **[awescholar](https://github.com/wehuman01/awescholar)** — 自动化科学文献发现
