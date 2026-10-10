---
version: 1
slug: "skills-bailian-tts-assets-pick-ui-html"
primary_target: "skills/bailian-tts/assets/pick_ui.html"
related_targets: []
---

## Scope

选音色页 `skills/bailian-tts/assets/pick_ui.html`，visitor mode：Operate。由 `tts.py pick-ui` 在 127.0.0.1 提供。用户（作者本人与业务同事）在 qwen-audio-3.1-tts-flash 的 68 个系统音色和本模型可用的复刻音色里，用同一句话逐个试听、对比，挑出收藏与默认音色。用户确认：左列表 + 右试听台；不用官方样音（保持零外部资源），全部现场合成，同一音色同一句子在本次会话里只合成一次；包含复刻音色。风格与 clone-ui 保持一致（压暗录音棚、石墨香槟、仅暗色），不新增视觉世界。

## Direction contract

THESIS: 选音色就是在录音棚里试一轮演员：同一句台词让候选者依次念，场记单上记下每一条 take。拒绝「音色卡片网格 + 每张卡一个播放键」的素材库式陈列。

OWN-WORLD: 沿用 DESIGN.md：石墨房间底、发丝线分行、象牙白正文与灰烬说明；唯一的面板是右侧试听台；香槟金只给主操作「试听」、播放键、收藏序号；系统中文无衬线，标题 300 宽字距，时长与计数等宽。

STORY: 先在顶部写好要试的那句话（可加指令），然后在左侧清单上下移动，每个音色按一次「试听」，听完的音色在清单上留下这条 take 的时长；满意的加入收藏或设为默认，最后点「完成」回到对话。

FIRST VIEWPORT: 64px 顶栏「选音色 · 试听台」，右侧等宽「已收藏 0N」与次级按钮「完成」。主体两栏：左 1fr 是筛选行（分组切换、性别、搜索）与发丝线分行的音色清单；右 1.15fr 是贴顶的试听台面板：音色名与编号、特质与适用、试听句子与指令、自绘播放器、香槟金主按钮「试听」、收藏与设为默认。窄屏试听台在上、清单在下。

FORM: 用户锁定的结构，豁免 concept-seed（无 seed key）。豁免依据是用户在结构化提问中的原文回答：「1. 选音色页的版面结构用哪种？」=「左列表 + 右试听台 (Recommended)」；用户另有要求「ui界面要参考插件中的impeccable配置」「跟clone-ui风格保持一致」，世界沿用 DESIGN.md，不另起视觉方向。签名动作：场记单——试听过的音色在清单行右侧用象牙白等宽数字记下这条 take 的时长；正在播放的那一行，底部发丝线变成象牙白播放进度。试听台自上而下：要试的那句话（剧本字型）与指令 → 音色名与特质 → 播放器与「试听」→ 收藏、设为默认与编号。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
