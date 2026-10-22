---
name: bailian-tts
description: 用阿里百炼 qwen-audio-3.1-tts-flash 把中文(及方言、多语种)文案合成自然语音:用任意自然语言指令控制语气/情感/语速/角色,在文本里嵌入 [excited]、[laughing] 等情感与拟声标签;支持试听音色、单段生成 wav、按脚本批量生成并输出字幕(SRT)与拼接音轨,以及用自己的录音复刻音色。当用户想用阿里/百炼/Qwen-Audio/DashScope 做语音合成、TTS、配音、旁白、朗读、文字转语音,给视频/PPT/课件加配音,要带情感或方言的配音,试听音色,把多段文案批量转成 wav 并对齐字幕,或复刻自己的声音时,使用本技能。所有文本合成命令跟随工作台默认模型，也支持 ElevenLabs Eleven v4（独立 Key、固定音色与收藏）。不要每次现写 SDK 代码。
disable-model-invocation: true
---

# 语音合成工作台（百炼 Flash / Next、Eleven v4）

把文案合成成接近真人的语音。核心是 `scripts/tts.py`,封装了「读 key → 调 Qwen-Audio-TTS(带指令)→ 规范化为 24kHz 单声道 wav → 量时长」,以及复刻音色的创建、查询、删除。

## 运行环境(一次性)

- **统一入口** `scripts/run.py` 仅依赖 Python 标准库。首次运行需确认创建或修复 `~/.bailian-tts-venv`，从阿里云 PyPI 镜像安装 `scripts/requirements.txt` 中固定版本的 `dashscope` 和 `websocket-client`；后续复用，不向系统 Python 安装、不需要 sudo。`BAILIAN_TTS_VENV` 可指定其他用户目录，不能放进插件目录。启动器不是常驻服务。
- **API key**:北京地域的百炼 key,脚本按「环境变量 `DASHSCOPE_API_KEY` → 文件 `~/.dashscope_key`(权限 600)」读取。只用 `key` 子命令或工作台页面保存;**不要自己读剪贴板、`cat` key 文件,不要把 key 打印到对话或写进其它文件**。
- **音频工具**:`ffmpeg`、`afplay`(macOS 试听播放)。

运行前先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录。调用统一写法:
```bash
python3 "$skill_dir/scripts/run.py" <子命令> ...
```

## 开工前自查与首次引导

每次被调用先跑 `python3 "$skill_dir/scripts/run.py" --check`（本地检查，不安装、不联网）。如果 `ready: false`，先说明会在用户目录下载并安装依赖，征得同意后执行 `python3 "$skill_dir/scripts/run.py" --setup --yes`；初始化失败时转述原因，不继续启动。非交互模式不会读取朗读正文作为确认输入，也不会擅自安装；交互式终端可直接运行启动器并回答确认提示。随后运行 `... run.py status`（本地检查，不联网）。最后一行是 `onboarding: 需要` 时,先带用户走完首次引导,再做用户要的事:

1. 后台运行 `ui`(运行方式见下文 **ui**),它会在用户默认浏览器打开工作台的「开始」页:说明插件能做什么、创建 API Key 的三步,以及「从剪贴板读取并保存」按钮。
2. 运行 `... run.py key --console`,在用户默认浏览器打开百炼控制台的 API Key 页(不依赖任何浏览器自动化工具),然后把操作交给用户:「请在刚打开的页面登录阿里云,确认右上角地域是华北2(北京),点『创建 API Key』(选项保持默认),再点 Key 旁的复制图标;复制好了回来告诉我。」不要替用户登录、填写或点击创建。
3. 用户说复制好了,运行 `... run.py key --clipboard`:读剪贴板 → 向百炼校验 → 写入 `~/.dashscope_key`(权限 600)→ 清空剪贴板,只打印掩码。失败时把报错原样转述(多半是没复制完整或地域不对),请用户重新复制后再跑。用户也可以直接在「开始」页点按钮或手动粘贴保存,效果相同。
4. 成功后「开始」页会自动显示新 key 的掩码。用户想先试听或复刻时,让他在同一个工作台里点顶栏的「选音色」「声音复刻」;否则继续原任务。

