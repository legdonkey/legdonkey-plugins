---
name: explainer-video
description: 制作带旁白、字幕、BGM、音效和高级动效的中文讲解视频（MP4）。流程是：百炼 TTS 配音 → Whisper 对时 → 写分镜 → 多个子代理并行用 HyperFrames（HTML+GSAP，逐帧确定性渲染）搭场景 → 本地 MusicGen 生成 BGM → 闪避混音并做响度标准化 → 渲染与质检。用户说"做个视频讲解""做成讲解视频""出一条解说片""用动画讲清楚""motion 动画、丝滑转场""横版 16:9 / 竖版视频"，或者想把一个回答、一篇文章、一组对比做成带配音的视频时，都使用本技能，即使没提 HyperFrames 也一样。不用于剪辑已有素材、录屏或直播。
---

# 中文讲解视频

把一个话题做成 1080p、30fps 的讲解片。旁白是全片时钟：先配音、拿到精确时间轴，再让画面去对声音，而不是反过来。

技能目录记为 `$K`（本文件所在目录），项目根目录记为 `P`（默认 `~/Movies/<主题短名>/`）。

## 产物与目录

```
P/
  narration/segments.json  spoken.txt  timeline.json
  dub/                     bailian-tts 逐段输出
  asr/                     Whisper 转写与读音核对表
  audio/narration.wav  bgm_plan.json  bgm.wav  musicgen_work/
  video/                   HyperFrames 工程（design.json、STORYBOARD.md、compositions/、sfx-cues/、assets/）
  <标题>.mp4               成片
```

## 环境约束

- HyperFrames CLI 固定用 `npx --yes hyperframes@0.8.198`，每条命令前设 `HYPERFRAMES_SKIP_SKILLS=1`。
  不运行 `hyperframes skills`、`publish`、`auth`、`cloud`。不往 `~/.claude`、`~/.agents`、`~/.codex` 安装 HyperFrames 技能。
  它的官方技能文档只下载到缓存里，作为只读参考。
- 下载优先走国内镜像：npm 用 npmmirror，PyPI 用阿里云，HuggingFace 用 hf-mirror.com。镜像缺包或版本落后时，用官方源校验，并告诉用户。
- 只按核实过的 PID 停进程，不用 pkill 或 killall。
- bailian-tts 的规则见 `references/audio.md` §2：不碰 API key，不自己切换模型。
- 下文按 Claude Code 的工具名写。宿主没有对应能力时这样退化：
  - 提问弹窗（AskUserQuestion）：有就用，没有就用一条普通消息一次问完。
  - 子代理：有就派，没有就由主会话按章节顺序自己搭场景，仍按 `references/subagents.md` 的简报逐章执行。
  - 后台命令（`run_in_background` 与完成通知）：没有时用 `nohup <命令> > <日志> 2>&1 & echo $!` 启动并记下 PID，在搭场景的间隙查日志末尾，不要空等。

## 流程

### 0. 确认需求

一次问清以下几项（用 AskUserQuestion）；用户已经说过的不要再问：
- 画幅和帧率（默认 1920×1080、30fps）。
- 目标时长。
- 旁白音色和语气。
- BGM 来源：本地 MusicGen（推荐，不能商用）、用户提供音乐文件、或者不要 BGM。
- 是否商用。如果商用，BGM 不能用 MusicGen。

### 1. 调研与解说词

1. 把屏幕上要出现的事实（数字、命令、许可证、功能）查清楚，记下来源。场景代理只照抄这些事实，不自己查。
2. 写 `P/narration/segments.json`，规则见 `references/audio.md` §1。要点：
   - display 和 spoken 分开写。
   - 按场景分组，标好章节。
   - 开场白不要承诺时长。

### 2. 配音、时间轴、字幕

先建 HyperFrames 工程。后面的脚本会往 `video/assets` 里写数据，`init` 要求目录还不存在：

```bash
cd P && HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@0.8.198 init video --example blank --resolution landscape --non-interactive --skip-transcribe
```

竖版用 `--resolution portrait`，同时把 `design.json` 的宽高改成 1080×1920。

然后按 `references/audio.md` §2–3 执行：
1. `narration.py script` 生成 bailian-tts 脚本。
2. `run.py script` 批量配音。
3. `narration.py assemble` 重新拼接旁白并算出场景边界。
4. 用 `transcribe` 做 Whisper 转写。
5. 运行 `make_captions.py`。

然后看 `asr/check.txt`，把读错的段改掉、重做，直到读音都对。**时间轴定下来之后再往下走**：后面每一步都依赖它，旁白一改，时间轴就要重新生成。

### 3. 搭工程地基

```bash
bash $K/scripts/fetch_assets.sh P/video                       # HyperFrames 文档（只读缓存）+ Pixabay 音效
bash $K/scripts/setup_fonts.sh P/video                        # Noto Sans SC woff2 + @font-face 片段
cp $K/assets/design.example.json P/video/design.json         # 改色板和 chapters（章数、标签、颜色）
python3 $K/scripts/gen_root.py --video P/video
cd P/video && HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@0.8.198 check --json
```

