# 场景作者指南

写给搭场景的子代理。先读项目里的 `video/STORYBOARD.md`，再按本文件写 `video/compositions/sXX.html`。
本文件里的数值都是示例，实际数值以 `video/assets/data/timeline.json` 为准。

## 1. 地基已经提供什么

地基由 `gen_root.py` 生成，场景作者不要改这些文件：

| 层 | 文件 | 说明 |
|---|---|---|
| 背景舞台 | `compositions/stage.html`（z 1） | 深色底、48px 点阵、随章节换色的柔光、暗角。**场景不要铺不透明的全屏底色**，否则会盖住舞台；只有转场时可以短暂铺满。 |
| 场景 | `compositions/s00…sNN.html`（z 10 起递增） | 在重叠的 0.6s 里，**下一个场景叠在你上面**。 |
| 章节 HUD | `compositions/hud.html`（z 900） | 左上角 `(96, 60)` 一个胶囊加 N 段进度条，只在 chapter > 0 的场景显示。每章开始后 1.5s 淡入。 |
| 字幕 | `compositions/captions.html`（z 950） | 底部居中，文字底边距画面底边 112px，背后有一条 220px 高的渐变带。 |
| 音轨 | `index.html` 里的 `<audio id="vo">` | 旁白是全片时钟。 |

柔光换色发生在章节变化的那个场景的 `visualStart`，过渡 0.8s，缓动 `power2.inOut`。
**章节第一个场景的章节卡**要在场景内 0.9s 后缩向左上角 `(96, 60)`，并在 1.5s 前淡出，之后由 HUD 接手。

## 2. 时间换算

- 宿主窗口是 `[visualStart, visualEnd + 0.6)`，最后一个场景不加 0.6。场景内时间 = 绝对时间 − `visualStart`。
- `0 – 0.6`：你的入场转场。它和上一场景的退场同时发生，上一场景在你下面。
- `vdur – vdur+0.6`（`vdur = visualEnd − visualStart`）：你的退场，和下一场景的入场同时发生。
- 元素在旁白**说到那个词**时出现。在 `assets/data/words_by_segment.json` 里找到这个词的 `s`（绝对秒），写成常量，再用 `at()` 换算成场景内时间。不能在运行时读 JSON，因为渲染时禁止网络请求。
- 窗口末尾那一帧不会被渲染，所以最后的动作要在窗口结束前完成。
- ASR 文字有同音错字，英文名常被识别成别的写法，只用它找时间。英文名没被识别时，第一个时间戳会落到后面的中文词上；这时用段的 `start` 加估算偏移，不要整体平移所有时间。

```js
const T0 = 26.92;                                   // 本场景 visualStart
const at = (abs) => +(abs - T0).toFixed(3);         // 绝对秒 → 场景内秒
const VDUR = 29.09;                                 // visualEnd - visualStart
const EXIT = VDUR;                                  // 退场起点（与下一场景重叠的 0.6s）
const W_HUIBAO = at(28.65); // ⟨汇报⟩               // 词时间写成带注释的常量
```

## 3. 最小完整骨架

把 `sXX` 全部换成你的场景 id，`T0`、`VDUR` 换成你的数值。`@font-face` 片段从 `assets/fonts/fonts.css.txt` 原样复制。CSS 变量从任一个占位场景的 `#root` 原样复制，色板以 `design.json` 为准，章节色是 `--c1…--cN`。

