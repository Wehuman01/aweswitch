# aweswitch：OpenCode 也支持了，可以轻松@agent了

![aweswitch](../../../logo/hero.png)

aweswitch 已经从一个配置切换工具，进化为跨平台的智能体配置管理器。现在可以轻松配置opencode，对接了 OpenCode 原生的 `@` 智能体调用机制，并通过安全和可移植性修复打磨了整体体验。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## OpenCode 支持

v0.3.2 现在也支持opencode 啦，与 Claude Code 和 Codex 并列。aweswitch 现在可以用一个 CLI 管理三个agent 平台。

### 有点儿问题

OpenCode 使用自己的配置格式——`~/.config/opencode/opencode.json`——里面有提供者专属的字段：`npm` 包、`baseURL`、模型字典。手动设置需要编辑 JSON、把 API 密钥复制进明文，然后为每个端点重复一遍。想切换提供者？再改一遍文件。

如果你同时用 Claude Code、Codex 和 OpenCode，就得在三套互不相干的配置系统之间来回折腾。

### 解决它

`aweswitch add` 现在包含 `opencode` 作为提供者选项：

```bash
aweswitch add
# > Provider: claude | codex | opencode
```

选择 `opencode`。输入基础 URL、API 密钥环境变量名和模型。aweswitch 将这些存储在自己的配置文件 `~/.config/aweswitch/config.json` 中：

```json
"oc-xiaomi": {
  "env": {
    "OPENCODE_BASE_URL": "https://token-plan-sgp.xiaomimimo.com/v1",
    "OPENCODE_API_KEY": "${XIAOMI_ANTHROPIC_AUTH_TOKEN}",
    "OPENCODE_MODEL": {
      "mimo-v2.5-pro": "MiMo-v2.5-Pro",
      "mimo-v2.5": "MiMo-v2.5"
    }
  }
}
```

这些就是你要写的全部。首次启动时，aweswitch 会将其展开为 OpenCode 在 `~/.config/opencode/opencode.json` 中所需的完整提供者配置块：

```json
{
  "provider": {
    "oc-xiaomi": {
      "models": { "mimo-v2.5-pro": { "name": "MiMo-v2.5-Pro" } },
      "name": "oc-xiaomi",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "{env:XIAOMI_ANTHROPIC_AUTH_TOKEN}",
        "baseURL": "https://token-plan-sgp.xiaomimimo.com/v1"
      }
    }
  }
}
```

那些繁琐的部分——`npm` 包、`options` 嵌套、`models` 字典——都是自动生成的。你只需要管理扁平版本：基础 URL、环境变量引用和模型名称。

这里有两个关键点：

1. **`{env:VAR}` 让密钥远离文件。** 写入文件的实际内容是 `{env:XIAOMI_ANTHROPIC_AUTH_TOKEN}` 这个字面量。OpenCode 在运行时从环境中解析它。文件可以安全地提交、分享或 diff。
2. **`OPENCODE_MODEL` 携带显示标签。** 字典格式 `{"mimo-v2.5-pro": "MiMo-v2.5-Pro"}` 将内部模型 ID 映射为人类可读的名称。aweswitch 会把这些直接传递给 OpenCode 的 `models` 字典。

启动一个 OpenCode 会话：

```bash
aweswitch oc-glm glm-5.1
```

这会读取 `oc-glm` 配置，展开环境变量，并以 `glm-5.1` 作为活动模型启动 OpenCode。如果省略模型参数，则使用 `OPENCODE_MODEL` 中的第一个模型。

`OPENCODE_MODEL` 也接受简单字符串（`"glm-5.1"`）或列表（`["glm-5.1", "glm-4.6"]`），如果你不需要显示标签的话。上面展示的字典格式是最明确的写法。

### opencode 直接启动即可

**启动模式**使用特定配置启动新的 OpenCode 会话：

```bash
aweswitch oc-glm glm-5.1
```

- 每个会话拥有独立的环境
- 多个配置可以在不同终端中同时运行
- 适用于需要并行、隔离会话的场景



需要注意的是opencode 启动可以指定模型，如果不指定模型的话，默认用配置字段下设置的第一个model 启动。（虽然opencode 切换model 也很方便，下面会讲）



**应用模式**（仅限 Claude）将配置写入 `~/.claude/settings.json`：

```bash
aweswitch apply cc-glm
```

- 环境在会话间持久化
- 适用于某个模型主导你工作流的场景

| 提供者 | 启动模式 | 应用模式 |
|--------|---------|---------|
| Claude | 支持 | 支持 |
| Codex | 支持 | 不支持 |
| OpenCode | 支持 | 不支持 |

这里同样没有为OpenCode 设计，主要是考虑opencode 天然是一个文件可以写入多个provider 信息，直接自由切换：
![image-20260627125530749](images/image-20260627125530749.png)



## 通过 @ 调用子智能体

区别于claudecode 和codex 调用智能体的不便以及无法任意配置provider。作为开源工具的OpenCode 天然支持配置各家公司的模型。目录让你可以定义多个模型，并通过 `@` 调用它们——不用离开当前对话。

跑多个模型通常意味着多个终端、多个进程、多个上下文窗口。你通过切换窗口来切换模型。上下文带不过去。

