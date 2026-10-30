# 旁白、BGM 与混音

## 1. 解说词：segments.json

格式见 `assets/segments.example.json`。每段一句或两句，一段对应一个 TTS 请求。

- **display 与 spoken 分开写**：
  - `display` 是屏幕和字幕上的文字，保留原始拼写，如 `ste-zh`、`ASD-STE100`、`25 条`。
  - `spoken` 是给 TTS 读的稿子：
    - 英文缩写拆成字母，加空格（`S T E Z H`、`H T M L`）。
    - 连字符换成空格（`plain chinese`、`diagram design`）。
    - 数字写成汉字（`二十五条`）。
    - 想要停顿的地方加逗号。
  - 两者意思必须一致，因为字幕按 display 显示、按 spoken 的读音对时。
- **scene 键**：用 `sNN-名称`。相邻同键的段属于一个场景。一个场景 1–4 段、8–30 秒最合适；超过 30 秒，就要在分镜里分拍。
- **chapter**：片头和片尾写 0，章节内写 1…N，和 `design.json` 的 `chapters` 顺序对应。
- **开场白不要承诺时长**。原稿写过"三分钟讲清楚"，配完音发现总长超过 4 分半，只好重写第一句再重配。
- 屏幕上的事实性内容（数字、命令、许可证）要先调研、附来源，再写进解说词和分镜。

## 2. 配音：bailian-tts

按技能名调用 bailian-tts，由宿主定位它，不按路径找它的文件：Claude Code 用 Skill 工具（插件安装时名为 `bailian-tts:bailian-tts`），Codex 用 `$bailian-tts`，Pi 用 `/skill:bailian-tts`。宿主里没有这个技能时停下，请用户先安装 bailian-tts。加载后宿主会给出它的目录，记为 `F`，再运行它的 `scripts/run.py`：

```bash
python3 $F/scripts/run.py --check          # ready: false 时，先征得用户同意，再运行 --setup --yes
python3 $F/scripts/run.py status           # 最后一行是"onboarding: 需要"时，按它的 SKILL.md 带用户完成首次引导
python3 $F/scripts/run.py fav              # 默认音色 = 收藏里的第 1 个
```

规则（来自 bailian-tts 的 SKILL.md，必须遵守）：
- 不读取、不打印 API key。只用 `key` 子命令或工作台页面保存 key。
- 合成跟随工作台的默认模型（`~/.config/bailian-tts/settings.json` 的 `model`，文件不存在时就是 Flash），不要自己切换模型。
- `@instruct` 和 `--instruct` 只有 Flash 支持，最多 100 字符（汉字按 2 个算）。默认模型不是 Flash 时，`narration.py script` 不要加 `--instruct`。

流程：

```bash
python3 <技能>/scripts/narration.py script --project P --instruct "沉稳自信的科技讲解男声，吐字清晰，语速适中偏快，像精品科技频道的旁白"
python3 $F/scripts/run.py script P/narration/spoken.txt --out-dir P/dub/ --gap 0.35
python3 <技能>/scripts/narration.py assemble --project P
```

`assemble` 不用 `all.wav`，而是重新拼接：开头留 0.8s，同一场景内段间隔 0.35s，换场景间隔 1.0s，结尾留 2.5s。
同时算出每个场景的 `visualStart`/`visualEnd`：画面在下一场景首句开始前 0.45s 切换，让转场先于声音发生。

只重做某一段（例如第 1 段）：

```bash
python3 $F/scripts/run.py gen --instruct "<与脚本相同的指令>" --text "<新的 spoken>" --out P/dub/001.wav
python3 <技能>/scripts/narration.py assemble --project P      # 时间轴会整体重算，之后的步骤都要重跑
```

## 3. 读音核对与词级时间戳

```bash
cd P && npx --yes hyperframes@0.8.198 transcribe audio/narration.wav -d asr -e whisper -m small -l zh --json > asr/run.log 2>&1
python3 <技能>/scripts/make_captions.py --project P
```

- `transcribe` 自己会写 `asr/transcript.json`。不要把 stdout 重定向到这个文件，否则两边写入会冲突。
- 打开 `asr/check.txt`，逐段比较朗读稿和识别结果。重点检查多音字、英文名、数字。读错的段改写 spoken，再用 `gen` 重做。
- 英文名经常识别不出来。这时段内第一个词的时间戳会落到后面的中文词上，看起来像"整体偏晚"，但实际上不是系统性偏差。段的起止来自 TTS，是准的。

## 4. BGM

先问用户 BGM 来源：
- **本地 MusicGen（默认推荐）**：免费、离线可复现。权重是 **CC-BY-NC 4.0，不能商用**。需要约 1.6GB 的 venv 和约 8GB 的模型缓存。5 分钟的片子分 19 步生成，实测约 22 分钟（M1 Max、MPS、medium），和场景代理并行，不占关键路径。
- **用户提供音乐文件**：直接作为 `--bgm` 传给混音脚本。长度不够时先用 ffmpeg 处理（循环或交叉淡化）。
- **不要 BGM**：混音时不传 `--bgm`。

