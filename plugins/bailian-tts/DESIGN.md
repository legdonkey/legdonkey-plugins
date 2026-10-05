---
name: bailian-tts 复刻向导
description: 普通话水平测试考场式的声音复刻向导：一张朗读卡、一个考位、读完当场评定。
colors:
  exam-blue: "#1f3a5f"
  exam-ink: "#ffffff"
  exam-soft: "#c6d3e6"
  seat-grey: "#eef1f5"
  card-white: "#ffffff"
  rule-line: "#c9d3e0"
  ink: "#17212e"
  muted: "#4f5d70"
  pass: "#1f7a4d"
  pass-bg: "#e3f2ea"
  warn: "#8a5a00"
  warn-bg: "#fbf0d9"
  fail: "#b3261e"
  fail-bg: "#fbe4e2"
  band: "#4f9a72"
  band-soft: "#d6e8dd"
  focus: "#3b7dd8"
  exam-dark: "#3d6699"
  exam-soft-dark: "#dbe6f4"
  ground-dark: "#10161f"
  live-dot: "#ff5a4f"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "clamp(28px, 3.4vw, 42px)"
    fontWeight: 400
    lineHeight: 1.9
    letterSpacing: "0.02em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 2
    letterSpacing: "0.02em"
  verdict:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "20px"
    fontWeight: 700
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "19px"
    fontWeight: 600
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.7
  control:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "15px"
    fontWeight: 400
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
  stamp:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "14px"
    fontWeight: 700
    letterSpacing: "0.1em"
  scale:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "\"tnum\""
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  stamp: "2px"
  track: "4px"
  control: "6px"
  card: "8px"
  pill: "20px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  xxl: "32px"
components:
  exam-bar:
    backgroundColor: "{colors.exam-blue}"
    textColor: "{colors.exam-ink}"
    height: "56px"
    padding: "0 24px"
  button-primary:
    backgroundColor: "{colors.exam-blue}"
    textColor: "{colors.exam-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
  button-secondary:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
  button-danger:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.fail}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 20px"
  input:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  card:
    backgroundColor: "{colors.card-white}"
    rounded: "{rounded.card}"
  card-head:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "14px 24px"
  block:
    padding: "20px 24px"
  mark-pass:
    textColor: "{colors.pass}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "2px 10px 2px 11px"
  mark-warn:
    textColor: "{colors.warn}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "2px 10px 2px 11px"
  mark-fail:
    textColor: "{colors.fail}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "2px 10px 2px 11px"
  mark-na:
    textColor: "{colors.muted}"
    typography: "{typography.stamp}"
    rounded: "{rounded.stamp}"
    padding: "2px 10px 2px 11px"
---

# Design System: bailian-tts 复刻向导

## Overview

**Creative North Star: "朗读考位"**

复刻一段声音，就是参加一次普通话水平测试的「朗读短文」：顶部一条考务蓝考位条，卡座灰的地面上放一张纯白朗读卡，读完当场拿到一张评定表。整个世界只有一种字体、一种分隔方式（1px 细线）和一种结论语言（印章式文字标签），层级全部靠字号、字重和细线建立，不靠颜色块、阴影或渐变。

密度是「考务文件」级：信息分行、分格、逐项给结论，留白克制但不空。唯一的戏剧性时刻是开录：考位条收起为一枚红点与计时，须知与卡框全部退场，念稿放大到满屏，下方只剩电平刻度与计时刻度。录音期间页面上不存在任何与「读」和「听自己音量」无关的东西。

明确拒绝「顶部步骤条 + 居中卡片 + 蓝色按钮」的通用 SaaS 开通向导观感；进度以考位条右侧的文字「第 n 项 / 共 4 项」表达，不画步骤圆点。

**Key Characteristics:**
- 考务蓝考位条（56px）贯穿所有视图，是唯一的大面积色块。
- 纯白卡片 + 1px 细线分格：卡头、卡体分块、表格行、对比栏之间都是同一条线。
- 单一系统中文无衬线字体，层级只靠字号与字重。
- 评定结论用描边印章文字标签，颜色只在印章、电平和结论词上出现。
- 刻度条带「合格区间」：计时与电平都把建议范围直接画在轨道上。
- 亮暗双主题由同一组 CSS 自定义属性在 `prefers-color-scheme: dark` 下整体替换。

