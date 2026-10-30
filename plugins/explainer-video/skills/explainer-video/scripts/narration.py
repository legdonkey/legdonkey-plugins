#!/usr/bin/env python3
"""旁白的两步：生成 bailian-tts 脚本、把逐段 wav 重新拼成全片旁白并算出时间轴。

用法（P 为项目根目录）：
  python3 narration.py script   --project P --instruct "沉稳自信的科技讲解男声，吐字清晰，语速适中偏快"
  python3 narration.py assemble --project P [--lead 0.8 --in-gap 0.35 --scene-gap 1.0 --tail 2.5 --pre 0.45]

输入 P/narration/segments.json：数组，每段
  {"scene": "s02-ste-zh", "chapter": 1, "display": "屏幕文字", "spoken": "朗读稿"}
  - scene：场景键，相邻同键的段属于同一场景；"-" 之后的部分作为场景名（没有 "-" 就用整个键）。
  - chapter：章节号，0 或缺省表示不属于任何章节（片头、片尾）。
  - spoken 缺省时等于 display。
第 i 段（从 1 起）对应 bailian-tts script 输出的 P/dub/{i:03d}.wav。

assemble 不用 bailian-tts 自带的 all.wav，因为它段间只有一种间隔；这里按"同场景短停、换场景长停"
重新拼接，并写出：
  P/audio/narration.wav、P/narration/timeline.json；
  若 P/video 存在，同时复制到 P/video/assets/audio/narration.wav 与 P/video/assets/data/timeline.json。
场景的画面边界：每个场景持续到下一场景首句开始前 --pre 秒（给转场留出时间），第一个从 0 开始，最后一个到片尾。
"""
import argparse
import json
import shutil
import sys
import wave
from pathlib import Path


def load_segments(p):
    segs = json.loads((p / "narration" / "segments.json").read_text(encoding="utf-8"))
    for s in segs:
        s.setdefault("spoken", s["display"])
        s.setdefault("chapter", 0)
    return segs


def cmd_script(a):
    p = Path(a.project).expanduser()
    segs = load_segments(p)
    lines = []
    if a.instruct:
        lines.append(f"@instruct {a.instruct}")
    for s in segs:
        if "\n" in s["spoken"]:
            sys.exit(f"spoken 里不能有换行：{s['spoken'][:30]}…")
        lines.append(s["spoken"])
    out = p / "narration" / "spoken.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(segs)} 段 → {out}")


def scene_name(key):
    return key.split("-", 1)[1] if "-" in key else key


def cmd_assemble(a):
    p = Path(a.project).expanduser()
    segs = load_segments(p)
    sr = None
    out = bytearray()
    t = 0.0

    def read(path):
        nonlocal sr
        with wave.open(str(path)) as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                sys.exit(f"{path} 不是 16-bit 单声道")
            if sr is None:
                sr = w.getframerate()
            elif w.getframerate() != sr:
                sys.exit(f"{path} 采样率 {w.getframerate()} 与前面的 {sr} 不一致")
            return w.readframes(w.getnframes())

    def silence(sec):
        nonlocal t
        n = int(round(sec * sr))
        out.extend(b"\0\0" * n)
        t += n / sr

    datas = []
    for i, _ in enumerate(segs, 1):
        f = p / "dub" / f"{i:03d}.wav"
        if not f.exists():
            sys.exit(f"缺少 {f}（segments.json 有 {len(segs)} 段）")
        datas.append(read(f))

    silence(a.lead)
    timeline, prev = [], None
    for i, (s, data) in enumerate(zip(segs, datas), 1):
        if prev is not None:
            silence(a.scene_gap if s["scene"] != prev else a.in_gap)
        start = t
        out.extend(data)
        t += len(data) / 2 / sr
        timeline.append({"id": i, **s, "start": round(start, 3), "end": round(t, 3)})
        prev = s["scene"]
    silence(a.tail)

    (p / "audio").mkdir(exist_ok=True)
    with wave.open(str(p / "audio" / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(out))

    scenes = []
    for x in timeline:
        if not scenes or scenes[-1]["key"] != x["scene"]:
            scenes.append({"id": f"s{len(scenes):02d}", "key": x["scene"], "name": scene_name(x["scene"]),
                           "chapter": x["chapter"], "start": x["start"], "segments": []})
        scenes[-1]["segments"].append(x["id"])
        scenes[-1]["speechEnd"] = x["end"]
    keys = [s["key"] for s in scenes]
    if len(set(keys)) != len(keys):
        sys.exit(f"同一个 scene 键出现在不相邻的位置：{keys}")
    for i, sc in enumerate(scenes):
        sc["visualStart"] = 0.0 if i == 0 else scenes[i - 1]["visualEnd"]
        sc["visualEnd"] = round(t, 3) if i == len(scenes) - 1 else round(scenes[i + 1]["start"] - a.pre, 3)

    tl = {"duration": round(t, 3), "segments": timeline, "scenes": scenes}
    (p / "narration" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    v = p / "video"
    if v.is_dir():
        (v / "assets" / "audio").mkdir(parents=True, exist_ok=True)
        (v / "assets" / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy(p / "audio" / "narration.wav", v / "assets" / "audio" / "narration.wav")
        shutil.copy(p / "narration" / "timeline.json", v / "assets" / "data" / "timeline.json")
    print(f"总长 {t:.2f}s，{len(timeline)} 段，{len(scenes)} 个场景")
    for sc in scenes:
        print(f"  {sc['id']} {sc['name']:<20} 章{sc['chapter']}  {sc['visualStart']:7.2f}–{sc['visualEnd']:7.2f}"
              f"  ({sc['visualEnd'] - sc['visualStart']:5.2f}s)  段 {sc['segments'][0]}–{sc['segments'][-1]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("script")
    s.add_argument("--project", required=True)
    s.add_argument("--instruct", default="", help="bailian-tts 的语气指令（@instruct）；Flash 以外的模型不支持，留空")
    s.set_defaults(fn=cmd_script)
    m = sub.add_parser("assemble")
    m.add_argument("--project", required=True)
    m.add_argument("--lead", type=float, default=0.8, help="片头静音")
    m.add_argument("--in-gap", type=float, default=0.35, help="同场景内段间静音")
    m.add_argument("--scene-gap", type=float, default=1.0, help="换场景时段间静音")
    m.add_argument("--tail", type=float, default=2.5, help="片尾静音（最后一帧保持）")
    m.add_argument("--pre", type=float, default=0.45, help="画面在下一场景首句前多少秒切换")
    m.set_defaults(fn=cmd_assemble)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
