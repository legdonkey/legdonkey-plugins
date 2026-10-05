---
name: bailian-tts 复刻向导
description: 灯光压暗的高端录音棚：只亮念稿与表头，录完当场质检。只做暗色，石墨香槟配色。
colors:
  room: "#111113"
  panel: "#1a1b1e"
  inset: "#222327"
  groove: "#2f3137"
  line: "#2c2e33"
  edge: "#6b6e76"
  ivory: "#ece8e1"
  ash: "#a8a196"
  champagne: "#c9b27c"
  champagne-hover: "#d8c393"
  champagne-ink: "#1a1712"
  champagne-soft: "#3a3324"
  ok: "#8fcfa6"
  warn: "#e3b56a"
  bad: "#f0948a"
  rec: "#ff5a4f"
typography:
  clock:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Display\", \"Segoe UI\", \"Helvetica Neue\", sans-serif"
    fontSize: "64px"
    fontWeight: 200
    lineHeight: 1
    letterSpacing: "0.02em"
    fontFeature: "\"tnum\""
  clock-narrow:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"SF Pro Display\", \"Segoe UI\", \"Helvetica Neue\", sans-serif"
    fontSize: "48px"
    fontWeight: 200
    lineHeight: 1
    letterSpacing: "0.02em"
    fontFeature: "\"tnum\""
  verdict:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "46px"
    fontWeight: 200
    lineHeight: 1.2
    letterSpacing: "0.08em"
  verdict-narrow:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "34px"
    fontWeight: 200
    lineHeight: 1.2
    letterSpacing: "0.08em"
  script-stage:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "clamp(24px, min(3.4vw, 4.4vh), 42px)"
    fontWeight: 400
    lineHeight: 1.85
    letterSpacing: "0.03em"
  script:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 2
    letterSpacing: "0.03em"
  script-narrow:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 2
    letterSpacing: "0.03em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "19px"
    fontWeight: 300
    letterSpacing: "0.12em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.7
  bar-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "15px"
    fontWeight: 300
    letterSpacing: "0.14em"
  control:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "15px"
    fontWeight: 400
    letterSpacing: "0.04em"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
  counter:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
    letterSpacing: "0.12em"
    fontFeature: "\"tnum\""
  mark:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans CJK SC\", sans-serif"
    fontSize: "14px"
    fontWeight: 500
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
  track: "4px"
  focus: "6px"
  control: "8px"
  panel: "12px"
  round: "50%"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  gutter: "28px"
  xxl: "32px"
  room: "48px"
components:
  bar:
    backgroundColor: "{colors.room}"
    textColor: "{colors.ivory}"
    typography: "{typography.bar-title}"
    height: "64px"
    padding: "0 32px"
  bar-narrow:
    backgroundColor: "{colors.room}"
    height: "56px"
    padding: "0 16px"
  button-primary:
    backgroundColor: "{colors.champagne}"
    textColor: "{colors.champagne-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "11px 22px"
  button-primary-hover:
    backgroundColor: "{colors.champagne-hover}"
    textColor: "{colors.champagne-ink}"
  button-secondary:
    textColor: "{colors.ivory}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "11px 22px"
  button-danger:
    textColor: "{colors.bad}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "11px 22px"
  input:
    backgroundColor: "{colors.inset}"
    textColor: "{colors.ivory}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  script-panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ivory}"
    rounded: "{rounded.panel}"
    padding: "32px 28px 28px"
  player:
    backgroundColor: "{colors.inset}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  play-button:
    textColor: "{colors.champagne}"
    rounded: "{rounded.round}"
    size: "40px"
  mark-pass:
    textColor: "{colors.ok}"
    typography: "{typography.mark}"
  mark-warn:
    textColor: "{colors.warn}"
    typography: "{typography.mark}"
  mark-fail:
    textColor: "{colors.bad}"
    typography: "{typography.mark}"
  mark-na:
    textColor: "{colors.ash}"
    typography: "{typography.mark}"
  verdict:
    textColor: "{colors.ok}"
    typography: "{typography.verdict}"
