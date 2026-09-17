<div align="center">
  <img src="logo/hero.png" alt="aweswitch" width="860">
  <h1>aweswitch: Agent Profile Switcher <a href="https://github.com/wehuman01/aweskill"><img src="https://raw.githubusercontent.com/wehuman01/aweskill/main/logo/aweskill-badge2.svg" alt="aweskill companion"></a></h1>
  <p><strong>一个很小的本地启动器，用来切换 AI agent 运行时 profile。</strong></p>
<p><strong>一份配置，一条命令 — Ubuntu、macOS、Windows 上用法一致。</strong></p>
  <p>用不同 API、token 和模型启动不同 agent 会话，同时不改写全局 agent 配置。</p>
  <p>
    <a href="./README.md">English</a> ·
    <strong>简体中文</strong> ·
    <a href="https://www.webioinfo.top/">Webioinfo</a>
  </p>
  <p>
    <a href="https://ko-fi.com/mugpeng"><img src="https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  </p>
  <p>
    <img src="https://img.shields.io/pypi/v/aweswitch?style=flat-square&color=7C3AED" alt="Version">
    <img src="https://img.shields.io/badge/python-%E2%89%A53.9-0EA5E9?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/license-MPL--2.0-22C55E?style=flat-square" alt="License">
  </p>
  <p>
    <img src="https://img.shields.io/badge/status-beta-c96a3d?style=flat-square" alt="Status">
    <img src="https://img.shields.io/badge/provider-Claude_Code_%7C_Codex_%7C_OpenCode_%7C_zcode-7C3AED?style=flat-square" alt="Provider">
    <img src="https://img.shields.io/badge/install-pip-22C55E?style=flat-square" alt="pip install">
    <img src="https://img.shields.io/badge/platform-ubuntu%20%7C%20macOS%20%7C%20windows-334155?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/pepy/dt/aweswitch?style=flat-square" alt="PyPI downloads">
    <img src="https://img.shields.io/github/stars/wehuman01/aweswitch?style=flat-square" alt="GitHub stars">
  </p>
</div>

> 让不同 agent profile 并行运行，同时不影响已经打开的会话。

`aweswitch` 从 `~/.config/aweswitch/config.json` 读取 profile，提供两种模式：

- **启动模式**（`aweswitch <profile>`）— 启动一个带独立 env 的新 agent 会话。每个会话有自己的 API endpoint、token 和模型。不同终端可以同时跑不同 profile。env 在启动时冻结。
- **写入模式**（`aweswitch apply <profile>`）— 把 profile 写入 agent 自己的配置成为持久默认：Claude env 写入 `~/.claude/settings.json`，Codex provider+model 写入 `~/.codex/config.toml`，OpenCode provider+模型列表写入 `~/.config/opencode/opencode.json`，zcode provider+模型写入 `~/.zcode/v2/config.json`。裸 `aweswitch apply` 会批量同步全部 OpenCode 和 zcode profile；`--opencode` / `--zcode` 把批量收窄到单个 agent。Claude 和 Codex 同一时间只有一个活跃默认。

它刻意保持小而直接。目前支持 Claude Code、Codex、OpenCode 和 zcode profile，以及官方帐号登录（Claude Code / Codex OAuth）。

## 快速开始

`aweswitch` 和 awesome 家族其他工具走同一条路：把引导交给 agent 跑一次，装完就有一份可用的第一配置，之后日常操作用自然语言驱动。第 1 步覆盖安装引导和直接上手；第 2、3 步是更复杂的操作——装上管理 skill 和各日常场景的细节。这个工具有一条特殊规则——agent 不会替你启动 profile，因为那会导致 agent 嵌套。应用 profile、管理配置交给 agent；启动留在你自己的终端里。

### 1. 安装和使用 aweswitch

如果你正在 Claude Code、Codex、Cursor 等编码 agent 里工作，直接把安装整个交给它——agent 会安装 CLI、初始化配置、装上 aweswitch skill，并直接把第一个 profile 写好：它会主动读取 shell 配置（`~/.zshrc`、`~/.bashrc` 或 Windows 用户环境变量）里已有的 API key 并直接引用，缺什么才问你什么。单靠这条自然语言引导，装完就有一份可用的配置。装完调用 skills（Claude Code 输入 `/`，Codex 输入 `$`）确认新 skill 已出现；没出现的话重启 agent 即可。

可以直接对 agent 说：

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

引导完成后就可以直接用了。使用一个 profile 有两种方式：

**写入（apply）**——把 profile 写入 agent 自己的配置，成为持久默认，之后正常打开的会话都用它。可以直接对 agent 说：

```text
添加一个 GLM 的 claude profile，然后把 cc-glm 写入 Claude settings。
```

**启动（launch）**——不改任何全局配置，直接启动一个带独立 API 和模型的临时会话，不同终端可以并行跑不同 profile。想这样用时，在你自己的终端运行（agent 不会替你启动，那会嵌套 agent）：

```bash
aweswitch cc-glm
```

不在编码 agent 里、想自己动手的话，从 PyPI 安装、创建默认配置，再交互式添加第一个 profile 或直接编辑配置文件——命令和参考配置收在下面的折叠块里。

