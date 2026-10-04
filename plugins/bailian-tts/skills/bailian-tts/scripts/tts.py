#!/usr/bin/env python3
"""阿里百炼语音合成(固定模型 qwen-audio-3.1-tts-flash)。

- voices:  列出系统音色(与官方对齐);--mine 列出账号下全部复刻音色,标出哪些本模型可用
- preview: 合成一句并播放(试听)
- gen:     合成整段并保存 wav(规范化 + 时长)
- script:  按脚本逐段生成 wav,并输出 manifest.json、subtitles.srt 与拼接好的 all.wav
- clone:   用本地录音(自动转码、上传百炼临时存储)或公网 URL 复刻音色
- delete:  删除一个复刻音色

指令(instruction):任意自然语言,≤100 字符(汉字计 2),系统音色与复刻音色都支持。
文本内可直接嵌入 [excited]、[laughing] 等情感/富语言标签。

API key:环境变量 DASHSCOPE_API_KEY → 文件 ~/.dashscope_key。
依赖:dashscope、ffmpeg、afplay(macOS 播放)。
"""
import argparse, json, os, re, subprocess, sys, tempfile, time, wave

MODEL = "qwen-audio-3.1-tts-flash"
DEFAULT_VOICE = "longanhuan_v3.1"
DEFAULT_SAMPLE = "这次活动的效果，真是出乎我的意料。"
EMOTION_ZH = {"neutral": "平静", "happy": "开心", "angry": "生气", "sad": "难过",
              "surprised": "惊讶", "fearful": "害怕", "disgusted": "厌恶"}
INSTRUCTION_LIMIT = 100
CLONE_LANGS = ["zh", "en", "fr", "de", "ja", "ko", "ru", "pt", "th", "id", "vi", "it", "es", "ms", "fil", "ar"]
TAG = re.compile(r"\[[^\[\]]*\]")

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "references", "voices.json")


def load_catalog():
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)["voices"]


def voice_entry(voice):
    for v in load_catalog():
        if v["voice"] == voice:
            return v
    return None


def check_voice(voice):
    """音色必须属于本模型,否则服务端只回 411。系统音色查 catalog,复刻音色看 ID 前缀。"""
    if voice_entry(voice) or voice.startswith(MODEL + "-"):
        return
    m = re.match(r"(.+)-[A-Za-z0-9]{1,10}-[0-9a-f]{16,}$", voice)  # 复刻音色 ID:{target_model}-{prefix}-{hex}
    if m:
        sys.exit(f"音色 {voice} 是为 {m.group(1)} 创建的复刻音色,不能用于 {MODEL}。需要用本模型重新 clone。")
    print(f"⚠ {voice} 不在 {MODEL} 的音色 catalog 中(系统音色以 _v3.1 结尾)。"
          "若是官方新增音色可继续;报 411 即音色不属于本模型。", file=sys.stderr)


def get_key():
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not k:
        p = os.path.expanduser("~/.dashscope_key")
        if os.path.exists(p):
            k = open(p).read().strip()
    if not k:
        sys.exit("找不到 API key:请设置 DASHSCOPE_API_KEY,或把 key 存到 ~/.dashscope_key")
    return k


def init_dashscope():
    import dashscope
    dashscope.api_key = get_key()


def instruction_length(text):
    """按官方口径计长度:汉字计 2,其余字符计 1。"""
    return sum(2 if re.match(r"[㐀-䶿一-鿿豈-﫿]", ch) else 1 for ch in text)


def resolve_instruction(instruct, emotion):
    """--instruct 原样使用;只给 --emotion 时拼成一句自然语言。"""
    instr = instruct or (f"用{EMOTION_ZH[emotion]}的语气说话。" if emotion else None)
    if instr and instruction_length(instr) > INSTRUCTION_LIMIT:
        sys.exit(f"指令过长:{instruction_length(instr)} 字符(汉字计 2),上限 {INSTRUCTION_LIMIT}:{instr}")
    return instr


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def synth(voice, text, instruction=None, rate=1.0, pitch=1.0, volume=50):
    from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
    init_dashscope()
    kw: dict = dict(model=MODEL, voice=voice, format=AudioFormat.WAV_24000HZ_MONO_16BIT,
              speech_rate=_clamp(rate, 0.5, 2.0), pitch_rate=_clamp(pitch, 0.5, 2.0),
              volume=int(_clamp(volume, 0, 100)))
    if instruction:
        kw["instruction"] = instruction
    try:
        audio = SpeechSynthesizer(**kw).call(text)
        if isinstance(audio, (bytes, bytearray)) and len(audio) > 2000:
            return bytes(audio)
    except Exception as e:
        print(f"  合成异常: {str(e)[-200:]}", file=sys.stderr)
    return None