---

# Design System: bailian-tts 复刻向导

## Overview

**Creative North Star: "压暗的录音棚"**

复刻声音就是进一间很贵的录音棚录一条：灯光压暗，石墨黑的房间里只亮着念稿、表头和一点香槟金。界面不画调音台、推子这类道具，录音棚感只来自三件事：深而不纯黑的石墨底、细字重加宽字距的标题、所有数字等宽的仪表读数。分隔只有 1px 发丝线，没有渐变、没有投影、没有光晕。

只做暗色，没有亮色主题。录音页是唯一保留面板的视图：左侧录音前准备，右侧一块圆角面板放录音稿与计时刻度。开录后面板外框退场，顶栏收起为红点「REC 录音中」，念稿放大占满屏幕，上方一枚 200 字重的大号计时，下方是带刻度、香槟金合格区的电平表与一行文字状态。质检、试听、完成三个视图不再用卡片，而是直接摆在房间里的单列：标题、发丝线分行、面板色只作为播放器和输入框的嵌入底。

明确拒绝「顶部步骤条 + 居中卡片 + 蓝色按钮」的开通向导，也拒绝把调音设备画到页面上的道具感。

**Key Characteristics:**
- 石墨黑房间底色，透明 64px 顶栏只靠一条发丝线与内容分开，右侧等宽「0N / 04」计数。
- 香槟金是唯一的强调色，只给主操作、10～20 秒建议区间、序号和播放键。
- 标题 300 字重、宽字距；计时与质检结论 200 字重的大号细字。
- 唯一的分隔方式是 1px 发丝线；质检 / 试听 / 完成是无卡片的房间单列。
- 结论标记是「状态圆点 + 文字」，颜色只在结论、电平和计时状态上出现。
- 播放器是自绘的：香槟金描边圆形播放键 + 刻度槽或波形。

## Colors

石墨冷灰的中性层级，一枚香槟金强调，外加只服务于结论的柔和绿 / 琥珀 / 珊瑚和一枚录音红。

### Primary
- **香槟金**（champagne）：主按钮底、计时刻度上的 10～20 秒建议区间线与边线和「建议 10～20 秒」标注、准备事项序号描边、播放键描边与图标、焦点环、表单 `accent-color`、选区底、加载圈。
- **浅香槟**（champagne-hover）：主按钮悬停底色。
- **香槟墨**（champagne-ink）：香槟金底上的文字与选区文字。
- **暗香槟**（champagne-soft）：电平表合格区（-24～-8 dBFS）的底色，两侧各有一条 1px 香槟金边。

### Neutral
- **石墨房间**（room）：页面底与顶栏底；顶栏是「透明」的，因为它和房间同色。
- **面板**（panel）：录音页的录音稿面板，以及窄屏折叠的准备事项摘要底。
- **嵌入**（inset）：输入框、下拉框、文本域、播放器、音色编号代码框的底色。面板色系只以嵌入的形式出现在无卡片视图里。
- **刻度槽**（groove）：计时刻度、电平表、播放进度的轨道底。
- **发丝线**（line）：全部 1px 分隔、面板外框、代码框描边、加载圈底环、滚动条滑块。
- **控件边**（edge）：按钮与输入框的 1px 描边（对面板 ≥3:1）、电平刻度线、波形未播放部分。
- **象牙白**（ivory）：正文、标题、播放进度与波形已播放部分、计时进度、按钮悬停描边、文字链接。
- **灰烬**（ash）：说明、提示、表头、顶栏步骤名与计数、刻度数字、链接下划线、「未检测」标记。

### Semantic
- **合格绿**（ok）：「合格」标记、可以提交的结论、电平合适、计时进入 10～20 秒区间（计时与状态句同时变色）。
- **琥珀**（warn）：「可用」标记、电平偏小、计时超过 20 秒、警告消息。
- **珊瑚**（bad）：「需重录」标记、建议重录的结论、电平破音、波形里削波的柱、危险按钮文字、错误消息。
- **录音红**（rec）：只用于录音中顶栏的 8px 圆点与「REC」字样。