```html
<!-- sXX 场景名（visualStart–visualEnd）。场景内时间 = 全片绝对时间 − visualStart -->
<template>
  <style>
      @font-face { font-family: 'Noto Sans SC'; font-style: normal; font-weight: 400; font-display: block; src: url('assets/fonts/noto-sans-sc-400.woff2') format('woff2'); }
      /* …500/700/900 同上… */
      #root {
        --ground: #06070b; --ink: #f3f5f9; --ink-2: #9aa3b5; --ink-3: #5b6475; --c1: #ffb547;  /* 从占位场景复制完整一组 */
        --font-cn: "Inter", "Noto Sans SC", sans-serif;            /* 西文数字走 Inter，汉字走 Noto */
        --font-mono: "JetBrains Mono", "Noto Sans SC", monospace;  /* 代码、命令、文件名 */
        position: absolute;
        inset: 0;
        font-family: var(--font-cn);
        color: var(--ink);
      }
      #sXX-title {
        position: absolute; left: 0; right: 0; top: 150px;
        text-align: center; font-size: 64px; font-weight: 900; letter-spacing: -0.02em;
        opacity: 0;               /* 初始隐藏写在 CSS 里 */
      }
      #sXX-line {
        position: absolute; left: 360px; top: 520px; width: 1200px; height: 2px;
        background: var(--c1); transform-origin: left center;
      }
  </style>
  <div id="root" data-composition-id="sXX" data-width="1920" data-height="1080">
    <div id="sXX-title">标题 <span style="color: var(--c1)">高亮词</span></div>
    <div id="sXX-line"></div>
  </div>
  <script>
    const tl = gsap.timeline({ paused: true });
    const T0 = 0.0, VDUR = 10;
    const at = (abs) => +(abs - T0).toFixed(3);
    const EXIT = VDUR;

    // 入场（0–0.6）：配合上一场景的退场
    tl.fromTo("#sXX-title", { opacity: 0, filter: "blur(8px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out" }, 0.1);
    // 会动的机制：⟨某词⟩时线条描出
    tl.fromTo("#sXX-line", { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: "expo.out" }, at(2.0));
    // 退场（EXIT 起，0.6s 内完成；比入场短 40–50%，power3.in）
    tl.to(["#sXX-title", "#sXX-line"], { opacity: 0, filter: "blur(8px)", duration: 0.3, ease: "power3.in" }, EXIT);

    window.__timelines["sXX"] = tl;   // 最后注册；key = data-composition-id = 宿主 id
  </script>
</template>
```

音效写在 `sfx-cues/sXX.json`，格式见 STORYBOARD 的音效一节。`t` 是场景内秒数，每个场景 0–4 条。

## 4. 踩过的坑

1. **样式作用域**：只有 `<template>` 里的 `<style>` 和 `<script>` 会保留。场景样式会被改写成 `[data-composition-id="sXX"] 选择器`，所以场景里写 `:root { --x }` **不生效**，CSS 变量要写在 `#root` 上。根元素用 `#root` 选择，不要给根元素加 class 再按 class 选。`@font-face` 和 `@keyframes` 保持全局。
2. **每个文件都要声明字体**：lint 规则 `font_family_without_font_face` 按文件检查。漏了 `@font-face` 不只是报错：渲染用的无头 Chrome 看不到系统的 PingFang，中文会掉到宋体。
3. **id**：
   - 根元素 `id="root"`。`data-composition-id`、宿主 id、`window.__timelines` 的 key 三者必须一致，否则每次渲染会等待 45s，然后输出静帧。
   - 其余元素的 id 一律加场景前缀（如 `s05-venn-left`），因为整片内联到一个文档后 id 必须唯一。
   - 不要在 JS 里选 `#root`（运行时会把根元素的 id 挪走），动画放在内层包裹元素上。
4. **初始隐藏不要用位置 0 的 `tl.set`**：播放头正好停在 0 时它不渲染（lint `gsap_timeline_set_initial_hide`）。把初始隐藏写进 CSS（`opacity: 0`），或者依赖第一个 `fromTo` 默认的 `immediateRender`。
5. **同一属性多段补间**：
   - 用 `fromTo` 写明起点。
   - 同一元素同一属性的**第二个及以后**的 `fromTo` 要加 `immediateRender: false`，否则它会在构建时就写入起始值，覆盖前面的状态。
   - 场景内不要用 `from()`。