`gen_root.py` 会生成根合成、背景舞台（随章节换色）、章节 HUD、字幕层和全部占位场景。
占位版本的 check 应该是 0 个 error。有两条 warning 是设计如此，可以保留：
- HUD 的 18px 标签触发 `text_below_floor`。
- 片头 0–0.8s 只亮背景，触发 `first_frame_empty`。

之后只要时间轴或字幕变了，就重跑 `gen_root.py`；它不会覆盖已经写好的正式场景。

### 4. 写分镜

主会话自己写 `P/video/STORYBOARD.md`，结构和默认视觉系统见 `references/storyboard.md`。
这是质量的上限：子代理只按分镜做。所以每个场景都要写清楚：
- 屏幕上出现的原文。
- 每个元素在旁白说到哪个词时出现（⟨词⟩）。
- 至少一个会动的机制。
- 退场方式，以及和下一场景怎么衔接。

### 5. 并行搭场景和生成 BGM

**在同一条消息里**做两件事：
- 按 `references/subagents.md` 的模板派场景代理 2–4 个：按章节拆，片头和片尾归第一章的代理。
- 主会话自己用 Bash 的 `run_in_background` 启动 BGM（不派 BGM 代理），命令见 `references/audio.md` §4。先写好 `P/audio/bgm_plan.json`，模板见 `$K/assets/bgm_plan.example.json`，`sections[].start` 取每章第一个场景的 `visualStart`。不用 MusicGen 时跳过。

BGM 不交给子代理，是因为子代理在后台命令完成后可能不会被唤醒：上次 BGM 代理两次停在“等完成通知”，空等共 59 分钟，成为整片最长的一段关键路径。主会话收得到完成通知。BGM 完成后，主会话读 `qc.txt` 做判断（判读方法见 `references/audio.md` §4）。

验收时，先跑 `check --json` 看 error 数，再用 `snapshot --at <秒>` 截关键时刻，用 Read 看**全分辨率**原图。重点看：
- 构图是否偏向一侧。
- 字号是否够大。
- 是否与字幕区、HUD 冲突。
- 接缝处（每个 `visualStart` 起 0–0.6s）是否衔接。

返工意见对每个代理只发一次，内容完整、前后不矛盾（原因见 `references/subagents.md` 的协作规则）。

### 6. 渲染与画面质检

所有代理确认停手后，封版渲染：

```bash
cd P/video && HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@0.8.198 check --json
HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@0.8.198 render --quality delivery --fps 30 --workers auto -o renders/visual_pass.mp4 > renders/render.log 2>&1
python3 $K/scripts/qc_video.py --video P/video --out <scratchpad>/qc
```

- 渲染要几分钟到十几分钟，用 `run_in_background` 运行，不要轮询。
- 渲染前 `grep -lE "perspective|preserve-3d|backface-visibility" compositions/*.html` 应该为空。只要有一个场景用了 CSS 3D，整片都会退回慢速截图模式（日志里出现 `disabling drawElementImage`）。上次一个场景用 `perspective` 做卡片翻面，整片 9059 帧都走了截图模式，抓帧用了 15 分 44 秒。
- 大帧差应该只出现在设计好的转场处；≥4s 的静止段要处理。
- 看 `seams.jpg` 找到可疑位置后，再看对应的全分辨率单帧。

### 7. 混音与成片

```bash
python3 $K/scripts/mix_audio.py --video P/video --bgm P/audio/bgm.wav     # 不要 BGM 时去掉 --bgm
bash $K/scripts/finalize.sh P/video "P/<标题>.mp4"
```

`mix_audio.py` 默认给 BGM 加 80Hz 高通和 150Hz 低搁架 −4dB（`--bgm-eq`），修正 MusicGen 低频偏重；用户提供的成品音乐传 `--bgm-eq ""` 关闭。
先审阅 `mix_audio.py` 打印的音效清单，把没有画面原因的音效在 cue 里标 `"drop": true`，再重跑。
目标：−16 LUFS，真峰值 ≤ −1.5 dBTP。只改音频时不用重渲画面。

### 8. 交付

告诉用户以下内容：
- 成片路径和规格：分辨率、帧率、时长、编码、响度。
- 用到的工具和素材来源。
- 许可：
  - MusicGen 是 CC-BY-NC，不能商用。商用时换 BGM，重跑第 7 步即可。
  - 音效来自 Pixabay，可以商用。
  - 字体是 OFL 许可。
- 可以清理的磁盘占用：`~/.venvs/musicgen`、`~/.cache/huggingface/hub`、`~/.cache/explainer-video`。

## 参考文件

| 文件 | 什么时候读 |
|---|---|
| `references/audio.md` | 写解说词、配音、核对读音、规划 BGM、混音时 |
| `references/storyboard.md` | 写 STORYBOARD.md 前 |
| `references/scene-authoring.md` | 交给场景代理必读；主会话自己改场景时也要读 |
| `references/subagents.md` | 派场景代理前，复制其中的简报模板 |
| `~/.cache/explainer-video/hf-skills/<标签>/skills/hyperframes/` | HyperFrames 官方文档（motion、format、review、captions） |