### Named Rules
**The 香槟只给三处 Rule.** 香槟金只出现在主操作、建议区间和序号（及与之同族的播放键、焦点环）上。不要用它做装饰线、标题色或区块底。

**The 颜色只给结论 Rule.** 绿、琥珀、珊瑚只用于结论与实时状态，每处颜色旁边都有一个文字词（合格 / 可用 / 需重录 / 太小 / 合适 / 太大 / 可以停了），不只靠颜色表达状态。

**The 只有暗色 Rule.** 这是一间压暗的录音棚，`color-scheme: dark`，没有亮色主题；新增颜色只在 `:root` 定义一次。

## Typography

**Body Font:** 系统中文无衬线栈（-apple-system / PingFang SC / Hiragino Sans GB / Microsoft YaHei / Noto Sans CJK SC，回退 sans-serif）
**Clock Font:** 系统西文显示栈（-apple-system / SF Pro Display / Segoe UI / Helvetica Neue），只用于录音计时
**Label/Mono Font:** ui-monospace / SFMono-Regular / Menlo，只用于音色编号

**Character:** 中文全部用系统无衬线；层级靠字重而不是字号堆叠：标题压到 300、结论和计时压到 200，配宽字距，像录音棚里安静的仪表字。所有数字等宽。

### Hierarchy
- **Clock**（200，64px / 窄屏 48px，行高 1，等宽数字）：录音中的「00:00.0」计时。
- **Verdict**（200，46px / 窄屏 34px，行高 1.2，字距 .08em）：质检单顶部的结论句（可以提交 / 建议重录 / 需要重录），按结论着色。
- **Script Stage**（400，clamp(24px, min(3.4vw, 4.4vh), 42px)，行高 1.85）：录音中的全屏念稿。
- **Script**（400，22px / 窄屏 19px，行高 2，字距 .03em）：录音稿面板里的正文。
- **Title**（300，19px，字距 .12em；区块小标题 .1em）：视图标题、准备事项标题、区块标题。
- **Body**（400，16px，行高 1.7）：基础正文。
- **Control**（400，15px，字距 .04em）：按钮、输入框、表格、准备事项条目、计时状态句、电平状态句。顶栏标题同为 15px，但用 300 与 .14em。
- **Label**（400，14px）：面板头副信息、字段说明、提示、消息、播放时间。顶栏计数「0N / 04」同为 14px，加 .12em 字距与等宽数字，当前项象牙白 500。
- **Mark**（500，14px，字距 .1em）：结论标记文字，「REC 录音中」同字号。
- **Scale**（400，12px，等宽数字）：刻度数字、建议区间标注、准备事项序号。

### Named Rules
**The 细字压暗 Rule.** 标题用 300、大号读数用 200，宽字距；不要用粗体做层级。粗字重只给按钮主操作（600）和电平图例的当前项（700）。

**The 数字等宽 Rule.** 计时、计数、时长、刻度、播放时间一律 `font-variant-numeric: tabular-nums`，数字跳动时不抖。

## Layout

内容区最大宽 1120px，内边距上 48px、左右 32px、下 80px。录音页宽屏两栏：左栏录音前准备与麦克风（`minmax(240px, 1fr)`），右栏录音稿面板（2fr），栏距 48px。质检 / 试听 / 完成是 980px 宽的房间单列，内容左右贴齐列边（行与区块的左右内边距在宽屏归零），区块之间 24px 上下留白加一条发丝线；试听原声与复刻左右两栏，中间一条竖发丝线。

间距节奏：8 / 12 / 16 / 20 / 24 / 28 / 32 / 48px。面板内横向 28px，区块 24px，表格行 16px 上下，按钮组 12px。