MusicGen 的计划写在 `P/audio/bgm_plan.json`（模板见 `assets/bgm_plan.example.json`）：
- `sections[].start` 取每章第一个场景的 `visualStart`。片头、总结、片尾各自单独成段。
- `style` 会拼到每条提示词后面，用来统一调性和速度。实测模型不一定照写的调性来（写 A 小调，实际出来的是 F 小调附近），但整体风格能保持一致。
- `recap` 让最后一段以开场的片段为 prompt 续写，形成主题回归。`impact` 填 riser→impact 所在的时刻。
- `target_lu` 控制能量曲线：开场低，逐章升高，总结时最高，收尾回落。
- 后处理把 BGM 标准化到约 −20 LUFS，交给混音时再闪避。
- **提示词不要写 `pulsing bass`、`pulsing synth bass`、`driving bass`**。上次第 2、3 章这样写，150Hz 以下占到 67–83%，接缝处还出现 +10.7dB 的跳变，只能重生成 10 步（15 分钟）。改写成 `mid-range arpeggios, light bass`。能量靠鼓和中频层次堆，不靠低音。

### 运行（主会话，后台）

由主会话在派场景代理的同一条消息里，用 Bash 的 `run_in_background` 启动。生成和后处理连成一条命令，后处理不依赖任何人被唤醒：

```bash
ps -eo pid,etime,command | grep musicgen_bgm | grep -v grep   # 先看有没有别的 MusicGen 在跑：共用 GPU 时每步慢约 50%
export HF_ENDPOINT=https://hf-mirror.com
~/.venvs/musicgen/bin/python <技能>/scripts/musicgen_bgm.py --plan P/audio/bgm_plan.json --work P/audio/musicgen_work > P/audio/musicgen_work.log 2>&1 \
  && ~/.venvs/musicgen/bin/python <技能>/scripts/bgm_post_qc.py --plan P/audio/bgm_plan.json --work P/audio/musicgen_work --out P/audio/bgm.wav >> P/audio/musicgen_work.log 2>&1
```

- venv 不存在时先建：`python3 -m venv ~/.venvs/musicgen`，再用阿里云镜像装 `torch torchaudio transformers soundfile numpy scipy accelerate pyloudnorm`（`-i https://mirrors.aliyun.com/pypi/simple/`）。
- 模型 `facebook/musicgen-medium`，设备 MPS。新版 huggingface_hub 把权重放在共享 blob 目录，模型目录只有符号链接，`du` 只显示约 2MB，不代表没下载。

### 读 qc.txt

完成通知到达后，主会话读 `P/audio/musicgen_work/qc.txt`。标了“<-- 注意”的接缝先区分真假：

| 现象 | 判断 |
|---|---|
| 接缝 1 秒内响度跳 ≥ 6dB，且频谱质心同时大幅变化 | 真跳变。改那一章的提示词或换种子，`musicgen_bgm.py --regen k`，再跑后处理 |
| 最大样本差落在交叉淡化区之前 | 假：原片段里的打击乐瞬态 |
| 质心变化大，但 ΔRMS3s 只有 1–2dB，接缝前后的鼓点起伏一样 | 假：鼓点本身的起伏 |
| 抬高持续约 2s 且跨过接缝，绝对值很小 | 假：一段过门 |
| recap 那一步相关系数 r≈0 | 预期：有意切回开场 |

某章 150Hz 以下占比高不需要重生成，混音时 `--bgm-eq` 会处理（见 §5）。

## 5. 混音

```bash
python3 <技能>/scripts/mix_audio.py --video P/video --bgm P/audio/bgm.wav
```

参数的由来：
- `--bgm-db -9`：旁白停顿处 BGM 的增益。`--duck-db -6`：说话时再压低 6dB（攻击 80ms，释放 700ms）。
  最初用 −17 / −7，旁白下面的音乐只剩约 −44 LUFS，基本听不见。
- `--bgm-eq` 默认 `highpass=f=80,lowshelf=f=150:g=-4`：MusicGen 的输出 150Hz 以下常占 70–80%，手机外放发闷。用户提供的成品音乐传 `--bgm-eq ""`。
- 最终响度 −16 LUFS、真峰值 −1.5 dBTP（两遍 loudnorm，`linear=true`，只做增益，不压缩动态）。
- 音效峰值对齐到画面动作之后一帧。同一采样重复出现时轮换变速，避免听出是同一个声音。
- 审听或审阅音效清单时，删掉的音效在 cue 里加 `"drop": true`，不要直接删掉那一行，这样能留下记录。
  上次的删减：打字声和按键声全删；点击声只留有画面原因的两次；同一场景里重复的 sparkle 删掉。
- 输出的清单按绝对时间排序，每条带 `why`，方便逐条判断这个音效有没有画面原因。