def normalize(raw, out_path):
    """流式返回的 wav 头长度不可靠,统一用 ffmpeg 重写成 24kHz 单声道 16bit。"""
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
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def synth_to_file(voice, text, instr, a, out_path):
    raw = synth(voice, text, instr, a.rate, a.pitch, a.volume)
    if not raw:
        sys.exit("✗ 合成失败(411 = 音色不属于本模型;指令过长或格式异常也会失败)")
    normalize(raw, out_path)
    return duration(out_path)


def describe(voice):
    v = voice_entry(voice)
    return f"{voice}({v['name']}·{v['gender']})" if v else voice


# ---------- voices / clone / delete ----------

def cmd_voices(a):
    if a.mine:
        return list_mine()
    cat = [v for v in load_catalog()
           if (not a.gender or v["gender"] == a.gender) and (not a.scene or a.scene in v["scene"] + v.get("usage", ""))]
    groups = {}
    for v in cat:
        groups.setdefault(v["scene"], []).append(v)
    print(f"{MODEL} 系统音色(共 {len(cat)} 个;全部支持自然语言指令)\n")
    for scene, vs in groups.items():
        print(f"【{scene}】")
        for v in vs:
            print(f"  {v['voice']:20s} {v['name']:8s} {v['gender']:2s} {v.get('trait', ''):10s} {v['lang']}")
            if v.get("usage"):
                print(f"        适用: {v['usage']}")
        print()
    print("指令:--instruct \"自然语言描述\"(≤100 字符,汉字计 2);文本内标签见 references/voices.md")
    print("数据来源(以官方为准):https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list")


def list_mine():
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    init_dashscope()
    svc, rows, page = VoiceEnrollmentService(), [], 0
    while True:
        batch = svc.list_voices(prefix=None, page_index=page, page_size=100) or []
        rows += batch
        if len(batch) < 100:
            break
        page += 1
    usable = [r for r in rows if r.get("target_model") == MODEL]
    others = [r for r in rows if r.get("target_model") != MODEL]
    print(f"账号共 {len(rows)} 个自定义音色(上限 1000):本模型可用 {len(usable)} 个,其它模型 {len(others)} 个\n")
    for title, group in [(f"【可用 · {MODEL}】", usable), ("【不可用 · 属于其它模型】", others)]:
        if not group:
            continue
        print(title)
        for r in group:
            model = "" if r.get("target_model") == MODEL else f"  模型 {r.get('target_model')}"
            print(f"  {r['voice_id']}  [{r.get('status')}]  创建于 {r.get('gmt_create')}{model}")
        print()
    if others:
        print("其它模型的音色本插件无法合成;不再需要可用 delete <voice_id> 释放配额。")