断点只有 760px：顶栏降为 56px、左右 16px；内容左右 16px；单栏；准备事项折叠成面板色底、发丝线框的 `details` 摘要（「（3 条，点开查看）」，宽屏强制展开）；计时 48px、结论 34px、念稿 19px；试听两栏改为上下堆叠，竖线变横线；顶栏只留「声音复刻」。

录音状态：内容宽收到 980px，顶部 5vh，单栏，准备事项与计时刻度隐藏，面板外框和底色透明化，计时行出现在念稿上方。

## Elevation & Depth

完全扁平，没有投影、渐变或光晕。深度只有色阶：房间（room）→ 面板（panel）→ 嵌入（inset）→ 刻度槽（groove），一级比一级亮。顶栏 `position: sticky`，与房间同色，靠底部发丝线分开。电平合格区两侧的 1px 香槟金边是用 `inset box-shadow` 画的线，属于刻度而不是投影。

### Named Rules
**The 发丝线即结构 Rule.** 所有分隔都是 1px `line`：顶栏底线、面板外框、面板头底线、质检行线、区块线、试听对比竖线。要再分一层就加一条线或降一级嵌入色，不加阴影。

## Shapes

柔和但克制的圆角，按物件分级：刻度与播放轨道 4px，焦点环 6px，按钮 / 输入框 / 播放器 / 代码框 8px，录音稿面板 12px。正圆用于播放键（40px）、准备事项序号（22px）、录音红点（8px）、结论圆点（7px）和加载圈。

## Components

### Buttons
安静的录音棚面板按键。
- **Shape:** 8px 圆角，11px 22px 内边距，15px 字、.04em 字距，可在文字前带 18px 线性 SVG 图标（麦克风、停止、重录、提交箭头），间距 10px。
- **Primary:** 香槟金底、香槟墨字、600 字重。每组只有一个主按钮，且跟随质检结论：结论建议重录时「重新录音」升为主按钮，「提交复刻」降级（时长不合格时禁用）。
- **Secondary:** 透明底、象牙白字、1px 控件边描边。
- **Danger:** 次级外观，珊瑚文字（「不满意，删除后重录」）。
- **Hover / Focus:** 悬停规则只写在 `@media (hover: hover)` 里：次级描边变象牙白，主按钮变浅香槟；过渡 .2s。焦点为 2px 香槟金描边、3px 偏移、6px 圆角。禁用 40% 透明度。
- **Link-style:** 无底无框的象牙白文字，灰烬色下划线、偏移 4px，14px（「选择文件」）。

### Inputs / Fields
- **Style:** 嵌入色底，1px 控件边，8px 圆角，10px 14px 内边距，15px 字；占位文字灰烬色；字段说明在上方，14px 灰烬、.04em。
- **Focus:** 全局香槟金焦点环；复选框通过 `accent-color` 跟随香槟金。
- **代码值:** 音色编号放在嵌入底、发丝线框、8px 圆角的等宽代码框里，可整段选中；窄屏换行不裁切。

### Navigation
- **顶栏:** 64px、房间底色、底部发丝线、贴顶。左「声音复刻 · 步骤名」（15px 300 .14em，步骤名灰烬 400），右等宽计数「01 / 04」（当前项象牙白 500，总数灰烬）。录音中两侧隐藏，换成录音红 8px 圆点 +「REC」（录音红 600）+「录音中」（14px .14em）。

### Script Panel（录音稿面板）
录音页唯一的面板：面板色底、发丝线外框、12px 圆角。面板头（左 19px 300 标题「录音稿」，右 14px 灰烬说明，底部发丝线，18px 28px）→ 念稿正文（32px 28px 28px）→ 面板底（计时刻度、按钮组、消息）。

### Timer Scale（计时刻度）
0–30 秒，6px 刻度槽轨道，象牙白进度从左按 `scaleX` 增长。10～20 秒建议区间画在轨道上方：一条 2px 香槟金线加两条 22px 高的 1px 香槟金边线，上方「建议 10～20 秒」12px 香槟金标注，下方刻度「0 秒 / 10 / 20 / 30 秒」。区间与进度不重叠。录音中隐藏，由计时读数接替。

