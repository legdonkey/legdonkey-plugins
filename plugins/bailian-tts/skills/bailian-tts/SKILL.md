---
name: bailian-tts
description: 用阿里百炼 qwen-audio-3.1-tts-flash 把中文(及方言、多语种)文案合成自然语音:用任意自然语言指令控制语气/情感/语速/角色,在文本里嵌入 [excited]、[laughing] 等情感与拟声标签;支持试听音色、单段生成 wav、按脚本批量生成并输出字幕(SRT)与拼接音轨,以及用自己的录音复刻音色。当用户想用阿里/百炼/Qwen-Audio/DashScope 做语音合成、TTS、配音、旁白、朗读、文字转语音,给视频/PPT/课件加配音,要带情感或方言的配音,试听音色,把多段文案批量转成 wav 并对齐字幕,或复刻自己的声音时,使用本技能。不要每次现写 SDK 代码。
disable-model-invocation: true
---

# 阿里百炼语音合成(qwen-audio-3.1-tts-flash)

把文案合成成接近真人的语音。核心是 `scripts/tts.py`,封装了「读 key → 调 Qwen-Audio-TTS(带指令)→ 规范化为 24kHz 单声道 wav → 量时长」,以及复刻音色的创建、查询、删除。

## 运行环境(一次性)

- **Python 依赖** `dashscope`:用 `~/.bailian-tts-venv` 跑脚本。若缺失:`python3 -m venv ~/.bailian-tts-venv && ~/.bailian-tts-venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ dashscope`(阿里云 PyPI 镜像)。
- **API key**:北京地域的百炼 key,脚本按「环境变量 `DASHSCOPE_API_KEY` → 文件 `~/.dashscope_key`」读取。优先用 `~/.dashscope_key`,**不要把 key 打印到对话或写进文件**。
- **音频工具**:`ffmpeg`、`afplay`(macOS 试听播放)。

运行前先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录。调用统一写法:
```bash
~/.bailian-tts-venv/bin/python "$skill_dir/scripts/tts.py" <子命令> ...
```

## 模型与音色

- **固定模型** `qwen-audio-3.1-tts-flash`,**默认音色** `longanhuan_v3.1`(女)。
- 68 个系统音色在 [references/voices.json](references/voices.json)(与官方列表对齐),`voices` 命令直接读。系统音色名都以 `_v3.1` 结尾,区分大小写。
- **音色必须属于本模型**:其它模型的系统音色(如 3.0 系列的 `*_v3.6`)、为其它模型创建的复刻音色都不能用,服务端只会回 `411`。脚本会提前识别并提示。
- 分组:**多语种与方言**(4 个,支持 8 种方言与 8 种外语)、**精品中文**(22 个,仅普通话)、**精品英文**(15 个,仅英文)、**其他系统**(27 个,角色/童声/陪伴等)。

## 控制语气

- **`--instruct "自然语言"`**:原样传给模型。写具体的声音特征比写主观词有效:「沉稳的中年女声,语速偏慢,适合新闻播报」好于「好听一点」。方言也用指令:「请用重庆话表达。」(只对多语种与方言组的 4 个音色有效)。上限 100 字符,汉字计 2,超长脚本直接报错。
- **`--emotion`**:`neutral / happy / angry / sad / surprised / fearful / disgusted`,未给 `--instruct` 时拼成「用开心的语气说话。」这类指令。
- **文本内标签**(写在文案里):控制类标签作用于其后文本直到下一个控制标签,如 `[excited] [sad] [serious] [whispers] [curious] [very slowly] [very fast]`;富语言类标签在当前位置插入拟声,如 `[laughing] [giggles] [sighing] [gasp] [cough] [clears throat]`。完整列表见 [references/voices.md](references/voices.md)。
- 副参数:`--rate 0.5-2.0` `--pitch 0.5-2.0` `--volume 0-100`(已自动钳制)。

> 用户说"开心点/严肃点""像客服/像主播/讲新闻""快一点""用东北话"——直接翻译成 `--instruct` 的自然语言;需要句中插笑声、叹气、或一段内切换情绪时用文本标签。

## 子命令

