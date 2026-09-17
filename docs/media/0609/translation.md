# aweswitch: 多端点 Agent 并行，不破坏已有会话

![aweswitch](../../../logo/hero.png)

用 Claude Code 的开发者正在接入越来越多的端点。官方 Anthropic API、智谱 GLM 的 Anthropic 兼容层、Gemini 代理、小米 Mimo——每个端点有不同的 token、不同的模型名、不同的计费方式。你可能白天用官方 API 做深度调试，晚上切到 GLM 跑长任务，偶尔用 Mimo 做对比测试。

这听起来很合理。但实际操作中，切换端点是一件很痛苦的事。

你得打开 `~/.claude/settings.json`，改 `ANTHROPIC_BASE_URL`，改 `ANTHROPIC_AUTH_TOKEN`，改 `ANTHROPIC_MODEL`。保存。然后你之前打开的那个 Claude Code 会话——正在跑重构的那个——底层的 API 端点突然就变了。下一个请求可能直接报错，因为它发到了错误的端点。

更糟的是，你同时开着三个终端窗口，每个都在跑不同端点的 Claude Code。你改了全局配置。三个窗口全部受影响。

这就是 `aweswitch` 要解决的问题——用命名 profile 管理多端点，只在启动时注入配置，永远不改写全局设置。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 旧的工作流：改配置，然后祈祷

没有 aweswitch 时，切换端点的流程大概是这样：

1. 打开 `~/.claude/settings.json`
2. 找到 `ANTHROPIC_BASE_URL`，改成新的端点地址
3. 找到 `ANTHROPIC_AUTH_TOKEN`，改成对应的 token
4. 找到 `ANTHROPIC_MODEL`，改成新端点支持的模型名
5. 保存文件
6. 启动新的 Claude Code 会话
7. 祈祷之前开的会话不要因为配置变更而崩溃

每切一次就要改三个字段。如果你有四五个端点，记住每个端点对应的三元组（URL、token、模型）本身就是一种负担。

有些人用 shell alias 部分解决这个问题：

```bash
alias cc-glm='ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=... ANTHROPIC_MODEL=... claude'
```

这能工作，但 alias 管不了复杂场景——模型覆盖设不了，token 的引用和脱敏做不了，配置散落在 `.zshrc` 里，越积越乱。

还有一些切换工具选择直接改写全局配置。切换时，它们修改 agent 的共享 settings 文件。这种方式简单直接，但有一个致命缺陷——所有已经运行的会话共享同一份配置。改一次，全部受影响。

## aweswitch 的工作流：命名 profile，运行时注入

`aweswitch` 把端点配置组织成命名 profile，存在自己的 JSON 文件里，只在启动新进程时注入。

安装：

```bash
pip install aweswitch
aweswitch config init
```

添加 profile：

```bash
aweswitch add
```

交互式提示你输入 profile 名称、端点地址、token 环境变量名、模型。或者直接编辑配置文件：

```bash
aweswitch config edit
```

配置长这样——按 provider 分组，简洁可读：

```json
{
  "profiles": {
    "claude": {
      "cc-glm": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
          "ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "glm-5.1"
        }
      },
      "cc-gemini": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://generativelanguage.googleapis.com",
          "ANTHROPIC_AUTH_TOKEN": "${GEMINI_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "gemini-3.1-pro-preview"
        }
      },
      "cc-xiaomi": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
          "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "mimo-v2.5-pro"
        }
      }
    }
  }
}
```

用一行命令启动：

```bash
aweswitch cc-glm
```

这就是全部。不需要改任何全局文件。不需要记住 URL 和 token。不需要祈祷。

## 核心原则：不动全局配置

`aweswitch` 最核心的设计决策是：**永远不改写全局 agent 配置**。

它通过 Claude Code 的运行时参数 `--settings` 注入环境变量，只作用于当前启动的子进程。已经打开的其他会话完全不受影响。

这意味着你可以同时做这些事：

- 终端 1：`aweswitch cc-glm` 跑智谱 GLM 做代码审查
- 终端 2：`aweswitch cc-gemini` 跑 Gemini 做文档生成
- 终端 3：`aweswitch cc-xiaomi` 跑 Mimo 做对比测试

三个会话，三个端点，三个模型，互不干扰。关掉其中一个，另外两个继续正常工作。


想想以前的痛苦：会话莫名报错，排查半天才发现是上次切端点改了全局配置。`aweswitch` 从根本上消除了这类问题。

## 用例 1：日常多端点切换

