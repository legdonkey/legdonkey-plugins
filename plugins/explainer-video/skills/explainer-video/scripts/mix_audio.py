#!/usr/bin/env python3
"""把旁白、BGM（按旁白闪避）和音效混成一条主音轨 video/assets/audio/mix.wav，并做两遍 loudnorm。

用法：python3 mix_audio.py --video P/video [--bgm P/audio/bgm.wav] [--bgm-db -9 --duck-db -6] [--bgm-eq ""]

BGM 混入前默认过 --bgm-eq（80Hz 高通 + 150Hz 低搁架 −4dB）：MusicGen 的输出 150Hz 以下常占 70–80%，
手机外放发闷。用户提供的成品音乐不需要时传 --bgm-eq ""。

音效来自 video/sfx-cues/<场景 id>.json（场景内时间）：
  [{"t": 5.9, "file": "whoosh-short.mp3", "gain_db": -12, "why": "两个圆靠拢"},
   {"t": 7.2, "file": "riser.mp3", "gain_db": -12, "pre": 3.7, "why": "峰值落在下一场景的 impact"},
   {"t": 9.0, "file": "pop.mp3", "drop": true, "why": "主会话审听后删掉"}]
  t     画面动作到位的那一帧；音效峰值对齐到它之后一帧（声音略晚于画面，听感更"跟手"）
  pre   只保留峰值前这么多秒（riser 类），开头 0.4s 淡入；riser.mp3 缺省 3.7
  drop  true 时跳过（审听后删减用，保留记录）
--drop-files 里的文件整体跳过：打字声、按键声与旁白抢同一频段，默认删掉。
同一采样重复出现时轮换 1.0 / 0.92 / 1.07 倍速（同时变调），避免听出是同一个声音；
whoosh 与 whoosh-short 视为同一个采样。
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np

SR = 48000


def load(path, af=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path] + (["-af", af] if af else []) + ["-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def db(x):
    return 10 ** (x / 20)


def duck_envelope(vo, n):
    """旁白包络 → 0..1 的"正在说话"曲线（攻击 80ms，释放 700ms），按 10ms 块平滑后展开。"""
    env = np.abs(vo).max(axis=1)
    win = int(0.03 * SR)
    env = np.sqrt(np.convolve(env ** 2, np.ones(win) / win, mode="same"))
    speaking = (env > 0.02).astype(np.float32)
    blk = int(0.01 * SR)
    sp = speaking[: n // blk * blk].reshape(-1, blk).max(axis=1)
    a_c, r_c = blk / (0.08 * SR), blk / (0.7 * SR)
    out = np.zeros_like(sp)
    level = 0.0
    for i, s in enumerate(sp):
        level += (s - level) * (a_c if s > level else r_c)
        level = min(max(level, 0.0), 1.0)
        out[i] = level
    duck = np.zeros(n, dtype=np.float32)
    duck[: len(out) * blk] = np.repeat(out, blk)
    duck[len(out) * blk:] = out[-1] if len(out) else 0
    return duck


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--bgm-db", type=float, default=-9.0, help="BGM 在旁白停顿处的增益（BGM 本身约 -20 LUFS 时）")
    ap.add_argument("--duck-db", type=float, default=-6.0, help="说话时相对停顿处再压低的量")
    ap.add_argument("--bgm-eq", default="highpass=f=80,lowshelf=f=150:g=-4",
                    help="BGM 混入前的 ffmpeg 滤镜；MusicGen 输出低频偏重，手机外放发闷。传空串关闭")
    ap.add_argument("--drop-files", default="typing.mp3,key-press.mp3")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--tp", type=float, default=-1.5)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(a.video))
    out_path = a.out or os.path.join(root, "assets/audio/mix.wav")
    drop_files = {f for f in a.drop_files.split(",") if f}
    frame = 1 / a.fps

    tl = json.load(open(os.path.join(root, "assets/data/timeline.json")))
    n = int(round(tl["duration"] * SR))
    starts = {sc["id"]: sc["visualStart"] for sc in tl["scenes"]}

    vo = load(os.path.join(root, "assets/audio/narration.wav"))[:n]
    vo = np.pad(vo, ((0, n - len(vo)), (0, 0)))
    mix = vo.copy()

    if a.bgm:
        bgm = load(os.path.expanduser(a.bgm), a.bgm_eq or None)[:n]
        if len(bgm) < n:
            print(f"警告：BGM 比旁白短 {(n - len(bgm)) / SR:.2f}s，末尾补静音")
        bgm = np.pad(bgm, ((0, n - len(bgm)), (0, 0)))
        duck = duck_envelope(vo, n)
        gain = db(a.bgm_db) * (1 - duck * (1 - db(a.duck_db)))
        mix += bgm * gain[:, None]

    report, uses = [], {}
    for f in sorted(glob.glob(os.path.join(root, "sfx-cues/*.json"))):
        sid = os.path.basename(f)[:-5]
        if sid not in starts:
            print(f"警告：{f} 对应的场景 {sid} 不在时间轴里，跳过")
            continue
        for cue in json.load(open(f)):
            if cue.get("drop") or cue["file"] in drop_files:
                continue
            x = load(os.path.join(root, "assets/sfx", cue["file"]))
            pre = cue.get("pre", 3.7 if cue["file"] == "riser.mp3" else None)
            key = cue["file"].replace("-short", "")
            k = uses.get(key, 0)
            uses[key] = k + 1
            rate = (1.0, 0.92, 1.07)[k % 3]
            if rate != 1.0 and pre is None:
                src = np.arange(len(x))
                dst = np.arange(0, len(x) - 1, rate)
                x = np.stack([np.interp(dst, src, x[:, c]) for c in range(2)], axis=1)
            peak_i = int(np.abs(x).max(axis=1).argmax())
            x = x / max(np.abs(x).max(), 1e-6) * db(-3) * db(cue.get("gain_db", -10))
            if pre is not None:
                keep = int(pre * SR)
                x = x[max(0, peak_i - keep):]
                peak_i = min(peak_i, keep)
                fade = min(int(0.4 * SR), len(x))
                x[:fade] *= np.linspace(0, 1, fade)[:, None]
            t_act = starts[sid] + cue["t"]
            start = int(round((t_act + frame) * SR)) - peak_i
            if start < 0:
                x, start = x[-start:], 0
            end = min(n, start + len(x))
            mix[start:end] += x[: end - start]
            report.append((round(t_act, 2), sid, cue["file"], cue.get("gain_db"), cue.get("why", "")))

    tmp = out_path + ".pre.wav"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-",
                    "-c:a", "pcm_f32le", tmp], input=np.clip(mix, -1, 1).astype(np.float32).tobytes(), check=True)
    ln = f"loudnorm=I={a.lufs}:TP={a.tp}:LRA=11"
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", ln + ":print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rfind("{"): meas.rfind("}") + 1])
    af = (ln + ":measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:"
          "measured_thresh={input_thresh}:offset={target_offset}:linear=true").format(**js)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le", out_path],
                   check=True)
    os.remove(tmp)
    print(f"音效 {len(report)} 个；混音前响度 {js['input_i']} LUFS → {out_path}")
    for r in sorted(report):
        print("  ", r)


if __name__ == "__main__":
    sys.exit(main())
