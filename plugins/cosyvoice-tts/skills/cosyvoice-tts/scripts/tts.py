#!/usr/bin/env python3
"""阿里百炼 CosyVoice 语音合成(默认模型 cosyvoice-v3-flash)。

- list:    列出 v3-flash 全部音色(与官方对齐),标出是否支持 Instruct
- preview: 合成一句并播放(试听)。支持 Instruct 的音色会按场景自动设指令并提示
- gen:     合成整段并保存 wav(含规范化 + 时长)

Instruct(仅部分音色支持):用规定中文句式控制情感/场景/角色,脚本自动拼好。
情感值:neutral/happy/angry/sad/surprised/fearful/disgusted。

API key:环境变量 DASHSCOPE_API_KEY → 文件 ~/.dashscope_key。
依赖:ffmpeg/ffprobe、afplay(macOS 播放)。
"""
import argparse, difflib, json, os, subprocess, sys, tempfile

DEFAULT_MODEL = "cosyvoice-v3-flash"
DEFAULT_VOICE = "longanhuan"
DEFAULT_SAMPLE = "这次活动的效果,真是出乎我的意料。"
EMOTIONS = ["neutral", "happy", "angry", "sad", "surprised", "fearful", "disgusted"]

# 没显式给情感时,按音色场景挑一个合适的默认情感(用于「根据场景设置 instruct」)。
SCENE_EMOTION = {
    "直播带货": "happy", "短视频配音": "happy", "电话销售": "happy",
    "童声": "happy", "儿童": "happy", "儿童故事机": "happy", "儿童玩具": "happy",
    "客服": "neutral", "新闻播报": "neutral", "有声书": "neutral",
    "语音助手": "neutral", "社交陪伴": "neutral", "诗词朗诵": "neutral",
}

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "references", "voices_v3flash.json")


def load_catalog():
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)["voices"]


def voice_entry(voice):
    for v in load_catalog():
        if v["voice"] == voice:
            return v
    return None


def get_key():
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not k:
        p = os.path.expanduser("~/.dashscope_key")
        if os.path.exists(p):
            k = open(p).read().strip()
    if not k:
        sys.exit("找不到 API key:请设置 DASHSCOPE_API_KEY,或把 key 存到 ~/.dashscope_key")
    return k


def _snap(req, allowed):
    """把用户给的值就近匹配到该音色的合法取值。返回 (值, 是否做了替换) 或 (None, False)。"""
    if not allowed:
        return None, False
    if req in allowed:
        return req, False
    for v in allowed:                       # 子串包含,如「客服」→「温和客服」
        if req in v or v in req:
            return v, True
    m = difflib.get_close_matches(req, allowed, n=1, cutoff=0.4)
    return (m[0], True) if m else (None, False)


