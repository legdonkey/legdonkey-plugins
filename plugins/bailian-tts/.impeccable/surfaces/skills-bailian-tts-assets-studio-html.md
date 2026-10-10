---
version: 1
slug: "skills-bailian-tts-assets-studio-html"
primary_target: "skills/bailian-tts/assets/studio.html"
related_targets: []
---

## Scope

配音工作台 `skills/bailian-tts/assets/studio.html`，visitor mode：Operate。由 `tts.py ui` 在 127.0.0.1 提供，顶栏四栏：开始（首次引导：功能介绍、运行环境、创建并保存 API Key）、选音色、声音复刻、选中朗读（仅 macOS：安装入口、OpenLogi 按键确认后自动写入、快捷指令步骤、试读与日志）；用户要求三者是同一个页面，以后管理音色、复刻都打开它。首次引导由助手配合：在默认浏览器打开百炼控制台 API Key 页并把操作交给用户，用户复制 key 后读剪贴板保存。三栏共用 DESIGN.md 的压暗录音棚世界，不另起视觉方向；以下是选音色与声音复刻两栏各自的方向约定。

## 声音复刻栏

### Scope

复刻向导页 `skills/bailian-tts/assets/clone_ui.html`，visitor mode：Operate。用户（作者本人与不懂技术的业务同事）在电脑前一次录出干净可用的声音并完成复刻、试听、收藏。功能与接口保持不变（见 PRODUCT.md）。用户明确不要：通用 SaaS 开通向导的模板感、过于技术化的信息、抢录音注意力的花哨效果、录完不知道好不好。用户要求：录音时全屏只留念稿和电平；配色要有高级感，「像是在很贵的录音室录音」（用户指定方向，取代首轮的普通话考场方向），配色选定「石墨香槟」。

### Direction contract

THESIS: 复刻声音就是进一间很贵的录音棚录一条：灯光压暗、只亮念稿和表头，录完当场质检。拒绝「顶部步骤条 + 居中卡片 + 蓝色按钮」的开通向导，也拒绝把调音台、推子画到页面上的道具感。

OWN-WORLD: 只做暗色，场景就是暗下来的录音棚。石墨黑 #111113 的房间底色，#1A1B1E 的面板，1px #2C2E33 发丝线是唯一分隔；象牙白 #ECE8E1 正文、灰烬 #A8A196 说明；香槟金 #C9B27C 只给主操作、建议区间与序号；合格 / 偏小 / 破音用柔和的绿 / 琥珀 / 珊瑚。系统中文无衬线一种字体，标题细字重加宽字距，所有数字等宽。无渐变、无投影光晕。

STORY: 进门先看录音前准备与录音稿；开录后整屏只剩念稿、REC 指示、大号计时和刻度电平；停止后质检单逐项给出时长、音量、破音的结论与总评，决定提交或重录；提交后试听原声与复刻对比；最后设为默认或收藏。

FIRST VIEWPORT: 顶部 64px 透明顶栏压在房间底色上，下方一条发丝线：左「声音复刻 · 录音」，右等宽「01 / 04」。主体两栏（宽屏）：左 1/3 录音前准备三条与麦克风选择；右 2/3 录音稿面板，大字正文，面板底部是带 10～20 秒香槟金区间的计时刻度与香槟金主按钮「开始录音」。窄屏单栏，准备事项折叠在面板上方。

FORM: 用户指定方向（高端录音棚，石墨香槟），取代 seed key c529637d 首轮所选的普通话考场方向。签名动作：开始录音后顶栏收起为红点「REC 录音中」，念稿放大占满屏幕，上方是细体大号计时，下方是带刻度、香槟金合格区的电平表与一行文字状态；停止后质检单逐行出现。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 选音色栏

### Scope

选音色页 `skills/bailian-tts/assets/pick_ui.html`，visitor mode：Operate。由 `tts.py pick-ui` 在 127.0.0.1 提供。用户（作者本人与业务同事）在 qwen-audio-3.1-tts-flash 的 68 个系统音色和本模型可用的复刻音色里，用同一句话逐个试听、对比，挑出收藏与默认音色。用户确认：左列表 + 右试听台；不用官方样音（保持零外部资源），全部现场合成，同一音色同一句子在本次会话里只合成一次；包含复刻音色。风格与 clone-ui 保持一致（压暗录音棚、石墨香槟、仅暗色），不新增视觉世界。

### Direction contract

THESIS: 选音色就是在录音棚里试一轮演员：同一句台词让候选者依次念，场记单上记下每一条 take。拒绝「音色卡片网格 + 每张卡一个播放键」的素材库式陈列。

OWN-WORLD: 沿用 DESIGN.md：石墨房间底、发丝线分行、象牙白正文与灰烬说明；唯一的面板是右侧试听台；香槟金只给主操作「试听」、播放键、收藏序号；系统中文无衬线，标题 300 宽字距，时长与计数等宽。

STORY: 先在顶部写好要试的那句话（可加指令），然后在左侧清单上下移动，每个音色按一次「试听」，听完的音色在清单上留下这条 take 的时长；满意的加入收藏或设为默认，最后点「完成」回到对话。

FIRST VIEWPORT: 64px 顶栏「选音色 · 试听台」，右侧等宽「已收藏 0N」与次级按钮「完成」。主体两栏：左 1fr 是筛选行（分组切换、性别、搜索）与发丝线分行的音色清单；右 1.15fr 是贴顶的试听台面板：音色名与编号、特质与适用、试听句子与指令、自绘播放器、香槟金主按钮「试听」、收藏与设为默认。窄屏试听台在上、清单在下。

FORM: 用户锁定的结构，豁免 concept-seed（无 seed key）。豁免依据是用户在结构化提问中的原文回答：「1. 选音色页的版面结构用哪种？」=「左列表 + 右试听台 (Recommended)」；用户另有要求「ui界面要参考插件中的impeccable配置」「跟clone-ui风格保持一致」，世界沿用 DESIGN.md，不另起视觉方向。签名动作：场记单——试听过的音色在清单行右侧用象牙白等宽数字记下这条 take 的时长；正在播放的那一行，底部发丝线变成象牙白播放进度。试听台自上而下：要试的那句话（剧本字型）与指令 → 音色名与特质 → 播放器与「试听」→ 收藏、设为默认与编号。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