运行环境需要修复时，先确认后重跑 `run.py --setup --yes`；不手动向系统 Python 安装 pip 包。`ffmpeg` 是独立的系统工具，启动器只检查、不自动通过包管理器安装，缺失时需按系统说明安装。

## 模型与音色

- **Flash 模型** `qwen-audio-3.1-tts-flash` 用于百炼音色收藏与声音复刻。`gen` / `script` / `preview` / `say` 均跟随工作台默认模型，工作台顶部可切换为 `qwen-audio-3.1-tts-next`，配置保存在 `~/.config/bailian-tts/settings.json`；Next 使用声音描述，不使用 Flash 音色 ID。**默认音色**:未指定 `-v` 时用用户**收藏的第 1 个**(见 `fav`),收藏为空时用 `longanhuan_v3.1`(女)。脚本会在 stderr 打印实际用了哪个。
- 68 个系统音色在 [references/voices.json](references/voices.json)(与官方列表对齐),`voices` 命令直接读。系统音色名都以 `_v3.1` 结尾,区分大小写。
- **音色必须属于本模型**:其它模型的系统音色(如 3.0 系列的 `*_v3.6`)、为其它模型创建的复刻音色都不能用,服务端只会回 `411`。脚本会提前识别并提示。
- 分组:**多语种与方言**(4 个,支持 8 种方言与 8 种外语)、**精品中文**(22 个,仅普通话)、**精品英文**(15 个,仅英文)、**其他系统**(27 个,角色/童声/陪伴等)。

### Eleven v4 / Eleven v4 Turbo

- `eleven_v4_turbo` 可在同一模型下拉框中选择，与 v4 共用 ElevenLabs Key、账号音色和本地收藏。保存后同步用于 UI 试听与中键朗读；不改变现有默认音色。
- Turbo 按[官方实时对话指南](https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tdd)使用 TTD WebSocket：注册一个 voice_id、一次提交全文、收齐 Base64 音频块后播放。不恢复文本分段，不承诺流式首包延迟；出错不自动重试、不会自动改用其他模型。
- Turbo 依赖 `websocket-client`，由启动器按 `requirements.txt` 与 dashscope 一起安装和校验；缺失时经用户确认执行 `run.py --setup --yes` 修复，不单独向其他 Python 环境安装。
- 官网当前 API 基础费率为 v4 $0.08/千字符、Turbo $0.04/千字符，实际价格与音色资格以账号为准；使用 Turbo 不解除音色库的付费套餐限制。