def resolve_instruction(a, ventry):
    """返回 (instruction, 说明文字, 回退指令)。
    要点:① 句式用全角逗号「，」(实测半角会失败);② 场景/角色/身份须用该音色的
    合法取值,脚本按官方取值就近匹配;③ 匹配不到则退回纯情感(纯情感最稳)。"""
    explicit = bool(a.instruct or a.emotion or a.scene or a.role or a.identity)
    supports = bool(ventry and ventry.get("instruct")) or (ventry is None and explicit)
    if not supports:
        if explicit:
            return None, "⚠ 该音色不支持 Instruct,已忽略,按普通合成", None
        return None, "该音色不支持 Instruct,普通合成", None
    opts = (ventry or {}).get("instruct_options", {})
    scene = (ventry or {}).get("scene")
    emo = a.emotion or SCENE_EMOTION.get(scene, "neutral")
    fallback = f"你说话的情感是{emo}。"          # 纯情感(全角句号),最稳的回退
    if a.instruct:
        instr = a.instruct.replace(",", "，")
        normalized = instr != a.instruct
        tag = f"Instruct(自定义):{instr}" + ("（已把半角逗号转为全角逗号）" if normalized else "")
        return instr, tag, fallback

    for dim, val, key, tmpl in [
        ("场景", a.scene, "scenes", "你正在进行{x}，你说话的情感是" + emo + "。"),
        ("角色", a.role, "roles", "你说话的角色是{x}，你说话的情感是" + emo + "。"),
        ("身份", a.identity, "identities", "你正在以一个{x}的身份说话，你说话的情感是" + emo + "。"),
    ]:
        if not val:
            continue
        picked, snapped = _snap(val, opts.get(key, []))
        if picked is None:
            allowed = "、".join(opts.get(key, [])) or "(无)"
            note = f"「{val}」不在 {ventry['name']} 的{dim}取值【{allowed}】内,改用纯情感 {emo}"
            return fallback, f"Instruct(情感 {emo};{note})", None
        tag = f"Instruct({dim} {picked}" + (f"←就近自「{val}」" if snapped else "") + f" / 情感 {emo})"
        return tmpl.format(x=picked), tag, fallback

    if a.emotion:
        return fallback, f"Instruct(情感 {emo})", None
    # 没显式给任何指令 → 用该音色的默认 Instruct(若配置了),否则纯情感
    dflt = opts.get("default")
    if dflt:
        demo = dflt.get("emotion", "neutral")
        fb2 = f"你说话的情感是{demo}。"
        if dflt.get("scene"):
            return (f"你正在进行{dflt['scene']}，你说话的情感是{demo}。",
                    f"Instruct(默认:场景 {dflt['scene']} / 情感 {demo})", fb2)
        if dflt.get("role"):
            return (f"你说话的角色是{dflt['role']}，你说话的情感是{demo}。",
                    f"Instruct(默认:角色 {dflt['role']} / 情感 {demo})", fb2)
        return fb2, f"Instruct(默认:情感 {demo})", None
    return fallback, f"Instruct(按场景「{scene}」默认情感 {emo})", None


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def synth(model, voice, text, instruction=None, rate=1.0, pitch=1.0, volume=50):
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
    dashscope.api_key = get_key()
    rate, pitch, volume = _clamp(rate, 0.5, 2.0), _clamp(pitch, 0.5, 2.0), int(_clamp(volume, 0, 100))
    kw = dict(model=model, voice=voice, format=AudioFormat.WAV_24000HZ_MONO_16BIT,
              speech_rate=rate, pitch_rate=pitch, volume=volume)
    if instruction:
        kw["instruction"] = instruction
    try:
        audio = SpeechSynthesizer(**kw).call(text)
        if isinstance(audio, (bytes, bytearray)) and len(audio) > 2000:
            return bytes(audio)
    except Exception as e:
        print(f"  合成异常: {repr(e)[:120]}", file=sys.stderr)
    return None


