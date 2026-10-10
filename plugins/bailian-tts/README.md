<p align="center">
  <img src="assets/banner.svg" alt="bailian-tts — 阿里百炼 Qwen-Audio 配音" width="100%">
</p>

# bailian-tts

> 一个跨 **Claude Code**、**Codex** 与 **Pi** 的插件（基于开放标准 [skill](https://agentskills.io)）：用阿里百炼 `qwen-audio-3.1-tts-flash` 把文案合成自然语音。
>
> ← 返回[仓库总览](../../README.md) ｜ 姊妹插件：[privatize-fork](../privatize-fork/) / [context-doctor](../context-doctor/)

同一份技能可安装到 Claude Code、Codex 与 Pi。它固定使用百炼当前一代的 `qwen-audio-3.1-tts-flash`：68 个系统音色都接受任意自然语言指令，文案里可以直接嵌入情感与拟声标签，还能用自己的录音复刻音色。

## 解决什么问题

做视频、PPT、课件、演示或产品旁白时，常见问题不是“能不能合成语音”，而是每次都要重新写 SDK 调用、查音色、记模型和音色的绑定关系、处理 `411` 报错，再拿音频时长去对时间轴、手打字幕。

`bailian-tts` 把这些固定动作收进一个技能：

| 能力 | 说明 |
|------|------|
| **音色清单** | 内置 68 个系统音色数据（多语种与方言 / 精品中文 / 精品英文 / 其他），可按性别、场景筛选。 |
| **自然语言指令** | `--instruct "沉稳的中年女声，语速偏慢"` 原样传给模型，不需要固定句式；也可用 `--emotion` 快捷指定情感。 |
| **文本内标签** | 在文案里写 `[excited]`、`[serious]` 切换情绪，写 `[laughing]`、`[sighing]` 插入拟声。 |
| **方言与多语种** | 4 个音色支持上海话、广东话、东北话、重庆话等 8 种方言和 8 种外语，用指令切换。 |
| **先试听再生成** | `preview` 合成一句并播放；`gen` 生成正式 `wav`，统一规范化为 24kHz 单声道并打印时长。 |
| **脚本批量配音** | `script` 按脚本逐段生成，每段可切换音色和指令，输出分段 `wav`、拼接好的 `all.wav`、`subtitles.srt` 和 `manifest.json`，可直接拖进剪辑工具。 |
| **配音工作台** | `ui` 在浏览器打开一个本地页面，顶栏三栏：**开始**介绍插件能做什么、检查运行环境，并引导创建 API Key（助手在默认浏览器打开百炼控制台的创建页、交给你操作，你复制后它读剪贴板、校验并保存，key 不出现在对话里）；**选音色**左侧清单列出 68 个系统音色和本模型可用的复刻音色，右侧试听台用同一句话逐个现场合成，清单上记下每个音色这条的时长，满意的收藏、设为默认，复刻音色也能在这里删除；**声音复刻**是「录音 → 质检 → 试听 → 完成」四步向导，开录后整屏只留念稿、大号计时和电平表，录完先给结论再逐项列出时长、音量、破音和波形。第一次使用时总是先落在「开始」。服务只监听 `127.0.0.1` 并校验一次性 token，页面不引用任何外部资源。 |
| **选中即朗读** | `say`（仅 macOS）：在任意 App 里选中文字，按一下鼠标按键或快捷键就用收藏的默认音色读出来。自动去掉代码块和 Markdown 符号，最多 1500 字；按句分段，播放当前段时合成下一段，长文也能连续念完；再按一次立即停止。`say --install` 生成 `~/.local/bin/bailian-say` 入口，并打印 OpenLogi 鼠标按键和「快捷指令」快捷键的配置。 |
| **声音复刻** | `clone` 直接接收本地录音（m4a/mp3/wav 等），自动转码、检查时长、上传百炼临时存储并完成复刻，无需自备 OSS；`voices --mine` 查询、`delete` 删除。 |
| **收藏音色** | `fav add` 收藏常用音色，`voices` 中标 ★；未指定音色时默认用收藏的第 1 个，收藏存在本机 `~/.config/bailian-tts/favorites.txt`，重装插件不丢。 |
| **提前拦截错配** | 音色不属于本模型（其它模型的系统音色、为其它模型创建的复刻音色）时直接提示，不让服务端只回一个 `411`。 |

## 安装

插件名 `bailian-tts@legdonkey`。完整安装方式（含桌面端图形界面、一键脚本 `install-plugins.sh`）见[根 README 的安装区](../../README.md#安装)。命令行速记：

```bash
# Claude Code
/plugin marketplace add legdonkey/legdonkey-plugins
/plugin install bailian-tts@legdonkey

# Codex
codex plugin marketplace add legdonkey/legdonkey-plugins --ref main
codex plugin add bailian-tts@legdonkey

# Pi（整个仓库作为 Pi 包安装，只暴露 bailian-tts 这一个技能）
pi install git:github.com/legdonkey/legdonkey-plugins
```

装完重启对应客户端（Pi 会话内可用 `/reload`）。触发名：**Claude Code** 用 `/bailian-tts`（插件命名空间下 `/bailian-tts:bailian-tts`）；**Codex** 用 `$bailian-tts`；**Pi** 用 `/skill:bailian-tts`。**不会自动调用**——CC 与 Pi 都读 frontmatter 的 `disable-model-invocation: true`，Codex 靠 `agents/openai.yaml` 的 `allow_implicit_invocation: false`，只能由你手动点名。Pi 下用 `pi update` 跟进新版本。

## 运行环境

这个插件会调用阿里百炼 DashScope API（北京地域），并在本机生成音频文件。使用前需要：

```bash
python3 -m venv ~/.bailian-tts-venv
~/.bailian-tts-venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ dashscope
```

上面用的是阿里云 PyPI 镜像；如需校验版本，可对照官方源 `https://pypi.org/project/dashscope/`。

API key 读取顺序是环境变量 `DASHSCOPE_API_KEY`，然后是 `~/.dashscope_key`。第一次使用时技能会自动打开工作台的「开始」页带你创建：在百炼控制台（华北2 北京）创建并复制 key 后，由 `tts.py key --clipboard` 或页面按钮读取剪贴板、向百炼校验，再写入 `~/.dashscope_key`（权限 600）并清空剪贴板。不要把 key 写进项目文件或对话内容。

还需要本机有 `ffmpeg`；macOS 试听播放用系统自带的 `afplay`。

## 用法

手动触发后，告诉模型你要合成的文案、想要的语气和用途。典型流程是：

0. 第一次用时会先打开配音工作台的「开始」页，按页面和助手的引导创建并保存 API Key；
1. 说一句「帮我选个音色」，会打开工作台的「选音色」，在浏览器里用同一句话逐个试听，满意的收藏或设为默认（之后不指定音色就默认用收藏的第 1 个）；也可以用 `voices --gender 女 --scene 新闻播报` 之类的条件在命令行缩小范围、`fav add` 收藏；
2. 用 `preview` 试听 1 到 2 个候选，确定音色和指令；
3. 单段用 `gen`；多段旁白写成脚本交给 `script`，拿到 `all.wav` 和 `subtitles.srt`；
4. 想在任意 App 里选中文字就读出来：说一句「帮我配置选中朗读」，会运行 `say --install` 并按你的鼠标按键或快捷键给出配置；
5. 想用自己的声音：说一句「复刻我的声音」，会打开工作台的「声音复刻」，在浏览器里录音、试听、收藏一次走完；已有录音文件也可以直接交给 `clone`。

脚本格式示例（每行一段，`@voice` / `@instruct` 切换之后各段的设置）：

```text
@voice xuyuyuan_v3.1
@instruct 沉稳知性的女声，语速适中
各位好，欢迎来到今天的发布会。
@voice yuxiaoyun_v3.1
@instruct 年轻活泼的女声，语速偏快
[excited]它真的太好用了！[laughing]
```

底层脚本是 `skills/bailian-tts/scripts/tts.py`，会从自身相邻的 `references/voices.json` 读取音色数据，不依赖固定安装路径。

## 模型支持边界

只支持 `qwen-audio-3.1-tts-flash`。音色与模型强绑定：系统音色以 `_v3.1` 结尾，复刻音色 ID 以 `qwen-audio-3.1-tts-flash-` 开头。

不在范围内：

- `qwen-audio-3.1-tts-next`（多人对话、配乐、音效一体生成）——能力与调用方式不同，需单独设计；
- 声音设计（按文字描述生成音色）——官方目前只对 `qwen-audio-3.0-tts-*` 开放；
- 百炼上的其它语音合成模型。

## 插件结构

```text
plugins/bailian-tts/
├── .claude-plugin/plugin.json      # CC 插件清单
├── .codex-plugin/plugin.json       # Codex 插件清单（skills 指向 ./skills/）
├── assets/                         # README 配图（src/ 为可编辑源，由根 assets/build-svg.sh 生成）
└── skills/bailian-tts/
    ├── SKILL.md                    # 入口（禁自动调用，只手动点名才跑）
    ├── agents/openai.yaml          # Codex 专属元数据
    ├── scripts/tts.py              # 合成、试听、脚本批量配音、选中朗读、声音复刻、本机页面服务
    ├── assets/studio.html          # 配音工作台页面：开始 / 选音色 / 声音复刻（由 ui 在本机提供）
    └── references/
        ├── voices.md               # 指令、文本标签、复刻与排错说明
        └── voices.json             # qwen-audio-3.1-tts-flash 音色清单
```