你有三个端点。白天用官方 Claude API 处理重要任务——稳定性最好。晚上跑长时间任务时切到 GLM——性价比更高。偶尔用 Mimo 做实验。

没有 aweswitch 时，每次切换都要手动改配置，或者维护一堆脆弱的 alias。

有了 aweswitch：

```bash
aweswitch list
```

```
cc-glm      glm-5.1        https://open.bigmodel.cn/api/anthropic
cc-xiaomi   mimo-v2.5-pro  https://token-plan-sgp.xiaomimimo.com/anthropic
```

```bash
aweswitch cc-glm
```

一行命令，启动。用完关掉终端，下次要用哪个端点，就启动哪个 profile。不需要记住 URL，不需要记住 token 变量名，不需要记住模型名。

## 用例 2：并行会话做对比测试

你在评估不同模型对同一任务的表现。你想知道 GLM、Gemini 和 Mimo 在代码审查质量上有什么差异。

你在三个终端窗口分别启动：

```bash
# 终端 1
aweswitch cc-glm

# 终端 2
aweswitch cc-gemini

# 终端 3
aweswitch cc-xiaomi
```

三个会话同时运行，各自使用不同的端点和模型。你在每个会话中给出相同的指令，对比输出结果。

如果用全局配置切换工具，这是做不到的——改一次全局配置，所有会话都会受影响。`aweswitch` 的运行时注入让并行测试成为可能。

## 用例 3：Token 安全管理

每个端点用不同的 token。你不希望 token 以明文形式出现在配置文件里。

`aweswitch` 用环境变量引用解决这个问题。配置中，token 写成 `${VAR_NAME}` 的形式：

```json
"ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}"
```

实际的 token 值存在 shell 环境变量里：

```bash
export GLM_ANTHROPIC_AUTH_TOKEN="your-secret-token"
```

放在 `~/.zshrc` 里，每次打开终端自动可用。配置文件里只有变量名，没有明文 token。

此外，`aweswitch` 的检查命令会自动隐藏敏感字段：

```bash
aweswitch show cc-glm
```

输出中 token、key、secret、password、auth 等字段会被替换为 `***`。你可以放心地把 `show` 的输出贴到聊天里求助，不用担心泄露凭证。

## 用例 4：模型分层配置

Claude Code 在不同场景下使用不同的模型——主模型处理复杂任务，轻量模型处理后台任务。你可能希望主模型用 `mimo-v2.5-pro`，但轻量任务用 `mimo-v2.5` 以节省成本。

`aweswitch` 支持 Claude 的模型覆盖：

```json
{
  "profiles": {
    "claude": {
      "cc-xiaomi": {
        "env": {
          "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
          "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
          "ANTHROPIC_MODEL": "mimo-v2.5-pro",
          "ANTHROPIC_DEFAULT_HAIKU_MODEL": "mimo-v2.5"
        }
      }
    }
  }
}
```

主模型是 `mimo-v2.5-pro`，haiku 级别的任务自动用 `mimo-v2.5`。一个 profile 搞定分层，不需要额外的配置。

## 用例 5：搭配 aweshelf 和 aweskill