**voices** —— 列出系统音色;`--gender 女|男`、`--scene <分组或适用场景>` 筛选;`--mine` 列出账号下全部复刻音色,分「本模型可用」和「属于其它模型」两组(后者无法合成,可 `delete` 释放配额):
```bash
... tts.py voices --gender 女 --scene 新闻播报
... tts.py voices --mine
```

**preview** —— 合成一句直接播放,**选音色、调语气时先用它**:
```bash
... tts.py preview -v xuyuyuan_v3.1 --instruct "沉稳知性,像新闻播报"
... tts.py preview -v longanhuan_v3.1 --instruct "请用重庆话表达。" --text "今天我们去吃火锅,好不好嘛。"
```

**gen** —— 生成单段 wav(`--text` 或 `--file`),打印时长:
```bash
... tts.py gen -v yuxiaoyun_v3.1 --text "[excited]新品上市![laughing]" --out audio/ad.wav
... tts.py gen --emotion sad --file 文案.txt --out out.wav
```

**script** —— 按脚本逐段生成,**做视频配音用它**。输出目录里有 `001.wav…`、拼好的 `all.wav`(段间插 `--gap` 秒静音,默认 0.3)、`subtitles.srt`(去掉标签后的文案,时间轴与 `all.wav` 一致)和 `manifest.json`(每段的音色、指令、起止时间):
```bash
... tts.py script 旁白.txt --out-dir dub/ --gap 0.4
```
脚本格式:每个非空行是一段;`#` 开头为注释;`@voice <音色>`、`@instruct <指令>` 设置之后各段,`@instruct` 留空即清除。命令行的 `-v` / `--instruct` 是初始值。
```text
@voice xuyuyuan_v3.1
@instruct 沉稳知性的女声，语速适中
各位好，欢迎来到今天的发布会。
@voice yuxiaoyun_v3.1
@instruct 年轻活泼的女声，语速偏快
[excited]它真的太好用了！[laughing]
```

**clone** —— 复刻用户自己的声音。直接给**本地录音路径**(m4a/mp3/wav 等,如 macOS 语音备忘录导出的文件):脚本用 ffmpeg 转成 24kHz 单声道 wav、检查时长(5~60 秒,推荐 10~20 秒),上传到百炼免费临时存储,再提交复刻并等待音色可用。用户不需要自己的 OSS。已有公网 URL 时也可直接传 URL。录音要求:单人、无背景音乐和噪音、至少 5 秒连续清晰朗读:
```bash
... tts.py clone ~/Desktop/我的录音.m4a --prefix ygd [--lang zh] [--denoise]
... tts.py clone "https://..." --prefix ygd
```
成功后打印 `voice_id`(形如 `qwen-audio-3.1-tts-flash-ygd-<hex>`),之后 `-v <voice_id>` 使用,复刻音色同样支持指令。**每次调用都会新建一个音色**(账号上限 1000 个),不要重复提交。

**delete** —— 删除复刻音色:`... tts.py delete <voice_id>`。**删除不可恢复,执行前先向用户确认。**

## 典型协作流程

1. 用户给文案 + 想要的语气/音色;用 `voices` 按性别、场景缩小范围。
2. `preview` 试听 1~2 个候选(音色 × 指令),让用户拍板。
3. 单段用 `gen`;多段/视频用 `script`,把 `all.wav` 和 `subtitles.srt` 交给剪辑工具。
4. 用户要用自己的声音:让用户录 10~20 秒清晰朗读,拿到本地文件路径后 `clone`。

## 排错

- `411`(`Engine error [411]: TTS speak operation failed`):音色不属于本模型。换 `voices` 列出的 `_v3.1` 音色,或为本模型重新 `clone`。
- 指令被拒或效果不明显:缩短指令、改成具体的声音特征描述;情绪切换优先用文本标签。
- 复刻失败:检查录音质量(单人、无背景音);有底噪时加 `--denoise`;用 URL 时确认无需鉴权即可下载。

## 边界

- 只支持 `qwen-audio-3.1-tts-flash` 一个模型。多人对话/配乐/音效一体生成(`qwen-audio-3.1-tts-next`)和声音设计(按文字描述生成音色,官方未对 3.1-flash 开放)不在本技能内。
- 复刻他人声音须取得本人授权。
