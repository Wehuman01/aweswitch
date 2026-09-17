# aweswitch更新：apply 全端到齐，三个 agent 的默认配置一把梭

![aweswitch](../../../logo/hero.png)

我的日常主力是一套 GLM 配置。但我手里有三个 agent：Claude Code、Codex、OpenCode，各管各的配置文件——`settings.json`、`config.toml`、`opencode.json`，三份家当三种格式。

以前 aweswitch 的答案是"启动模式"：`aweswitch cc-glm` 开一个隔离会话，环境变量只在那个会话里生效，终端之间互不串味。这很优雅，直到你某天手指不听使唤，直接敲了个 `codex`——欢迎回到三天前的旧 provider。

更早之前，apply 只能伺候 Claude 一家，Codex 和 OpenCode 的配置文件想改？自己动手吧。

我合上笔记本前跟我的 agent 说：

> "把我常用的 profile 直接写成三个 agent 的默认配置，别让我再手动改 toml 了。"

说完下楼取快递去了。等我爬回楼上，随手敲了个裸的 `codex`——打开就是我自己的模型和 endpoint。对味了。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## v0.4.5：apply 全端到齐

aweswitch 有两种玩法：

- **启动模式**（`aweswitch <profile>`）：开一个新会话，环境在启动瞬间冻结。不同终端可以同时跑不同 profile。
- **写入模式**（`aweswitch apply <profile>`）：把 profile 变成 agent 自己的持久默认值。

v0.4.5 之后，写入模式三家通吃：

```bash
aweswitch apply cc-glm    # Claude：env -> ~/.claude/settings.json
aweswitch apply cx-glm    # Codex：provider+model -> ~/.codex/config.toml
aweswitch apply oc-glm    # OpenCode：provider+models -> ~/.config/opencode/opencode.json
```

还能混着来，一条命令各写一家：

```bash
aweswitch apply cc-glm cx-glm oc-glm
```

规则很简单：Claude 和 Codex 一次最多一个（它们各自只有一个"当前默认"的概念），OpenCode 随便批量。

## Codex 那份 toml 只动必要的

`config.toml` 是开发者手写痕迹最重的文件，整文件重写等于灾难。所以 Codex 的 apply 是外科手术式的：只动该动的段落，注释和排版原样保留。写之前自动留一份 `.toml.bak`，API key 从你 shell 里已有的 `${VAR}` 引用解析，不会把明文 key 糊进去。

## OpenCode 支持批量，还带大扫除

OpenCode 的配置是"多个 provider 共存"的结构，所以批量才有意义：

```bash
aweswitch apply --opencode                # 所有 opencode profile 一次写完
aweswitch apply --opencode --prune-orphans
```

顺带一提：apply 是三个 agent 共用的入口，所以"全部 opencode"做成了显式的 `--opencode` 参数，裸的 `aweswitch apply` 会提示你补上 profile 名或这个参数，不会偷偷只动一家。

第二条值得单独说：profile 改名或者删掉之后，`opencode.json` 里会留下没人认领的孤儿 provider。现在 apply 时会提醒你有孤儿，`--prune-orphans` 负责安全清走。

另外，恢复会话时也有提醒：`aweswitch oc-glm -s <session-id>` 恢复旧会话，OpenCode 会还原会话上次用的模型并把 `-m` 无视掉。两边对不上时 aweswitch 会告诉你，进了 TUI 记得按 Tab 切回去。

## 手滑了？一键回滚

所有写入动作都有退路：

- Codex 写入前自动留 `.toml.bak`
- Claude 的 `settings.json` 备份不会被悄悄覆盖，除非加 `--force`
- v0.4.1 起，`aweswitch config backup` 随时手动备份并打印路径，`aweswitch config restore [FILE]` 从默认备份或任意快照恢复

| 你说 | skill 跑 |
|---|---|
| "把我的 GLM 配置设为三个 agent 的默认。" | `aweswitch apply cc-glm cx-glm oc-glm` |
| "opencode 的全部写进去。" | `aweswitch apply --opencode` |
| "opencode.json 里那些没主的 provider 清一下。" | `aweswitch apply --opencode --prune-orphans` |
| "改之前先备份一下 settings.json。" | `aweswitch config backup` |
| "改坏了，退回去。" | `aweswitch config restore` |
| "用短名启动这个模型。" | `aweswitch cx-aihubmix step-router-v1` |

一句话总结：以前只有"从 aweswitch 启动才生效"，现在 profile 可以直接成为 agent 的出厂设置。

## 顺便，0.4.x 这条线捋一遍

- **v0.4.0** 官方账号一等公民：Claude Code / Codex 的 OAuth 登录可以多开并存，私有目录隔离（上一篇账号专文讲的就是它）
- **v0.4.1** 备份体系归位：新增 `aweswitch config backup`，`restore` 挪到 `config restore [FILE]`，还能指定任意快照文件恢复
- **v0.4.2** 启动参数认短名：model 配成映射时，启动可以直接写显示值（`step-router-v1` 代替 `peng1/step-router-v1`），重名会被拒绝并列出候选

细节都在 [CHANGELOG](https://github.com/wehuman01/aweswitch/blob/main/docs/CHANGELOG.md) 里。

## 试一下

### 让 agent 来装

如果你在 Claude Code、Codex 或其他编程 agent 里，跟它说：

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

### 或者自己动手

```bash
pip install aweswitch

# 把常用 profile 写成持久默认值
aweswitch apply cc-glm cx-glm oc-glm

# 或者只收拾 opencode，顺手扫掉孤儿
aweswitch apply --opencode --prune-orphans

# 该启动还是启动
aweswitch cc-glm
```

不用再背哪份配置在哪个文件里。一个 profile，三个 agent，说默认就默认。



## aweswitch 系列文章

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)
- [aweswitch更新：谁说windows不能有同样丝滑体验](https://mp.weixin.qq.com/s/6PipJIV7aw95cUOtyg5Vmw)
- [aweswitch更新：官方账号也能多开了，不同账号直接切](https://mp.weixin.qq.com/s/HwBu2gjGNj8sc6lvAMnl8w)



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
