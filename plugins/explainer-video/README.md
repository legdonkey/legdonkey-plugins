# explainer-video

> 一个跨 **Claude Code**、**Codex** 与 **Pi** 的插件（基于开放标准 [skill](https://agentskills.io)）：把一个话题做成带旁白、字幕、BGM、音效和高级动效的中文讲解视频（MP4）。
>
> ← 返回[仓库总览](../../README.md) ｜ 依赖：[bailian-tts](../bailian-tts/)

旁白是全片时钟：先配音、拿到精确时间轴，再让画面去对声音，而不是反过来。

## 流程

1. 确认画幅、时长、音色、BGM 来源和是否商用。
2. 调研事实，写解说词（屏幕文字与朗读文字分开）。
3. 用 bailian-tts 批量配音，Whisper 转写核对读音，生成时间轴和字幕。
4. 搭 HyperFrames 工程地基（根合成、背景舞台、章节 HUD、字幕层、占位场景）。
5. 主会话写分镜 `STORYBOARD.md`。
6. 子代理按章节并行搭场景；主会话同时在后台用本地 MusicGen 生成 BGM。
7. 渲染、抽帧质检；闪避混音，响度标准化到 −16 LUFS / 真峰值 ≤ −1.5 dBTP。

## 前提

- **先安装 [bailian-tts](../bailian-tts/) 插件**，并配好百炼 API Key。本技能按技能名调用它，CC、Codex、Pi 中任一宿主装了即可。
- Node.js（`npx hyperframes@0.8.198`）、Python 3、ffmpeg。
- 用 MusicGen 时需下载模型到 `~/.venvs/musicgen` 与 `~/.cache/huggingface`（走 hf-mirror.com 与阿里云 PyPI 镜像）。

## 许可提醒

MusicGen 生成的 BGM 是 CC-BY-NC，**不能商用**；商用时改用自己的音乐。音效来自 Pixabay（可商用），字体是 Noto Sans SC（OFL）。

## 安装

插件名 `explainer-video@legdonkey`，安装方式见[根 README 的安装区](../../README.md#安装)。Pi 装整个仓库即可；装了子代理和提问扩展（如 `pi-subagents`、`rpiv-ask-user-question`）体验最好，没装时技能会退化为主会话顺序搭场景、普通消息提问。

触发：直接说「做个视频讲解」，模型会自动调用；也可以点名，Claude Code `/explainer-video:explainer-video`，Codex `$explainer-video`，Pi `/skill:explainer-video`。