包主页：[pypi.org/project/aweswitch](https://pypi.org/project/aweswitch/)

<details>
<summary>安装与引导的 CLI 命令</summary>

```bash
# 从 PyPI 安装
pip3 install aweswitch
aweswitch --help

# 创建默认配置，再按真实 provider 调整
aweswitch config init
aweswitch config edit

# 或者交互式添加 profile / 官方帐号（api 或 official）
aweswitch add

# 验证已配置的 profile（密钥已脱敏）
aweswitch list
aweswitch show cc-glm
```

</details>

<details>
<summary>参考配置与 token 环境变量</summary>

默认配置先按类型分组（`api` 为基于 env 的 API profile，`accounts` 为官方登录帐号），再按 provider 分组。以下是可以直接修改的参考配置：

```json
{
  "profiles": {
    "api": {
      "claude": {
        "cc-glm": {
          "env": {
            "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "ANTHROPIC_MODEL": "glm-5.1"
          }
        },
        "cc-xiaomi": {
          "env": {
            "ANTHROPIC_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
            "ANTHROPIC_MODEL": "mimo-v2.5-pro"
          }
        }
      },
      "codex": {
        "cx-openai": {
          "env": {
            "OPENAI_BASE_URL": "https://api.openai.com",
            "OPENAI_API_KEY": "${OPENAI_API_KEY}"
          }
        }
      },
      "opencode": {
        "oc-glm": {
          "env": {
            "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "OPENCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "OPENCODE_NAME": "Zhipu GLM",
            "OPENCODE_MODEL": {
              "glm-5.1": "GLM-5.1",
              "glm-5.2": "GLM-5.2"
            }
          }
        }
      },
      "zcode": {
        "zc-glm": {
          "env": {
            "ZCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "ZCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "ZCODE_NAME": "BigModel - Coding Plan",
            "ZCODE_CHAT_MODEL": {
              "GLM-5.3-Flash": "GLM-5.3-Flash",
              "GLM-5-Turbo": "GLM-5-Turbo"
            }
          }
        }
      }
    },
    "accounts": {}
  }
}
```

v0.4 之前的配置（profile 直接按 provider 分组）在首次加载时会自动迁移，并在配置文件旁生成 `config.json.bak` 备份。

配置 profile 引用的 token 环境变量：

```bash
# Claude / OpenCode profiles
export GLM_ANTHROPIC_AUTH_TOKEN="..."
export XIAOMI_ANTHROPIC_AUTH_TOKEN="..."

# Codex profiles
export OPENAI_API_KEY="..."

# zcode profiles
export ZCODE_API_KEY="..."
```

如果希望每次打开终端都可用，可以把这些变量放进你的 shell 配置文件：macOS 用 `~/.zshrc`，bash 用 `~/.bashrc` 或 `~/.bash_profile`，PowerShell 用 `$PROFILE`。

</details>

<details>
<summary>示例：查看已配置的 profile</summary>

![image-20260622102235441](assets/images/image-20260622102235441.png)

</details>

<details>
<summary>示例：应用 profile 并切换模型</summary>

![image-20260622100567](assets/images/image-20260622100567.png)

</details>

### 2. 给 agent 装上管理能力

第 1 步的引导 prompt 通常会顺带把 `aweswitch` skill 装好（`README.ai.md` 把它作为自己的第 2 步），所以大多数人走到这里已经具备管理能力。如果你是手动安装的，或者 skill 缺失，投影一次即可——它教会 agent 列出、查看、添加、编辑、删除 profile，把 profile 写入 settings（`aweswitch apply`）、从备份恢复（`aweswitch config restore`），并在写 profile 时主动读取 shell 配置里已有的 API key。

可以直接对 agent 说：

```text
把 aweswitch skill 装进当前 agent，之后你可以用自然语言帮我管理 profile。
```

<details>
<summary>等价的 CLI 命令</summary>

```bash
# 通过 aweskill（推荐）：从 GitHub 安装并投影给当前 agent
aweskill install wehuman01/aweswitch
aweskill agent add skill aweswitch --global --agent codex
aweskill agent list --global --agent codex   # 期望 aweswitch 显示为 linked

# 不用 aweskill：把 SKILL.md 直接拷进 agent 的 skill 目录
mkdir -p ~/.claude/skills/aweswitch
curl -fsSL https://raw.githubusercontent.com/wehuman01/aweswitch/main/resources/skills/aweswitch/SKILL.md -o ~/.claude/skills/aweswitch/SKILL.md
```

</details>

### 3. 开始用自然语言管理 profile

到此为止，日常管理不需要记命令：把意图直接告诉 agent，它会读取配置、做修改、验证结果。`aweswitch apply`、`aweswitch config backup`、`aweswitch config restore` 它都可以直接执行；唯一不会做的是启动 profile（那会嵌套 agent）。下面几个场景覆盖日常使用；想手动执行 CLI 或核对具体行为时，再展开等价的命令。

用哪种模式是人的决定：

| 场景 | 模式 |
|---|---|
| 多个 profile 并行运行 | 启动（你的终端） |
| 在会话内用 `/model` 切换模型 | 写入（agent 可以执行） |
| 快速试用不同 API | 启动 |
| 设置持久默认 profile | 写入 |
| 把改过的 OpenCode profile 推送到 opencode.json | 写入（`aweswitch apply`） |
| 把改过的 zcode profile 推送到 zcode config.json | 写入（`aweswitch apply`） |

> **注意：** 两种模式互不影响。`aweswitch cc-glm` 不会读取或修改 settings.json。`aweswitch apply cc-glm` 不会影响正在运行的会话。

#### 查看与检查 profile

所有 profile 都在一个本地配置文件里，查看类命令自动脱敏。改动之前，先让 agent 报告现状。

可以直接对 agent 说：

```text
列出我所有的 aweswitch profile，再看看 cc-glm 指向什么。
```

<details>
<summary>等价的 CLI 命令</summary>

```bash
aweswitch list                        # 列出所有 profile（含 api/account 类型）
aweswitch show cc-glm                 # 查看单个 profile（密钥已脱敏）
aweswitch usage cxo-work              # 查看 Codex 官方帐号的配额使用情况
aweswitch config path                 # 查看配置文件路径
aweswitch config show                 # 查看完整配置（密钥已脱敏）
aweswitch config edit                 # 编辑配置文件
```

</details>

#### 新增或修改 profile

新增 profile 就是在 `profiles.api.<provider>` 下加一个用 `${VAR_NAME}` 引用 token 的条目。agent 会先读当前配置，再扫描 shell 配置（`~/.zshrc`、`~/.bashrc` 或 Windows 用户环境变量）里已导出的 API key，直接引用它们把 profile 写好——只有缺失的 key 才需要你提供，agent 还能顺手帮你持久化进 shell 配置。修改同理：重命名 profile、把 `cc-glm` 的模型改成 `glm-5.2`、或给后台任务加一个更轻的 haiku 档模型。

可以直接对 agent 说：

```text
添加一个 AiHubMix 的 codex profile，名字叫 cx-aihubmix；API key 优先用我 shell 里已有的，缺了再问我。
```

<details>
<summary>等价的 CLI 命令</summary>

```bash
aweswitch add                         # 交互式添加 profile 或官方帐号
# Provider: codex
# Profile name: cx-myprovider
# OPENAI_BASE_URL: https://myprovider.com/v1
# OPENAI_API_KEY env var name: MY_PROVIDER_KEY

aweswitch config edit                 # 或者直接编辑 ~/.config/aweswitch/config.json
```

各 provider 的 env 键、模型格式和命名规则见 [Profile 规则](#profile-规则)。

</details>

#### 设置持久默认 profile

`aweswitch apply <profile>` 把 profile 写入 agent 自己的配置，成为持久默认——Claude env 写入 `~/.claude/settings.json`，Codex provider+model 写入 `~/.codex/config.toml`，OpenCode 和 zcode 的 provider+模型列表写入各自配置文件。Claude 和 Codex 同一时间只有一个活跃默认；OpenCode 和 zcode 的 profile 天然并存，裸 `aweswitch apply` 会批量同步两侧。首次写入会自动备份，Claude 的改动可以用 `aweswitch config restore` 撤销。

可以直接对 agent 说：

```text
把 cc-glm 写入 Claude settings，这样我可以用 /model 切换模型。
```

<details>
<summary>等价的 CLI 命令</summary>

```bash
aweswitch apply cc-glm                # Claude：env -> ~/.claude/settings.json
aweswitch apply cx-glm                # Codex：provider+model -> ~/.codex/config.toml
aweswitch apply oc-glm                # OpenCode：provider+模型列表 -> ~/.config/opencode/opencode.json
aweswitch apply zc-glm                # zcode：provider+模型列表 -> ~/.zcode/v2/config.json
aweswitch apply                       # 批量：先同步全部 OpenCode profile，再同步全部 zcode profile
aweswitch apply --opencode            # 只批量 OpenCode
aweswitch apply --zcode               # 只批量 zcode
aweswitch apply cc-glm cx-glm oc-glm  # 混合：一条命令多个 agent 各写一个
aweswitch apply cc-glm --force        # 覆盖已有备份

# 清理没有 profile 对应的受管 OpenCode / zcode provider
aweswitch apply --prune orphans             # 批量同步两个 agent，并清理没有 profile 对应的已登记 provider
aweswitch apply --opencode --prune all      # 再清理所有没有 profile 对应的 provider（含手写条目）
aweswitch apply --opencode --prune old-a,old-b --dry-run  # 预览点名清理，不写入任何文件

# 备份与恢复 Claude settings
aweswitch config backup               # 手动备份并输出备份路径
aweswitch config restore              # 从默认备份恢复 settings
aweswitch config restore <file>       # 从指定备份文件恢复 settings
```

除 `--dry-run` 外，每次 prune 都会先打印目标，并要求输入 `y` 确认后才写入配置。zcode 的 `builtin:*` 预设 provider 永远受保护，`--prune all` 也不会删除；点名清理它们会被直接拒绝。

各 agent 的写入语义：

- **Claude** — env 合并进 `~/.claude/settings.json`；无关设置会保留，而新 profile 未声明的旧 `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` 认证替代项会被移除。重启会话或用 `/model` 选择新模型。
- **Codex** — provider 表和默认模型写入 `~/.codex/config.toml`（`mcp_servers` 等已有内容原样保留；首次写入会生成 `.toml.bak` 备份）。API key 仍留在环境里：`env_key` 指向 profile 引用的 `${VAR_NAME}`，codex 运行时从你的 shell 读取。
- **OpenCode** — provider 条目（base URL、key 引用、显示名）及其**完整模型列表**按 upsert 写入 `~/.config/opencode/opencode.json`：存在则覆盖、不存在则添加。每个受管模型默认带 `low` / `medium` / `high` / `xhigh` / `max` 五档思考强度 variant，可在 OpenCode 中用 `ctrl+t` 切换。手写 variant 永远优先；若 OpenAI 官方 Responses 端点拒绝 `max`，切回有效档位即可。启动 profile 会以增量方式写入该 profile 的完整模型列表（不会删除任何已有条目）；apply 则精确对齐。aweswitch 会在 `.aweswitch-managed-providers.json` 中登记自己管理的 provider key；已登记的 profile 改名或删除后，apply 会对残留条目发出警告（老 session 锚定着这些旧模型 ID），`aweswitch apply --opencode --prune orphans` 可将其删除。该模式下的所有权从不根据配置形状猜测，手写条目默认不动，除非显式选择：`--prune old-a,old-b` 只删除点名条目（必须存在、且不能有同名 profile 背书）；`--prune all` 删除所有没有 profile 对应的 provider——即完全对齐，手写条目也会被删；`--prune orphans` 只清理已登记的残留条目；config 里一个 OpenCode profile 都没有时会拒绝执行。任何 prune 都不会让文件顶层 `model` 悬空：若其指向的 provider 被删，会重指到按字母序第一个 profile 的第一个配置模型。`--dry-run` 可零写入预览 sync 与清理计划（双 agent 批量时只预览 OpenCode 侧，zcode 侧清理没有预览）。含 `/` 的模型 ID（如 `hub/seed-evolving`）在模型选择器中以完整 ID 显示，不同 producer 的条目不会再长得一样。
- **zcode** — provider 条目（base URL、环境变量 key 引用、显示名）及其**完整模型列表**按 upsert 写入 `~/.zcode/v2/config.json`。zcode 的一个 provider 只支持一种 API 格式，因此 profile 只能声明 `ZCODE_CHAT_MODEL`（chat completions，provider `kind: openai-compatible`）**或** `ZCODE_RESPONSES_MODEL`（Responses API，provider `kind: openai`），二者互斥——需要两种格式就拆成两个 profile。模型字段的 key 顺序即选择器顺序，每次 apply 都会重写。每个受管模型——chat（`ZCODE_CHAT_MODEL`）或 Responses（`ZCODE_RESPONSES_MODEL`）——都会补写一个 fill-only 的默认 reasoning 块：`variants: [none, low, medium, high, xhigh, max]`（默认 `medium`）。`none` 是 canonical 档位名，选中即发送 `reasoning_effort: "none"`，模型不再思考——已在大模型 GLM、ark deepseek、sensenova、weixin、kimi 端点实测关闭生效（stepfun 忽略该值，仍会思考），选择器里显示为 "None"。zcode 对没有 reasoning 块的 chat 模型会隐藏该选择器，且只有 canonical 档位名会映射到请求参数——普通 `off` 条目等于什么都不发，所以默认档以 `none` 领衔而非 `off`。普通 reasoning 块也是 zcode 对自定义 provider 唯一会保留的形式：catalog 格式的 `zcode.reasoning` spec 加载时被忽略、zcode 下次保存配置时被整体剥离。aweswitch 自己旧版的填充（精确匹配的 plain `low..max` 块，或未发布版本写下的 `zcode.reasoning` spec）会在下次 apply 时迁移；其余手写 reasoning 配置整体保留（已有的 variants 列表、非 aweswitch 形状的 `zcode.reasoning` 均不会被增删或重排），`"reasoning": false` 或 `enabled: false` 表示显式关闭。Responses API（`ZCODE_RESPONSES_MODEL`）的模型同样补写该块——这正是 zcode 自己在档位选择后持久化的 plain 形状，两类模型无需任何额外设置就有一致的思考/关闭档位。zcode 是桌面 GUI 应用，因此 zcode profile 只支持 apply，不支持启动。`--zcode` 会同步全部 zcode profile；aweswitch 用 `.aweswitch-managed-providers.json` 登记自己管理的 provider，默认只警告孤儿条目，显式加 `--prune`（`orphans` / `all` / 点名）才清理；`--dry-run` 没有 zcode 侧预览。

Claude 和 Codex 同一时间只有一个活跃默认配置，单次 apply 各最多一个 profile；OpenCode 和 zcode 的 provider 天然并存，可以一次应用多个——裸 `aweswitch apply` 会批量同步两侧全部 profile（某一侧没有 profile 时跳过并提示），`--opencode` / `--zcode` 把批量收窄到单个 agent。

</details>

#### 钉住 subagent 模型

subagent（OpenCode 的 `task` agent、zcode 内置的 Explore / general-purpose、Claude Code 的 `Task` subagent）默认继承主模型，因此本来就会跟着你启动/apply 的 profile 走。agent 文件的寿命比任何 profile 都长，所以 OpenCode/zcode 的钉子放在与 `profiles` 平级的顶层 `subagents` 栏目里——每个目标一张映射表，值同时写明 provider 和模型。典型场景是主模型用 pro、只读侦查类 subagent 用便宜的 flash：

```json
{
  "profiles": {
    "api": {
      "opencode": {
        "oc-glm": {"env": {
          "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
          "OPENCODE_API_KEY": "${GLM_API_KEY}",
          "OPENCODE_MODEL": {"glm-5.2": "GLM-5.2", "glm-5.1-flash": "GLM-5.1-Flash"}
        }}
      },
      "zcode": {
        "zc-bigmodel": {"env": {
          "ZCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
          "ZCODE_API_KEY": "${GLM_API_KEY}",
          "ZCODE_CHAT_MODEL": {"GLM-5.3-Flash": "GLM-5.3-Flash"}
        }}
      }
    }
  },
  "subagents": {
    "opencode": {
      "explore": "oc-glm/glm-5.1-flash",
      "review": "oc-step/step-3.7-flash"
    },
    "zcode": {
      "general-purpose": "zc-bigmodel/GLM-5.3-Flash",
      "Explore": "zc-bigmodel/GLM-5.3-Flash",
      "review": "zc-bigmodel/GLM-5.3-Flash"
    }
  }
}
```

- `subagents.opencode` — `{agent名: "profile/model"}` 映射。名字在 `~/.config/opencode/agents/` 里没有对应 markdown 文件时，会**用通用模板创建**（描述与正文提示词都是模板，只有模型一行不同）；已有文件则只改写其 frontmatter 的 `model:` 一行（正文提示词永不触碰），写进文件的就是你写的 `profile/model` 原文。
- `subagents.zcode` — 同样的形态，`~/.zcode/agents/` 同样适用"缺文件即模板创建"。两个内置名（`general-purpose`、`Explore`）写入 zcode 内置 agent 的模型覆盖（`~/.zcode/v2/agents-state.json`）；其余名字钉住具名用户 subagent——只改写其 frontmatter 的 `model:` 一行，写成 zcode 自己使用的 `custom:<provider>:<model>` 形式。内置与用户 agent 可以出现在同一张表里，各钉各的模型。
- 每个值就是 agent 文件里最终那串字符：`profile/model-id`，按第一个 `/` 切分（模型 ID 本身可以含斜杠，例如 `hub/seed-evolving`）。被指名的 profile 必须是同目标的 api profile 且列出该模型；每次 apply 都会把这些 provider 一并 ensure，钉子始终可解析。借用别的 profile 的 provider 就是直接写它的名字——`"review": "oc-step/step-3.7-flash"` 让主模型继续用 GLM、review 跑 StepFun。
- 旧配置直接兼容：profile env 里的 `OPENCODE_SUBAGENT_MODEL` / `ZCODE_SUBAGENT_MODEL` 会在首次加载时迁入该栏目（配置重写并留 `.json.bak` 备份；`@profile/model` 引用和 zcode 的单值形态会被展开）。
- **Claude** 不需要栏目条目：在 profile env 里直接写 `CLAUDE_CODE_SUBAGENT_MODEL`——这是 Claude Code 对 `Task` subagent 和 agent-teams teammate 的全局默认值，优先级高于 agent frontmatter 的 `model:`。模型必须由本 profile 的 `ANTHROPIC_BASE_URL` 服务（一个会话一个端点，因此跨 provider 引用不适用）。aweswitch 像托管 tier 变量一样托管该键：每次 launch/apply 都会写出它，profile 未设置时写 `inherit`（Claude Code 的显式回落值），别的 provider 留下的钉子永远漏不进来；在 `~/.claude/settings.json` 里手写的值同样会被覆盖。
- **Claude 按别名细分的替代方案**：在 profile env 里写 `ANTHROPIC_DEFAULT_HAIKU_MODEL`（或任意 OPUS/SONNET/HAIKU/FABLE tier 变量），agent frontmatter 里写 `model: haiku`——tier 重映射保留每个 agent 的别名区分，而不是一刀切。
- **Codex** —— 在 profile env 里写 `CODEX_SUBAGENT_MODEL`（该 profile 端点服务的模型 ID）。launch 以 `-c agents.default_subagent_model=...` 注入；apply 则托管 `~/.codex/config.toml` 里 `[agents]` 表中的同名键——它是 codex 对 `spawn_agent` sub-agent 的默认模型（主 agent 显式指定 spawn 模型时仍以后者为准）。apply 一个没有该字段的 profile 会释放这个键（随之变空的 `[agents]` 表一并消失）；手写的 `[agents]` 角色和其他键原样保留。不支持跨 profile 引用——codex 的 sub-agent 走会话唯一的端点。

钉子跟随 aweswitch 配置，而不是最后一次 apply 的 profile：任何 apply 都会把钉子收敛到栏目当前声明的状态——上次被管理但栏目已不再提及的 agent 会被移除：aweswitch 用模板创建的文件直接**删除**，用户手写的文件只去掉 `model:` 一行，落回继承主/会话模型（对任何 provider 都合法）。启动某个 profile 只会增量（重）写栏目声明的钉子（缺失的声明文件也会按模板创建），绝不移除任何东西。aweswitch 从未管理过的 agent 文件一个字节不碰；apply 还会对「钉着已不存在 provider」的非受管 agent 文件发出警告。

#### 并行启动不同 profile

启动是唯一留在你手里的动作：agent 不会运行 `aweswitch <profile>`，因为那会导致 agent 嵌套。每次启动都是一个新的会话，env 在启动时冻结，所以不同终端可以同时跑不同 profile，互不改写全局 agent 配置。

在你自己的终端运行：

```bash
aweswitch cc-glm                      # 启动 Claude Code profile
aweswitch cx-openai                   # 启动 Codex profile
aweswitch oc-glm glm-5.2              # 启动 OpenCode profile 并指定模型
aweswitch cxo-work                    # 启动 Codex 官方帐号（见下文）
```

<details>
<summary>额外参数与自动 bookmark</summary>

```bash
# 把额外参数透传给 agent
aweswitch cc-glm --dangerously-skip-permissions
aweswitch cx-openai --model o3
aweswitch oc-glm glm-5.1 --mini

# 配合 aweshelf 在启动时自动 bookmark
aweswitch cc-glm -c backend -t "Fix auth bug"
```

详见 [aweshelf 集成](#aweshelf-集成)。

</details>

#### 多个官方帐号并行使用

官方帐号登录（OAuth）以 account 形式保存，启动时走独立的 per-account 配置目录，多个 Claude Code / Codex 登录可以并行使用，完全不碰全局的 `~/.claude` 或 `~/.codex`。OAuth 登录流程是交互式的，要在你的终端里跑；导入当前登录、回写刷新 token 则可以交给 agent。

可以直接对 agent 说：

```text
把我当前登录的 Claude 帐号导入为 team-a。
```

<details>
<summary>帐号命令与工作方式</summary>

```bash
aweswitch account login codex work    # 运行 codex login 并捕获为帐号 work
aweswitch account add claude team-a   # 导入当前已登录的 claude 帐号
aweswitch cxo-work                    # 用 work 帐号启动 codex
aweswitch account sync codex work     # 把刷新过的 token 回写到配置
aweswitch account remove codex work --purge
aweswitch usage cxo-work              # 查看 Codex 官方帐号的配额使用情况
aweswitch usage --all-codex           # 查看所有 Codex 官方帐号的配额使用情况
```

`aweswitch add` 选 `official` 类型是同样两条路径的交互式入口：依次询问 provider、帐号名和方式（`login` 运行 OAuth 登录，`import` 读取当前 CLI 登录）。

工作方式：

- 启动帐号时，aweswitch 将 `CODEX_HOME`（codex）或 `CLAUDE_CONFIG_DIR` + `CLAUDE_CODE_DONT_USE_KEYCHAIN=1`（claude）指向 `~/.config/aweswitch/accounts/<provider>/<name>/` 下的私有目录。凭据以不透明 blob 形式存在 `config.json` 中，`show` / `config show` 整段脱敏；配置文件包含帐号后权限收紧为 600。
- 帐号目录一旦存在就是事实来源 — CLI 会在里面刷新 OAuth token，已存在的凭据文件永远不会被配置里的旧 blob 覆盖。需要备份/迁移时运行 `aweswitch account sync` 把刷新过的 token 回写到配置。
- macOS 上 Claude Code 默认把登录存在 Keychain；`account login` 和帐号启动都会强制凭据走帐号目录内的文件，保证帐号隔离。`account add` 读取的是 `~/.claude/.credentials.json`，该文件不存在时会失败 — macOS 上建议直接用 `account login`。
- 帐号只支持启动模式，不参与 `apply`。
- `aweswitch usage <codex-帐号>` 可读取 Codex 官方帐号的配额使用情况。仅 Codex 官方帐号暴露兼容的配额 API；GLM 和 Doubao 仍只能在 dashboard 查看。基于 API key 的 Codex profile 不支持此功能。
- 会话默认按帐号隔离：每个帐号目录各有自己的 `sessions/`，`codex resume` 只能看到该帐号录制的会话。在 `config.json` 顶层设置 `"share_sessions": true` 即可让 Codex 会话跨帐号共享：下次启动时，每个 Codex 帐号的 `sessions/` 和 `archived_sessions/` 会变成指向共享池 `~/.config/aweswitch/accounts/codex/.shared/` 的链接，已有的 rollout 文件自动迁入。之后任意帐号都能续任何会话 — `aweswitch cxo-peng resume <id>` 可以续 `cxo-heck` 录的会话 — `codex resume` 选择器也会列出所有帐号的会话（加 `--all` 可解除 cwd 过滤）。默认 Codex home 也会进池：直接运行 `codex` 或 `cx-*` api profile 录制的会话落在 `~/.codex/sessions`，下次 Codex 启动时该目录同样变成池链接，这些会话在任何帐号下都能续，池里的会话在裸 codex 下也能续。关掉开关会再次解除帐号目录和默认 home 的链接；已进入共享池的文件留在池里，因为 rollout 文件本身不带帐号身份。Claude 帐号暂不共享。

</details>

## 支持工具

aweswitch 由三个配套工具驱动：

- **[aweskill](https://github.com/wehuman01/aweskill)** — 面向 AI agent 的 CLI skill 包管理器。负责 skill 的安装、更新和投影，支持 47+ 编程 agent。
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — Claude Code 和 Codex 的会话 bookmark 管理器。可以保存、分类和恢复会话，支持 aweswitch profile。
- **[awerouter](https://github.com/wehuman01/awerouter)** — 智能 LLM 路由器：按结构信号把 agent 请求分给 flash（便宜）或 pro（强力）模型。

aweswitch 管**启动**会话，aweshelf 管**记住**会话。用 `aweswitch -c` 在启动时自动 bookmark，用 `aweshelf resume` 恢复时会带上相同的 profile。搭配 awerouter 也一样丝滑：把 profile 的 `BASE_URL` 指向 awerouter daemon（`ANTHROPIC_MODEL=auto`），启动的每个会话都走它的 flash/pro 智能分流。

## 自动更新

aweswitch 每次运行时会在后台检查 PyPI 是否有新版本。如果有更新，会在会话结束后在 stderr 输出提醒。

<details>
<summary>self-update 命令</summary>

```bash
aweswitch self-update                 # 手动更新
aweswitch self-update --check         # 仅检查不更新
export AWESWITCH_NO_UPDATE_CHECK=1    # 禁用后台检查
```

</details>

## aweshelf 集成

[aweshelf](https://github.com/wehuman01/aweshelf) 是 Claude Code 和 Codex CLI 的会话 bookmark 管理器，可以保存、标记、搜索和恢复历史 coding 会话。

aweswitch 与 aweshelf 集成，支持在启动会话时自动完成 bookmark，无需额外操作：

```bash
aweswitch cc-glm -c backend -t "Fix auth bug"
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-c`, `--category` | bookmark 的分类标签（如 `backend`、`research`、`infra`）。 |
| `-t`, `--title` | 自定义 bookmark 标题。不传时 aweshelf 用会话的第一条消息作为标题。 |

两个参数都需要 aweshelf 已安装。如果 aweshelf 未找到，参数会被忽略并输出警告到 stderr。Claude Code 不受影响，正常启动。

> **注意**：在同一项目目录下同时启动多个 `aweswitch -c` 会话可能导致 bookmark 标记错误。顺序启动是安全的——只要前一个会话的 JSONL 文件已创建（通常几秒内），再启动下一个就不会有问题。详见 [CONTRIBUTING.md](./docs/CONTRIBUTING.md#known-limitation-concurrent-launch-race-condition)。

### 安装 aweshelf

```bash
pip3 install aweshelf
```

<details>
<summary>aweshelf 独立使用</summary>

即使不使用 aweswitch 的 `-c`/`-t` 参数，aweshelf 也可以独立使用：

```bash
aweshelf bookmark               # 交互式 bookmark 会话
aweshelf bookmark --current     # bookmark 当前项目最近的会话
aweshelf list                   # 列出所有 bookmark
aweshelf search "auth"          # 全文搜索 bookmark
aweshelf resume BOOKMARK_ID     # 恢复已保存的会话
aweshelf browse                 # 交互式 TUI 浏览器
```

</details>

完整文档见 [aweshelf README](https://github.com/wehuman01/aweshelf)。

## FAQ

### aweswitch 解决什么问题，适合谁？

`aweswitch` 适合同时使用多个 AI coding agent 运行时端点、模型或 token 来源的人。它提供一个可重复的本地命令，避免你来回手改 settings。

- **一个本地配置文件**：`~/.config/aweswitch/config.json`
- **命名 agent profile**：例如 `cc-glm`、`cc-gemini`、`cc-xiaomi`、`cx-openai`、`oc-glm`
- **并行会话**：不同终端可以启动不同 API/model 组合
- **只在运行时注入配置**：通过 provider 对应的运行参数
- **不修改全局 agent 配置**：已经打开的 agent 会话继续使用启动时的配置
- **token 引用**：来自 shell 环境变量或 `~/.claude/settings.json`
- **可读 JSON**：`profiles.api`（基于 env 的 profile）和 `profiles.accounts`（官方登录）分组

<details>
<summary>更多 FAQ</summary>

### aweswitch 把 profile 存在哪里？

默认路径：

```bash
~/.config/aweswitch/config.json
```

你可以用 `AWESWITCH_CONFIG` 覆盖这个路径。

### aweswitch 会修改 Claude settings 吗？

**启动模式**不会 — 它只读取 aweswitch 自己的配置，并为当前启动的 Claude Code 进程传入运行时 settings。已经运行的会话不受影响。

**写入模式**会 — `aweswitch apply <profile>` 把 profile 写入 agent 自己的配置（Claude env 写入 `~/.claude/settings.json`，Codex provider+model 写入 `~/.codex/config.toml`，OpenCode provider+模型列表写入 `~/.config/opencode/opencode.json`）。Claude 和 Codex 首次写入时会自动备份；Claude 可用 `aweswitch config restore` 撤销。

### aweswitch 支持 Codex 吗？

支持。Codex profile 在 `env` 中使用 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。aweswitch 通过 Codex 的 `-c` 配置覆盖注入 base URL，通过环境变量注入 API key，不会写入 `~/.codex/`。

### aweswitch 支持 OpenCode 吗？

支持。OpenCode profile 在 `env` 中使用 `OPENCODE_BASE_URL`、`OPENCODE_API_KEY` 和 `OPENCODE_MODEL`（或 `OPENCODE_RESPONSES_MODEL`）（另有可选的 `OPENCODE_NAME`）。启动时，aweswitch 将 provider 条目写入 `~/.config/opencode/opencode.json`（使用 `{env:VAR}` 语法，实际 key 不落盘），然后运行 `opencode -m <provider>/<model>`。

Profile name（如 `oc-glm`）作为 opencode.json 中的 provider key。模型在启动时指定：`aweswitch oc-glm glm-5.1`。不指定模型时默认使用列表中的第一个。启动会以增量方式写入该 profile 的完整模型列表（subagent 钉住的非当次模型也能解析）；修改配置后用 `aweswitch apply oc-glm` 精确 upsert 该 provider（`aweswitch apply --opencode` 则全部应用）。

恢复会话（`-s <session-id>`）时，opencode 会还原该会话上次使用的模型并忽略 `-m`——两者不一致时 aweswitch 会给出警告，提示进入 TUI 后手动切换模型（Tab）。

### aweswitch 支持官方（OAuth）登录吗？

支持 — Claude Code 和 Codex 的官方帐号通过 `aweswitch account login` 保存（或用 `account add` 导入当前登录），之后像 profile 一样启动：`aweswitch <帐号名>`。每个帐号运行在自己的配置目录（`CODEX_HOME` / `CLAUDE_CONFIG_DIR`）中，多个官方帐号可以并行。详见[官方帐号](#多个官方帐号并行使用)。

### aweswitch 支持 Hermes 吗？

暂时不支持。配置格式已经按 provider 分组，后续可以自然扩展。

</details>

## 同类工具

### [cc-switch](https://github.com/farion1231/cc-switch)

`cc-switch` 是相邻方向的 Claude Code 切换工具。它是同一问题空间里的有用参考：让 Claude Code 的 provider/model 切换更容易通过命令行完成。

关键区别是 `aweswitch` 不改写全局配置。很多切换工具通过修改 agent 共享的 API/model settings 来完成切换；这样一来，之前已经打开的 agent 会话可能会因为底层全局 API 变化而不可用。`aweswitch` 把 profile 放在自己的 JSON 文件里，只在启动新进程时注入运行时 settings，所以每个会话都保留它启动时的 API 和模型。

`aweswitch` 目前采用更小的 Python package 路线：本地 JSON profile 文件、运行时注入（Claude Code `--settings`、Codex `-c` 参数和环境变量）、检查命令隐藏敏感字段，并保留 provider 分组以便未来支持更多 agent。

## Profile 规则

- Profile 放在 `profiles.api.<provider>.<profileName>` 下；官方帐号放在 `profiles.accounts.<provider>.<accountName>` 下。
- 支持的 provider：`claude`、`codex`、`opencode`（帐号：`claude`、`codex`）。
- profile 名和帐号名在整个 `profiles` 树内全局唯一，且不能复用 aweswitch 顶层命令名；帐号名还必须是单个路径组件。
- `env` 只作用于本次启动的子进程。
- `${VAR_NAME}` 会从当前 shell 环境变量中展开。
- `show` 和 `config show` 会隐藏 token、key、secret、password、auth 这类敏感字段；帐号凭据 blob 整段脱敏。
- `aweswitch usage` 仅支持读取 Codex 官方帐号的配额。GLM 和 Doubao 未开放兼容的配额 API，仍只能在 dashboard 查看。基于 API key 的 Codex profile 不支持此功能。

### Claude Profile

- 通过运行时 `--settings '{"env": ...}'` 传入 `env`。
- 模型通过 `env.ANTHROPIC_MODEL` 配置。
- token 在 shell 中不存在时，也可以从 `~/.claude/settings.json` 中展开。

`ANTHROPIC_DEFAULT_HAIKU_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_OPUS_MODEL` 默认都不配置。如果你希望 Claude Code 对轻量任务或后台任务使用更轻的模型，可以给 profile 增加 `ANTHROPIC_DEFAULT_HAIKU_MODEL`：

<details>
<summary>Claude profile 示例 JSON</summary>

```json
{
  "profiles": {
    "api": {
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
}
```

</details>

这样主模型仍然使用 `mimo-v2.5-pro`，同时允许 Claude Code 在轻量任务中使用 `mimo-v2.5`。

### Codex Profile

- 需要 `env` 中配置 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。
- base URL 通过 `-c model_providers.custom.base_url=...` 注入（不写文件）。
- API key 通过环境变量注入（不写 `~/.codex/auth.json`）。
- 额外参数透传给 `codex` CLI。

Codex profile 只切换 API 源（base URL + API key），不切换模型。实际体验来看，Codex 配合 OpenAI 自身模型效果最好——常见用法是通过第三方 provider 中转，而不是换用完全不同的模型。

<details>
<summary>Codex profile 示例 JSON</summary>

```json
{
  "profiles": {
    "api": {
      "codex": {
        "cx-aihubmix": {
          "env": {
            "OPENAI_BASE_URL": "https://aihubmix.com/v1",
            "OPENAI_API_KEY": "${AIHUBMIX_OPENAI_KEY}"
          }
        }
      }
    }
  }
}
```

</details>

aweswitch 不会写入 `~/.codex/`。base URL 通过 Codex 的 `-c` 参数传入，API key 通过环境变量传入。你的全局 Codex 配置不会被修改。

交互式添加 Codex profile：

```bash
aweswitch add
# Provider: codex
# Profile name: cx-myprovider
# OPENAI_BASE_URL: https://myprovider.com/v1
# OPENAI_API_KEY env var name: MY_PROVIDER_KEY
```

### OpenCode Profile

- 需要在 `env` 中配置 `OPENCODE_BASE_URL`、`OPENCODE_API_KEY` 和 `OPENCODE_MODEL`。
- Profile name（如 `oc-glm`）作为 `~/.config/opencode/opencode.json` 中的 provider key。
- `OPENCODE_MODEL` 支持三种格式：dict、list 或逗号分隔字符串。
- 模型作为第一个位置参数指定：`aweswitch oc-glm glm-5.1`。匹配不区分大小写，可按模型 ID 或显示名书写（如 `doubao-seed-evolving` 可匹配 `Doubao-Seed-Evolving`）。
- 不指定模型时，默认使用列表中的第一个。
- 额外参数透传给 `opencode` CLI。
- API key 以 `{env:VAR}` 格式写入 opencode.json — 实际 key 不落盘。

<details>
<summary>OpenCode profile 示例 JSON</summary>

```json
{
  "profiles": {
    "api": {
      "opencode": {
        "oc-glm": {
          "env": {
            "OPENCODE_BASE_URL": "https://open.bigmodel.cn/api/coding/paas/v4",
            "OPENCODE_API_KEY": "${GLM_ANTHROPIC_AUTH_TOKEN}",
            "OPENCODE_NAME": "Zhipu GLM",
            "OPENCODE_MODEL": {
              "glm-5.1": "GLM-5.1",
              "glm-5.2": "GLM-5.2"
            }
          }
        }
      }
    }
  }
}
```

</details>

`OPENCODE_MODEL` 格式（设置了 `OPENCODE_RESPONSES_MODEL` 时可省略——两者至少需要其一）：

| 格式 | 示例 | opencode.json 中的 model `name` |
|------|------|--------------------------------|
| Dict | `{"glm-5.1": "GLM-5.1"}` | 使用值（`GLM-5.1`） |
| List | `["glm-5.1", "glm-5.2"]` | 使用 key（`glm-5.1`） |
| String | `"glm-5.1,glm-5.2"` | 使用 key（`glm-5.1`） |

`OPENCODE_NAME`（可选）设置 opencode.json 中 provider 的显示名称。默认使用 profile name。

`OPENCODE_RESPONSES_MODEL`（可选）逗号分隔的字符串或模型 ID 列表，这些模型会带上单模型 Responses 覆盖（对应模型条目上写 `"provider": {"npm": "@ai-sdk/openai"}`），其余模型仍走 chat（`@ai-sdk/openai-compatible`）。它与 `OPENCODE_MODEL` 地位对等：省略 `OPENCODE_MODEL` 时，该列表就是 profile 的全部模型，且所有模型都走 Responses API。模型顺序（以及无参数启动时的默认模型）以 `OPENCODE_MODEL` 为准（在配置了它的情况下）；不在 `OPENCODE_MODEL` 中的 responses 模型会追加在后面。清空列表后，下次同步会移除过期的覆盖；不在此列表中的模型，手动设置的 vendor npm 不会被改动。

启动：

```bash
aweswitch oc-glm                      # 默认：第一个模型（glm-5.1）
aweswitch oc-glm glm-5.2              # 指定模型
aweswitch oc-glm glm-5.1 --mini       # 传递额外参数
```

首次启动时，aweswitch 将 provider 条目写入 `~/.config/opencode/opencode.json`。后续启动复用已有条目，仅在需要时添加新模型。

交互式添加 OpenCode profile：

```bash
aweswitch add
# Provider: opencode
# Profile name: oc-myprovider
# OPENCODE_BASE_URL: https://myprovider.com/v1
# OPENCODE_API_KEY env var name: MY_API_KEY
# OPENCODE_MODEL: model-1,model-2
```

## 赞助与支持

如果 aweswitch 帮到了你，欢迎支持一下：

- ⭐ 给项目点个 Star — 让更多人看到它。
- ☕ [Ko-fi](https://ko-fi.com/mugpeng) — 请我喝杯咖啡。
- 💬 微信 — 扫描下方收款码。

<p align="center">
  <img src="assets/images/wechat-pay.jpg" alt="微信收款码" width="240">
</p>

> aweswitch 是免费开源的，你的支持让它持续维护下去 — 谢谢。

## 开发

详见 [贡献指南](./docs/CONTRIBUTING.md)，包含环境搭建、测试、分支规范和发布流程。

- [贡献指南](./docs/CONTRIBUTING.md)
- [更新日志](./docs/CHANGELOG.md)

## Awesome 软件生态

aweswitch 是一个不断壮大的 "awesome" 工具家族中的一员 — 围绕 AI 编程 agent 打造，local-first、可被 agent 直接操作。

### CLI 工具

- **[aweskill](https://aweskill.wehuman.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent。
- **[aweswitch](https://github.com/wehuman01/aweswitch)** — Claude Code、Codex、OpenCode 的 agent 配置切换器。
- **[awerouter](https://github.com/wehuman01/awerouter)** — 智能路由器，用结构信号把请求分给 Flash 或 Pro 模型，减少不必要的模型开销。
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — 收藏、分类、恢复 AI 编程会话，还能搭配 aweswitch 实现保存配置，一键启动。
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM，或国产厂商 coding plan，或已授权的 OpenAI/Anthropic 帐号订阅，实现 token 的共享经济。
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保持器，让 AI 编程套餐的窗口持续激活，无论是本地设置，还是通过远程连接的服务器。
- **[awescholar](https://github.com/wehuman01/awescholar)** — AI agent 可自主执行的科学文献发现与策展，搜索、标注、筛选和报告学术论文。

### 桌面应用

- **[awedot](https://awedot.wehuman.top/)** — 悬浮球驻留屏幕边缘，实时追踪当前 AI 会话；一键收藏、随时恢复，并可搭配 aweswitch 固定 agent 配置（比如用 GLM 模型启动）。

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — AI 在生物学、生物信息学和生物医学研究中应用的精选综述。由 awescholar 驱动。
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — 面向虚拟肿瘤建模与仿真的前沿 AI 系统精选合集：静态模型、动态模型、agent、基准与综述。
