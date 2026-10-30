#!/usr/bin/env python3
"""BGM 后处理（章节能量包络、高通、48k 立体声、裁剪、淡入淡出、loudnorm 两遍法）+ 客观自检，结果写 qc.txt。

用法：~/.venvs/musicgen/bin/python bgm_post_qc.py --plan P/audio/bgm_plan.json --work P/audio/musicgen_work \
          --out P/audio/bgm.wav [--qc-only]

听不到声音，所以用数据判断：分章节响度、接缝前后 RMS/频谱质心跳变（与全曲自然波动的分位数比较）、
近静音段、每 10s 能量曲线、调性粗估。qc.txt 里标"<-- 注意"的接缝要换种子重生成（musicgen_bgm.py --regen k）。
sections[].target_lu 是相对响度目标（LU），可以是数字，也可以是 [起, 止] 表示章节内线性爬升；
plan.impact 是 riser→impact 所在时刻，那里的包络过渡更短，且不受相邻差上限约束。
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf

FADE_IN, FADE_OUT = 1.5, 3.0
TARGET_TP = -1.5
# 以下由 configure() 填入
WORK = OUT = RAW = SHAPED = MID = LIM = None
TOTAL, TARGET_I, IMPACT = 0.0, -20.0, None
CHAPTERS, TARGETS = [], []


def configure(plan_path, work, out):
    global WORK, OUT, RAW, SHAPED, MID, LIM, TOTAL, TARGET_I, IMPACT, CHAPTERS, TARGETS
    plan = json.loads(Path(plan_path).expanduser().read_text(encoding="utf-8"))
    WORK = Path(work).expanduser().resolve()
    OUT = Path(out).expanduser().resolve()
    RAW, SHAPED = WORK / "bgm_raw_32k.wav", WORK / "bgm_shaped_32k.wav"
    MID, LIM = WORK / "bgm_pre_48k.wav", WORK / "bgm_lim_48k.wav"
    TOTAL = float(plan["total"])
    TARGET_I = float(plan.get("target_i", -20.0))
    IMPACT = plan.get("impact")
    secs = plan["sections"]
    ends = [x["start"] for x in secs[1:]] + [TOTAL]
    CHAPTERS = [(float(x["start"]), float(e), x.get("name", x["key"])) for x, e in zip(secs, ends)]
    TARGETS = [x.get("target_lu", -2.0) for x in secs]


def target_lu(t):
    """目标相对响度（LU）：按所在章节取值，[a, b] 表示章节内从 a 线性升到 b。"""
    for (a, b, _), tg in zip(CHAPTERS, TARGETS):
        if a <= t < b or (t >= b and b == TOTAL):
            if isinstance(tg, list):
                return tg[0] + (tg[1] - tg[0]) * min(max((t - a) / (b - a), 0), 1)
            return tg
    return TARGETS[-1] if not isinstance(TARGETS[-1], list) else TARGETS[-1][1]


def is_impact(t):
    return IMPACT is not None and abs(t - IMPACT) < 1e-6


MAX_CORR_DB = 6.0   # 单步增益修正上限（相对中位数）
MAX_STEP_DB = 3.0   # 相邻两步增益差上限，避免包络本身造成接缝处电平跳变
RAMP = 2.0          # 步与步之间的增益过渡（每侧秒数）
LIMIT_DBTP = -2.0   # 预限幅天花板（4 倍过采样上限幅，留 0.5dB 给后续重采样/抖动）
EQ = "lowshelf=f=100:g=-3:t=q:w=0.7"   # 床乐 EQ：收一点超低频，让中频在手机外放上更可闻


def shape_energy():
    """按步测响度，生成分段线性（dB 域）增益曲线，把各段响度拉向 target_lu。"""
    import pyloudnorm as pyln
    x, sr = sf.read(RAW, dtype="float64")
    meter = pyln.Meter(sr)
    steps = json.loads((WORK / "prompts.json").read_text())["steps"]
    rows = []
    for st in steps:
        a, b = st["t0"], min(st["t1"], TOTAL - FADE_OUT)
        L = meter.integrated_loudness(x[int(a * sr):int(b * sr)])
        rows.append([a, min(st["t1"], TOTAL), L])
    Ls = np.array([r[2] for r in rows])
    raw_g = np.array([target_lu((r[0] + r[1]) / 2) for r in rows]) - Ls
    med = np.median(raw_g)
    pts_t, pts_g, prev = [], [], None
    for (a, b, L), g0 in zip(rows, raw_g):
        impact_a, impact_b = is_impact(a), is_impact(b)
        ra = 0.5 if impact_a else RAMP   # 收尾接缝（impact 处）过渡更短，且不受相邻差上限约束
        rb = 0.5 if impact_b else RAMP
        for i, t in enumerate((a + ra if a > 0 else 0.0, b - rb if b < TOTAL else TOTAL)):
            g = float(np.clip(target_lu(t) - L, med - MAX_CORR_DB, med + MAX_CORR_DB))
            if i == 0 and prev is not None and not impact_a:
                g = float(np.clip(g, prev - MAX_STEP_DB, prev + MAX_STEP_DB))
            if i == 1:
                g = float(np.clip(g, pts_g[-1] - MAX_STEP_DB, pts_g[-1] + MAX_STEP_DB))
            pts_t.append(t); pts_g.append(g)
        prev = pts_g[-1]
    tt = np.arange(len(x)) / sr
    gain_db = np.interp(tt, pts_t, pts_g) - np.max(pts_g)   # 只衰减不提升，避免削波
    sf.write(SHAPED, (x * 10 ** (gain_db / 20)).astype(np.float32), sr, subtype="FLOAT")
    return [dict(t0=a, t1=b, loudness=round(L, 1), target=round(target_lu((a + b) / 2), 1)) for a, b, L in rows], \
        list(zip([round(t, 2) for t in pts_t], [round(g - max(pts_g), 2) for g in pts_g]))


def ff(args, capture=True):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-3000:])
    return r.stderr


def postprocess():
    pre = (f"highpass=f=35:poles=2,{EQ},aresample=48000:filter_size=64:cutoff=0.97,pan=stereo|c0=c0|c1=c0,"
           f"atrim=0:{TOTAL},afade=t=in:st=0:d={FADE_IN},afade=t=out:st={TOTAL - FADE_OUT}:d={FADE_OUT}")
    ff(["-i", str(SHAPED), "-af", pre, "-c:a", "pcm_f32le", str(MID)])
    # 先把整体增益推到目标响度，再在 4 倍过采样（192k）下限幅，使真峰值有余量，
    # 这样 loudnorm 第二遍能保持 linear（纯增益），不会退化成会压平章节包络的 dynamic 模式
    I0 = ebur(MID)["I"]
    gain = TARGET_I - I0
    lim = 10 ** (LIMIT_DBTP / 20)
    ff(["-i", str(MID), "-af", f"volume={gain:.3f}dB,aresample=192000:filter_size=64,"
        f"alimiter=limit={lim:.5f}:attack=1:release=60:level=disabled,aresample=48000:filter_size=64:cutoff=0.97",
        "-c:a", "pcm_f32le", str(LIM)])
    ln = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=20"
    err = ff(["-i", str(LIM), "-af", ln + ":print_format=json", "-f", "null", "-"])
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    ln2 = (f"{ln}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json")
    err = ff(["-i", str(LIM), "-af", ln2 + ",aresample=48000:filter_size=64:cutoff=0.97:dither_method=triangular",
              "-ar", "48000", "-c:a", "pcm_s16le", str(OUT)])
    m2 = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    return m, m2


def ebur(path, start=None, end=None):
    args = []
    if start is not None:
        args += ["-ss", str(start), "-t", str(end - start)]
    err = ff([*args, "-i", str(path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
    s = err[err.rindex("Summary:"):]
    g = lambda pat: float(re.search(pat, s, re.S).group(1))
    return dict(I=g(r"I:\s+(-?[\d.]+) LUFS"), LRA=g(r"LRA:\s+(-?[\d.]+) LU"), TP=g(r"True peak:.*?Peak:\s+(-?[\d.inf]+) dBFS"))


def frames(x, sr, win, hop):
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def centroid(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float(np.sum(f * spec) / (np.sum(spec) + 1e-12))


def qc(norm_meta):
    lines = []
    P = lambda *a: lines.append(" ".join(str(v) for v in a))
    x, sr = sf.read(OUT, dtype="float32")
    info = sf.info(OUT)
    mono = x.mean(axis=1)
    P("# BGM 客观自检", OUT)
    P(f"格式：{info.samplerate} Hz，{info.channels} 声道，{info.subtype}，时长 {info.frames / info.samplerate:.3f}s")
    if norm_meta:
        P(f"loudnorm 第二遍：normalization_type={norm_meta.get('normalization_type')}，"
          f"输出 I={norm_meta.get('output_i')} TP={norm_meta.get('output_tp')}")

    P("\n## 1. 响度与峰值（ffmpeg ebur128，true peak）")
    full = ebur(OUT)
    P(f"整体：I={full['I']:.1f} LUFS，LRA={full['LRA']:.1f} LU，真峰值={full['TP']:.1f} dBTP")
    clipped = int(np.sum(np.abs(x) >= 32767 / 32768))
    P(f"削波样本数（|x|≥满幅）：{clipped}；采样峰值 {20 * np.log10(np.abs(x).max()):.2f} dBFS")
    P("分章节：")
    for a, b, name in CHAPTERS:
        e = ebur(OUT, a, b)
        P(f"  {name:<12} {a:7.2f}–{b:7.2f}s  I={e['I']:6.1f} LUFS  TP={e['TP']:6.1f} dBTP  RMS={rms_db(mono[int(a*sr):int(b*sr)]):6.1f} dBFS")

    P("\n## 2. 拼接点平滑度（交叉淡化区前后各 1s / 3s 窗；3s 窗平均掉节拍起伏，作为主判据）")
    meta = json.loads((WORK / "prompts.json").read_text())
    # 基线：全曲每 0.5s 取"前 1s vs 后 1s"的 RMS 差与质心比，作为非接缝处的自然波动分布
    base_dr, base_dc = [], []
    for t in np.arange(2.0, TOTAL - 4.0, 0.5):
        a, b = mono[int((t - 1) * sr):int(t * sr)], mono[int((t + 1) * sr):int((t + 2) * sr)]
        base_dr.append(abs(rms_db(b) - rms_db(a)))
        base_dc.append(abs(np.log2(centroid(b, sr) / centroid(a, sr))))
    base_dr, base_dc = np.array(base_dr), np.array(base_dc)
    base_dr3 = np.array([abs(rms_db(mono[int((t + 1) * sr):int((t + 4) * sr)]) - rms_db(mono[int((t - 3) * sr):int(t * sr)]))
                         for t in np.arange(4.0, TOTAL - 6.0, 0.5)])
    P(f"基线（非接缝，跨 1s 间隔）：|ΔRMS| 中位 {np.median(base_dr):.2f} dB / P90 {np.percentile(base_dr, 90):.2f} dB；"
      f"|Δ质心| 中位 {np.median(base_dc):.2f} oct / P90 {np.percentile(base_dc, 90):.2f} oct；"
      f"3s 窗 |ΔRMS| 中位 {np.median(base_dr3):.2f} dB / P90 {np.percentile(base_dr3, 90):.2f} dB")
    d = np.abs(np.diff(mono))
    click_ref = np.percentile(d, 99.99)
    for j in meta["joins"]:
        s0, s1 = j["xfade"]
        a, b = mono[int((s0 - 1) * sr):int(s0 * sr)], mono[int(s1 * sr):int((s1 + 1) * sr)]
        dr = rms_db(b) - rms_db(a)
        dr3 = rms_db(mono[int(s1 * sr):int((s1 + 3) * sr)]) - rms_db(mono[int((s0 - 3) * sr):int(s0 * sr)])
        pr3 = (base_dr3 < abs(dr3)).mean() * 100
        dc = np.log2(centroid(b, sr) / centroid(a, sr))
        seg = d[int((s0 - 0.25) * sr):int((s1 + 0.25) * sr)]
        around = np.concatenate([d[int((s0 - 4.25) * sr):int((s0 - 0.25) * sr)], d[int((s1 + 0.25) * sr):int((s1 + 4.25) * sr)]])
        win = mono[int((s0 - 0.5) * sr):int((s1 + 0.5) * sr)]
        fr = frames(win, sr, int(0.05 * sr), int(0.025 * sr))
        min_fr = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)).min() + 1e-12)
        pr = (base_dr < abs(dr)).mean() * 100
        pc = (base_dc < abs(dc)).mean() * 100
        click = seg.max() / around.max()
        flag = "  <-- 注意" if (pr3 > 95 or pc > 95 or click > 1.2 or min_fr < -50) else ""
        if j["step"] == len(meta["steps"]) - 1 and flag:
            flag += "（若设了 recap：主题回归处有意切回开场氛围，r≈0 与质心下移属预期）"
        P(f"  步{j['step']:02d} @{j['time']:7.2f}s r={j['corr']:+.2f}  ΔRMS3s={dr3:+5.2f} dB(基线 P{pr3:3.0f})  ΔRMS1s={dr:+5.2f} dB(P{pr:3.0f})  "
          f"Δ质心={dc:+.2f} oct(基线 P{pc:3.0f})  接缝/邻近4s最大样本差={click:4.2f}  "
          f"50ms 最低RMS={min_fr:6.1f} dBFS{flag}")

    P("\n## 3. 近静音段（50ms 窗 RMS < -50 dBFS，连续 > 1.5s；淡入淡出区除外）")
    fr = frames(mono, sr, int(0.05 * sr), int(0.05 * sr))
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-12)
    quiet = db < -50
    runs, start = [], None
    for i, q in enumerate(np.append(quiet, False)):
        t = i * 0.05
        if q and start is None:
            start = t
        elif not q and start is not None:
            if t - start > 1.5 and start > FADE_IN and t < TOTAL - FADE_OUT:
                runs.append((start, t))
            start = None
    P("  无" if not runs else "\n".join(f"  {a:.2f}–{b:.2f}s" for a, b in runs))
    P(f"  全曲 50ms 窗 RMS 最低（淡入淡出区外）：{db[int(FADE_IN / 0.05):int((TOTAL - FADE_OUT) / 0.05)].min():.1f} dBFS")

    P("\n## 4. 能量曲线（每 10s RMS dBFS / 频谱质心 Hz / 150Hz 以下能量占比）")
    for t in np.arange(0, TOTAL, 10):
        seg = mono[int(t * sr):int(min(t + 10, TOTAL) * sr)]
        spec = np.abs(np.fft.rfft(seg)) ** 2
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        low = spec[f < 150].sum() / spec.sum()
        r = rms_db(seg)
        ch = next(n for a, b, n in CHAPTERS if a <= t < b)
        P(f"  {t:5.0f}–{min(t + 10, TOTAL):6.1f}s  RMS={r:6.1f}  质心={centroid(seg, sr):6.0f}  <150Hz={low * 100:4.1f}%  "
          f"{'#' * max(0, int((r + 45) * 1.5))}  [{ch}]")
    P("\n## 5. 调性粗估（100–2000Hz 色度 + Krumhansl 模板，仅供参考）")
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    for a, b, name in CHAPTERS:
        seg, chroma = mono[int(a * sr):int(b * sr)], np.zeros(12)
        for i in range(0, len(seg) - 8192, 4096):
            p = np.abs(np.fft.rfft(seg[i:i + 8192] * np.hanning(8192))) ** 2
            f = np.fft.rfftfreq(8192, 1 / sr)
            m = (f > 100) & (f < 2000)
            np.add.at(chroma, np.round(12 * np.log2(f[m] / 440) + 9).astype(int) % 12, p[m] / p[m].sum())
        r, key = max((np.corrcoef(np.roll(t, k), chroma)[0, 1], names[k] + mode)
                     for t, mode in ((maj, " 大调"), (mnr, " 小调")) for k in range(12))
        P(f"  {name:<12} 最接近 {key}（r={r:.2f}），前三音级 {[names[i] for i in np.argsort(chroma)[-3:][::-1]]}")
    (WORK / "qc.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--qc-only", action="store_true")
    a = ap.parse_args()
    configure(a.plan, a.work, a.out)
    m2 = None
    if not a.qc_only:
        rows, pts = shape_energy()
        (WORK / "envelope.json").write_text(json.dumps(dict(steps=rows, gain_points_db=pts), ensure_ascii=False, indent=1))
        m1, m2 = postprocess()
        print("loudnorm pass1:", m1)
    qc(m2)