## Colors

一个冷静的考务蓝主色，配冷灰中性色，外加只服务于结论的三色语义组（合格绿、可用琥珀、需重录红）。

### Primary
- **考务蓝**（exam-blue）：考位条底色、主按钮底色、表单 `accent-color`、选区底色、链接与须知序号描边。暗色下由暗色考务蓝（exam-dark）接替，仍承担同样角色。
- **考位白字**（exam-ink）：考位条与主按钮上的文字。
- **考位浅蓝**（exam-soft）：考位条上的次要文字（步骤名、进度、计时数字）；暗色下由暗色考位浅蓝（exam-soft-dark）接替，并接管须知序号描边与文字链接色，因为暗色考务蓝在深底上对比不足。

### Neutral
- **卡座灰**（seat-grey）：页面地面，也用于音色编号代码框与音频控件底。暗色下由夜间卡座（ground-dark）接替。
- **朗读卡白**（card-white）：卡片、按钮次级底、输入框、刻度轨道底。暗色 `#182230`。
- **细线灰蓝**（rule-line）：全部 1px 分隔、卡框、输入框描边、次级按钮描边。暗色 `#2e3b4e`。
- **墨色**（ink）：正文与标题。暗色 `#e8edf4`。
- **说明灰**（muted）：卡头副信息、字段说明、提示、表头、刻度数字、「未检测」印章。暗色 `#a3b0c2`。

### Semantic
- **合格绿**（pass）：「合格」印章、结论词、电平「合适」状态填充与提示、计时刻度上方的「建议 10～20 秒」标注、成功消息。暗色 `#6fcf9b`。
- **可用琥珀**（warn）：「可用」印章、电平偏小、警告消息。暗色 `#e8b55a`。
- **需重录红**（fail）：「需重录」印章、电平过大、错误消息、危险按钮文字。暗色 `#f08a80`。
- **区间绿**（band）：计时刻度上 10～20 秒建议区间的实心填充与两条区间边线。暗色 `#3d8a5f`。
- **区间浅绿**（band-soft）：电平轨道上的合格区间底色，电平填充在其上方叠加。暗色 `#1f3b2c`。
- **录音红点**（live-dot）：录音中考位条上的 10px 圆点，是唯一不随亮暗切换的颜色，只在录音状态出现。
- **焦点蓝**（focus）：全局 `:focus-visible` 2px 描边。暗色 `#7aa9ec`。
- pass-bg / warn-bg / fail-bg 已定义为浅底色，但当前构建中印章为透明底，这三个值尚未被任何组件使用，保留作为语义组的配套底色。

### Named Rules
**The 一块蓝 Rule.** 大面积的考务蓝只出现在考位条和主按钮上。卡片、区块、表头都不铺色；层级交给细线和字号。

**The 颜色只给结论 Rule.** 绿、琥珀、红只用于评定结论（印章、结论词、电平状态、消息），从不用作装饰或分区底色；每处颜色旁边都有一个说明状态的文字词（合格 / 可用 / 需重录 / 太小 / 合适 / 太大），不只靠颜色表达状态。

## Typography

**Body Font:** 系统中文无衬线栈（-apple-system / PingFang SC / Hiragino Sans GB / Microsoft YaHei / Noto Sans CJK SC，回退 sans-serif）
**Label/Mono Font:** ui-monospace / SFMono-Regular / Menlo，仅用于音色编号这一机器值

**Character:** 一种字体从考位条用到念稿，像一份统一印刷的考务材料；层级只靠字号和字重的阶梯，不引入展示字体。

