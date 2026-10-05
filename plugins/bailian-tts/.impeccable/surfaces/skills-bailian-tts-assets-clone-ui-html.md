---
version: 1
slug: "skills-bailian-tts-assets-clone-ui-html"
primary_target: "skills/bailian-tts/assets/clone_ui.html"
related_targets: []
---

## Scope

复刻向导页 `skills/bailian-tts/assets/clone_ui.html`，visitor mode：Operate。用户（作者本人与不懂技术的业务同事）在电脑前一次录出干净可用的声音并完成复刻、试听、收藏。功能与接口保持不变（见 PRODUCT.md）。用户明确不要：通用 SaaS 开通向导的模板感、过于技术化的信息、抢录音注意力的花哨效果、录完不知道好不好。用户要求：录音时全屏只留念稿和电平；配色要有高级感，「像是在很贵的录音室录音」（用户指定方向，取代首轮的普通话考场方向），配色选定「石墨香槟」。

## Direction contract

THESIS: 复刻声音就是进一间很贵的录音棚录一条：灯光压暗、只亮念稿和表头，录完当场质检。拒绝「顶部步骤条 + 居中卡片 + 蓝色按钮」的开通向导，也拒绝把调音台、推子画到页面上的道具感。

OWN-WORLD: 只做暗色，场景就是暗下来的录音棚。石墨黑 #111113 的房间底色，#1A1B1E 的面板，1px #2C2E33 发丝线是唯一分隔；象牙白 #ECE8E1 正文、灰烬 #A8A196 说明；香槟金 #C9B27C 只给主操作、建议区间与序号；合格 / 偏小 / 破音用柔和的绿 / 琥珀 / 珊瑚。系统中文无衬线一种字体，标题细字重加宽字距，所有数字等宽。无渐变、无投影光晕。

STORY: 进门先看录音前准备与录音稿；开录后整屏只剩念稿、REC 指示、大号计时和刻度电平；停止后质检单逐项给出时长、音量、破音的结论与总评，决定提交或重录；提交后试听原声与复刻对比；最后设为默认或收藏。

FIRST VIEWPORT: 顶部 64px 透明顶栏压在房间底色上，下方一条发丝线：左「声音复刻 · 录音」，右等宽「01 / 04」。主体两栏（宽屏）：左 1/3 录音前准备三条与麦克风选择；右 2/3 录音稿面板，大字正文，面板底部是带 10～20 秒香槟金区间的计时刻度与香槟金主按钮「开始录音」。窄屏单栏，准备事项折叠在面板上方。

FORM: 用户指定方向（高端录音棚，石墨香槟），取代 seed key c529637d 首轮所选的普通话考场方向。签名动作：开始录音后顶栏收起为红点「REC 录音中」，念稿放大占满屏幕，上方是细体大号计时，下方是带刻度、香槟金合格区的电平表与一行文字状态；停止后质检单逐行出现。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