def prepare_recording(path):
    """把本地录音转成 24kHz 单声道 16bit wav 并检查时长,返回临时 wav 路径。"""
    if not os.path.isfile(path):
        sys.exit(f"找不到录音文件:{path}")
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="clone_"); os.close(fd)
    r = subprocess.run(["ffmpeg", "-y", "-i", path, "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        os.unlink(out)
        sys.exit(f"录音转码失败(ffmpeg 无法读取 {path}):{r.stderr.strip().splitlines()[-1:]}")
    d = duration(out)
    if not 5 <= d <= 60:
        os.unlink(out)
        sys.exit(f"录音时长 {d:.1f}s,需在 5~60 秒之间(推荐 10~20 秒)")
    if not 10 <= d <= 20:
        print(f"⚠ 录音时长 {d:.1f}s,推荐 10~20 秒效果最好", file=sys.stderr)
    return out


def upload_recording(path):
    """上传到百炼免费临时存储(48 小时有效),返回 oss:// 地址。文件与 voice-enrollment 绑定。"""
    from dashscope.utils.oss_utils import OssUtils
    url, _ = OssUtils.upload(model="voice-enrollment", file_path=path, api_key=get_key())
    return url


def cmd_clone(a):
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    prefix = a.prefix.lower()  # SDK 约定前缀为小写字母和数字
    if not re.fullmatch(r"[a-z0-9]{1,10}", prefix):
        sys.exit("--prefix 只能是英文字母和数字,最多 10 个字符")
    init_dashscope()
    if re.match(r"https?://", a.source):
        url, svc = a.source, VoiceEnrollmentService()
    else:
        wav = prepare_recording(a.source)
        try:
            print("⬆ 上传录音到百炼临时存储…")
            url = upload_recording(wav)
        except Exception as e:
            sys.exit(f"✗ 上传失败:{str(e)[-200:]}")
        finally:
            os.unlink(wav)
        # oss:// 临时地址必须带这个请求头,服务端才会去解析
        svc = VoiceEnrollmentService(headers={"X-DashScope-OssResourceResolve": "enable"})
    kw: dict = dict(target_model=MODEL, prefix=prefix, url=url, language_hints=[a.lang],
                    max_prompt_audio_length=a.max_seconds)
    if a.denoise:
        kw["enable_preprocess"] = True
    try:
        voice_id = svc.create_voice(**kw)
    except Exception as e:
        sys.exit(f"✗ 复刻失败:{str(e)[-200:]}\n检查录音:10~20 秒、单人、无背景音;用 URL 时须公网可直接下载")
    print(f"已提交复刻:{voice_id}")
    status = None
    for _ in range(30):  # 最多等约 60 秒
        info: dict = svc.query_voice(voice_id) or {}  # type: ignore[assignment]  # SDK 注解为 list,实际返回 dict
        status = info.get("status")
        if status == "OK":
            print(f"✅ 可用。合成时用 -v {voice_id}")
            return
        time.sleep(2)
    print(f"仍未就绪(状态 {status}),稍后用 voices --mine 查看")


def cmd_delete(a):
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    init_dashscope()
    VoiceEnrollmentService().delete_voice(a.voice_id)
    print(f"已删除 {a.voice_id}")


# ---------- preview / gen / script ----------

def read_text(a, allow_default):
    if getattr(a, "file", None):
        return open(a.file, encoding="utf-8").read().strip()
    if a.text:
        return a.text
    if allow_default:
        return DEFAULT_SAMPLE
    sys.exit("请用 --text \"...\" 或 --file 文件 提供文本。")


def cmd_preview(a):
    check_voice(a.voice)
    instr = resolve_instruction(a.instruct, a.emotion)
    out = a.out or os.path.join(tempfile.gettempdir(), f"preview_{a.voice}.wav")
    print(f"🎙 {describe(a.voice)}  | 指令:{instr or '无'}")
    print(f"✅ {out}  ({synth_to_file(a.voice, read_text(a, True), instr, a, out):.2f}s)")
    if sys.platform == "darwin":
        print("▶️ 播放中…"); subprocess.run(["afplay", out])


def cmd_gen(a):
    check_voice(a.voice)
    instr = resolve_instruction(a.instruct, a.emotion)
    print(f"🎙 {describe(a.voice)}  | 指令:{instr or '无'}")
    print(f"✅ {a.out}  ({synth_to_file(a.voice, read_text(a, False), instr, a, a.out):.2f}s)")


def parse_script(path, voice, instruct):
    """脚本格式:每个非空行是一段;`#` 开头为注释;
    `@voice <音色>` / `@instruct <指令>` 设置之后各段的音色与指令,`@instruct` 留空即清除。"""
    segs = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            key, _, val = line[1:].partition(" ")
            if key == "voice" and val.strip():
                voice = val.strip()
            elif key == "instruct":
                instruct = val.strip() or None
            else:
                sys.exit(f"{path}:{n} 未知指令行:{line}(只支持 @voice / @instruct)")
            continue
        segs.append({"line": n, "voice": voice, "instruction": instruct, "text": line})
    if not segs:
        sys.exit(f"{path} 里没有可合成的文本行")
    for s in segs:
        check_voice(s["voice"])
        resolve_instruction(s["instruction"], None)  # 先校验长度,避免跑到一半才失败
    return segs


def srt_time(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_script(a):
    segs = parse_script(a.file, a.voice, a.instruct)
    os.makedirs(a.out_dir, exist_ok=True)
    t, srt = 0.0, []
    for i, s in enumerate(segs, 1):
        s["file"] = f"{i:03d}.wav"
        print(f"[{i}/{len(segs)}] {describe(s['voice'])} | {s['instruction'] or '无指令'} | {s['text'][:30]}")
        s["duration"] = round(synth_to_file(s["voice"], s["text"], s["instruction"], a,
                                            os.path.join(a.out_dir, s["file"])), 3)
        s["start"], s["end"] = round(t, 3), round(t + s["duration"], 3)
        subtitle = TAG.sub("", s["text"]).strip()
        if subtitle:
            srt.append(f"{len(srt) + 1}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{subtitle}\n")
        t = s["end"] + a.gap

    with wave.open(os.path.join(a.out_dir, "all.wav"), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000)
        silence = b"\x00\x00" * round(24000 * a.gap)
        for i, s in enumerate(segs):
            with wave.open(os.path.join(a.out_dir, s["file"])) as w:
                out.writeframes(w.readframes(w.getnframes()))
            if i < len(segs) - 1:
                out.writeframes(silence)
    with open(os.path.join(a.out_dir, "subtitles.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    with open(os.path.join(a.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "gap": a.gap, "total": round(t - a.gap, 3), "segments": segs},
                  f, ensure_ascii=False, indent=2)
    print(f"✅ {len(segs)} 段,总长 {t - a.gap:.2f}s → {a.out_dir}/(all.wav、subtitles.srt、manifest.json)")


# ---------- CLI ----------

def add_synth_opts(sp):
    sp.add_argument("-v", "--voice", default=DEFAULT_VOICE, help=f"音色(默认 {DEFAULT_VOICE};复刻音色填 voice_id)")
    sp.add_argument("--instruct", help="自然语言指令(≤100 字符,汉字计 2)")
    sp.add_argument("--emotion", choices=list(EMOTION_ZH), help="情感快捷方式(未给 --instruct 时生效)")
    sp.add_argument("--rate", type=float, default=1.0, help="语速 0.5-2.0")
    sp.add_argument("--pitch", type=float, default=1.0, help="音调 0.5-2.0")
    sp.add_argument("--volume", type=int, default=50, help="音量 0-100")


def main():
    p = argparse.ArgumentParser(description=f"阿里百炼语音合成({MODEL})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("voices", help="列出系统音色,或 --mine 列出复刻音色")
    sp.add_argument("--gender", choices=["女", "男"])
    sp.add_argument("--scene", help="按分组或适用场景筛选,如 精品中文 / 新闻播报 / 方言")
    sp.add_argument("--mine", action="store_true", help="列出账号下全部复刻音色(分本模型可用 / 属于其它模型)")
    sp.set_defaults(func=cmd_voices)

    sp = sub.add_parser("preview", help="合成一句并试听"); add_synth_opts(sp)
    sp.add_argument("--text", help="自定义试听文本"); sp.add_argument("--out", help="保存路径")
    sp.set_defaults(func=cmd_preview)

    sp = sub.add_parser("gen", help="合成整段并保存"); add_synth_opts(sp)
    sp.add_argument("--text", help="要合成的文本"); sp.add_argument("--file", help="从文件读取")
    sp.add_argument("--out", required=True, help="输出 wav 路径")
    sp.set_defaults(func=cmd_gen)

    sp = sub.add_parser("script", help="按脚本逐段生成 + 字幕 + 拼接音轨"); add_synth_opts(sp)
    sp.add_argument("file", help="脚本文件(每行一段;@voice / @instruct 切换设置)")
    sp.add_argument("--out-dir", required=True, help="输出目录")
    sp.add_argument("--gap", type=float, default=0.3, help="段间静音秒数(默认 0.3)")
    sp.set_defaults(func=cmd_script)

    sp = sub.add_parser("clone", help="用本地录音或公网 URL 复刻音色")
    sp.add_argument("source", help="本地录音路径(m4a/mp3/wav 等,自动转码上传)或公网 http(s) URL")
    sp.add_argument("--prefix", required=True, help="音色名前缀(字母数字,≤10 字符,自动转小写)")
    sp.add_argument("--lang", choices=CLONE_LANGS, default="zh", help="录音语种(默认 zh)")
    sp.add_argument("--max-seconds", type=float, default=10.0, dest="max_seconds", help="参考音频最大时长 3-30 秒")
    sp.add_argument("--denoise", action="store_true", help="开启降噪/增强(录音有底噪时用)")
    sp.set_defaults(func=cmd_clone)

    sp = sub.add_parser("delete", help="删除一个复刻音色")
    sp.add_argument("voice_id")
    sp.set_defaults(func=cmd_delete)

    a = p.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