### Hierarchy
- **Display**（400，clamp(28px, 3.4vw, 42px)，行高 1.9，字距 .02em）：只用于录音中的全屏念稿。
- **Headline**（400，22px，行高 2，字距 .02em；窄屏 19px）：朗读卡内的正文朗读稿。
- **Verdict**（700，20px）：评定表总评结论词（建议重读 / 可以提交 等），按结论着色。
- **Title**（600，19px）：卡头标题、须知标题、区块小标题。
- **Body**（400，16px，行高 1.7）：页面基础正文。
- **Control**（400，15px）：按钮、输入框、表格、须知条目、电平提示句。考位条标题同为 15px 但用 600 与 .02em 字距。
- **Label**（400，14px）：卡头副信息、字段说明、提示、消息、考位条进度。
- **Stamp**（700，14px，字距 .1em）：印章标签文字。
- **Scale**（400，12px，等宽数字）：刻度数字、区间标注与须知序号；电平图例用 Label 的 14px。

### Named Rules
**The 一种字体 Rule.** 除音色编号用等宽字体外，全页只用系统中文无衬线栈。不要为了「有设计感」引入衬线或展示字体。

**The 数字对齐 Rule.** 计时、进度、时长值一律 `font-variant-numeric: tabular-nums`，数字跳动时不抖。

## Layout

内容区最大宽 1120px，左右 24px、上 32px、下 64px 内边距，居中。朗读视图宽屏为两栏网格：左栏须知与麦克风选择（`minmax(240px, 1fr)`），右栏朗读卡（2fr），栏距 32px，顶部对齐。评定表与试听视图是居中的单卡，最大宽 760px；完成视图单卡最大宽 640px，距顶 6vh。

间距节奏以 8 / 12 / 16 / 20 / 24 / 32px 为主：卡头 14px 24px，区块 20px 24px，表格单元 14px 24px，按钮组间距 10px。

断点只有一个：760px 以下单栏，考位条与内容左右内边距收到 16px，所有卡内横向内边距收到 16px；须知折叠成卡片上方一个带细框的 `details` 摘要（「（3 条，点开查看）」）；试听对比由左右两栏改为上下堆叠，分隔线由竖线改为横线；考位条隐藏步骤名只留「声音复刻」。

录音状态改变布局：内容宽收到 960px，顶部留 6vh，网格变单栏，须知隐藏。

## Elevation & Depth

完全扁平。整套系统没有任何 `box-shadow`、渐变或光晕；深度只有两层：卡座灰地面上放朗读卡白卡片，用 1px 细线勾边。考位条用 `position: sticky` 贴顶，靠色块而非阴影与内容分开。

### Named Rules
**The 细线即结构 Rule.** 所有分隔都是 1px `rule-line` 实线：卡框、卡头底线、区块间线、表格行线、对比栏竖线。需要再分一层时加一条线，不加阴影、不加底色。

## Shapes

小圆角、方正为主，按物件大小分级：印章 2px（接近直角的盖章感），计时与电平刻度轨道 4px，按钮与输入框 6px，卡片 8px，音频控件 20px 胶囊。须知序号与录音红点是正圆。印章用 1.5px `currentColor` 描边，是全系统唯一比 1px 粗的线。

## Components

### Buttons
朴素、像考场里的实体按键。
- **Shape:** 6px 圆角，10px 20px 内边距，15px 字，可在文字前带 18px 线性 SVG 图标（麦克风、停止、重读、提交箭头），间距 8px。
- **Primary:** 考务蓝底、白字、600 字重。每个区块只有一个主按钮，且主按钮跟随评定结论：结论建议重读时「重新朗读」升为主按钮，「提交复刻」降为次级。
- **Secondary:** 卡片白底、墨色字、1px 细线描边；悬停时描边变考务蓝。
- **Danger:** 次级按钮外观，文字用需重录红（「不满意，删除后重录」），删除动作另有确认。
- **Hover / Focus:** 主按钮悬停 `brightness(1.12)`；背景与描边 .15s 过渡；焦点为 2px 焦点蓝描边、2px 偏移。禁用为 45% 透明度。
- **Link-style:** 无底无框的考务蓝下划线文字（偏移 3px，14px），用于「选择文件」这类次要入口。

### Cards / Containers
- **Corner Style:** 8px。
- **Background:** 朗读卡白，放在卡座灰上。
- **Shadow Strategy:** 无，见 Elevation & Depth。
- **Border:** 1px 细线。
- **Anatomy:** 卡头（左侧 19px 600 标题，右侧 14px 说明灰副信息或印章，底部细线，14px 24px）→ 若干区块（20px 24px，区块之间细线，最后一块无线）。评定表、试听、完成都用同一套卡头 + 区块结构。

