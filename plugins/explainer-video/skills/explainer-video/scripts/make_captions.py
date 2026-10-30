#!/usr/bin/env python3
"""用 Whisper 词级时间戳切字幕，并按段整理词时间，供场景作者把画面对到"说到那个词"。

用法：python3 make_captions.py --project P [--max 24]

输入：P/narration/timeline.json（narration.py assemble 的输出）、
      P/asr/transcript.json（hyperframes transcribe 的输出：[{text, start, end}, …]）。
输出：P/video/assets/data/captions.json        [{seg, scene, text, start, end}]，显示文字来自 display
      P/video/assets/data/words_by_segment.json [{id, scene, start, end, words:[{t, s, e}]}]
      P/asr/check.txt                          每段"朗读稿 vs 识别结果"，用来人工核对读音

段的起止来自 TTS，是准的；段内的切分点按 ASR 字符累积比例换算。ASR 文字有同音错字，
英文名常被识别成别的写法，只用它找时间，不用来显示。
"""
import argparse
import json
import re
from pathlib import Path

PUNCT = "，。；：？！,;:?!"


def chunks(text, mx):
    """按标点切成不超过 mx 个字符的字幕条；仍然过长的硬切。"""
    parts = re.findall(rf"[^{PUNCT}]+[{PUNCT}]?", text)
    out, cur = [], ""
    for part in parts:
        if len((cur + part).rstrip(PUNCT)) <= mx:
            cur += part
        else:
            if cur:
                out.append(cur)
            cur = part
    if cur:
        out.append(cur)
    res = []
    for c in out:
        while len(c) > mx + 4:
            res.append(c[:mx])
            c = c[mx:]
        res.append(c)
    return [c.strip() for c in res if c.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--max", type=int, default=24, help="每条字幕最多字符数（1920 宽、38px 字号时 24 字约 900px）")
    a = ap.parse_args()
    p = Path(a.project).expanduser()
    tl = json.loads((p / "narration" / "timeline.json").read_text(encoding="utf-8"))
    W = json.loads((p / "asr" / "transcript.json").read_text(encoding="utf-8"))

    caps, wbs, report = [], [], []
    for s in tl["segments"]:
        ws = [w for w in W if s["start"] - 0.2 <= w["start"] < s["end"]]
        wbs.append({"id": s["id"], "scene": s["scene"], "start": s["start"], "end": s["end"],
                    "words": [{"t": w["text"], "s": w["start"], "e": w["end"]} for w in ws]})
        report.append(f"{s['id']:>3} 朗读：{s['spoken']}\n    识别：{''.join(w['text'] for w in ws)}")
        cs = chunks(s["display"], a.max)
        tot = sum(len(w["text"]) for w in ws) or 1

        def t_at(frac):
            target, acc = frac * tot, 0
            for w in ws:
                n = len(w["text"])
                if acc + n >= target:
                    return w["start"] + (w["end"] - w["start"]) * ((target - acc) / n if n else 0)
                acc += n
            return s["end"]

        dtot, acc = sum(len(c) for c in cs), 0
        for i, c in enumerate(cs):
            st = s["start"] if i == 0 else t_at(acc / dtot)
            acc += len(c)
            en = s["end"] if i == len(cs) - 1 else t_at(acc / dtot)
            caps.append({"seg": s["id"], "scene": s["scene"], "text": c.rstrip("，；：,;:。"),
                         "start": round(st, 3), "end": round(en, 3)})

    d = p / "video" / "assets" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "captions.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "words_by_segment.json").write_text(json.dumps(wbs, ensure_ascii=False, indent=1), encoding="utf-8")
    (p / "asr" / "check.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"字幕 {len(caps)} 条，最长 {max(len(c['text']) for c in caps)} 字；读音核对表 → {p / 'asr' / 'check.txt'}")


if __name__ == "__main__":
    main()