def normalize(raw, out_path):
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(raw); tmp = f.name
    try:
        subprocess.run(["ffmpeg", "-y", "-i", tmp, "-ar", "24000", "-ac", "1",
                        "-c:a", "pcm_s16le", out_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    finally:
        os.unlink(tmp)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def cmd_list(a):
    cat = load_catalog()
    if a.instruct_only:
        cat = [v for v in cat if v["instruct"]]
    # 按场景分组,保持原顺序
    groups = {}
    for v in cat:
        groups.setdefault(v["scene"], []).append(v)
    n_ins = sum(1 for v in load_catalog() if v["instruct"])
    print(f"cosyvoice-v3-flash 音色(共 {len(cat)} 个;⭐ = 支持 Instruct,实测可用 {n_ins} 个)\n")
    for scene, vs in groups.items():
        print(f"【{scene}】")
        for v in vs:
            star = "⭐" if v["instruct"] else "  "
            age = v.get("age", "")
            trait = v.get("trait", "")
            print(f"  {star} {v['voice']:18s} {v['name']:8s} {v['gender']:2s} {age:8s} {trait:8s} {v['lang']}")
            o = v.get("instruct_options")
            if o:
                if o.get("scenes"):     print(f"        场景: {'、'.join(o['scenes'])}")
                if o.get("roles"):      print(f"        角色: {'、'.join(o['roles'])}")
                if o.get("identities"): print(f"        身份: {'、'.join(o['identities'])}")
        print()
    print("Instruct 控制(仅⭐音色):")
    print("  --emotion", "/".join(EMOTIONS))
    print("  --scene/--role/--identity:用上面各音色的合法取值(会自动就近匹配;匹配不到则退回纯情感)")
    print("用法:preview -v longanyang --scene 新闻播报 [--text \"...\"]   /   -v longhuhu_v3 --role 可爱孩童")
    print("数据来源(以官方为准):https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list")


def _run(a, save_path, play):
    ventry = voice_entry(a.voice)
    instr, tag, fallback = resolve_instruction(a, ventry)
    text = None
    if getattr(a, "file", None):
        text = open(a.file, encoding="utf-8").read().strip()
    elif a.text:
        text = a.text
    elif play:  # preview 允许用默认示例
        text = DEFAULT_SAMPLE
    if not text:
        sys.exit("请用 --text \"...\" 或 --file 文件 提供文本。")

    print(f"🎙 {a.model} / {a.voice}" + (f"({ventry['name']}·{ventry['gender']})" if ventry else "") + f"  | {tag}")
    raw = synth(a.model, a.voice, text, instr, a.rate, a.pitch, a.volume)
    if not raw and fallback and fallback != instr:
        print(f"  ↩ 指令未被接受,回退到纯情感重试:{fallback}")
        raw = synth(a.model, a.voice, text, fallback, a.rate, a.pitch, a.volume)
    if not raw:
        hint = "(带指令失败多为该音色不支持 Instruct 或取值不合规)" if instr else "(组合可能无效,见 list)"
        sys.exit(f"✗ 合成失败 {hint}")
    normalize(raw, save_path)
    print(f"✅ {save_path}  ({duration(save_path):.2f}s)")
    if play and sys.platform == "darwin":
        print("▶️ 播放中…"); subprocess.run(["afplay", save_path])


def cmd_preview(a):
    out = a.out or os.path.join(tempfile.gettempdir(), f"preview_{a.voice}.wav")
    _run(a, out, play=True)


def cmd_gen(a):
    _run(a, a.out, play=False)


def add_instruct_opts(sp):
    sp.add_argument("-m", "--model", default=DEFAULT_MODEL)
    sp.add_argument("-v", "--voice", default=DEFAULT_VOICE)
    sp.add_argument("--emotion", choices=EMOTIONS, help="情感值")
    sp.add_argument("--scene", help="场景(自动就近匹配到该音色合法取值)")
    sp.add_argument("--role", help="角色(自动就近匹配)")
    sp.add_argument("--identity", help="身份(自动就近匹配)")
    sp.add_argument("--instruct", help="直接给完整指令文本(高级;覆盖上面)")
    sp.add_argument("--rate", type=float, default=1.0, help="语速 0.5-2.0")
    sp.add_argument("--pitch", type=float, default=1.0, help="音调 0.5-2.0")
    sp.add_argument("--volume", type=int, default=50, help="音量 0-100")


def main():
    p = argparse.ArgumentParser(description="阿里 CosyVoice 语音合成(v3-flash + Instruct)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="列出 v3-flash 全部音色")
    sp.add_argument("--instruct-only", action="store_true", dest="instruct_only", help="只看支持 Instruct 的")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("preview", help="合成一句并试听"); add_instruct_opts(sp)
    sp.add_argument("--text", help="自定义试听文本"); sp.add_argument("--out", help="保存路径")
    sp.set_defaults(func=cmd_preview)

    sp = sub.add_parser("gen", help="合成整段并保存"); add_instruct_opts(sp)
    sp.add_argument("--text", help="要合成的文本"); sp.add_argument("--file", help="从文件读取")
    sp.add_argument("--out", required=True, help="输出 wav 路径")
    sp.set_defaults(func=cmd_gen)

    a = p.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
