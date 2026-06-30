---
name: cosyvoice-tts
description: 用阿里百炼 CosyVoice 把中文文本合成成自然语音,并充分利用 Instruct——用一句规定格式的指令控制语气/情感(开心/难过/生气/惊讶等)、场景、角色、身份,还能调语速音调。当前固定使用 cosyvoice-v3-flash,支持选音色、先试听再批量生成 wav。当用户想用阿里/百炼/CosyVoice/DashScope 做语音合成、TTS、配音、旁白、朗读、文字转语音,或要给视频/PPT/课件加中文配音、要带情感/不同语气的配音、试听某音色、把多段文案批量转成 wav 时,使用本技能。涉及阿里云语音合成的几乎都用它,不要每次现写 SDK 代码。
disable-model-invocation: true
---

# 阿里 CosyVoice 语音合成(Instruct)

把中文文案合成成接近真人的语音,**重点是用好 Instruct**:同一个音色,靠一句指令就能说出不同情感/风格,做出有表现力的配音。核心是 `scripts/tts.py`,封装了「读 key → 调 CosyVoice(带 Instruct)→ 规范化音频 → 量时长」。

## 运行环境(一次性)

- **Python 依赖** `dashscope`:本机已建好 `~/.cosyvoice-tts-venv`,**用它跑脚本**。若缺失:`python3 -m venv ~/.cosyvoice-tts-venv && ~/.cosyvoice-tts-venv/bin/pip install dashscope`。
- **API key**:脚本按「环境变量 `DASHSCOPE_API_KEY` → 文件 `~/.dashscope_key`」读取。优先用 `~/.dashscope_key`,**不要把 key 打印到对话或写进文件**。
- **音频工具**:`ffmpeg`/`ffprobe`、`afplay`(macOS 播放)。

运行前先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录。调用统一写法:
```bash
~/.cosyvoice-tts-venv/bin/python "$skill_dir/scripts/tts.py" <子命令> ...
```

## 默认与数据

- **固定模型** `cosyvoice-v3-flash`,**默认音色** `longanhuan`(女)。当前只维护 v3-flash 的音色 catalog,不暴露模型切换;未来需要其它模型时再补对应 catalog 和兼容逻辑。
- v3-flash 的**全部音色**(88 个,含中文名/性别/场景/语言/是否支持 Instruct)在 [references/voices_v3flash.json](references/voices_v3flash.json),与官方列表对齐;`list` 命令直接读它。

## Instruct(自动按场景设置,可覆盖)

只有少数音色支持 **Instruct**(用规定句式控制情感/场景/角色)。脚本对每个音色都知道它是否支持:

- **支持 Instruct 的音色**:即使你不指定,也会**按音色的场景自动设一个合适情感**(如童声→happy、客服→neutral),并在输出里**打印当前 Instruct 设置**;你可用下列选项覆盖。
- **不支持 Instruct 的音色**:若你仍传了情感,脚本会**提示忽略并按普通合成**(不会报 428)。

控制选项(preview / gen 通用):
- `--emotion`:`neutral / happy / angry / sad / surprised / fearful / disgusted`(最稳)
- `--scene` / `--role` / `--identity`:**每个音色有各自的合法取值**(用 `list --instruct-only` 查)。脚本会:① 句式用全角逗号;② 把你给的词**就近匹配**到该音色的合法取值(如「客服」→「温和客服」);③ 取值匹配不到、或后端仍不接受时,**自动回退到纯情感**并提示——所以你大胆传,坏不了。
- `--instruct "完整指令"`:直接给整句(覆盖上面)
- 副参数:`--rate 0.5-2.0` `--pitch 0.5-2.0` `--volume 0-100`(已自动钳制)

> 实测坑(脚本已规避):句式必须**全角逗号**;场景/角色/身份只认**该音色的合法取值**;`角色` 句式较易被拒(会自动回退);`longanhuan_v3` 官标 Instruct 但 API 失败。
> 用户说"开心点/严肃点""像客服/像主播/讲新闻""快一点"——映射到这些选项,主动用上;不确定取值就先 `list --instruct-only` 看该音色支持什么。

## 三个子命令

**list** —— 列出 v3-flash 全部音色(按场景分组,⭐=支持 Instruct);`--instruct-only` 只看可情感控制的:
```bash
... tts.py list
... tts.py list --instruct-only
```

**preview** —— 试听(合成一句直接播放),**选音色/调情感时先用它**。输出会显示当前 Instruct:
```bash
... tts.py preview -v longanhuan --emotion happy
... tts.py preview -v longhuhu_v3 --text "你的句子"          # 童声,自动 happy
... tts.py preview -v longyingxun_v3 --text "..."           # 客服音色(不支持instruct,普通合成)
```

**gen** —— 正式生成 wav(单段或从文件),打印**时长**(视频对轴要用):
```bash
... tts.py gen -v longanhuan --emotion sad --text "要念的文案" --out audio/s1.wav
... tts.py gen -v longanhuan --file 文案.txt --out out.wav
```

## 典型协作流程

1. 用户给文案 + 想要的语气/情感/音色。
2. `preview` 试听 1~2 个候选(音色 × 情感),让用户拍板。
3. 定了之后 `gen` 批量生成各段 wav,记录每段时长。
4. (若用于视频)把时长交给视频/字幕工具对齐时间轴。

## 选音色/排错要点

- **以官方列表为准,不要靠"探测"**:全部音色用 `list` 查(数据在 [references/voices_v3flash.json](references/voices_v3flash.json),对齐官方页 `https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list`)。Instruct 用法与排错另见 [references/voices.md](references/voices.md)。
- **报错判断**:`418`=音色无效或后端不接受该组合;`428`=对不支持 Instruct 的音色发了指令,或情感/句式不合规(脚本已尽量规避)。
- 想给视频做整段配音:`gen` 逐段输出 wav 并记录时长,交给视频/字幕工具对齐时间轴。

## 边界

- 本技能做**预置音色**的合成 + Instruct。**声音复刻**(克隆用户自己的声音)需要 OSS 上传 + `VoiceEnrollmentService`,更重,不在脚本内,用户要时再单独处理(见 voices.md 末尾)。
- 默认中文。CosyVoice 也有多语种/方言音色(见官方列表),按需指定。
