# aweswitch更新：模型名不用背，协议也能换了

![aweswitch](../../../logo/hero.png)

我的模型列表里躺着一堆这种名字：`peng1/step-router-v1`、`gpt-5.2-codex`、`Doubao-Seed-Evolving`。启动时得原样复述一遍，少一个字符都不行——大小写错了、忘了带前缀，直接报错。

另一个烦恼更隐蔽：有些后端的模型只讲 OpenAI 的 Responses 协议，而 aweswitch 写进 `opencode.json` 的 provider 一直是 chat completions。想用？手动改文件，还得祈祷下次同步别被覆盖回去。

现在敲 `aweswitch cx-aihubmix GPT`，回车，命中的就是 `gpt-5.2-codex`。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 打个大概就行：模型名的三级跳

这个体验是分三步补齐的：

- **v0.4.2 短名**：model 配成映射时（`"peng1/step-router-v1": "step-router-v1"`），启动直接写显示值就行
- **v0.4.7 大小写免疫**：`GLM-5.1`、`Glm-5.1`、`glm-5.1` 随便拼
- **v0.4.8 子串匹配**：输入是 ID 或显示名的片段也能命中

匹配顺序有讲究：精确 ID → 精确显示名 → 忽略大小写全匹配 → 忽略大小写子串。窄的先试，越往后越宽，唯一命中直接赢。

```bash
aweswitch cx-aihubmix GPT        # -> gpt-5.2-codex
aweswitch cc-glm glm-5.2         # 该精确时就精确
```

歧义时不猜。比如列表里同时有 `glm-5.1` 和 `glm-5.2`，你只打个 `glm`——aweswitch 会拒绝启动，把命中的候选列出来让你选。宁可多打两个字，也不静默启动一个错的。

## v0.5.1：OpenCode 也能讲 Responses 了

同一个 OpenAI 生态其实有两种"方言"——主流的 Chat Completions（`/chat/completions`），和新一点的 Responses（`/responses`）。OpenCode 靠 npm 包决定讲哪种：`@ai-sdk/openai-compatible` 是 chat，`@ai-sdk/openai` 是 Responses。

aweswitch 以前写死的都是前者。v0.5.1 起加一个环境变量就能换：

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

设为 `true`，provider 的 npm 就换成 `@ai-sdk/openai`，整个 profile 走 Responses。这个字段和其他 aweswitch 管的字段一样：launch 和 `aweswitch apply` 都会同步——哪天删掉这行，下次同步就还原成 chat 包，不留垃圾。

手写的部分照旧不碰：如果你在 `opencode.json` 里手动换过别的 SDK（比如 `@ai-sdk/anthropic`），aweswitch 只在两个 openai 包之间改写，你的不会被动。

## 一个 provider，两种协议

更常见的情况是混着来：同一家里大部分模型讲 chat，个别只讲 Responses。总不能为此拆两个 profile。

`OPENCODE_RESPONSES_MODEL` 就是干这个的：

```json
"OPENCODE_RESPONSES_MODEL": "glm-5.2"
```

列表里的模型会带上单模型覆盖，写进 `opencode.json` 长这样：

```json
"models": {
  "glm-5.1": { "name": "GLM-5.1" },
  "glm-5.2": { "name": "GLM-5.2", "provider": { "npm": "@ai-sdk/openai" } }
}
```

provider 整体还是 chat 包，`glm-5.2` 单独走 Responses。哪天清空列表，下次同步会把过期的覆盖扫掉。列表里的 ID 必须真的在 `OPENCODE_MODEL` 里——写错了直接报错，不猜。

| 你说 | skill 跑 |
|---|---|
| "用短名启动这个模型。" | `aweswitch cx-aihubmix step-router-v1` |
| "就 GPT 那个，全名我忘了。" | `aweswitch cx-aihubmix GPT` |
| "oc-glm 整个换成 Responses。" | env 加 `"OPENCODE_RESPONSES": "true"`，再 `aweswitch apply oc-glm` |
| "只有 glm-5.2 走 Responses，其他照旧。" | env 加 `"OPENCODE_RESPONSES_MODEL": "glm-5.2"` |
| "改回 chat。" | 删掉那两行，重新 `aweswitch apply oc-glm` |

一句话总结：模型名随口打，协议按需换，手写的配置依然没人动。

## 顺便，这条线捋一遍

- **v0.4.6** 裸 `aweswitch apply` 不再偷偷写所有 opencode profile，批量要显式 `--opencode`（上一篇写过）
- **v0.5.0** codex 0.150 兼容修复：上游加的 provider `name` 校验让所有启动报错，现在启动路径补上了这个注入

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

# 大概打个模型名，也能启动
aweswitch cx-aihubmix GPT

# OpenCode 换 Responses：profile 的 env 里加一行
#   "OPENCODE_RESPONSES": "true"
# 然后同步
aweswitch apply oc-glm
```

模型名不用背了，协议也不用改配置文件了。



## aweswitch 系列文章

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)
- [aweswitch更新：谁说windows不能有同样丝滑体验](https://mp.weixin.qq.com/s/6PipJIV7aw95cUOtyg5Vmw)
- [aweswitch更新：官方账号也能多开了，不同账号直接切](https://mp.weixin.qq.com/s/HwBu2gjGNj8sc6lvAMnl8w)
- [aweswitch更新：apply 全端到齐，所有agent一把配](https://mp.weixin.qq.com/s/_N2qhrm62BPk181NOdAvjg)



## Awesome 生态系统

aweshare 是一个不断壮大的 "awesome" 工具家族的一部分 — CLI 优先、本地优先，可由 AI agent 操作。

### CLI 工具

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent。
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
