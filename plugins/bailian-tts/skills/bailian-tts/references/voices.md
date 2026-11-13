# qwen-audio-3.1-tts-flash / qwen-audio-3.1-tts-plus 音色、指令与复刻

**权威音色列表(以它为准,不要靠探测):**
https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list

快照在 [voices.json](voices.json),`voices` 命令直接读它。音色名以 `_v3.1` 结尾,区分大小写;同名不同后缀的音色(如 3.0 系列的 `longanhuan_v3.6`)属于别的模型,不能混用。

## 模型与计费

- Flash `qwen-audio-3.1-tts-flash` 支持快照中的全部 68 个系统音色。
- Plus `qwen-audio-3.1-tts-plus` 只支持标有 `plus: true` 的 4 个多语种与方言旗舰系统音色：龙安欢 `longanhuan_v3.1`、龙安灵心 `longanlingxin_v3.1`、龙安风悦 `longanfengyue_v3.1`、许南川 `xunanchuan_v3.1`。其余 Flash 系统音色不能用于 Plus。
- Plus 使用北京地域百炼 API Key，合成按输入文本字符计费，价格为 **1.4 元/万字符**，不按音频时长计费；实际以官方账单为准。Flash / Plus 单次正文均限制 20000 字符，长文增加等待时间与费用，不自动拆段或重试。

## 音色分组（Flash 全部；Plus 仅多语种与方言组）

| 分组 | 数量 | 语言 | 说明 |
| --- | --- | --- | --- |
| 多语种与方言 | 4 | 中文 + 上海话/广东话/东北话/重庆话/陕西话/云南话/宁波话/甘肃话 + 日韩法德葡意越印尼语 | `longanhuan_v3.1`、`longanlingxin_v3.1`、`longanfengyue_v3.1`(女)、`xunanchuan_v3.1`(男);用指令切换方言 |
| 精品中文 | 22 | 仅普通话 | 广告、有声书、旁白、新闻、客服等,`voices` 里有声线特质和适用场景 |
| 精品英文 | 15 | 仅英文 | 英式/美式口音 |
| 其他系统 | 27 | 中文 | 角色音、童声、社交陪伴、直播带货等 |

## 指令(instruction)

- 系统音色与复刻音色都接受**任意自然语言**,不需要固定句式。
- 上限 100 字符:汉字(含繁体、日文汉字、韩文汉字)计 2,其它字符(标点、字母、数字、假名、谚文)计 1。
- 写法:具体而非模糊(「低沉」「语速偏快」而不是「好听」);多维组合(性别、年龄、音调、语速、情感、用途);描述声音特质而非模仿具体人物。
- 示例:「沉稳的中年女声,语速偏慢,适合新闻播报」「年轻活泼的女声,语速较快,语调上扬,适合介绍时尚产品」「请用河南话表达。」

## 文本内标签

写在待合成文本里。**控制类**标签作用于其后所有文本,直到下一个控制类标签(或长句被自动切分);**富语言类**标签在当前位置插入一段拟声,不影响前后情感。

- 控制类:`[sad]` 悲伤、`[amazed]` 惊叹、`[deep and loud shouting]` 深沉大声呐喊、`[trembling]` 颤抖、`[angry]` 愤怒、`[excited]` 兴奋、`[sarcastic]` 讽刺、`[curious]` 好奇、`[like dracula]` 低沉阴森、`[bored]` 无聊、`[tired]` 疲惫、`[scornful]` 轻蔑、`[shouting]` 大喊、`[asmr]` 轻柔耳语、`[panicked]` 恐慌、`[mischievously]` 调皮、`[empathetic]` 共情、`[whispers]` 耳语、`[reluctantly]` 不情愿、`[crying]` 哭泣、`[serious]` 严肃、`[very slowly]` 非常缓慢、`[very fast]` 非常快速
- 富语言类:`[gasp]` 倒吸一口气、`[sighing]` 叹息、`[clears throat]` 清嗓、`[giggles]` 咯咯笑、`[laughing]` 大笑、`[cough]` 咳嗽、`[snorts]` 哼声
- 示例:`[serious]请注意安全事项。[excited]好了,现在让我们开始吧![laughing]`

`script` 生成字幕时会去掉方括号标签。

## 参数

