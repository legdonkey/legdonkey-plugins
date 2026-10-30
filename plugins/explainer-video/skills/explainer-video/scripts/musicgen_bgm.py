#!/usr/bin/env python3
"""用 MusicGen 音频续写生成随章节演进的连续 BGM（原始 32kHz 单声道），之后交给 bgm_post_qc.py。

用法：
  HF_ENDPOINT=https://hf-mirror.com ~/.venvs/musicgen/bin/python musicgen_bgm.py \
      --plan P/audio/bgm_plan.json --work P/audio/musicgen_work
  # 从第 k 步起重生成（k 之前复用 segments/ 中已有原始片段），可覆盖种子：
  ... --from-step 7 --seed 7=1234 --seed 9=555
  # 只重生成指定步（其后以它为 prompt 的续写步会连带重生成；主题回归步只依赖开场）：
  ... --regen 14

bgm_plan.json 见技能 assets/bgm_plan.example.json：total、style（拼到每条提示词后，统一调性与速度）、
sections（起点、键、提示词列表，章节内各步按进度均匀分配提示词）、可选 recap（主题回归的开场片段）、seed。

每一步：取已拼接音频末尾 CTX 秒作为 audio prompt，配当前章节提示词续写；
模型输出 = 重新解码的 prompt 区 + 新内容。按输出中 prompt 区末尾对齐到时间 T，
在接缝处做相关性自适应的等功率交叉淡化（不相关时为标准等功率，高度相关时退化为等幅线性，
避免两段相干信号叠加出现 +3dB 鼓包）。
设了 recap 时，最后一段不接上一段尾部，而以开场片段为 prompt 续写，实现主题回归。
每步生成后自检（断档、与 prompt 电平落差、超低频、中频占比），不通过则换种子重试，最多 MAX_TRIES 次。
"""
import argparse, json, math, os, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

SR = 32000
FRAME = 640            # EnCodec 32kHz 帧长（50Hz）
CTX = 8.0              # audio prompt 长度（秒）；8s 比 10s 给文本提示词更多引导力
MAX_NEW = 19.5         # 单步新内容上限（CTX+新内容 ≤ 30s）
XF = 1.0               # 常规接缝交叉淡化长度
TAIL_MARGIN = 3.0      # 多生成的余量
OUTRO_XF = 1.0         # 主题回归接缝居中于该段起点，前后各 0.5s
MAX_TRIES = 5          # 单步自检不通过时换种子重试的次数上限
SEED_STRIDE = 7919

# 以下由 configure() 按 bgm_plan.json 填入
WORK = SEG = None
TOTAL = 0.0
CHAPTERS = []          # [(起点, 键, 提示词列表)]
OUTRO_CTX = None       # (a, b)：最后一段以开场这一段为 prompt 续写（主题回归）；None 表示照常续写
BASE_SEED = 20251025


def configure(plan_path, work):
    global WORK, SEG, TOTAL, CHAPTERS, OUTRO_CTX, BASE_SEED
    plan = json.loads(Path(plan_path).expanduser().read_text(encoding="utf-8"))
    WORK = Path(work).expanduser().resolve()
    SEG = WORK / "segments"
    TOTAL = float(plan["total"])
    style = plan.get("style", "")
    CHAPTERS = [(float(x["start"]), x["key"], [f"{pr}, {style}" if style else pr for pr in x["prompts"]])
                for x in plan["sections"]]
    OUTRO_CTX = tuple(plan["recap"]) if plan.get("recap") else None
    BASE_SEED = int(plan.get("seed", BASE_SEED))


