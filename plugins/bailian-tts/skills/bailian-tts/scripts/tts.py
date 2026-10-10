#!/usr/bin/env python3
"""阿里百炼语音合成(固定模型 qwen-audio-3.1-tts-flash)。

- voices:  列出系统音色(与官方对齐);--mine 列出账号下全部复刻音色,标出哪些本模型可用
- preview: 合成一句并播放(试听)
- gen:     合成整段并保存 wav(规范化 + 时长)
- script:  按脚本逐段生成 wav,并输出 manifest.json、subtitles.srt 与拼接好的 all.wav
- clone:   用本地录音(自动转码、上传百炼临时存储)或公网 URL 复刻音色
- delete:  删除一个复刻音色
- fav:     管理收藏音色;未指定 -v 时默认用收藏的第 1 个
- status:  检查运行环境与 API key(不联网);未配置 key 时提示打开引导页
- ui:      打开本地配音工作台:开始(配置 API key、功能介绍)、选音色、声音复刻在同一个页面
           clone-ui / pick-ui 是它的别名,分别直接打开声音复刻 / 选音色
- say:     朗读选中文本(macOS):配合鼠标按键或快捷键,分段边合成边播放,再次触发即打断

指令(instruction):任意自然语言,≤100 字符(汉字计 2),系统音色与复刻音色都支持。
文本内可直接嵌入 [excited]、[laughing] 等情感/富语言标签。

API key:环境变量 DASHSCOPE_API_KEY → 文件 ~/.dashscope_key(权限 600,可在工作台「开始」页校验后保存)。
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
FAV_PATH = os.path.expanduser("~/.config/bailian-tts/favorites.txt")
KEY_PATH = os.path.expanduser("~/.dashscope_key")
KEY_CONSOLE = "https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key"


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


def read_key():
    """返回 (key, 来源);来源为 "env" / "file",没有 key 时为 ("", None)。"""
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if k:
        return k, "env"
    if os.path.exists(KEY_PATH):
        k = open(KEY_PATH).read().strip()
    return (k, "file") if k else ("", None)


def get_key():
    k = read_key()[0]
    if not k:
        sys.exit("找不到 API key:运行 tts.py ui 在「开始」页配置,或设置 DASHSCOPE_API_KEY / 写入 ~/.dashscope_key")
    return k


def mask_key(k):
    return f"{k[:3]}…{k[-4:]}" if len(k) > 10 else "…"


def key_status():
    """页面与 status 用的 key 状态;只给掩码,不回传完整 key。"""
    k, source = read_key()
    st = {"configured": bool(k), "source": source, "masked": mask_key(k) if k else "",
          "path": KEY_PATH.replace(os.path.expanduser("~"), "~", 1)}
    if source == "file":
        st["loose"] = bool(os.stat(KEY_PATH).st_mode & 0o077)  # 组或其他用户可读
    return st


def verify_key(k):
    """用免费的「列出复刻音色」接口校验 key:能通过说明 key 有效且属于北京地域。失败时 sys.exit 给出原因。"""
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    try:
        VoiceEnrollmentService(api_key=k).list_voices(page_size=1)
    except Exception as e:
        err = str(e)
        if "InvalidApiKey" in err or "401" in err:
            sys.exit("这个 API Key 无效:确认复制完整,且是在「华北2(北京)」地域创建的。")
        sys.exit(f"暂时无法校验(网络或服务异常):{err[-200:]}")


def save_key(k):
    """校验后写入 ~/.dashscope_key:先写同目录临时文件(权限 600)再原子替换,不会留下半截或可被他人读取的文件。"""
    k = k.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{16,200}", k):
        sys.exit("格式不对:API Key 一般以 sk- 开头,只含字母、数字和连字符,中间不能有空格。")
    verify_key(k)
    tmp = KEY_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(k + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, KEY_PATH)
    if os.environ.get("DASHSCOPE_API_KEY", "").strip() not in ("", k):
        os.environ["DASHSCOPE_API_KEY"] = k  # 本进程立即改用新 key;环境变量仍优先,需用户自己移除
        return dict(key_status(), source="env", env_conflict=True)
    return key_status()


def clipboard(text=None):
    """读(text 为 None)或写系统剪贴板;macOS 用 pbpaste / pbcopy,Linux 用 wl-paste 或 xclip。没有可用工具时返回 None。"""
    import shutil
    tools = ([["pbpaste"], ["pbcopy"]] if sys.platform == "darwin" else
             [["wl-paste", "-n"], ["wl-copy"]] if shutil.which("wl-paste") else
             [["xclip", "-o", "-selection", "clipboard"], ["xclip", "-selection", "clipboard"]] if shutil.which("xclip") else None)
    if not tools:
        return None
    if text is None:
        return subprocess.run(tools[0], capture_output=True, text=True).stdout
    subprocess.run(tools[1], input=text, text=True)
    return text


def save_key_from_clipboard():
    """读剪贴板里刚复制的 key,校验并保存;保存成功后清空剪贴板,不让 key 留在里面。"""
    raw = clipboard()
    if raw is None:
        sys.exit("这台电脑读不了剪贴板,请把 key 粘贴到页面输入框,或用 key --stdin。")
    if not raw.strip():
        sys.exit("剪贴板是空的:在百炼控制台点 API Key 旁的复制图标后再试。")
    if not re.fullmatch(r"sk-[A-Za-z0-9._-]{8,}", raw.strip()):  # 不回显内容,剪贴板里可能是别的隐私
        sys.exit(f"剪贴板里不是 API Key(读到 {len(raw.strip())} 个字符,不是 sk- 开头):"
                 "可能复制没成功,或被别的程序覆盖了。回到百炼控制台点 Key 旁的复制图标后再试。")
    st = save_key(raw)
    clipboard("")
    return st


def deps_status():
    import importlib.util, shutil
    return {"dashscope": importlib.util.find_spec("dashscope") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None}


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


def load_favorites():
    try:
        with open(FAV_PATH, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []


def save_favorites(favs):
    os.makedirs(os.path.dirname(FAV_PATH), exist_ok=True)
    with open(FAV_PATH, "w", encoding="utf-8") as f:
        f.write("".join(v + "\n" for v in favs))


def default_voice():
    favs = load_favorites()
    return (favs[0], "收藏第 1 个") if favs else (DEFAULT_VOICE, "内置默认")


def cmd_fav(a):
    favs = load_favorites()
    if a.action == "add":
        for v in a.voices:
            check_voice(v)
            if v not in favs:
                favs.append(v)
        save_favorites(favs)
    elif a.action == "rm":
        missing = [v for v in a.voices if v not in favs]
        if missing:
            print(f"⚠ 不在收藏中:{' '.join(missing)}", file=sys.stderr)
        favs = [v for v in favs if v not in a.voices]
        save_favorites(favs)
    if not favs:
        print(f"收藏为空。未指定 -v 时使用内置默认 {DEFAULT_VOICE}。用 fav add <音色> 添加。")
        return
    print(f"收藏音色({FAV_PATH}):第 1 个为未指定 -v 时的默认音色\n")
    for i, v in enumerate(favs, 1):
        e = voice_entry(v)
        info = f"{e['name']} {e['gender']} {e.get('trait', '')}" if e else "复刻/catalog 外音色"
        print(f"  {i}. {v:20s} {info}" + ("  ← 默认" if i == 1 else ""))


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
    favs = set(load_favorites())
    print(f"{MODEL} 系统音色(共 {len(cat)} 个;全部支持自然语言指令;★ = 已收藏)\n")
    for scene, vs in groups.items():
        print(f"【{scene}】")
        for v in vs:
            star = "★" if v["voice"] in favs else " "
            print(f" {star}{v['voice']:20s} {v['name']:8s} {v['gender']:2s} {v.get('trait', ''):10s} {v['lang']}")
            if v.get("usage"):
                print(f"        适用: {v['usage']}")
        print()
    print("指令:--instruct \"自然语言描述\"(≤100 字符,汉字计 2);文本内标签见 references/voices.md")
    print("数据来源(以官方为准):https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list")


def fetch_custom_voices():
    """账号下全部自定义(复刻)音色,含其它模型的。"""
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    init_dashscope()
    svc, rows, page = VoiceEnrollmentService(), [], 0
    while True:
        batch = svc.list_voices(prefix=None, page_index=page, page_size=100) or []
        rows += batch
        if len(batch) < 100:
            break
        page += 1
    return rows


def list_mine():
    rows = fetch_custom_voices()
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


def clone_voice(source, prefix, lang="zh", max_seconds=10.0, denoise=False):
    """复刻音色:source 为本地录音路径或公网 URL。返回 (voice_id, 是否已可用);出错时 sys.exit。"""
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    prefix = prefix.lower()  # SDK 约定前缀为小写字母和数字
    if not re.fullmatch(r"[a-z0-9]{1,10}", prefix):
        sys.exit("前缀只能是英文字母和数字,最多 10 个字符")
    init_dashscope()
    if re.match(r"https?://", source):
        url, svc = source, VoiceEnrollmentService()
    else:
        wav = prepare_recording(source)
        try:
            print("⬆ 上传录音到百炼临时存储…")
            url = upload_recording(wav)
        except Exception as e:
            sys.exit(f"✗ 上传失败:{str(e)[-200:]}")
        finally:
            os.unlink(wav)
        # oss:// 临时地址必须带这个请求头,服务端才会去解析
        svc = VoiceEnrollmentService(headers={"X-DashScope-OssResourceResolve": "enable"})
    kw: dict = dict(target_model=MODEL, prefix=prefix, url=url, language_hints=[lang],
                    max_prompt_audio_length=max_seconds)
    if denoise:
        kw["enable_preprocess"] = True
    try:
        voice_id = svc.create_voice(**kw)
    except Exception as e:
        sys.exit(f"✗ 复刻失败:{str(e)[-200:]}\n检查录音:10~20 秒、单人、无背景音;用 URL 时须公网可直接下载")
    print(f"已提交复刻:{voice_id}")
    for _ in range(30):  # 最多等约 60 秒
        info: dict = svc.query_voice(voice_id) or {}  # type: ignore[assignment]  # SDK 注解为 list,实际返回 dict
        if info.get("status") == "OK":
            return voice_id, True
        time.sleep(2)
    return voice_id, False


def cmd_clone(a):
    voice_id, ready = clone_voice(a.source, a.prefix, a.lang, a.max_seconds, a.denoise)
    print(f"✅ 可用。合成时用 -v {voice_id}" if ready else f"仍未就绪,稍后用 voices --mine 查看:{voice_id}")


class LocalUI:
    """本地页面服务:只监听 127.0.0.1,每个请求须带一次性随机 token。
    routes 把 (方法, 路径) 映射到处理函数 fn(query, body, content_type),返回 dict(按 JSON 回复)。
    GET / 返回页面,GET /audio 取本次合成的音频,POST /done 关闭服务。"""

    def __init__(self, asset):
        import itertools, secrets
        self.page = open(os.path.join(os.path.dirname(__file__), "..", "assets", asset), "rb").read()
        self.token = secrets.token_urlsafe(16)
        self.audio, self._ids = {}, itertools.count()  # 页面并发请求时编号也不冲突
        self.workdir = tempfile.mkdtemp(prefix="bailian_ui_")

    def say(self, voice, text, instruction=None):
        """合成并暂存在内存,返回 (页面可用的音频地址, 时长秒)。"""
        import types
        key = str(next(self._ids))
        path = os.path.join(self.workdir, f"say_{key}.wav")
        secs = synth_to_file(voice, text, instruction, types.SimpleNamespace(rate=1.0, pitch=1.0, volume=50), path)
        self.audio[key] = open(path, "rb").read()
        return f"/audio?t={self.token}&k={key}", round(secs, 2)

    def serve(self, title, routes, a, page=""):
        import http.server, threading, urllib.parse, webbrowser
        ui = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002  # 静默访问日志
                pass

            def reply(self, body, ctype="application/json; charset=utf-8"):
                data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data)

            def handle_request(self, method):
                u = urllib.parse.urlparse(self.path)
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                if q.get("t") != ui.token:
                    return self.send_error(403)
                if method == "GET" and u.path == "/":
                    return self.reply(ui.page, "text/html; charset=utf-8")
                if method == "GET" and u.path == "/audio" and q.get("k") in ui.audio:
                    return self.reply(ui.audio[q["k"]], "audio/wav")
                if method == "POST" and u.path == "/done":
                    self.reply({})
                    threading.Thread(target=server.shutdown, daemon=True).start()
                    return
                fn = routes.get((method, u.path))
                if not fn:
                    return self.send_error(404)
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else b""
                try:
                    out = fn(q, body, (self.headers.get("Content-Type") or "").split(";")[0])
                except SystemExit as e:
                    out = {"error": str(e)}
                except Exception as e:
                    out = {"error": str(e)[-300:]}
                self.reply(out)

            def do_GET(self):
                self.handle_request("GET")

            def do_POST(self):
                self.handle_request("POST")

        server = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
        url = f"http://127.0.0.1:{server.server_address[1]}/?t={self.token}" + (f"#{page}" if page else "")
        print(f"{title}已启动:{url}\n在页面上点「完成」后自动退出(或按 Ctrl-C)。", flush=True)
        if not a.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            import shutil; shutil.rmtree(self.workdir, ignore_errors=True)


def print_favorites_summary():
    favs = load_favorites()
    print("当前收藏:" + (" ".join(favs) if favs else "无") + (f"(默认 {favs[0]})" if favs else ""))


def cmd_status(a):
    """不联网的快速自查:依赖、ffmpeg、API key。未配置 key 时最后一行提示打开引导页。"""
    deps, key = deps_status(), key_status()
    yes = lambda ok: "✓" if ok else "✗"
    print(f"{yes(deps['dashscope'])} Python 依赖 dashscope" + ("" if deps["dashscope"] else
          "(缺失:python3 -m venv ~/.bailian-tts-venv && ~/.bailian-tts-venv/bin/pip install "
          "-i https://mirrors.aliyun.com/pypi/simple/ dashscope)"))
    print(f"{yes(deps['ffmpeg'])} ffmpeg" + ("" if deps["ffmpeg"] else "(缺失:macOS 用 brew install ffmpeg)"))
    if key["configured"]:
        where = "环境变量 DASHSCOPE_API_KEY" if key["source"] == "env" else KEY_PATH
        print(f"✓ API key {key['masked']}(来自 {where})" + (",⚠ 文件权限过宽,建议 chmod 600" if key.get("loose") else ""))
    else:
        print("✗ API key 未配置")
    favs = load_favorites()
    print(f"收藏音色:{len(favs)} 个" + (f",默认 {favs[0]}" if favs else ""))
    print("onboarding: " + ("不需要" if key["configured"] else "需要,运行 ui 打开「开始」页配置 API key"))


def cmd_key(a):
    """配置 API key:--console 在默认浏览器打开百炼控制台的 API Key 页;--clipboard 读剪贴板
    (用户在控制台复制后执行);--stdin 读标准输入。只打印掩码,完整 key 不进输出。"""
    if a.console:
        import webbrowser
        webbrowser.open(KEY_CONSOLE)
        print(f"已在默认浏览器打开百炼控制台的 API Key 页:{KEY_CONSOLE}")
        return
    if a.clipboard:
        st = save_key_from_clipboard()
        print(f"✅ 已校验并保存 API key {st['masked']} → {KEY_PATH}(权限 600),剪贴板已清空")
    elif a.stdin:
        st = save_key(sys.stdin.read())
        print(f"✅ 已校验并保存 API key {st['masked']} → {KEY_PATH}(权限 600)")
    else:
        st = key_status()
        print(f"API key {st['masked']}(来自 {'环境变量' if st['source'] == 'env' else KEY_PATH})" if st["configured"]
              else f"API key 未配置。在百炼控制台创建:{KEY_CONSOLE}")
        return
    if st.get("env_conflict"):
        print("⚠ 环境变量 DASHSCOPE_API_KEY 里是另一个 key,它优先于文件;请从 shell 配置里删掉它。")


def cmd_ui(a):
    """本地配音工作台:「开始」(配置 API key、功能介绍)、「选音色」、「声音复刻」三栏在同一个页面。
    还没配置 key 时总是先打开「开始」页。"""
    ui = LocalUI("studio.html")
    created, takes, log = [], {}, {"key_saved": False}  # takes:(音色, 句子, 指令) → (音频地址, 时长),本次会话内不重复合成
    page = a.page if key_status()["configured"] else "home"

    def state(q, body, ctype):
        return {"model": MODEL, "key": key_status(), "deps": deps_status(), "console": KEY_CONSOLE,
                "catalog": load_catalog(), "favorites": load_favorites(), "sample": DEFAULT_SAMPLE,
                "platform": sys.platform}

    def key(q, body, ctype):
        d = json.loads(body)
        st = save_key_from_clipboard() if d.get("clipboard") else save_key(d.get("key", ""))
        log["key_saved"] = True
        return {"key": st}

    def key_get(q, body, ctype):
        return {"key": key_status()}

    def mine(q, body, ctype):
        rows = [r for r in fetch_custom_voices() if r.get("target_model") == MODEL]
        return {"voices": [{"voice": r["voice_id"], "status": r.get("status"), "created": r.get("gmt_create")}
                           for r in rows]}

    def say(q, body, ctype):
        d = json.loads(body)
        voice, text = d["voice"], d["text"].strip()[:200]
        if not text:
            return {"error": "请先写一句要试听的话。"}
        check_voice(voice)
        instr = resolve_instruction((d.get("instruct") or "").strip() or None, None)
        k = (voice, text, instr)
        cached = k in takes
        if not cached:
            takes[k] = ui.say(voice, text, instr)
        url, secs = takes[k]
        return {"audio": url, "duration": secs, "cached": cached}

    def fav(q, body, ctype):
        d = json.loads(body)
        voice, action = d["voice"], d["action"]
        old = load_favorites()
        if action == "default":
            favs = [voice] + [v for v in old if v != voice]
        elif action == "add":
            favs = old if voice in old else old + [voice]
        else:
            favs = [v for v in old if v != voice]
        save_favorites(favs)
        return {"favorites": favs}

    def clone(q, body, ctype):
        ext = {"audio/webm": ".webm", "audio/mp4": ".m4a", "audio/ogg": ".ogg", "audio/wav": ".wav",
               "audio/mpeg": ".mp3", "audio/x-m4a": ".m4a"}.get(ctype, ".bin")
        src = os.path.join(ui.workdir, f"recording_{len(created)}{ext}")
        open(src, "wb").write(body)
        voice_id, ready = clone_voice(src, q.get("prefix", ""), denoise=q.get("denoise") == "1")
        created.append(voice_id)
        if not ready:
            return {"voice_id": voice_id, "error": "音色仍在处理中,请稍后再试听"}
        return {"voice_id": voice_id,
                "audio": ui.say(voice_id, "大家好，这是用我自己的声音复刻出来的音色，听起来像不像我本人？")[0]}

    def delete(q, body, ctype):
        from dashscope.audio.tts_v2 import VoiceEnrollmentService
        d = json.loads(body)
        init_dashscope(); VoiceEnrollmentService().delete_voice(d["voice"])
        if d["voice"] in created:
            created.remove(d["voice"])
        save_favorites([v for v in load_favorites() if v != d["voice"]])
        return {"deleted": d["voice"]}

    ui.serve("配音工作台", {("GET", "/state"): state, ("POST", "/key"): key, ("GET", "/key"): key_get,
                          ("GET", "/mine"): mine,
                          ("POST", "/say"): say, ("POST", "/fav"): fav, ("POST", "/clone"): clone,
                          ("POST", "/delete"): delete}, a, page)
    st = key_status()
    print("API key:" + (f"已配置 {st['masked']}" + (",本次新保存" if log["key_saved"] else "") if st["configured"] else "未配置"))
    print("本次创建的音色:" + (" ".join(created) if created else "无"))
    print(f"本次试听 {len({k[0] for k in takes})} 个音色,合成 {len(takes)} 次")
    print_favorites_summary()


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


# ---------- say:朗读选中文本(macOS) ----------
# 鼠标按键 / 快捷键触发:清理 Markdown → 截断 → 按句分段,播放当前段的同时合成下一段。
# 每次朗读自成进程组,组 ID 记在 SAY_PID;再次触发时整组结束(含正在合成与播放的段落)。

SAY_DIR = os.path.expanduser("~/Library/Caches/bailian-tts/say")
SAY_PID = os.path.join(SAY_DIR, "reader.pid")
SAY_CLIP = os.path.join(SAY_DIR, "clipboard.txt")
SAY_LOG = os.path.expanduser("~/Library/Logs/bailian-tts-say.log")
SAY_WRAPPER = os.path.expanduser("~/.local/bin/bailian-say")
SAY_FIRST, SAY_SIZE = 80, 180  # 首段短一些,尽快开口;后续每段约 180 字


def clean_markdown(text):
    """去掉代码块与 Markdown 符号,只留要念的文字。"""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)                    # 代码块不念
    text = re.sub(r"`([^`]*)`", r"\1", text)                              # 行内代码只留内容
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)                      # 图片
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)                  # 链接只念文字
    text = re.sub(r"^\s*(#{1,6}|>+|[-*+]|\d+[.)])\s+", "", text, flags=re.M)  # 标题、引用、列表符号
    text = re.sub(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", "", text, flags=re.M)    # 表格分隔行
    text = re.sub(r"[*_~|#>]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text, limit):
    """超过 limit 字时在最后一个句末截断;句末太靠前就硬切并加省略号。"""
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(c) for c in "。！？!?；;.")
    return head[:cut + 1] if cut >= limit // 2 else head + "……"


def split_segments(text, first=SAY_FIRST, size=SAY_SIZE):
    """按句切段:首段不超过 first 字,其余不超过 size 字;超长的句子再按逗号切,找不到就硬切。"""
    pieces = []
    for sent in re.findall(r"[^。！？!?；;…\n]+[。！？!?；;…]*", text):
        while len(sent) > size:
            cut = max(sent.rfind(c, 0, size) for c in "，,、：: ")
            cut = cut + 1 if cut > size // 3 else size
            pieces.append(sent[:cut]); sent = sent[cut:]
        pieces.append(sent)
    parts, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) > (first if not parts else size):
            parts.append(cur); cur = ""
        cur += piece
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def notify(text):
    subprocess.run(["osascript", "-e", f'display notification "{text}" with title "bailian-tts 朗读"'], check=False)


def pb_paste():
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def pb_copy(text):
    subprocess.run(["pbcopy"], input=text, text=True)


def stop_previous_say():
    """结束上一次朗读的整个进程组;先确认那个进程确实是 say,避免误杀复用的进程号。"""
    import signal
    try:
        pid = int(open(SAY_PID).read())
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
        if "tts.py" in cmd and " say" in cmd:
            os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def speak_segments(parts, voice, instr, a):
    """播放第 i 段的同时合成第 i+1 段。返回是否全部念完。"""
    import shutil, signal
    from concurrent.futures import ThreadPoolExecutor
    os.setpgrp()  # 自成进程组,方便下次触发时整组结束
    open(SAY_PID, "w").write(str(os.getpid()))
    tmp = tempfile.mkdtemp(prefix="bailian_say_")

    def interrupted(*_):  # 被打断:清掉临时音频后直接退出,不等合成线程
        shutil.rmtree(tmp, ignore_errors=True)
        os._exit(0)
    signal.signal(signal.SIGTERM, interrupted)

    def job(i):
        raw = synth(voice, parts[i], instr, a.rate, a.pitch, a.volume)
        if not raw:
            return None
        path = os.path.join(tmp, f"{i}.wav")
        normalize(raw, path)
        return path

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(job, 0)
            for i in range(len(parts)):
                path = fut.result()
                if not path:
                    notify(f"第 {i + 1} 段合成失败,详情见 {SAY_LOG}")
                    return False
                if i + 1 < len(parts):
                    fut = pool.submit(job, i + 1)
                subprocess.run(["afplay", path])
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_say():
    """生成 ~/.local/bin/bailian-say:把参数转给当前这份 tts.py 的 say;路径失效时找插件缓存里最新的一份。"""
    tts = os.path.abspath(__file__)
    os.makedirs(os.path.dirname(SAY_WRAPPER), exist_ok=True)
    with open(SAY_WRAPPER, "w", encoding="utf-8") as f:
        f.write(f'''#!/bin/sh
# 由 bailian-tts 的 `tts.py say --install` 生成:把参数转给 tts.py say。
# 插件移动或升级后,原路径失效时自动改用 Claude Code 插件缓存里最新的 bailian-tts。
TTS="{tts}"
[ -f "$TTS" ] || TTS=$(ls -dt "$HOME"/.claude/plugins/cache/*/bailian-tts/*/skills/bailian-tts/scripts/tts.py 2>/dev/null | head -1)
exec "{sys.executable}" "$TTS" say "$@"
''')
    os.chmod(SAY_WRAPPER, 0o755)
    print(f"✅ 已生成 {SAY_WRAPPER}(指向 {tts})\n")
    print("任选一种触发方式:\n")
    print("① 鼠标按键(OpenLogi,~/.config/openlogi/config.toml 设备的 bindings 段,改后重开 OpenLogi):")
    print('MiddleClick = { Workflow = [ { RunShellCommand = "$HOME/.local/bin/bailian-say --save" }, '
          '{ Delay = { millis = 120 } }, { PressKey = "Cmd+C" }, { Delay = { millis = 200 } }, '
          '{ RunShellCommand = "$HOME/.local/bin/bailian-say --clipboard >/dev/null 2>&1 &" } ] }\n')
    print("② 键盘快捷键(「快捷指令」):设置 → 高级 → 允许运行脚本;新建快捷指令,勾选「用作快速操作」,接收「文本」;")
    print("   添加「运行 Shell 脚本」,传递输入选「作为 stdin」,内容为:$HOME/.local/bin/bailian-say")
    print("   再到 系统设置 → 键盘 → 键盘快捷键 → 服务 里给它设快捷键。")


def cmd_say(a):
    if sys.platform != "darwin":
        sys.exit("say 只支持 macOS(依赖 pbpaste / pbcopy / afplay)")
    # 按键工作流和快捷指令里的 PATH 很短,合成要用 Homebrew 的 ffmpeg
    os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "/usr/bin:/bin")
    if a.install:
        return install_say()
    os.makedirs(SAY_DIR, exist_ok=True)
    # 按键工作流:--save 存下剪贴板文字并清空 → 按键发 Cmd+C 复制选中内容 → --clipboard 读出并还原剪贴板。
    # 只还原纯文字,图片等其它剪贴板内容不保留。
    if a.save:
        stop_previous_say()
        open(SAY_CLIP, "w", encoding="utf-8").write(pb_paste())
        return pb_copy("")
    if a.clipboard:
        raw = pb_paste()
        pb_copy(open(SAY_CLIP, encoding="utf-8").read() if os.path.exists(SAY_CLIP) else "")
        if not raw.strip():
            return notify("没有选中文字")
    else:
        raw = a.text if a.text is not None else sys.stdin.read()
        stop_previous_say()  # 没有 --save 这一步,在这里结束上一次
    text = truncate_text(clean_markdown(raw), a.max)
    if not text:
        return notify("没有可朗读的文字")
    check_voice(a.voice)
    instr = resolve_instruction(a.instruct, a.emotion)
    parts = split_segments(text)
    with open(SAY_LOG, "a", encoding="utf-8") as log:
        sys.stdout = sys.stderr = log  # 后台运行时输出写进日志
        print(f"\n--- {time.strftime('%F %T')} {describe(a.voice)} {len(text)} 字,分 {len(parts)} 段 "
              f"{[len(p) for p in parts]}:{text[:40]}", flush=True)
        speak_segments(parts, a.voice, instr, a)


# ---------- CLI ----------

def add_synth_opts(sp):
    sp.add_argument("-v", "--voice", help=f"音色(默认:收藏的第 1 个,收藏为空时 {DEFAULT_VOICE};复刻音色填 voice_id)")
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

    sp = sub.add_parser("status", help="检查运行环境与 API key(不联网)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("key", help="查看或保存 API key(校验后写入 ~/.dashscope_key,权限 600)")
    src = sp.add_mutually_exclusive_group()
    src.add_argument("--console", action="store_true", help="在默认浏览器打开百炼控制台的 API Key 页")
    src.add_argument("--clipboard", action="store_true", help="读取剪贴板里刚复制的 key,保存后清空剪贴板")
    src.add_argument("--stdin", action="store_true", help="从标准输入读取 key")
    sp.set_defaults(func=cmd_key)

    for name, page, desc in [("ui", "home", "打开本地配音工作台(开始 / 选音色 / 声音复刻;未配置 key 时先到「开始」)"),
                             ("pick-ui", "voices", "打开工作台的「选音色」(ui --page voices 的别名)"),
                             ("clone-ui", "clone", "打开工作台的「声音复刻」(ui --page clone 的别名)")]:
        sp = sub.add_parser(name, help=desc)
        sp.add_argument("--page", choices=["home", "voices", "clone"], default=page, help=f"打开哪一栏(默认 {page})")
        sp.add_argument("--port", type=int, default=0, help="监听端口(默认随机)")
        sp.add_argument("--no-open", action="store_true", dest="no_open", help="不自动打开浏览器")
        sp.set_defaults(func=cmd_ui)

    sp = sub.add_parser("say", help="朗读选中文本(macOS,配合鼠标按键或快捷键;分段边合成边播放)")
    add_synth_opts(sp)
    sp.add_argument("--text", help="要朗读的文本(默认从 stdin 读)")
    sp.add_argument("--max", type=int, default=1500, help="最多朗读的字数(默认 1500,超出在句末截断)")
    mode = sp.add_mutually_exclusive_group()
    mode.add_argument("--save", action="store_true", help="按键工作流第 1 步:结束上一次朗读,存下剪贴板文字并清空")
    mode.add_argument("--clipboard", action="store_true", help="按键工作流最后一步:朗读刚复制的文字并还原剪贴板")
    mode.add_argument("--install", action="store_true", help="生成 ~/.local/bin/bailian-say 并打印按键 / 快捷键配置")
    sp.set_defaults(func=cmd_say)

    sp = sub.add_parser("fav", help="管理收藏音色(第 1 个为默认音色)")
    sp.add_argument("action", nargs="?", choices=["list", "add", "rm"], default="list")
    sp.add_argument("voices", nargs="*", help="音色(add / rm 时必填,可多个)")
    sp.set_defaults(func=cmd_fav)

    a = p.parse_args()
    if a.cmd == "fav" and a.action != "list" and not a.voices:
        p.error(f"fav {a.action} 需要至少一个音色")
    if getattr(a, "voice", "") is None and not (getattr(a, "save", False) or getattr(a, "install", False)):
        a.voice, source = default_voice()
        print(f"未指定音色,使用{source}:{a.voice}", file=sys.stderr)
    a.func(a)


if __name__ == "__main__":
    main()
