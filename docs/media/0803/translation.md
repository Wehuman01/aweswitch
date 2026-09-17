# aweswitch：谁说windows不能有同样丝滑体验

![aweswitch](../../../logo/hero.png)

我还是用上 Windows 了。打开 `cmd.exe`，输入 `aweswitch cc-glm`。我打开 PowerShell。输入同样的命令。回来的东西一样丝滑。我合上笔记本，去倒了杯咖啡，然后跟我的 agent 说：

> "我的 `GLM_ANTHROPIC_AUTH_TOKEN` 在 Windows 上没被识别。查清楚为什么，修掉它。"

等我回来时，token 已经进了用户环境变量，profile 从 `cmd.exe` 和 PowerShell 里都能顺利启动，agent 还给了我一段话的修改总结。那套在 macOS 上跑了几个月的配置，现在在 Windows 上也能跑了。同一条命令，同样的结果，两个 shell 都是。

GitHub：[github.com/wehuman01/aweswitch](https://github.com/wehuman01/aweswitch)

## 两个 Bug修了

Windows 支持从 v0.2.0 起就"发布"了。Python 代码能跑。CLI 能用。真正用不了的是设置这步——而那恰恰是用户最先撞上的部分。

**Bug 1：文档只照顾了 PowerShell。** `aweswitch` 告诉 Windows 用户把 token 放进 `$PROFILE`，可那只有 PowerShell 会读。用 `cmd.exe` 的用户——而 Windows 用户里有不少就是用 cmd 的——会设好 token、重启终端、运行 `aweswitch <profile>`，然后眼睁睁看着同一个 `command not found: claude` 又冒出来。同一台机器、同一个 token、同一分钟，开哪个窗口，就是两种结果。

**Bug 2：`.ps1` 垫片对启动器不可见。** 就算文档修好了，还是有一部分 Windows 用户撞上 `command not found`。他们的 `claude` 是作为一个 `.ps1` 脚本装的——这正是 Windows 上的 npm 安装 Node CLI 的默认方式——而 `aweswitch` 的启动路径根本找不到它。用户看到的现象一模一样：一个在 macOS 上跑得好好的 profile，到 Windows 上启动不了。原因却完全不同：一段代码不知道该怎么让 Windows 去跑一个 PowerShell 脚本。

v0.3.5 把这两个都修了。

## 改了什么

### 用 `setx` 取代 `$PROFILE`

`setx` 写入的是用户环境变量存储区——也就是 System Properties 那个 GUI 在编辑的同一个地方。`cmd.exe` 和 PowerShell 在下次启动时都会读它。`$PROFILE` 仍然支持，但只作为一种 PowerShell 专属的替代方案。

Windows 上的新配置方式：

```bat
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
```

之后开一个新终端（`setx` 对当前这个窗口不生效），然后 `aweswitch cc-glm` 就能像在 macOS 上一样跑了。你开口让 agent 做就行：它会替你跑 `setx`、回查那个值、然后叫你开个新终端。

skill 里的平台表现在长这样：

| 平台 | 目标 | 作用范围 |
|---|---|---|
| zsh（macOS 默认） | `~/.zshrc` | 所有 zsh shell |
| bash | `~/.bashrc` 或 `~/.bash_profile` | 所有 bash shell |
| Windows | `setx` | **cmd 和 PowerShell 都生效** |
| Windows（仅 PowerShell） | `$PROFILE` | 仅 PowerShell |

### `.ps1` 的 agent 可执行文件现在能启动了

如果你的 `claude` 或 `codex` 是作为 `.ps1` 垫片（**npm 在 Windows 上安装命令行工具时生成的包装脚本**）装的，`aweswitch <profile>` 现在能找到它并启动。启动器做的是显而易见的事：当可执行文件解析出来是个 `.ps1` 时，它就走 `powershell.exe -File` 并加上 `-ExecutionPolicy Bypass`，让脚本不弹提示就能跑。`.exe`、`.cmd`、`.bat` 还是照常工作。

这些你全都看不到。你只会看到 `aweswitch cc-glm` 第一次在一台 Windows 机器上、从 `cmd.exe` 里把 Claude Code 跑起来，然后正常工作。

## Windows 上的一天

今天是周三。你在一台 Windows 机器上，一个窗口开着 `cmd.exe`，另一个开着 PowerShell。

**上午 9:00。** 第一次安装：

```cmd
pip install aweswitch
aweswitch -v
```

你试 `aweswitch cc-glm` 测一下自带的 profile。`command not found: claude`。你把报错贴给 agent。它替你跑 `setx`，叫你开个新终端，然后干别的去了。你照做。`aweswitch cc-glm` 现在能走 GLM 代理把 Claude Code 跑起来。同一条命令在另一个窗口的 PowerShell 里也管用。

**上午 10:30。** 你想要给 Mimo 再加一个 profile：

> "加一个 Mimo profile。我的环境里已经有 `XIAOMI_ANTHROPIC_AUTH_TOKEN` 了。"

agent 跑 `aweswitch add`，选 `claude` 作为 provider，给 profile 取名 `cc-mimo`，把它接到小米的 base URL 和 `${XIAOMI_ANTHROPIC_AUTH_TOKEN}` 上。它没跑 `setx`，因为你说 token 已经在环境里了。不过它先查了一下，确认无误。

```bash
aweswitch cc-mimo
```

第二个终端，第二个会话，换个模型。第一个会话还跑在 GLM 上。

**下午 1:00。** 你要在一次代码评审里对比 GLM 和 Mimo。两个并行会话：

```bash
aweswitch cc-glm -c review -t "PR #247 review"      # 终端 1（cmd.exe）
aweswitch cc-mimo -c review -t "PR #247 review"     # 终端 2（PowerShell）
```

两个都存成了书签。cmd.exe 那个找到的是 `claude.cmd` 并跑起来。PowerShell 那个找到的是 `claude.ps1`，通过 `powershell.exe -File` 跑起来。哪个都没失败。你用 `aweshelf browse` 在两者之间切来切去对比输出。

**下午 3:00。** 你发现 codex profile 里有个笔误：

> "把 `cx-aihubmix` 里的 base URL 改成 `https://aihubmix.com/v1`。"

agent 读配置、改、跑 `aweswitch show cx-aihubmix` 验证，然后回报。不用重启。

**下午 5:00。** 收工。三个 profile，两个并行会话，一次配置改动，两个书签。你从没打开过 `$PROFILE`。你从没把 token 粘进过哪个 JSON 文件。Windows 的配置和 macOS 的配置一模一样：装、设环境变量、启动。

## Agent 在 Windows 上现在够得到什么

v0.3.5 给 skill 加了两项新能力：

| 你说 | skill 跑 |
|---|---|
| "给 Windows 设好 `OPENAI_API_KEY`。" | `setx OPENAI_API_KEY "..."` |
| "切到 cc-mimo。" | `aweswitch cc-mimo` —— 自动找到并运行 `.ps1`、`.cmd` 或 `.exe` |
| "读一下我现在的 Windows 环境变量。" | `[Environment]::GetEnvironmentVariable("VAR", "User")` |
| "删掉 `OLD_TOKEN`。" | `setx OLD_TOKEN ""` |
| "列出我的 aweswitch profile。" | `aweswitch list` |
| "给我看看 cc-glm。" | `aweswitch show cc-glm` |
| "加一个 AiHubMix 的 codex profile。" | 编辑 `~/.config/aweswitch/config.json` |

在 v0.3.5 之前，agent 的工具腰带上有个 Windows 形状的洞：它能改配置（v0.2.0 起跨平台）、能启动 profile（v0.2.0 起跨平台）、能应用它们（v0.3.0 起跨平台），但它没有一种安全的办法去*设置 profile 引用的那些环境变量*——非要对系统里一半的 shell 撒谎不可。`setx` / `[Environment]::SetEnvironmentVariable` 这一对把那个缺口补上了。

## 一致的体验

对 Windows 用户来说，现在的流程和 macOS 完全一样。装。设 token。启动。shell 从 zsh 换成了 `cmd.exe`，设环境变量的命令从 `export` 换成了 `setx`，别的什么都不变。`aweswitch cc-glm` 干的事和别处一模一样。`aweswitch apply cc-glm`、`aweswitch list`、`aweswitch add`、`aweswitch show`、`aweswitch restore` 也都一样。同一个配置文件，同样的命令名，同样的行为。

这种一致也延伸到了 `/aweswitch` skill。Windows 用户现在能用到 macOS 和 Linux 用户自 v0.1.9 起就有的那个自然语言界面。skill 读的是同一个 `README.ai.md`，走的是同一个 `aweswitch add` 流程，编辑的是同一个 `~/.config/aweswitch/config.json`，只是在检测到 Windows 时改用 `setx` 而非 `~/.zshrc`。agent 不需要一个单独的"Windows 模式"——它为这个平台挑出对的命令，然后跑。

> "加一个 AiHubMix 的 codex profile。我的用户环境变量里有 `AIHUBMIX_OPENAI_KEY`。"

这条提示在一台 Windows 笔记本上和在 Mac 上跑起来一个样。agent 跑 `aweswitch add`，选 provider，给 profile 命名，接到 token 上，用 `aweswitch show` 验证。你这边不用念什么 shell 专属的咒语。配置就是一项任务。agent 就是干任务的。所以我把这活儿交给了 agent。

## 在 Windows 上试试

### 让 agent 来装

如果你在 Claude Code、Codex、Cursor 或其他编程 agent 里，跟它说：

```text
Read https://github.com/wehuman01/aweswitch/blob/main/README.ai.md and follow it to install and configure aweswitch.
```

agent 会装好 CLI，替你跑 `setx GLM_ANTHROPIC_AUTH_TOKEN "..."`，回查那个值，然后叫你开个新终端。之后 `aweswitch cc-glm` 就能像在 macOS 上一样跑了。

### 或者自己动手

```cmd
pip install aweswitch
setx GLM_ANTHROPIC_AUTH_TOKEN "sk-..."
aweswitch -v
aweswitch cc-glm
```

`setx` 之后开一个新终端。`.ps1`、`.cmd`、`.exe` 垫片都能跑。

这就是现在 Windows 上的全部丝滑体验。同一个配置，同一条命令，同一个 `/aweswitch` skill，同一个 agent 替你管着一切。

## aweswitch 系列文章

- [aweswitch: 让多provider操作agent像点菜一样简单](https://mp.weixin.qq.com/s/oi-c9goNBS5ps1cfO_iQwA)
- [aweswitch更新：启动即记录，升级不操心](https://mp.weixin.qq.com/s/o3tEmFJuW7k3GFN0SqbuWg)
- [aweswitch更新：支持opencode了，可以轻松@agent了](https://mp.weixin.qq.com/s/2uir5z84-fecKy_xL4S3jg)
- [aweswitch：用ai 来管理ai是种怎么样的体验？](https://mp.weixin.qq.com/s/CjqS1fdQ9Df1uOfiVy8VZg)



## Webioinfo 的更多内容

aweswitch 是 [Webioinfo](https://www.webioinfo.top/) 生态的一部分：

- **[aweskill](https://aweskill.wehuman.top/)** —— 为 47+ AI 编程 agent 打造的 CLI 优先 Skill 包管理器
- **[aweshelf](https://github.com/wehuman01/aweshelf)** —— AI 编程会话管理器，支持按 profile 恢复
- **[awescholar](https://github.com/wehuman01/awescholar)** —— 自动化的科研文献发现
