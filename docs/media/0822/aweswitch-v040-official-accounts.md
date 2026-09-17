# aweswitch更新：官方账号也能多开了，工作号个人号一起跑

![aweswitch](../../../logo/hero.png)

我有两个 Claude Code 账号：一个公司发的，一个自己的。以前想同时开着它们是不可能的——`~/.claude` 只有一份，切账号意味着退出登录、重新 `/login`、浏览器跳转、等授权，然后祈祷这次登的是对的那一个号。Codex 也一样。

更别提"两个终端，两个账号，并排跑"了。以前那叫异想天开。

我合上笔记本前跟我的 agent 说：

> "把我的官方账号都收进 aweswitch。我要能一条命令启动任何一个账号，而且能同时跑。"

说完就下楼取快递去了，顺手把门口的垃圾也捎了下去。等我拎着箱子爬回楼上，`aweswitch list` 里已经多了几行 kind 列标着 `account` 的条目。公司号和个人号都在里面，谁也不挤占谁的登录态。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## v0.4.0：官方账号是一等公民

aweswitch 从第一天起就在解决一个问题：多个 API 来源之间丝滑切换。但官方 OAuth 登录的账号一直是三不管地带——cc-switch 不管它，环境变量方案碰不到它，你只能手动登进登出。

v0.4.0 把官方账号拉进来，和 API profile 平起平坐。配置里从此分成两类：`api`（环境变量型 profile）和 `account`（官方 OAuth 登录），名字统一管理，`aweswitch list` 一列打尽，kind 列标得清清楚楚。

```text
NAME         PROVIDER   KIND      DETAIL
cco-work     claude     account   official login
cxo-team     codex      account   official login
cc-glm       claude     api       glm-5.1
cx-aihubmix  codex      api       gpt-5.2-codex, kimi-k2.7
```

## 三条命令的事

**把已登录的账号收进来**（前提是当前 CLI 已经登录过）：

```bash
aweswitch account add codex cxo-work
```

**或者让 aweswitch 带你走一遍登录流程**——它会在账号自己的私有目录里跑官方的 `codex login`（claude 则是启动后你在里面执行 `/login`），凭证落袋即走：

```bash
aweswitch account login claude cco-personal
```

macOS 用户注意：Claude Code 在 mac 上把凭证放钥匙串，`account add` 读不到，所以 claude 账号请走 `account login` 这条路。

**然后像启动任何 profile 一样启动它**：

```bash
aweswitch cxo-work        # 终端 1：公司的 Codex 号
aweswitch cco-personal    # 终端 2：个人的 Claude 号，同时在跑
```

两个终端，两个账号，互不打扰。你的全局 `~/.codex` 和 `~/.claude` 一个字节都没被动过。

## 隔离是怎么做到的

每个账号有自己的私有配置目录。codex 账号通过 `CODEX_HOME` 启动，claude 账号通过 `CLAUDE_CONFIG_DIR`（外加禁用钥匙串的环境变量）启动。OAuth token 过期后，CLI 在各自的私有目录里自行刷新——aweswitch 不读这些凭证，只把它们当作不透明的块原样保存。

安全这块也没含糊：

- 凭证在配置里整体脱敏，`aweswitch show` 和 `config show` 里只能看到 `<redacted>`
- 存入第一个账号时，配置文件自动收紧为 `600` 权限
- 私有目录里的 token 永远是最新的；`aweswitch account sync` 负责把刷新后的 token 抄回配置，而旧快照绝不会反过来覆盖新鲜的凭证

老用户也不用迁移：第一次加载旧配置时自动升级到新结构，升级前先写一份 `.json.bak` 备份。

| 你说 | skill 跑 |
|---|---|
| "把我的工作号收进 aweswitch。" | `aweswitch account add codex cxo-work` |
| "再加个个人 Claude 账号。" | `aweswitch account login claude cco-personal` |
| "用工作号开一个会话。" | `aweswitch cxo-work` |
| "两个账号并排跑。" | 两个终端分别 `aweswitch cxo-work` 和 `aweswitch cco-personal` |
| "token 该刷新了吧？" | `aweswitch account sync codex cxo-work` |
| "这个号不用了。" | `aweswitch account remove codex cxo-work --purge` |

一句话总结：API profile 怎么玩，官方账号现在就怎么玩。

## 顺便，把欠的账还了

v0.3.7 到 v0.3.9 的更新也随这个版本一起到货，一句话带过：Codex profile 现在支持启动时直接选第三方模型（`aweswitch cx-aihubmix kimi-k2.7`）、OpenCode 凭据变更自动同步不再报错、明文 API key 从硬性拒绝放宽为提示、外加一轮针对损坏配置和后台进程的稳定性加固。

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

# 收编你正在用的官方账号
aweswitch account login codex cxo-work
aweswitch account login claude cco-personal

# 并排起飞
aweswitch cxo-work &
aweswitch cco-personal
```

不用再登出登出登出。不用再数这是第几个浏览器授权跳转。工作号和个人号，一人一个终端，各回各家。



## aweswitch 系列文章

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)
- [aweswitch更新：谁说windows不能有同样丝滑体验](https://mp.weixin.qq.com/s/6PipJIV7aw95cUOtyg5Vmw)



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
