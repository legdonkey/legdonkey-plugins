#!/usr/bin/env python3
"""生成 HyperFrames 工程的"地基"：根合成、常驻层（背景舞台 / 章节 HUD / 字幕）、占位场景。

用法：python3 gen_root.py --video P/video [--audio auto|mix|narration]

读取：
  video/design.json             画幅、色板、章节（见技能 assets/design.example.json）
  video/assets/data/timeline.json   narration.py assemble 的输出
  video/assets/data/captions.json   make_captions.py 的输出
  video/assets/fonts/fonts.css.txt  setup_fonts.sh 的输出（@font-face 片段）

写出（每次整体重写，不要手改，改数据后重跑）：
  index.html                    场景宿主 data-start = visualStart，data-duration = 场景时长 + overlap（最后一个不加）
  compositions/stage.html       底色 + 点阵 + 随章节换色的柔光 + 暗角
  compositions/hud.html         左上角章节胶囊 + N 段进度条（只在 chapter > 0 的场景显示；没有章节就不生成）
  compositions/captions.html    每条字幕一个带稳定 id 的静态 .clip
  compositions/sXX.html         只为缺失或仍带 data-placeholder="true" 的场景写占位；正式场景不覆盖

叠放顺序：舞台 z 1 < 场景 z 10+序号 < HUD z 900 < 字幕 z 950。
"""
import argparse
import html
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--audio", default="auto", choices=["auto", "mix", "narration"],
                help="根合成挂哪条音轨：mix = assets/audio/mix.wav（混音后），narration = 纯旁白；auto 有 mix 就用 mix")
A = ap.parse_args()

ROOT = Path(A.video).expanduser().resolve()
DATA = ROOT / "assets" / "data"
D = json.loads((ROOT / "design.json").read_text(encoding="utf-8"))
TL = json.loads((DATA / "timeline.json").read_text(encoding="utf-8"))
CAPS = json.loads((DATA / "captions.json").read_text(encoding="utf-8")) if (DATA / "captions.json").exists() else []
SCENES = TL["scenes"]
DUR = TL["duration"]
W, H = D.get("width", 1920), D.get("height", 1080)
OVERLAP = D.get("overlap", 0.6)
CHAPTERS = D.get("chapters", [])
CH_COLORS = [c["color"] for c in CHAPTERS]
NEUTRAL = D.get("neutral") or (CH_COLORS[:3] if CH_COLORS else ["#9aa3b5"])
NEUTRAL = [NEUTRAL[i % len(NEUTRAL)] for i in range(3)]
CAP = {"size": 38, "bottom": 112, "maxWidth": 1500, **D.get("captions", {})}

for sc in SCENES:
    if sc.get("chapter", 0) > len(CHAPTERS):
        sys.exit(f"{sc['id']} 的 chapter={sc['chapter']}，但 design.json 只定义了 {len(CHAPTERS)} 章")


def num(x):
    """秒数写成最短的十进制字符串（去掉浮点尾差）。"""
    return f"{round(x, 3):.3f}".rstrip("0").rstrip(".")


def font_faces():
    f = ROOT / "assets" / "fonts" / "fonts.css.txt"
    if not f.exists():
        print("警告：缺少 assets/fonts/fonts.css.txt，先运行 setup_fonts.sh；本次生成的文件不含 @font-face")
        return ""
    return "\n".join("      " + l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("@font-face"))


def palette_css(indent="        "):
    rows = [f"--{k}: {v};" for k, v in D["palette"].items()]
    rows += [f"--c{i + 1}: {c};" for i, c in enumerate(CH_COLORS)]
    rows += ['--font-cn: "Inter", "Noto Sans SC", sans-serif;',
             '--font-mono: "JetBrains Mono", "Noto Sans SC", monospace;']
    return "\n".join(indent + r for r in rows)


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