def plan_steps():
    """把章节切成若干步：每步覆盖 [T, T_next]，新内容 ≤ MAX_NEW。"""
    ends = [c[0] for c in CHAPTERS[1:]] + [TOTAL + TAIL_MARGIN]
    steps = []
    for (start, key, prompts), end in zip(CHAPTERS, ends):
        n = max(1, math.ceil((end - start) / MAX_NEW))
        for i in range(n):
            t0 = start + (end - start) * i / n
            t1 = start + (end - start) * (i + 1) / n
            steps.append(dict(chapter=key, t0=round(t0, 3), t1=round(t1, 3),
                              prompt=prompts[i * len(prompts) // n]))
    for k, s in enumerate(steps):
        s["step"] = k
        s["seed"] = BASE_SEED + k * 101
        if OUTRO_CTX and s["chapter"] == CHAPTERS[-1][1] and steps[k - 1]["chapter"] != s["chapter"]:
            s["mode"] = "outro_recap"
        elif k == 0:
            s["mode"] = "text_only"
        else:
            s["mode"] = "continue"
    return steps


def samples(sec):
    return int(round(sec * SR))


def adaptive_xfade(a, b):
    """相关性自适应等功率交叉淡化：增益满足 ga²+gb²+2·r·ga·gb = 1。"""
    n = len(a)
    r = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    r = max(0.0, r)
    t = np.linspace(0.0, 1.0, n)
    ga, gb = 1.0 - t, t
    norm = np.sqrt(ga ** 2 + gb ** 2 + 2 * r * ga * gb)
    return (a * ga + b * gb) / norm, r


def prompt_lag(ctx, out, win=SR, search=2000):
    """检查输出中重新解码的 prompt 区是否与原 prompt 逐样本对齐（返回最佳相关的偏移）。"""
    ref = ctx[-win:]
    best = (-2.0, 0)
    for lag in range(-search, search + 1, 20):
        st = len(ctx) - win + lag
        if st < 0 or st + win > len(out):
            continue
        seg = out[st:st + win]
        r = float(np.dot(ref, seg) / (np.linalg.norm(ref) * np.linalg.norm(seg) + 1e-12))
        best = max(best, (r, lag))
    return best[1]


def one_sec_db(x):
    w = SR
    rms = np.array([np.sqrt(np.mean(x[i:i + w] ** 2)) for i in range(0, len(x) - w + 1, w // 2)])
    return 20 * np.log10(rms + 1e-12)


def step_check(new, check_until, ctx=None):
    """单步自检：无断档、与 prompt 电平衔接、超低频不过量、中频不缺失（手机外放可闻）。返回 (是否通过, 指标)。"""
    x = new[:max(check_until, SR)]
    db = one_sec_db(x)
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    sub = float(p[f < 60].sum() / p.sum())
    mid = float(p[(f >= 150) & (f < 2000)].sum() / p.sum())
    m = dict(min_1s_db=round(float(db.min()), 1), median_1s_db=round(float(np.median(db)), 1),
             sub60_share=round(sub, 3), mid150_2k_share=round(mid, 3))
    reasons = []
    if db.min() < -40 or db.min() < np.median(db) - 12:
        reasons.append("断档/掉电平")
    if ctx is not None:
        m["ctx_median_1s_db"] = round(float(np.median(one_sec_db(ctx))), 1)
        if abs(np.median(db) - m["ctx_median_1s_db"]) > 8:
            reasons.append("与上一段电平落差过大")
    if sub > 0.75:
        reasons.append("超低频过多")
    if mid < 0.08:
        reasons.append("中频缺失")
    m["fail"] = reasons
    return not reasons, m


def load_model(device):
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    name = "facebook/musicgen-medium"
    proc = AutoProcessor.from_pretrained(name)
    model = MusicgenForConditionalGeneration.from_pretrained(name, torch_dtype=torch.float32)
    model.to(device).eval()
    return proc, model


def generate(proc, model, device, prompt, seed, new_sec, ctx_audio=None):
    torch.manual_seed(seed)
    np.random.seed(seed % (2 ** 32))
    if device == "mps":
        torch.mps.manual_seed(seed)
    if ctx_audio is None:
        inputs = proc(text=[prompt], padding=True, return_tensors="pt")
    else:
        inputs = proc(audio=ctx_audio, sampling_rate=SR, text=[prompt], padding=True, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, do_sample=True, guidance_scale=3.0, top_k=250,
                             max_new_tokens=int(math.ceil(new_sec * 50)) + 8)  # 码本延迟模式会吃掉约 4 帧
    return out[0, 0].float().cpu().numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="bgm_plan.json")
    ap.add_argument("--work", required=True, help="过程目录：原始片段、prompts.json、bgm_raw_32k.wav")
    ap.add_argument("--from-step", type=int, default=0)
    ap.add_argument("--regen", type=int, action="append", default=[], help="只重生成这些步")
    ap.add_argument("--seed", action="append", default=[], help="k=seed 覆盖第 k 步种子")
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = ap.parse_args()
    configure(args.plan, args.work)
    SEG.mkdir(parents=True, exist_ok=True)

    steps = plan_steps()
    pj = WORK / "prompts.json"
    if pj.exists():  # 沿用之前记录的种子（含历史覆盖）
        old = {s["step"]: s for s in json.loads(pj.read_text())["steps"]}
        for s in steps:
            o = old.get(s["step"])
            if o and o["t0"] == s["t0"] and o["prompt"] == s["prompt"] and o.get("mode") == s["mode"]:
                for key in ("seed", "history", "gen_seconds", "attempts", "qc"):
                    if key in o:
                        s[key] = o[key]
    for kv in args.seed:
        k, v = kv.split("=")
        s = steps[int(k)]
        s.setdefault("history", []).append(s["seed"])
        s["seed"] = int(v)

    proc = model = None
    acc = np.zeros(0, dtype=np.float32)
    joins = []
    t_start = time.time()
    for s in steps:
        k = s["step"]
        T = s["t0"]
        nxt = steps[k + 1] if k + 1 < len(steps) else None
        post = OUTRO_XF / 2 if (nxt and nxt["mode"] == "outro_recap") else 0.0
        new_sec = s["t1"] - s["t0"] + post
        seg_path = SEG / f"seg{k:02d}_{s['chapter']}.wav"

        if s["mode"] == "text_only":
            ctx = None
        elif s["mode"] == "outro_recap":
            a, b = samples(OUTRO_CTX[0]), samples(OUTRO_CTX[1])
            ctx = acc[a:b].copy()
        else:
            ctx = acc[samples(T) - samples(CTX):samples(T)].copy()
        ctx_len = 0 if ctx is None else len(ctx)
        assert ctx_len % FRAME == 0, (k, ctx_len)

        need = samples(s["t1"] + post) - samples(T)
        # 自检只看最终会保留的部分（收尾步排除末尾淡出区与余量）
        check_until = need - (samples(TAIL_MARGIN + 3.0) if nxt is None else 0)
        if args.regen:
            dirty = k in args.regen or (s["mode"] == "continue" and steps[k - 1].get("_regen"))
        else:
            dirty = k >= args.from_step
        s["_regen"] = dirty or not seg_path.exists()
        if not s["_regen"]:
            out, _ = sf.read(seg_path, dtype="float32")
        else:
            if model is None:
                print(f"加载模型到 {args.device} ...", flush=True)
                proc, model = load_model(args.device)
            s["attempts"] = []
            base = s["seed"]
            best = None
            for attempt in range(MAX_TRIES):
                seed = base + attempt * SEED_STRIDE
                t0 = time.time()
                out = generate(proc, model, args.device, s["prompt"], seed, new_sec, ctx)
                dt = round(time.time() - t0, 1)
                ok, m = step_check(out[ctx_len:ctx_len + need], check_until,
                                   ctx if s["mode"] == "continue" else None)
                s["attempts"].append(dict(seed=seed, seconds=dt, **m))
                score = (len(m["fail"]), -m["mid150_2k_share"])
                if best is None or score < best[0]:
                    best = (score, out, seed, m)
                print(f"[{k:02d}] {s['chapter']} T={T:.2f} new={new_sec:.2f}s seed={seed} "
                      f"out={len(out)/SR:.2f}s ctx={ctx_len/SR:.2f}s 耗时 {dt}s 自检 {m}", flush=True)
                if ok:
                    break
            else:
                _, out, seed, m = best
                print(f"[{k:02d}] {MAX_TRIES} 次均未通过自检，保留问题最少的 seed={seed}", flush=True)
            s["seed"], s["qc"] = seed, m
            s["gen_seconds"] = round(sum(a["seconds"] for a in s["attempts"]), 1)
            sf.write(seg_path, out, SR, subtype="FLOAT")
        assert np.isfinite(out).all(), f"step {k} 输出含 NaN/Inf"
        s["raw_file"] = str(seg_path.relative_to(WORK))
        s["out_seconds"] = round(len(out) / SR, 3)

        if ctx is None:
            assert len(out) >= need, f"step {k} 输出不足：{len(out)} < {need}"
            acc = out[:need].astype(np.float32)
            continue
        s["prompt_align_lag"] = prompt_lag(ctx, out)
        assert s["prompt_align_lag"] == 0, f"step {k} prompt 区未对齐，lag={s['prompt_align_lag']}"

        new_part = out[ctx_len:ctx_len + need]
        if len(new_part) < need:
            raise RuntimeError(f"step {k} 输出不足：{len(new_part)} < {need}")
        if s["mode"] == "outro_recap":
            # 接缝居中于 T：acc 已多生成 0.5s；取输出 prompt 区最后 0.5s 作为淡入前导
            h = samples(OUTRO_XF / 2)
            lead = out[ctx_len - h:ctx_len]
            a_tail = acc[samples(T) - h:samples(T) + h]
            b_head = np.concatenate([lead, new_part[:h]])
            mixed, r = adaptive_xfade(a_tail, b_head)
            acc = np.concatenate([acc[:samples(T) - h], mixed, new_part[h:]])
            joins.append(dict(step=k, time=T, xfade=[T - OUTRO_XF / 2, T + OUTRO_XF / 2], corr=round(r, 3)))
        else:
            x = samples(XF)
            assert len(acc) == samples(T), (k, len(acc), samples(T))
            a_tail = acc[-x:]
            b_head = out[ctx_len - x:ctx_len]   # 输出中重新解码的 prompt 区末尾
            mixed, r = adaptive_xfade(a_tail, b_head)
            acc = np.concatenate([acc[:-x], mixed, new_part])
            joins.append(dict(step=k, time=T, xfade=[T - XF, T], corr=round(r, 3)))
        s["join_corr"] = joins[-1]["corr"]

    sf.write(WORK / "bgm_raw_32k.wav", acc, SR, subtype="FLOAT")
    for s in steps:
        s.pop("_regen", None)
    meta = dict(model="facebook/musicgen-medium", device=args.device, sr=SR, ctx_seconds=CTX,
                guidance_scale=3.0, top_k=250, xfade_seconds=XF, total_seconds=round(len(acc) / SR, 3),
                wall_seconds=round(time.time() - t_start, 1), steps=steps, joins=joins)
    pj.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"完成：{len(acc)/SR:.2f}s，接缝 {len(joins)} 个，用时 {meta['wall_seconds']}s")


if __name__ == "__main__":
    main()