`aweswitch` 独立可用，但 [Webioinfo](https://www.webioinfo.top/) 生态里有两个搭档让工作流更完整：

- **[aweshelf](https://github.com/wehuman01/aweshelf)** — AI 编程会话管理器。收藏会话时，会记录当时激活的 aweswitch profile。恢复会话时，自动用相同的端点、模型和 token 重启。你的 GLM 调试会话不会被错误地恢复到 Gemini 端点上。
- **[aweskill](https://github.com/wehuman01/aweskill)** — 面向 47+ AI 编程 Agent 的 Skill 包管理器。把 `aweswitch` 作为 Skill 安装一次，你用的任何 Agent 都能读取 SKILL.md 并操作 CLI，无需手动配置。

三条流水线各司其职：**aweskill** 安装技能，**aweswitch** 管理运行时配置，**aweshelf** 持久化会话——你只管写代码。

## 用例 6：交互式添加新端点

你刚拿到了一个新的端点。不想手动编辑 JSON 文件。

```bash
aweswitch add
```

交互式提示你输入：

1. Profile 名称（比如 `cc-deepseek`）
2. Base URL
3. Auth token 环境变量名
4. 模型名
5. 可选的 haiku/sonnet 模型覆盖

填完之后，profile 自动写入配置文件。不需要手动编辑 JSON，不用担心格式错误。

```bash
aweswitch cc-deepseek
```

立即可用。

## 与 cc-switch 的区别

[cc-switch](https://github.com/farion1231/cc-switch) 同样是一个好用的工具——图形界面、系统托盘、内置数据库，支持 Claude Desktop、Codex、Gemini、Hermes 等多个 provider。

两者的核心区别在于**切换方式**：

**cc-switch** 切换时改写 Agent 的全局配置文件。新启动的 Agent 会读到新配置，但已经在跑的会话也跟着变了——如果你终端里正跑着 Claude Code，切 profile 后原来的会话可能因端点突变而报错。

**aweswitch** 不碰任何全局配置。它通过运行时参数注入，只对当前启动的进程生效，已有会话完全不受影响。三个终端跑三个不同端点，互不干扰。

这个区别决定了它们各自的适用场景：

### 什么时候用 aweswitch

- 你需要**同时运行多个不同端点的 Claude Code 会话**——比如并行对比不同模型的输出
- 你用 **CLI 和终端**为主，不需要图形界面
- 你想让 **Agent 能自动操作**——aweswitch 的 CLI 可被 aweskill 注册为 Skill，Agent 通过自然语言就能切换
- 你在**远程服务器、CI、或没有桌面环境**的地方工作
- 你需要跟 **aweshelf 配合**做 profile 感知的会话恢复

### 什么时候用 cc-switch

- 你更喜欢**图形界面**——系统托盘一键切换，不需要记命令
- 你用 **Claude Desktop、Codex、Gemini CLI、Hermes** 等多个 Agent，而不只是 Claude Code
- 你需要**管理 MCP 服务器**——cc-switch 有内置的 MCP 配置管理
- 你想跟踪 **usage 和成本**——cc-switch 有 usage 跟踪功能
- 你每次**只用一个 profile**，不需要并行运行多个端点

两个工具不矛盾。如果你用 Claude Code 并且需要并行多端点，用 aweswitch。如果你用多种 Agent 并且偏好 GUI，用 cc-switch。

## 为什么这很重要

AI 编程 Agent 的生态正在快速多样化。开发者不再只用一个端点。官方 API、自建代理、第三方兼容层——每个端点有自己的优势和适用场景。

但工具链没有跟上这个变化。切换端点仍然是一个手动、容易出错、会破坏已有会话的操作。很多切换工具选择改写全局配置，因为它简单——但它不正确。

`aweswitch` 坚持一个原则：**每个会话保留它启动时的配置**。

这不是一个技术细节——这是一个正确性保证。当你运行 `aweswitch cc-glm` 时，你知道这个会话会一直使用 GLM 端点，不管你之后启动了多少个其他 profile 的会话。你的配置不会被偷偷改掉。你的会话不会因为底层的全局设置变化而突然失败。

它不试图成为平台。它不需要注册账号。它不向云端同步任何东西。配置在本地磁盘上，格式是纯 JSON。五个端点还是五十个端点——管理方式完全一样。

## Awesome 生态系统

aweshare 是一个不断壮大的 "awesome" 工具家族的一部分 — CLI 优先、本地优先，可由 AI agent 操作。

### CLI 工具

- **[aweskill](https://aweskill.wehuman.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent。
- **[aweswitch](https://github.com/wehuman01/aweswitch)** — Claude Code、Codex 和 OpenCode 的 agent 配置切换器。
- **[awerouter](https://github.com/wehuman01/awerouter)** — 智能路由器，使用结构信号在 Flash 和 Pro 模型之间分配请求，减少不必要的模型开销。
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — 收藏、分类和恢复 AI 编程会话；与 aweswitch 配合保存配置并一键启动。
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM 后端、国内编程计划或授权的 OpenAI/Anthropic 订阅 — token 的共享经济。
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保温器，保持 AI 编程套餐窗口激活，适用于本地设置和远程 hub 服务器。
- **[awescholar](https://github.com/wehuman01/awescholar)** — 可由 AI agent 操作的科学文献发现和整理工具。

### 桌面应用

- **[awedot](https://awedot.wehuman.top/)** — 屏幕边缘的浮动球体跟踪当前 AI 会话：一键收藏，随时恢复，并可与 aweswitch 配合固定 agent 配置（例如使用 GLM 模型重新启动）。

### 项目集合

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — AI 在生物学、生物信息学和生物医学研究中应用的精选综述。由 awescholar 驱动。
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — 用于虚拟肿瘤建模和模拟的最先进 AI 系统精选集合：静态模型、动态模型、agent、基准测试和综述。