语速 `speech_rate` 与音调 `pitch_rate` 取 `[0.5, 2.0]`,音量 `volume` 取 `[0, 100]`,默认 1.0 / 1.0 / 50,脚本已钳制。调用走 `dashscope.audio.tts_v2.SpeechSynthesizer`,默认 `dashscope.aliyuncs.com` 端点即可;官方示例里的 `{WorkspaceId}` 专属域名是可选的性能优化。

## 声音复刻

- 接口:`dashscope.audio.tts_v2.VoiceEnrollmentService`(`create_voice` / `list_voices` / `query_voice` / `delete_voice`),`target_model` 为 `qwen-audio-3.1-tts-flash` 或 `qwen-audio-3.1-tts-plus`，必须与合成时一致。默认仅跟随工作台 Flash / Plus；默认为 Next / Eleven 时不显示百炼复刻步骤，CLI 未指定 `--model` 则报错，可用 `clone --model` 显式指定目标。Plus 提供抗噪能力更强的独立声音复刻，不能复用 Flash 的复刻音色，反向也不能混用。
- 录音:推荐 10~20 秒,最长 60 秒,至少 5 秒连续清晰朗读;WAV(16bit)/MP3/M4A,≥16kHz,≤10MB;单人、无背景音乐和噪音。
- 上传:接口只接受 URL,不接受本地文件或 base64 Data URI。脚本对本地录音的处理是:ffmpeg 转码 → `dashscope.utils.oss_utils.OssUtils.upload(model="voice-enrollment")` 上传到百炼免费临时存储(48 小时有效,文件与 `voice-enrollment` 和本账号绑定)→ 得到 `oss://` 地址 → 创建音色时带请求头 `X-DashScope-OssResourceResolve: enable`。临时文件过期不影响已创建的音色。也可直接传公网可访问且无需鉴权的 http(s) URL(此时不需要该请求头)。
- 临时存储文档:https://help.aliyun.com/zh/model-studio/get-temporary-file-url
- 可选参数:`language_hints`(录音语种,默认 `zh`)、`max_prompt_audio_length`(参考音频最大时长 3~30 秒,默认 10)、`enable_preprocess`(降噪/增强/音量规整,有底噪时开)。
- 音色 ID：`{target_model}-{prefix}-{唯一标识}`，例如 `qwen-audio-3.1-tts-plus-ygd-<hex>`；`prefix` 仅数字和字母，≤10 字符。切换合成模型必须重新复刻；系统音色共享不代表复刻音色共享。
- 配额与费用:创建免费;每个账号的复刻音色(含其它模型)共享 1000 个上限,满了需手动删除;1 年未用于合成会被自动删除。
- 文档:https://help.aliyun.com/zh/model-studio/voice-cloning-user-guide 、https://help.aliyun.com/zh/model-studio/voice-clone-python-sdk

## 独立收藏与默认音色

- Flash 收藏：`~/.config/bailian-tts/favorites.txt`；Plus 收藏：`~/.config/bailian-tts/plus-favorites.txt`。每行一个音色，第 1 个为该模型默认音色，空收藏使用 `longanhuan_v3.1`。
- Plus 文件不存在时，只读筛选 Flash 收藏中的 4 个旗舰系统音色作为初始收藏，不继承 Flash 复刻音色，也不创建文件。首次增删或设默认后独立落盘，不改 Flash 收藏；Plus 文件存在但为空时不再继承。
- `voices` / `fav` / `clone` 仅跟随默认 Flash / Plus，可用 `--model` 显式指定；默认为 Next / Eleven 且未指定目标时直接报错，不会操作 Flash。文本合成仍只跟随保存的默认模型。
- 各模型使用独立配置面板与专属界面。Next 只显示声音描述试听，不加载百炼音色目录或收藏；Eleven 只显示自己的 Key、音色与收藏。本地复刻页只供 Flash / Plus 使用，Next / Eleven 下显示本模型说明与切换入口，不显示 Flash 录音界面。状态与关闭汇总按当前模型展示，不夹带 Flash 收藏。

## 常见报错

- **411**(`InvalidParameter` + `Engine error [411]: TTS speak operation failed`):音色不属于本模型。
- 复刻失败:录音不合规;或直接传的 URL 需要鉴权、无法下载;或 `oss://` 地址缺少 `X-DashScope-OssResourceResolve: enable` 请求头。

文档:https://help.aliyun.com/zh/model-studio/realtime-tts-user-guide
