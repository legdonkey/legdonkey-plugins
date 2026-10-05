---
version: 1
slug: "skills-bailian-tts-assets-clone-ui-html"
primary_target: "skills/bailian-tts/assets/clone_ui.html"
related_targets: []
---

## Scope

复刻向导页 `skills/bailian-tts/assets/clone_ui.html`，visitor mode：Operate。用户（作者本人与不懂技术的业务同事）在电脑前一次录出干净可用的声音并完成复刻、试听、收藏。功能与接口保持不变（见 PRODUCT.md）。用户明确不要：通用 SaaS 开通向导的模板感、过于技术化的信息、抢录音注意力的花哨效果、录完不知道好不好。用户要求：录音时全屏只留念稿和电平。

## Direction contract

THESIS: 录一段复刻用的声音，就是参加一次普通话水平测试的「朗读短文」：一张朗读卡、一个考位、读完当场评定。拒绝「顶部步骤条 + 居中卡片 + 蓝色按钮」的开通向导。

OWN-WORLD: 考务蓝 #1F3A5F 承担整条考位信息条与主按钮；卡座灰 #EEF1F5 地；朗读卡纯白，1px #C9D3E0 细框、卡头一行「朗读作品」与建议用时；评定用「合格 / 需重录」两档印章式文字标签，不用图标堆砌。正文与标签只用系统中文无衬线一种字体，字号对比分层；所有分隔为 1px 细线，无渐变、无投影光晕。

STORY: 进入页面先看到考场须知与朗读卡，知道要读什么、怎么读；开录后整屏只剩念稿与电平；停止后评定表逐项给出时长、音量、破音的结论与一句总评，决定提交或重读；提交后试听原声与复刻对比；最后设为默认或收藏。

FIRST VIEWPORT: 顶部 56px 考务蓝考位条：左侧「声音复刻 · 朗读录音」，右侧以文字显示「第 1 项 / 共 4 项 朗读」。主体两栏（宽屏）：左 1/3 是考场须知三条（环境、距离、语气）与麦克风选择；右 2/3 是朗读卡，卡内大字正文，卡底一条计时刻度（10–20 秒区间标出）与主按钮「开始朗读」。窄屏单栏，须知折叠在卡片上方。

FORM: 普通话水平测试考场与朗读卡（自有候选第 1 位，作为 IMPECCABLE’S PICK 被用户选中），seed key c529637d。签名动作：开始朗读后朗读卡展开为全屏念稿（考位条收起为一枚红色「录音中」与计时），电平以一条带合格区间的细刻度贴在念稿下方；停止后评定表逐行出现。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