### Inputs / Fields
- **Style:** 卡片白底，1px 细线描边，6px 圆角，9px 12px 内边距，15px 字；字段说明放在框上方，14px 说明灰。
- **Focus:** 全局焦点蓝 2px 描边；复选框与表单控件着色通过 `accent-color` 跟随考务蓝。
- **代码值:** 音色编号放在卡座灰底、细线描边的等宽代码框里，可整段选中；窄屏换行而非裁切。

### Navigation
- **考位条:** 56px 高、考务蓝底、贴顶。左侧「声音复刻 · 步骤名」（15px 600，步骤名用考位浅蓝 400），右侧「第 n 项 / 共 4 项」文字进度（当前项加粗白字）。录音中左右内容隐藏，改为录音红点（10px 圆）+「录音中」+ 计时。

### Stamp（印章标签）
评定系统的签名件。透明底、1.5px 当前色描边、2px 圆角、14px 700、字距 .1em。四种状态：合格（合格绿）、可用（可用琥珀）、需重录（需重录红）、未检测（说明灰）。也用于完成视图卡头的结果标签（「已设为默认」等）。

### Grade Sheet（评定表）
三行表格：项目名（说明灰 600，22% 宽）/ 数值（等宽数字）/ 印章 + 可选一行提示。行间细线；各行以 .4s 从左 6px 淡入，依次延迟 .08s。表下是总评行：Verdict 字号的着色结论词 + 一句说明，窄屏改为上下排列。

### Timer Scale（计时刻度）
0–30 秒的 8px 细轨道，10～20 秒区间以区间绿实心填出，两端各有一条 20px 高的区间边线，区间上方标注「建议 10～20 秒」（合格绿 12px），下方刻度 0 秒 / 10 / 20 / 30 秒。计时进度以考务蓝（暗色为浅蓝 `#dbe7fb`）从左 `scaleX` 增长并覆盖在区间之上。

### Level Meter（电平刻度）
只在录音中出现。10px 细轨道，合格区间（约 60%–86.7%）用区间浅绿铺底，电平填充按状态着色：偏小琥珀、合适绿、过大红，.08s 线性跟随。下方图例「太小 / 合适 / 太大」，当前状态那一项加粗并着色；再下方一句状态提示文字（并以 `aria-live` 播报）。

### Recording State（录音全屏）
开录时 `body.recording`：考位条变为红点计时，须知、卡框、卡头、文件入口全部退场，念稿升为 Display 字号，下方依次是电平刻度、计时刻度和「停止」主按钮。

## Do's and Don'ts

### Do:
- **Do** 用 1px `rule-line` 细线完成所有分隔与分组，需要更多层级时再加一条线。
- **Do** 每个评定结论都同时给出文字词与颜色（合格 / 可用 / 需重录 / 未检测），并用印章标签呈现。
- **Do** 把建议范围直接画在刻度轨道上（计时 10～20 秒、电平合格区间），让用户看位置就知道好不好。
- **Do** 新增视图沿用卡头 + 区块的卡片结构，并在考位条右侧以文字更新「第 n 项 / 共 4 项」。
- **Do** 每个区块只保留一个主按钮，并让它指向评定推荐的下一步。
- **Do** 新增颜色时在 `:root` 与 `prefers-color-scheme: dark` 两处同时定义，保持 WCAG AA 对比度。

### Don't:
- **Don't** 加 `box-shadow`、渐变或光晕；本系统是纯平的。
- **Don't** 引入第二种正文或展示字体；等宽字体只给机器值（音色编号）。
- **Don't** 用图标代替评定结论；印章是文字，按钮上的线性 SVG 图标只做动作提示。
- **Don't** 画顶部步骤条或步骤圆点；进度只用考位条上的文字。
- **Don't** 让语义色（绿 / 琥珀 / 红）出现在非结论位置，例如装饰性底色或分区色块。
- **Don't** 在录音状态下显示念稿、电平、计时和停止按钮以外的任何内容。