### Clock（录音计时）
念稿上方的一行：200 字重 64px 计时「00:13.3」+ 15px 状态句。未到 10 秒为象牙白与灰烬「还差 N 秒到建议时长」；10～20 秒两者都变合格绿，状态为「可以停了」；超过 20 秒变琥珀，「已超过 20 秒，可以停了」。颜色过渡 .3s。

### Level Meter（电平表）
只在录音中出现。-60～0 dBFS 的 8px 刻度槽轨道；合格区（-24～-8 dBFS，60%～86.7%）铺暗香槟、两侧 1px 香槟金边；电平填充 .08s 线性跟随，合适为合格绿、偏小琥珀、破音珊瑚。轨道下方每 6 dB 一道 1px 控件边刻度（11 道，6px 高），再下方图例「太小 / 合适 / 太大」（14px），当前状态那项加粗着色；最后一行状态句（15px，`aria-live` 播报）。

### Verdict & Rows（质检结论与行）
房间单列：视图标题行（发丝线下）→ 46px 200 字重结论句 + 15px 灰烬说明 → 三行质检表（项目名灰烬 22% 宽 / 等宽数值 / 结论标记 + 可选提示，行间发丝线，逐行 .45s 左移 6px 淡入、依次延迟 .08s）→ 回放与起名区块。

### Mark（结论标记）
「状态圆点 + 文字」：7px 正圆圆点用 `currentColor`，间距 8px，14px 500 .1em。四态：合格（合格绿）、可用（琥珀）、需重录（珊瑚）、未检测（灰烬）。也用于完成视图标题行右侧的结果（「已设为默认」「已收藏」）。

### Player（播放器）
自绘，替代浏览器原生音频控件。嵌入色底、8px 圆角、12px 16px 内边距、间距 16px：40px 香槟金描边圆形播放 / 暂停键（16px 实心图标）→ 进度区 → 14px 灰烬等宽时间「0:00 / 0:13」。进度区两种：
- **刻度槽**：6px 刻度槽轨道，象牙白已播放部分，可点击跳转（试听原声与复刻）。
- **波形**：56px 高 canvas，160 根柱，已播放部分象牙白、未播放部分控件边、削波（峰值 ≥0.98）的柱珊瑚色，可点击跳转（质检回放）。
无音频时播放键 40% 透明且不可点。窄屏间距 10px、内边距 10px 12px。

## Do's and Don'ts

### Do:
- **Do** 用 1px `line` 发丝线完成所有分隔；需要更多层级时加一条线或降一级嵌入色。
- **Do** 质检、试听、完成这类结果视图用无卡片的房间单列，面板色只做播放器和输入框的嵌入底。
- **Do** 每个结论都同时给出颜色与文字词，结论标记用「状态圆点 + 文字」。
- **Do** 把建议范围直接画在刻度上（计时 10～20 秒香槟金区间、电平合格区）。
- **Do** 标题用 300 字重加宽字距，大号读数用 200 字重，所有数字等宽。
- **Do** 悬停样式只写在 `@media (hover: hover)` 里。
- **Do** 每组只保留一个主按钮，并让它指向质检推荐的下一步。

### Don't:
- **Don't** 加投影、渐变或光晕；本系统完全扁平。
- **Don't** 加亮色主题或亮色面板。
- **Don't** 把香槟金用在主操作、建议区间和序号以外的装饰位置。
- **Don't** 画调音台、推子、VU 表头这类录音设备道具。
- **Don't** 画顶部步骤条或步骤圆点；进度只用顶栏右侧的等宽「0N / 04」。
- **Don't** 用浏览器原生音频控件；播放统一用自绘播放器。
- **Don't** 在录音状态下显示念稿、REC 指示、计时、电平和停止按钮以外的内容。
