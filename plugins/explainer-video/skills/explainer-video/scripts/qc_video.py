#!/usr/bin/env python3
"""渲染后的画面质检：帧差统计、长时间静止段、接缝联系表。

用法：python3 qc_video.py --video P/video --mp4 renders/visual_pass.mp4 --out <截图目录> [--seams all|chapters]

输出：
  - 帧差中位数 / P99，以及最大的 25 个帧差和它离最近场景接缝的距离。
    大帧差应只出现在设计好的转场处；出现在场景中间说明有跳变（元素闪现、窗口末尾硬切）。
  - 超过 4s 画面完全不变的起点（片尾保持帧除外）。
  - <out>/seams.jpg：每个接缝前后 6 帧拼成的联系表，只用来定位；判断版面、字号一律看全分辨率单帧
    （<out>/f_<秒>.png），缩小的联系表会让比例看起来不对。
"""
import argparse
import json
import os
import subprocess

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--mp4", default="renders/visual_pass.mp4")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seams", default="chapters", choices=["all", "chapters"])
    a = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(a.video))
    mp4 = os.path.join(root, a.mp4)
    os.makedirs(a.out, exist_ok=True)
    tl = json.load(open(os.path.join(root, "assets/data/timeline.json")))
    fps = 30

    w, h = 160, 90
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    print(f"帧数 {len(f)}，帧差中位 {np.median(d):.2f}，P99 {np.percentile(d, 99):.2f}（0–255 灰度均值）")
    seams = [s["visualStart"] for s in tl["scenes"]][1:]
    print("最大帧差：")
    for i in sorted(np.argsort(d)[::-1][:25]):
        t = (i + 1) / fps
        near = min(seams, key=lambda s: abs(s - t)) if seams else 0
        print(f"  t={t:7.2f}s  差={d[i]:6.2f}  最近接缝 {near}（{t - near:+.2f}s）")
    static, run, starts = d < 0.05, 0, []
    for i, s in enumerate(static):
        run = run + 1 if s else 0
        if run == 4 * fps:
            starts.append(round((i - 4 * fps + 1) / fps, 2))
    tail = tl["duration"] - 4
    print("≥4s 静止段起点：", [s for s in starts if s < tail] or "无", "（片尾保持帧不计）")

    sc = tl["scenes"]
    if a.seams == "chapters":
        picks = [s["visualStart"] for p, s in zip(sc, sc[1:]) if s.get("chapter", 0) != p.get("chapter", 0)]
    else:
        picks = seams
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("没有 PIL，跳过联系表；单帧仍可用 ffmpeg -ss <秒> -frames:v 1 抽取")
        return
    offs = [-0.2, 0.15, 0.35, 0.5, 0.7, 1.2]
    cw, ch = 480, 270
    sheet = Image.new("RGB", (cw * len(offs), ch * max(1, len(picks))))
    dr = ImageDraw.Draw(sheet)
    for r, s in enumerate(picks):
        for c, o in enumerate(offs):
            t = s + o
            p = os.path.join(a.out, f"f_{t:.2f}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", p], check=True)
            sheet.paste(Image.open(p).resize((cw, ch)), (c * cw, r * ch))
            dr.text((c * cw + 6, r * ch + 4), f"{t:.2f}", fill=(255, 255, 0))
    sheet.save(os.path.join(a.out, "seams.jpg"), quality=85)
    print("接缝联系表：", os.path.join(a.out, "seams.jpg"))


if __name__ == "__main__":
    main()