6. **transform 只交给 GSAP**：被 GSAP 变换的元素不要写 CSS `transform`。版面位置用 `left`/`top`，运动用 `x`/`y`/`scale`/`rotation`。`<span>` 要做变换，需要设 `display: inline-block`。`transform-origin` 可以写在 CSS 里。
7. **绝对定位的容器要给尺寸**：`position: absolute` 但没有 `inset`/`width`/`height` 的容器宽高为 0，子元素的 `right:` 和 `left:0; right:0; text-align:center` 全部失效。要按画面坐标摆放子元素时，容器写 `inset: 0`。
8. **对比度不达标是 error**：`--ink-3`（#5B6475）在底色上约 3.3:1，只能用于 ≥ 24px 的字，更小的字用 `--ink-2`。`check` 的对比度失败会阻断渲染。
9. **字号与版面**：
   - 阅读文字 ≥ 28px，否则报 `text_below_floor` 警告。
   - 场景内容避开底部 260px，这里是字幕区。
   - 关键文字放在 80% 标题安全框（1080p 下 x 192–1728、y 108–972）内，装饰可以到 90% 动作安全框（x 96–1824）。
   - 章节期间，左上角 `(96, 60)` 附近 300×80 的区域是 HUD，不要放内容。
   - 构图要左右平衡：任何一拍都不要只占画面一侧，除非另一侧马上有元素进入。
10. **clip-path 揭示**：`inset()` 的上下要留负值（如 `inset(-30% 100% -30% 0%)`），否则字的上下沿会被裁掉。
11. **退场与叠放**：重叠的 0.6s 里，下一场景在你上面。"对象变世界"类的转场要在**你自己的**退场段里做完，并在窗口结束前收干净，否则窗口结束时会硬切。
12. **静止段**：超过 3s 画面无变化会报 `dead_stretch`。确实要停住的元素加 `data-hold`。不要为了过检查加呼吸、漂浮或循环动画。
13. **确定性**：不用 `Math.random()`、`Date.now()`、定时器、`repeat: -1`。随机量用固定种子的小 PRNG（mulberry32）。
14. **运动模糊**：根合成没有开 `data-motion-blur`，快速位移时自己加 6–12px 的 `filter: blur()`。水平甩切只在运动方向上做拖影。
15. **不用 CSS 3D**：`perspective`、`transform-style: preserve-3d`、`backface-visibility` 会让渲染器关闭快速抓帧（日志：`composition uses a CSS 3D rendering context ... disabling drawElementImage`），整片退回逐帧截图模式。上次一个场景的卡片翻面用了 `perspective`，整片 9059 帧都走了截图模式，抓帧用了 15 分 44 秒。替代做法：翻面用 `scaleX` 1→0→1、在 0 点换内容；等轴测用 2D 合成（外层 `scaleY 0.574`、内层 `rotation −35`）。自查：`grep -nE "perspective|preserve-3d|backface" compositions/sXX.html` 应该为空。
16. **光圈退场要快**：用光圈退场时，从 VDUR 起 0.3s 内收拢完（`power3.in`），并在 VDUR+0.3 把整个场景 opacity 设成 0 作保险。收得慢的话，你的内容会和下一场景的章节卡叠在一起。圆心用分镜指定的坐标，下一场景会从同一点展开。
17. **占位文件**：占位场景的根元素带 `data-placeholder="true"`。直接整体覆盖；去掉这个属性后，`gen_root.py` 不会再覆盖你的文件。

## 5. 自查命令

在 `video/` 下执行，先 `export HYPERFRAMES_SKIP_SKILLS=1`。

```bash
npx --yes hyperframes@0.8.198 lint
npx --yes hyperframes@0.8.198 check --json
npx --yes hyperframes@0.8.198 snapshot --composition sXX --frames 8
npx --yes hyperframes@0.8.198 snapshot --at 30.5,41.2 --no-end   # 绝对时间
```

用 Read 逐张看**全分辨率**截图。缩小的联系表只能用来找位置，判断版面比例和字号会出错。
