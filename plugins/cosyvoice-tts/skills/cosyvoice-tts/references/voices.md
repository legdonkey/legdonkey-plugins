# CosyVoice 音色与 Instruct 对照

**权威完整列表(以它为准,不要靠探测):**
https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list

CosyVoice 音色很多(v3-flash 有 80+,涵盖客服/有声书/方言/多语种/带货等场景),但**支持 Instruct 的只有少数几个**。本技能聚焦 Instruct,所以下面只列支持 Instruct 的组合;想用其它普通音色,直接查上面官方页拿 voice 名即可。

## 支持 Instruct 的组合(实测)

默认模型 **`cosyvoice-v3-flash`**,实测带 Instruct 可用的音色:

| 模型 | 音色 | 性别 | 备注 |
| --- | --- | --- | --- |
| `cosyvoice-v3-flash` | `longanyang`(龙安洋) | 男 | 实测 Instruct 可用 |
| `cosyvoice-v3-flash` | `longanhuan`(龙安欢) | 女 | 实测 Instruct 可用(**默认音色**) |
| `cosyvoice-v3-flash` | `longhuhu_v3`(龙呼呼) | 女 | 实测 Instruct 可用 |

> 注 1:官方表给 v3-flash 标了 4 个 Instruct 音色,但 `longanhuan_v3` 实测带 instruction 调用会失败,故不收录。
> 注 2:`cosyvoice-v3-plus` 上 `longanyang`/`longanhuan` 也支持 Instruct;本技能默认用 v3-flash,需要时可 `-m cosyvoice-v3-plus`。

## Instruct 用法

**情感值(emotion,只能用这 7 个)**:`neutral`、`happy`、`angry`、`sad`、`surprised`、`fearful`、`disgusted`

**四种指令句式**(脚本会自动拼,手写也按这个格式,否则报 428):

| 类型 | 句式 | 例 |
| --- | --- | --- |
| 情感 | `你说话的情感是<情感>。` | `你说话的情感是happy。` |
| 场景+情感 | `你正在进行<场景>，你说话的情感是<情感>。` | `你正在进行直播带货，你说话的情感是happy。` |
| 角色+情感 | `你说话的角色是<角色>，你说话的情感是<情感>。` | `你说话的角色是客服，你说话的情感是neutral。` |
| 身份+情感 | `你正在以一个<身份>的身份说话，你说话的情感是<情感>。` | `你正在以一个新闻主播的身份说话，你说话的情感是neutral。` |

对应脚本选项:`--emotion` 必填;`--scene` / `--role` / `--identity` 三选一与之组合;或 `--instruct` 直接给整句。

## 常见报错

- **418**:模型 + 音色组合无效(同名音色换了模型)。→ 换音色或换模型。
- **428**:带了 Instruct 但音色不支持 Instruct,或指令句式/情感值不合规。→ 用上表组合 + 规定句式 + 7 个情感值之一。

## 参数范围与文档

官方 SDK 文档确认:**Instruct 仅 `cosyvoice-v3-flash` 与 `cosyvoice-v3-plus` 支持**(`cosyvoice-v3.5-plus`/`v3.5-flash`/`v2`/`v1` 不支持 Instruct)。取值范围:语速 `speech_rate` 与音调 `pitch_rate` 均 `[0.5, 2.0]`,音量 `volume` `[0, 100]`,默认各为 1.0 / 1.0 / 50。脚本已对超范围值做钳制。

- SDK 文档:https://help.aliyun.com/zh/model-studio/cosyvoice-python-sdk
- TTS SDK 文档:https://help.aliyun.com/zh/model-studio/cosyvoice-tts-python-sdk

## 声音复刻(自定义音色,不在本技能脚本内)

复刻出的音色 id 形如 `cosyvoice-v2-ygdap-xxxx`,用法和预置音色一样(把 voice 换成该 id、model 用对应版本)。复刻流程需要:录样音 → 传到 OSS 拿公网 URL → `VoiceEnrollmentService.create_voice(target_model, prefix, url)` → 得到 voice_id。需要时单独做。