因此，

每个智能体是 `~/.config/opencode/agents/` 目录下的一个 markdown 文件。文件名就是智能体名称。YAML frontmatter 定义配置。

创建三个智能体：

`~/.config/opencode/agents/glm.md`

```markdown
---
description: 通用助手
mode: subagent
model: oc-glm/glm-5.1
---
```

`~/.config/opencode/agents/step.md`

```markdown
---
description: 通用助手
mode: subagent
model: stepfun/step-3.7-flash
---
```

`~/.config/opencode/agents/xiaomi.md`

```markdown
---
description: 通用助手
mode: subagent
model: oc-xiaomi/mimo-v2.5-pro
---
```

三个字段。整个文件就这么多。

frontmatter 下面的任何文本都会成为智能体的系统提示词。不用改提供者配置，就能定制智能体的行为：

```markdown
---
description: 代码审查员
mode: subagent
model: oc-glm/glm-5.1
---

你是一位资深代码审查员。关注正确性、性能和安全性。
```

![image-20260627124930075](images/image-20260627124930075.png)

![image-20260627124935923](images/image-20260627124935923.png)

就像@ 你的好朋友一样@ 任意配置的agent 替你干你想干的任何事。



### @ 的工作原理

在 OpenCode 对话中，直接叫名字就能调用任意智能体：

```
@glm 创建一个用户资料更新的 REST 端点
@step 审查验证中间件的边界情况
@xiaomi 编写 API 文档，描述该端点的请求和响应格式
```

每次 `@` 调用都会路由到该智能体配置中定义的模型。不需要新终端。不需要切换配置。不会丢失上下文。主线程原地不动，子智能体在自己的模型上跑完把结果交回来。

### aweswitch 与 OpenCode：分工

aweswitch 管基础设施。OpenCode 管编排。

| 层级 | 工具 | 职责 |
|------|------|------|
| 提供者配置（`opencode.json`） | aweswitch | API 密钥、基础 URL、模型定义 |
| 智能体路由（`agents/*.md`） | OpenCode | 每个 `@` 智能体用哪个模型、系统提示词 |

分开管理，自然就能干净地组合。在 aweswitch 里改一个密钥，该提供者上的所有智能体都会生效。加一个新的智能体文件，它就能跟 aweswitch 已经配好的任何提供者一起工作。

### 一天的实践

早上。你用 aweswitch 设置好提供者，创建三个智能体文件。以 GLM 为默认模型启动：

```bash
aweswitch oc-offical sonnet-4.6
```

你开始写一个新的 API 路由。GLM 生成了处理器和验证中间件。

上午。你想对验证逻辑找个第二双眼睛：

```
@step 审查验证中间件的边界情况
```

Step 发现了一个遗漏：带 null 字段的部分更新没处理。你修好了，还在同一个对话线程里。

下午。你在写文档。想要一份简洁的中文摘要：

```
@xiaomi 编写 API 文档，描述该端点的请求和响应格式
```

MiMo 生成了文档。你粘贴到 README 里。

晚上。同事问某个函数是哪个模型写的。其实无所谓——每次 `@` 调用都记录在线程里。GLM 在哪结束、Step 从哪开始，一目了然。

## 其他更新

### v0.3.3 — 安全加固

`OPENCODE_API_KEY` 现在必须使用 `{env:VAR}` 语法。启动时会拒绝明文密钥，报错信息清清楚楚。这防止了手一抖把密钥写进 `opencode.json`。

`/tmp/aweswitch/` 里的临时设置文件现在每次启动都会垃圾回收。超过 24 小时的文件在创建新文件之前就会被清理掉。

`aweswitch apply` 现在会在无法创建设置备份时（比如磁盘满了）直接报错退出，而不是闷声继续。

## 为什么这很重要

aweswitch 最初只是一个智能体的配置切换器。加上 OpenCode 之后，它成了三个平台的切换器——Claude Code、Codex 和 OpenCode——全靠同一个 `aweswitch add` / `aweswitch <profile>` 接口搞定。

OpenCode 带来了另外两个平台没有的东西：在**一个对话里**跑多个模型的原生能力。智能体目录加上 `@` 调用，把单个会话变成了一个专家团队。一个写，一个审，一个总结——各自用最适合这项工作的模型。

aweswitch 和 Claude Code、Codex、 OpenCode 之间的分工还是没变。aweswitch 管连接——API 密钥、基础 URL、有哪些模型。这些agent 工具管编排——哪个智能体跑哪个模型，什么时候跑。`{env:VAR}` 边界是它们之间的契约：密钥待在环境里，配置待在文件里，敏感信息不碰磁盘。



## 更多来自 Webioinfo

aweswitch 是 [Webioinfo](https://www.webioinfo.top/) （域名现在从we.webioinfo.top 现在变成了www.webioinfo.top ）生态的一部分：

- **[aweskill](https://aweskill.wehuman.top/)** — 面向 47+ AI 编程智能体的 CLI 优先 Skill 包管理器
- **[aweshelf](https://github.com/wehuman01/aweshelf)** — 支持配置感知恢复的 AI 编程会话管理器
- **[awescholar](https://github.com/wehuman01/awescholar)** — 自动化科学文献发现