# ---------- 根合成 ----------
def gen_index():
    if A.audio == "mix" or (A.audio == "auto" and (ROOT / "assets/audio/mix.wav").exists()):
        audio = "assets/audio/mix.wav"
    else:
        audio = "assets/audio/narration.wav"
    hosts = []
    for i, sc in enumerate(SCENES):
        sid = sc["id"]
        dur = sc["visualEnd"] - sc["visualStart"] + (OVERLAP if i < len(SCENES) - 1 else 0)
        hosts.append(
            f'      <!-- {sid} {html.escape(sc["name"])}：{num(sc["visualStart"])}–{num(sc["visualEnd"])}s -->\n'
            f'      <div id="{sid}" data-composition-id="{sid}" class="clip" data-composition-src="compositions/{sid}.html" '
            f'data-start="{num(sc["visualStart"])}" data-duration="{num(dur)}" data-track-index="{1 + i % 2}" '
            f'data-track-kind="graphics" data-width="{W}" data-height="{H}" style="z-index: {10 + i}"></div>')
    layer = lambda cid, track, kind, z: (
        f'      <div id="{cid}" data-composition-id="{cid}" class="clip" data-composition-src="compositions/{cid}.html" '
        f'data-start="0" data-duration="{num(DUR)}" data-track-index="{track}" data-track-kind="{kind}" '
        f'data-width="{W}" data-height="{H}" style="z-index: {z}"></div>')
    hud = layer("hud", 3, "graphics", 900) if CHAPTERS else "      <!-- 没有章节，不生成 HUD -->"
    write("index.html", f"""<!doctype html>
<html lang="zh-CN" data-resolution="{'portrait' if H > W else 'landscape'}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      :root {{
{palette_css()}
      }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: var(--ground); }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
    </style>
  </head>
  <body>
    <!-- 由 gen_root.py 根据 design.json 与 assets/data/ 生成，不要手改；改数据后重跑。
         叠放：舞台 z 1 < 场景 z 10+序号 < HUD z 900 < 字幕 z 950。重叠的 {OVERLAP}s 里后一个场景在上面。 -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{num(DUR)}" data-width="{W}" data-height="{H}">
{layer("stage", 0, "graphics", 1)}
{chr(10).join(hosts)}
{hud}
{layer("captions", 4, "captions", 950)}
      <!-- 主音轨。旁白是全片时钟；混音后换成 assets/audio/mix.wav（gen_root.py --audio mix） -->
      <audio id="vo" class="clip" src="{audio}" data-start="0" data-duration="{num(DUR)}" data-track-index="5" data-volume="1"></audio>
    </div>
    <script>
      // 根时间线只负责注册；常驻层与场景由运行时各自驱动，不要把子时间线 add 进来
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")


# ---------- 背景舞台 ----------
def glow_colors(ch):
    return NEUTRAL if ch == 0 else [CH_COLORS[ch - 1]] * 3


def gen_stage():
    shifts = []
    for prev, sc in zip(SCENES, SCENES[1:]):
        if sc.get("chapter", 0) != prev.get("chapter", 0):
            shifts.append((sc["visualStart"], sc.get("chapter", 0)))
    first = glow_colors(SCENES[0].get("chapter", 0))
    sx, sy = W / 1920, H / 1080
    drift = max(DUR - 2.9, 1)
    shift_js = ",\n      ".join(f'[{num(t)}, {json.dumps(glow_colors(c))}, {0.15 if c == 0 else 0.13}]' for t, c in shifts)
    write("compositions/stage.html", f"""<!-- 由 gen_root.py 生成，不要手改。常驻层：背景舞台，从 0 开始，时间 = 全片绝对时间 -->
<template>
  <style>
      #root {{
        --ground: {D["palette"]["ground"]};
        position: absolute;
        inset: 0;
        overflow: hidden;
        background: var(--ground);
      }}
      /* 点阵网格：间距 48px，点透明度 0.06；边缘用遮罩收淡 */
      #stg-dots {{
        position: absolute;
        inset: 0;
        background-image: radial-gradient(circle, rgba(255, 255, 255, 0.06) 1.4px, transparent 1.9px);
        background-size: 48px 48px;
        background-position: 0 12px;
        -webkit-mask-image: radial-gradient(ellipse 80% 75% at 50% 45%, #000 45%, transparent 100%);
        mask-image: radial-gradient(ellipse 80% 75% at 50% 45%, #000 45%, transparent 100%);
      }}
      /* 柔光：三团光斑以 screen 叠加；三团不同色时混成冷白（片头片尾），章节内三团同色。
         颜色走 color + currentColor 渐变，GSAP 直接补间 color */
      #stg-glow {{ position: absolute; left: 0; top: 0; width: 1400px; height: 1400px; isolation: isolate; }}
      #stg-orbit {{ position: absolute; inset: 0; }}
      .stg-blob {{
        position: absolute;
        width: 1200px;
        height: 1200px;
        border-radius: 50%;
        mix-blend-mode: screen;
        background: radial-gradient(closest-side, currentColor 0%, color-mix(in srgb, currentColor 55%, transparent) 30%,
          color-mix(in srgb, currentColor 18%, transparent) 62%, transparent 100%);
      }}
      #stg-b1 {{ left: 0; top: 60px; color: {first[0]}; }}
      #stg-b2 {{ left: 200px; top: 0; color: {first[1]}; }}
      #stg-b3 {{ left: 110px; top: 200px; color: {first[2]}; }}
      #stg-vig {{
        position: absolute;
        inset: 0;
        background: radial-gradient(ellipse 70% 65% at 50% 48%, transparent 55%, rgba(0, 0, 0, 0.42) 100%);
      }}
  </style>
  <div id="root" data-composition-id="stage" data-width="{W}" data-height="{H}">
    <div id="stg-dots"></div>
    <div id="stg-glow" data-layout-ignore>
      <div id="stg-orbit">
        <div id="stg-b1" class="stg-blob"></div>
        <div id="stg-b2" class="stg-blob"></div>
        <div id="stg-b3" class="stg-blob"></div>
      </div>
    </div>
    <div id="stg-vig"></div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const BLOBS = ["#stg-b1", "#stg-b2", "#stg-b3"];
    // [时刻, 三团颜色, 柔光强度]：章节变化时刻 = 该场景 visualStart
    const SHIFTS = [
      {shift_js}
    ];
    const LEVEL0 = {0.15 if SCENES[0].get("chapter", 0) == 0 else 0.13};

    // 开场：柔光与点阵亮起
    tl.fromTo("#stg-glow", {{ opacity: 0 }}, {{ opacity: LEVEL0, duration: 0.8, ease: "power2.out" }}, 0);
    tl.fromTo("#stg-dots", {{ opacity: 0 }}, {{ opacity: 1, duration: 1.2, ease: "power2.out" }}, 0);
    // 漂移：从右上缓慢移向中部（约 3px/s，匀速是本意），三团绕中心缓慢公转
    tl.fromTo("#stg-glow", {{ x: {num(1640 * sx - 700)}, y: {num(210 * sy - 700)} }},
      {{ x: {num(900 * sx - 700)}, y: {num(520 * sy - 700)}, duration: {num(drift)}, ease: "none" }}, 0);
    tl.fromTo("#stg-orbit", {{ rotation: 0 }}, {{ rotation: {num(drift)}, duration: {num(drift)}, ease: "none" }}, 0);

    // 换色 0.8s power2.inOut；一律 fromTo 写明起点，任意时刻 seek 都确定
    let prev = {json.dumps(first)}, prevLevel = LEVEL0;
    SHIFTS.forEach(([t, colors, level]) => {{
      BLOBS.forEach((b, i) =>
        tl.fromTo(b, {{ color: prev[i] }}, {{ color: colors[i], duration: 0.8, ease: "power2.inOut", immediateRender: false }}, t),
      );
      tl.fromTo("#stg-glow", {{ opacity: prevLevel }}, {{ opacity: level, duration: 0.8, ease: "power2.inOut", immediateRender: false }}, t);
      prev = colors;
      prevLevel = level;
    }});

    // 片尾渐暗，最后约 2s 画面静止
    tl.fromTo("#stg-glow", {{ opacity: prevLevel }}, {{ opacity: 0.05, duration: 0.9, ease: "power2.inOut", immediateRender: false }}, {num(drift)});
    tl.fromTo("#stg-dots", {{ opacity: 1 }}, {{ opacity: 0.45, duration: 0.9, ease: "power2.inOut", immediateRender: false }}, {num(drift)});

    window.__timelines["stage"] = tl;
  </script>