- UI 与 `say` 支持 `eleven_v4`，使用官方 Text to Dialogue HTTPS 接口（单人朗读发送一条 `text` / `voice_id` 输入），支持固定音色。`gen` / `script` / `preview` 同样跟随默认模型；声音复刻仍使用百炼 Flash。
- 在工作台顶部选择 Eleven v4，打开 ElevenLabs API Key 页面，由用户创建具有读取音色与语音生成权限的 Key，粘贴到本地密码输入框并点击「校验并保存 Key」。不要读取用户剪贴板或把 Key 写进对话。校验只读取账号音色，不提交合成。
- 密钥：`ELEVENLABS_API_KEY` → `~/.config/bailian-tts/elevenlabs.key`，文件权限 600；只显示掩码，环境变量与新 Key 冲突时拒绝覆盖。
- 点「保存模型设置」切换试听与中键朗读。刷新账号音色后可加入收藏、设为默认；收藏位于 `~/.config/bailian-tts/elevenlabs-favorites.json`，第 1 个为中键默认音色，与百炼收藏隔离。本地取消收藏不删除 ElevenLabs 账号音色。首次读取账号音色时，若本地收藏文件尚不存在，从可用账号音色中导入 Siqi Liu、Adrian、Roger；不会导入 Coco Li。
- 使用 `mp3_44100_128` 下载后规范化为现有 24kHz 单声道 WAV，不需要新的 Python 依赖。仅使用文本内音频标签，不传百炼的 `--instruct` / `--emotion` / `--rate` / `--pitch` / `--volume` 参数。UI 试听最多 200 字；中键按当前模型的长度配置截断（初始 1500 字）、整段生成后播放，底层单次限制 2000 字符。
- Eleven 选音色页与 Flash 一样采用左侧列表、右侧试听台：已有收藏时默认「已收藏」，可切换「全部」「免费套餐可试」「API 需付费」「资格待确认」，支持搜索、性别筛选、↑↓ 切换与回车试听；右侧管理收藏、默认音色、播放与重复试听，列表显示试听时长。取消收藏只影响本地收藏，不删除账号音色。资格信息标注「免费套餐可试」「API 需付费」「资格待确认」，可勾选仅显示免费套餐可试。依据官方音色元数据：非本人共享音色按 API 付费资格标注，非共享 premade 音色在无付费层级限制时标为免费套餐可试；无法确认时不标免费。`sharing.free_users_allowed` 不等同于 API 免费套餐资格。标注不替代当前账号、模型和额度校验，不提交合成探测资格；免费套餐可试仍消耗额度。
- 正文会发送到 ElevenLabs；生成消耗该账号额度，用户确认后才提交试听。相同音色与文本在同一工作台中复用已有音频。音色费率与模型费率需按账号确认，首次导入不代表自动核验价格。
- 参考：[模型文档](https://elevenlabs.io/docs/overview/models#eleven-v4)、[接口](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert)、[API 定价](https://elevenlabs.io/pricing/api)。

## 控制语气（百炼 Flash）

- **`--instruct "自然语言"`**:原样传给模型。写具体的声音特征比写主观词有效:「沉稳的中年女声,语速偏慢,适合新闻播报」好于「好听一点」。方言也用指令:「请用重庆话表达。」(只对多语种与方言组的 4 个音色有效)。上限 100 字符,汉字计 2,超长脚本直接报错。
- **`--emotion`**:`neutral / happy / angry / sad / surprised / fearful / disgusted`,未给 `--instruct` 时拼成「用开心的语气说话。」这类指令。
- **文本内标签**(写在文案里):控制类标签作用于其后文本直到下一个控制标签,如 `[excited] [sad] [serious] [whispers] [curious] [very slowly] [very fast]`;富语言类标签在当前位置插入拟声,如 `[laughing] [giggles] [sighing] [gasp] [cough] [clears throat]`。完整列表见 [references/voices.md](references/voices.md)。
- 副参数:`--rate 0.5-2.0` `--pitch 0.5-2.0` `--volume 0-100`(已自动钳制)。

> 用户说"开心点/严肃点""像客服/像主播/讲新闻""快一点""用东北话"——直接翻译成 `--instruct` 的自然语言;需要句中插笑声、叹气、或一段内切换情绪时用文本标签。

## 全局模型与命令行限制

`gen` / `script` / `preview` / `say` 使用工作台保存的模型，不会自动回退到 Flash。ElevenLabs 未指定 `-v` 时使用其独立收藏的第一个音色，Next 使用工作台声音描述，不接受 `-v` / `@voice`。`voices` / `fav` / `clone` / `delete` 仍管理百炼 Flash 音色。

`gen` / `script` / `preview` 不自动截断正文；Next 单段上限 2800 字符，Eleven 单段上限 2000 字符。Next 不接受 `--instruct` / `--emotion` / `--pitch` / `@instruct`；Eleven 还不接受非默认 `--rate` / `--volume`。不兼容设置在合成前报错；脚本先校验全部段落再提交。Next 的输出时长限制仍可能导致长文不完整，先用短句验证。

## 子命令

**voices** —— 列出系统音色;`--gender 女|男`、`--scene <分组或适用场景>` 筛选;`--mine` 列出账号下全部复刻音色,分「本模型可用」和「属于其它模型」两组(后者无法合成,可 `delete` 释放配额):
```bash
... run.py voices --gender 女 --scene 新闻播报
... run.py voices --mine
```

**preview** —— 合成一句直接播放,**选音色、调语气时先用它**:
```bash
... run.py preview -v xuyuyuan_v3.1 --instruct "沉稳知性,像新闻播报"
... run.py preview -v longanhuan_v3.1 --instruct "请用重庆话表达。" --text "今天我们去吃火锅,好不好嘛。"
```

**gen** —— 生成单段 wav(`--text` 或 `--file`),打印时长:
```bash
... run.py gen -v yuxiaoyun_v3.1 --text "[excited]新品上市![laughing]" --out audio/ad.wav
... run.py gen --emotion sad --file 文案.txt --out out.wav
```

**script** —— 按脚本逐段生成,**做视频配音用它**。输出目录里有 `001.wav…`、拼好的 `all.wav`(段间插 `--gap` 秒静音,默认 0.3)、`subtitles.srt`(去掉标签后的文案,时间轴与 `all.wav` 一致)和 `manifest.json`(每段的音色、指令、起止时间):
```bash
... run.py script 旁白.txt --out-dir dub/ --gap 0.4
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

**ui** —— **本地配音工作台,首次引导、挑音色、复刻声音、配置选中朗读都用它**。在本机启动只监听 `127.0.0.1` 的服务(每个请求带一次性 token)并自动打开浏览器,同一个页面顶栏有四栏(选中朗读仅 macOS):
- **开始**:功能介绍、运行环境检查、创建并保存 API Key(校验后写入 `~/.dashscope_key`,权限 600)。还没配置 key 时,不论要打开哪一栏都先落在这里。
- **选音色**:左侧是 68 个系统音色和本模型可用的复刻音色(按分组、性别、关键词筛选),右侧试听台写一句话(可加指令),逐个音色点「试听」现场合成;试听过的音色在清单上记下时长。可加入收藏、取消收藏、设为默认(直接写 `favorites.txt`),复刻音色还可在这里删除。
- **选中朗读**(仅 macOS):安装 `bailian-say` 入口、配置鼠标按键(OpenLogi,确认后自动改配置并备份)或快捷指令、试读与查看朗读日志,详见下文 **say**。
- **声音复刻**:四步向导。录音(准备事项、麦克风选择、录音稿;开录后整屏只留念稿、大号计时与电平表;也可选已有文件)→ 质检(先给结论,再列时长 / 音量 / 破音与波形)→ 试听(原声与复刻对比、自定义句子再试)→ 完成(设为默认 / 加入收藏 / 不收藏 / 删除重录)。
```bash
... run.py ui                      # 打开「开始」
... run.py ui --page voices        # 直接打开「选音色」,等同 pick-ui
... run.py ui --page clone         # 直接打开「声音复刻」,等同 clone-ui
... run.py ui --page say           # 直接打开「选中朗读」
```
- **模型切换**：展开顶部「默认模型」，选择 Flash、Next、Eleven v4 或 Eleven v4 Turbo 后保存；同步用于工作台试听及 `gen` / `script` / `preview` / `say`；声音复刻、`voices` / `fav` / `delete` 仍为 Flash 专属。Next 沿用北京地域 API Key，需要填写业务空间 ID（或设置优先级更高的 `SFM_WORKSPACE_ID`）与声音描述；参考[官方接口](https://help.aliyun.com/zh/model-studio/audio-generation-api)。不上传参考录音，不保证每次音色一致。提示词合计最多 3000 字符，普通场景音频最长 120 秒，1500 字长文可能无法完整生成；试听仍限制 200 字。先用短句试听，不要为尝试模型自动提交付费请求。
- 用户要挑音色、逐个试听比较 → `--page voices`;要复刻自己的声音 → `--page clone`;要管理音色(收藏、默认、删除复刻)→ `--page voices`。
- 它会一直运行到用户点顶栏的「完成」。宿主支持后台运行时(如 Claude Code)放到后台,不要轮询;不支持时(如 Pi)前台运行且**不设超时**,地址会先打印出来,命令在用户点「完成」后返回。启动后告诉用户「已在浏览器打开配音工作台(某一栏),操作完点右上角『完成』回到这里」。
- 进程退出时 stdout 打印 API key 状态(掩码)、本次创建的音色、试听了几个音色合成几次,以及「当前收藏」,据此向用户汇报。
- 浏览器没自动打开时,把输出里的 `http://127.0.0.1:…/?t=…#…` 地址给用户手动打开(token 只在本次有效)。
- 试听按次计费;同一音色、同一句子、同一指令在本次页面里只合成一次。页面里的删除自带二次确认,并会同时从收藏中移除,无需再问。

**status** / **key** —— `status` 检查依赖、ffmpeg、API key 与收藏;`key` 查看 key 掩码,`key --console` 在默认浏览器打开百炼控制台的 API Key 页,`key --clipboard` 保存剪贴板里刚复制的 key 并清空剪贴板,`key --stdin` 从标准输入读取。保存前都会向百炼校验,无效 key 不会覆盖已有文件。

### 按模型配置朗读长度

- 工作台顶部模型设置提供「当前模型的朗读字数上限」，每个模型独立保存到 `settings.json` 的 `read_limits`。未配置或旧配置按 1500 字处理；修改后点击「保存模型设置」，中键、快捷键与「选中朗读」试读都会读取对应模型的值。
- CLI 显式指定 `say --max N` 时覆盖该模型的本地配置，仍需满足安全范围：Flash 1～20000、Next 1～2800、Eleven v4 与 Turbo 各 1～2000。Next 为声音描述预留提示词长度，Eleven 使用插件保守的接口限制，不代表模型能力上限；增大字数不能解除输出时长限制。
- 字数在清理 Markdown 后计算；超出仍优先向前退到句末，必要时硬切并加省略号。整段生成后播放，不恢复自动分段。UI 的音色试听仍固定最多 200 字。

**say** —— **用户想「选中文字按一下就读出来」(鼠标按键、快捷键朗读)时用它**,仅 macOS。读入文字 → 去掉代码块与 Markdown 符号 → 超过当前模型的字数配置（未配置时 1500，`--max` 可覆盖）时优先在句末截断 → 整段一次合成,完成后播放;再次触发会结束上一次本地合成与播放，再处理当前选中的文字；新旧启动入口统一识别，所有模型共用进程间控制锁和播放锁，避免中键、热键并发播放。已提交到服务端的请求仍可能计费，不自动重试。也接受 `-v` / `--instruct` / `--emotion`,不给音色时用收藏第 1 个。输出与报错写到 `~/Library/Logs/bailian-tts-say.log`,失败弹系统通知。
```bash
... run.py say --install          # 生成 ~/.local/bin/bailian-say,并打印鼠标按键与快捷键的配置方法
echo "要读的文字" | ~/.local/bin/bailian-say
```
- **帮用户配置时默认后台运行 `ui --page say`**,打开工作台的「选中朗读」栏:一键安装 `bailian-say` 入口;鼠标按键选好 OpenLogi 设备和按键后,页面弹出确认(写明原来的动作),确认后先整份备份 `~/.config/openlogi/config.toml` 再只改那一个键,用户在菜单栏重开 OpenLogi 即生效;快捷指令给出分步说明与可复制的脚本;还能现场试读、看最近的朗读日志。页面里的确认就是用户同意,无需再问。
- 不方便用页面时运行 `say --install`,把它打印的配置转述给用户:**鼠标按键**(如 OpenLogi 的 `Workflow`:`bailian-say --save` → 按 `Cmd+C` → `bailian-say --clipboard`,会临时借用剪贴板,只还原纯文字;在 Ghostty、Orca 里 `Cmd+C` 复制不到时(如 Pi 全屏模式接管了鼠标),改读选中时已自动复制的文字)或**快捷指令**快速操作(文字作为 stdin 传给 `bailian-say`,再在系统设置里绑快捷键)。改第三方软件的配置前先备份并征得用户同意。
- `~/.local/bin/bailian-say` 通过标准库启动器使用同一虚拟环境，不依赖工作台服务。插件移动或升级后原路径失效时，回退到 Claude Code / Codex 插件缓存的最新副本；旧版入口升级后需运行 `run.py say --install` 更新一次。不要修改原有鼠标绑定。

**clone** —— 命令行复刻,适合用户已经有录音文件、或不方便用浏览器时。直接给**本地录音路径**(m4a/mp3/wav 等,如 macOS 语音备忘录导出的文件):脚本用 ffmpeg 转成 24kHz 单声道 wav、检查时长(5~60 秒,推荐 10~20 秒),上传到百炼免费临时存储,再提交复刻并等待音色可用。用户不需要自己的 OSS。已有公网 URL 时也可直接传 URL。录音要求:单人、无背景音乐和噪音、至少 5 秒连续清晰朗读:
```bash
... run.py clone ~/Desktop/我的录音.m4a --prefix ygd [--lang zh] [--denoise]
... run.py clone "https://..." --prefix ygd
```
成功后打印 `voice_id`(形如 `qwen-audio-3.1-tts-flash-ygd-<hex>`),之后 `-v <voice_id>` 使用,复刻音色同样支持指令。**每次调用都会新建一个音色**(账号上限 1000 个),不要重复提交。

**delete** —— 删除复刻音色:`... run.py delete <voice_id>`。**删除不可恢复,执行前先向用户确认。**

**fav** —— 管理用户的收藏音色,存在 `~/.config/bailian-tts/favorites.txt`(每行一个,按添加顺序,第 1 个即默认音色)。系统音色和本模型的复刻音色都能收藏;`voices` 列表里收藏的音色标 ★:
```bash
... run.py fav                      # 查看收藏
... run.py fav add longanwen_v3.1 longanlang_v3.1
... run.py fav rm longanlang_v3.1
```
用户说"收藏这个音色""以后默认用 X"时用 `fav add`;要换默认就先 `rm` 再按想要的顺序 `add`。

## 典型协作流程

0. `status` 自查;需要 onboarding 时按「开工前自查与首次引导」走完。
1. 用户给文案 + 想要的语气/音色。**用户没指定音色时,先 `fav` 看收藏**:只有 1 个就直接用;有多个时问用户用哪个,或用收藏音色各 `preview` 一句让用户选。收藏为空、或用户想多比较几个时,后台运行 `ui --page voices` 让用户在页面上逐个试听挑选;只想按条件缩小范围时用 `voices`。
2. `preview` 试听 1~2 个候选(音色 × 指令),让用户拍板。
3. 单段用 `gen`;多段/视频用 `script`,把 `all.wav` 和 `subtitles.srt` 交给剪辑工具。
4. 用户想在任意 App 里选中文字就朗读:后台运行 `ui --page say`,在页面上安装入口、配置鼠标按键或快捷键并试读。
5. 用户要用自己的声音:后台运行 `ui --page clone`,等用户点「完成」后汇报结果;用户已给出录音文件路径时可直接 `clone`。

## 排错

- 找不到 API key / `InvalidApiKey`:按「开工前自查与首次引导」重新创建并 `key --clipboard` 保存。key 必须是华北2(北京)地域创建的。

- `411`(`Engine error [411]: TTS speak operation failed`):音色不属于本模型。换 `voices` 列出的 `_v3.1` 音色,或为本模型重新 `clone`。
- 指令被拒或效果不明显:缩短指令、改成具体的声音特征描述;情绪切换优先用文本标签。
- 复刻失败:检查录音质量(单人、无背景音);有底噪时加 `--denoise`;用 URL 时确认无需鉴权即可下载。

## 边界

- 支持 Flash 音色配音、Eleven v4 / Turbo 固定音色配音，以及 Next 的文字描述声音配音；Next 的多人对话、参考录音、配乐与音效编排不在本技能内。Flash 的声音设计不在本技能内。
- 复刻他人声音须取得本人授权。