</template>
""")


# ---------- 章节 HUD ----------
def chapter_spans():
    spans = []
    for sc in SCENES:
        ch = sc.get("chapter", 0)
        if ch and spans and spans[-1][2] == ch and abs(spans[-1][1] - sc["visualStart"]) < 1e-6:
            spans[-1][1] = sc["visualEnd"]
        elif ch:
            spans.append([sc["visualStart"], sc["visualEnd"], ch])
    return spans


def gen_hud():
    spans = chapter_spans()
    if not CHAPTERS or not spans:
        return
    first = spans[0][2]
    labels = "\n".join(
        f'          <span id="hud-l{i + 1}" class="hud-label"{"" if i + 1 == first else " style=\"opacity: 0\""}>'
        f'<span class="hud-num">{html.escape(c["num"])}</span><span class="hud-sep">·</span>{html.escape(c["label"])}</span>'
        for i, c in enumerate(CHAPTERS))
    segs = "\n".join(f'        <div class="hud-seg"><div id="hud-f{i + 1}" class="hud-fill" style="background: var(--c{i + 1})"></div></div>'
                     for i in range(len(CHAPTERS)))
    spans_js = ", ".join(f"[{num(s)}, {num(e)}, {c}]" for s, e, c in spans)
    write("compositions/hud.html", f"""<!-- 由 gen_root.py 生成，不要手改。常驻层：章节 HUD，从 0 开始，时间 = 全片绝对时间 -->
<template>
  <style>
{font_faces()}
      #root {{
{palette_css()}
        position: absolute;
        inset: 0;
        pointer-events: none;
        font-family: var(--font-cn);
      }}
      /* 左上角 (96, 60)，落在 90% 动作安全框内；场景在章节期间不要在这里放内容 */
      #hud-box {{ opacity: 0; position: absolute; left: 96px; top: 60px; }}
      #hud-pill {{
        position: relative;
        display: inline-flex;
        align-items: center;
        height: 40px;
        padding: 0 18px 0 16px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: rgba(14, 17, 24, 0.62);
      }}
      #hud-dot {{
        width: 8px;
        height: 8px;
        margin-right: 12px;
        border-radius: 50%;
        background: currentColor;
        color: var(--c{first});
        box-shadow: 0 0 10px currentColor;
      }}
      .hud-labels {{ position: relative; display: inline-block; }}
      .hud-label {{
        display: inline-block;
        font-size: 18px;
        font-weight: 500;
        line-height: 40px;
        color: var(--ink-2);
        white-space: nowrap;
        letter-spacing: 0.02em;
      }}
      .hud-label + .hud-label {{ position: absolute; left: 0; top: 0; }}
      .hud-num {{ font-weight: 600; font-variant-numeric: tabular-nums; color: var(--ink); }}
      .hud-sep {{ margin: 0 8px; }}
      #hud-prog {{ display: flex; gap: 6px; margin-top: 12px; margin-left: 4px; }}
      .hud-seg {{ position: relative; width: 64px; height: 3px; border-radius: 2px; overflow: hidden; background: var(--line); }}
      .hud-fill {{ position: absolute; inset: 0; border-radius: 2px; transform-origin: left center; }}
  </style>
  <div id="root" data-composition-id="hud" data-width="{W}" data-height="{H}">
    <div id="hud-box">
      <div id="hud-pill">
        <span id="hud-dot"></span>
        <span class="hud-labels">
{labels}
        </span>
      </div>
      <div id="hud-prog">
{segs}
      </div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    // [开始, 结束, 章节号]；连续的同章场景已合并
    const SPANS = [{spans_js}];
    const COLORS = {json.dumps(CH_COLORS)};
    const SHOW_DELAY = 1.5; // 章节卡在场景开头约 0.9s 后缩向左上角，HUD 在 1.5s 接手
    // 初始隐藏写在 CSS 里；不要在位置 0 用 tl.set 隐藏（播放头停在 0 时不渲染）
    let cur = {first};
    const filled = new Set();
    SPANS.forEach(([s, e, ch], i) => {{
      const joined = i > 0 && Math.abs(SPANS[i - 1][1] - s) < 1e-6;
      let at = s;
      if (joined) {{
        tl.to("#hud-box", {{ opacity: 0, filter: "blur(6px)", duration: 0.3, ease: "power3.in" }}, s);
        at = s + 0.3;
      }}
      if (ch !== cur) {{
        tl.set("#hud-l" + cur, {{ opacity: 0 }}, at);
        tl.set("#hud-l" + ch, {{ opacity: 1 }}, at);
        tl.set("#hud-dot", {{ color: COLORS[ch - 1] }}, at);
        tl.set("#hud-f" + cur, {{ opacity: 0.45 }}, at); // 已完成的章节段压暗
        cur = ch;
      }}
      tl.fromTo("#hud-box", {{ opacity: 0, filter: "blur(6px)" }},
        {{ opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out", immediateRender: false }}, s + SHOW_DELAY);
      // 进度条线性填充是本意；同一段第二次出现时不能再 immediateRender
      tl.fromTo("#hud-f" + ch, {{ scaleX: 0 }}, {{ scaleX: 1, duration: e - s, ease: "none", immediateRender: !filled.has(ch) }}, s);
      filled.add(ch);
      const next = SPANS[i + 1];
      if (!next || Math.abs(next[0] - e) > 1e-6) {{
        tl.to("#hud-box", {{ opacity: 0, filter: "blur(6px)", duration: 0.4, ease: "power3.in" }}, e);
      }}
    }});
    window.__timelines["hud"] = tl;
  </script>
</template>
""")


# ---------- 字幕 ----------
def est_width(s, size):
    """粗估单行宽度：CJK 与全角标点按 1em，其余按 0.56em。"""
    return sum(size if ord(c) > 0x2E80 else size * 0.56 for c in s)


def gen_captions():
    rows, cues = [], []
    for n, c in enumerate(CAPS, 1):
        cid = f"cap-{n:03d}"
        w = est_width(c["text"], CAP["size"])
        if w > CAP["maxWidth"]:
            print(f"警告：{cid} 估算宽度 {w:.0f}px 超过 {CAP['maxWidth']}px：{c['text']}")
        rows.append(f'    <div id="{cid}" class="clip cap" data-start="{num(c["start"])}" data-duration="{num(c["end"] - c["start"])}">'
                    f'<span class="cap-text">{html.escape(c["text"])}</span></div>')
        cues.append(f'["{cid}", {num(c["start"])}, {num(c["end"])}]')
    last_end = max((c["end"] for c in CAPS), default=0)
    write("compositions/captions.html", f"""<!-- 由 gen_root.py 根据 assets/data/captions.json 生成，不要手改 -->
<template>
  <style>
{font_faces()}
      #root {{
{palette_css()}
        position: absolute;
        inset: 0;
        pointer-events: none;
      }}
      /* 底部渐变带，不是黑框 */
      #cap-band {{
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 220px;
        background: linear-gradient(to bottom, rgba(6, 7, 11, 0), rgba(6, 7, 11, 0.72));
      }}
      .cap {{ position: absolute; left: 0; right: 0; bottom: {CAP["bottom"]}px; text-align: center; overflow: visible; }}
      .cap-text {{
        display: inline-block;
        max-width: {CAP["maxWidth"]}px;
        white-space: nowrap;
        font-family: var(--font-cn);
        font-size: {CAP["size"]}px;
        font-weight: 500;
        line-height: 1.3;
        letter-spacing: 0.01em;
        color: var(--ink);
        text-shadow: 0 2px 18px rgba(6, 7, 11, 0.55);
      }}
  </style>
  <div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}">
    <div id="cap-band"></div>
{chr(10).join(rows)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    // [id, 开始, 结束]（绝对秒）
    const CUES = [
      {("," + chr(10) + "      ").join(cues)}
    ];
    tl.fromTo("#cap-band", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, 0.3);
    tl.fromTo("#cap-band", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.5, ease: "power2.inOut", immediateRender: false }}, {num(last_end)});
    // 入场：整行 blur(6px)→0 + 透明度 0→1，0.16s；退场 0.12s。可见窗口由 .clip 自身控制
    CUES.forEach(([id, s, e]) => {{
      const el = "#" + id + " .cap-text";
      tl.fromTo(el, {{ opacity: 0, filter: "blur(6px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.16, ease: "power2.out" }}, s);
      tl.to(el, {{ opacity: 0, filter: "blur(4px)", duration: 0.12, ease: "power2.in" }}, Math.max(s + 0.16, e - 0.12));
    }});
    window.__timelines["captions"] = tl;
  </script>
</template>
""")


# ---------- 占位场景 ----------
def gen_placeholders():
    for sc in SCENES:
        sid = sc["id"]
        path = ROOT / "compositions" / f"{sid}.html"
        if path.exists() and 'data-placeholder="true"' not in path.read_text(encoding="utf-8"):
            continue
        vdur = sc["visualEnd"] - sc["visualStart"]
        write(f"compositions/{sid}.html", f"""<!-- 占位场景：由 gen_root.py 生成。场景作者整体替换本文件；删掉 data-placeholder 后不再被覆盖 -->
<template>
  <style>
{font_faces()}
      #root {{
{palette_css()}
        position: absolute;
        inset: 0;
        font-family: var(--font-cn);
        color: var(--ink);
      }}
      .ph-wrap {{ position: absolute; left: 0; right: 0; top: {int(H * 0.35)}px; text-align: center; }}
      .ph-id {{ font-family: var(--font-mono); font-size: 28px; color: var(--ink-3); letter-spacing: 0.08em; }}
      .ph-name {{ margin-top: 18px; font-size: 64px; font-weight: 700; letter-spacing: -0.02em; }}
      .ph-note {{ margin-top: 18px; font-size: 30px; color: var(--ink-2); }}
      .ph-track {{ position: relative; width: 480px; height: 2px; margin: 40px auto 0; background: var(--line); }}
      .ph-fill {{ position: absolute; inset: 0; background: var(--ink-3); transform-origin: left center; }}
  </style>
  <div id="root" data-composition-id="{sid}" data-placeholder="true" data-width="{W}" data-height="{H}">
    <div id="{sid}-ph" class="ph-wrap">
      <div class="ph-id">{sid.upper()} · {num(sc["visualStart"])}–{num(sc["visualEnd"])}s</div>
      <div class="ph-name">{html.escape(sc["name"])}</div>
      <div class="ph-note">占位场景，待替换</div>
      <div class="ph-track"><div id="{sid}-ph-fill" class="ph-fill"></div></div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#{sid}-ph", {{ opacity: 0, filter: "blur(8px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "expo.out" }}, 0.3);
    tl.fromTo("#{sid}-ph-fill", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {num(vdur)}, ease: "none" }}, 0);
    tl.to("#{sid}-ph", {{ opacity: 0, filter: "blur(8px)", duration: 0.25, ease: "power3.in" }}, {num(vdur)});
    window.__timelines["{sid}"] = tl;
  </script>
</template>
""")
        print("占位：", path.relative_to(ROOT))


if __name__ == "__main__":
    (ROOT / "compositions").mkdir(exist_ok=True)
    gen_index()
    gen_stage()
    gen_hud()
    gen_captions()
    gen_placeholders()
    print(f"完成：{len(SCENES)} 个场景宿主，{len(CAPS)} 条字幕，{len(CHAPTERS)} 章，全长 {num(DUR)}s")
