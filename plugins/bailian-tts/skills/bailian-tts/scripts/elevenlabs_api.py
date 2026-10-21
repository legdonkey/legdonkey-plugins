"""Eleven v4：独立密钥、账号音色和本地收藏，不自动提交合成。"""
import json
import os
import re
import tempfile
import urllib.error
import urllib.request

MODEL = "eleven_v4"
TURBO_MODEL = "eleven_v4_turbo"
MODELS = (MODEL, TURBO_MODEL)
KEY_PATH = os.path.expanduser("~/.config/bailian-tts/elevenlabs.key")
FAV_PATH = os.path.expanduser("~/.config/bailian-tts/elevenlabs-favorites.json")
BASE = "https://api.elevenlabs.io"
PREFERRED = ("Siqi Liu - Calm, Warm and Gentle", "Adrian - Chinese Mandarin Narration", "Roger - Laid-Back, Casual, Resonant")


TRAITS_ZH = {
    "Clear, Engaging Educator": "清晰、生动的教学声线", "Calm, Warm and Gentle": "平静、温暖、柔和",
    "Chinese Mandarin Narration": "标准普通话旁白", "Laid-Back, Casual, Resonant": "松弛、自然、浑厚",
    "Deep, Resonant and Comforting": "低沉、浑厚、温暖", "Steady Broadcaster": "沉稳的播报声线",
    "Professional, Bright, Warm": "专业、明亮、温暖", "Mature, Reassuring, Confident": "成熟、安心、自信",
    "Enthusiast, Quirky Attitude": "热情、活泼、有个性", "Deep, Confident, Energetic": "低沉、自信、有活力",
    "Warm, Captivating Storyteller": "温暖、引人入胜的叙述声线", "Husky Trickster": "沙哑、狡黠的角色声线",
    "Relaxed, Neutral, Informative": "放松、中性、适合信息讲解", "Fierce Warrior": "强劲的战士角色声线",
    "Energetic, Social Media Creator": "活力充沛的社交媒体声线", "Knowledgable, Professional": "知性、专业",
    "Relaxed Optimist": "轻松、乐观", "Playful, Bright, Warm": "俏皮、明亮、温暖",
    "Smooth, Trustworthy": "流畅、可信赖", "Charming, Down-to-Earth": "亲切、有魅力、接地气",
    "Velvety Actress": "柔滑细腻的表演声线", "Dominant, Firm": "有力、坚定",
    "Wise, Mature, Balanced": "睿智、成熟、稳重", "Smooth and Relaxed": "流畅、放松",
    "Calm, Young and Trustworthy": "平静、年轻、可信赖", "Calm": "平静",
}


def trait_zh(name):
    trait = name.partition(" - ")[2].strip()
    if trait in TRAITS_ZH:
        return TRAITS_ZH[trait]
    return trait if re.search(r"[\u4e00-\u9fff]", trait) else "暂无中文描述"


def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_key():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key and os.path.exists(KEY_PATH):
        with open(KEY_PATH, encoding="utf-8") as f:
            key = f.read().strip()
    return key


def key_status():
    key = read_key()
    return {"configured": bool(key), "masked": f"{key[:3]}…{key[-4:]}" if len(key) > 10 else "…" if key else "",
            "source": "env" if os.environ.get("ELEVENLABS_API_KEY", "").strip() else "file"}


def request(path, payload=None, key=None):
    key = key or read_key()
    if not key:
        raise ValueError("请先在顶部模型设置中保存 ElevenLabs API Key")
    req = urllib.request.Request(BASE + path, headers={"xi-api-key": key, "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        try:
            with e:
                result = json.loads(e.read(16384))
            detail = result.get("detail", {})
            message = json.dumps(detail, ensure_ascii=False) if isinstance(detail, (dict, list)) else str(detail)
        except (ValueError, UnicodeError, AttributeError):
            message = "服务端未提供错误详情"
        message = re.sub(r"https?://\S+", "[已隐藏 URL]", message.replace(key, "[已隐藏 Key]"))[:600]
        raise ValueError(f"ElevenLabs 请求失败（HTTP {e.code}）：{message}") from None
    return json.loads(data) if payload is None else data


def api_access(voice):
    """区分 API 免费套餐资格与音色库网页试听资格。"""
    sharing = voice.get("sharing") or {}
    tiers = voice.get("available_for_tiers") or []
    if sharing and not voice.get("is_owner"):
        # free_users_allowed 不足以证明免费套餐可通过 API 调用音色库音色。
        return "paid_plan"
    if tiers and "free" not in tiers:
        return "paid_plan"
    if voice.get("category") == "premade":
        return "free_plan"
    return "unknown"


def list_voices(key=None):
    from urllib.parse import urlencode
    voices, token, seen = [], None, set()
    for _ in range(100):
        query = {"page_size": 100}
        if token:
            query["next_page_token"] = token
        data = request("/v2/voices?" + urlencode(query), key=key)
        for v in data.get("voices", []):
            if v["voice_id"] not in seen:
                seen.add(v["voice_id"])
                voices.append({"voice": v["voice_id"], "name": v.get("name", v["voice_id"]),
                               "trait_zh": trait_zh(v.get("name") or ""),
                               "api_access": api_access(v), "gender": (v.get("labels") or {}).get("gender", ""),
                               "description": v.get("description") or ""})
        if not data.get("has_more"):
            return voices
        next_token = data.get("next_page_token")
        if not next_token or next_token == token:
            raise ValueError("ElevenLabs 音色列表分页异常，请稍后刷新")
        token = next_token
    raise ValueError("账号音色过多，请减少后重试")


def save_key(key):
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", key):
        raise ValueError("ElevenLabs API Key 格式不正确，请重新复制")
    env = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if env and env != key:
        raise ValueError("ELEVENLABS_API_KEY 环境变量已有另一个 Key，请先修改或移除该变量")
    voices = list_voices(key)
    atomic_write(KEY_PATH, key + "\n")
    return voices


def favorites():
    if not os.path.exists(FAV_PATH):
        return []
    with open(FAV_PATH, encoding="utf-8") as f:
        return [dict(v, trait_zh=trait_zh(v.get("name", ""))) for v in json.load(f)]


def save_favorites(rows):
    atomic_write(FAV_PATH, json.dumps(rows, ensure_ascii=False))
    return rows


def seed_favorites(voices):
    if not os.path.exists(FAV_PATH):
        save_favorites([v for name in PREFERRED for v in voices if v["name"] == name])
    by_id = {v["voice"]: v for v in voices}
    rows = favorites()
    updated = [by_id.get(v["voice"], v) for v in rows]
    if updated != rows:
        save_favorites(updated)
    return updated


def update_favorite(voice, name, action):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", voice):
        raise ValueError("音色 ID 格式不正确")
    rows = favorites()
    row = next((v for v in rows if v["voice"] == voice), {"voice": voice, "name": name[:200]})
    if action == "default":
        rows = [row] + [v for v in rows if v["voice"] != voice]
    elif action == "add":
        if not any(v["voice"] == voice for v in rows):
            rows.append(row)
    elif action == "rm":
        rows = [v for v in rows if v["voice"] != voice]
    else:
        raise ValueError("不支持的收藏操作")
    return save_favorites(rows)


def synth_turbo(text, voice):
    """一次提交全文，通过官方 TTD WebSocket 收齐音频，不自动重试。"""
    import base64
    import time
    try:
        import websocket
    except ImportError:
        raise ValueError("Eleven v4 Turbo 需要 websocket-client，请在插件 Python 环境安装该依赖") from None
    key = read_key()
    if not key:
        raise ValueError("请先在顶部模型设置中保存 ElevenLabs API Key")
    ws = None
    try:
        deadline = time.monotonic() + 180
        ws = websocket.create_connection(
            BASE.replace("https://", "wss://") + "/v1/text-to-dialogue/stream-input"
            f"?model_id={TURBO_MODEL}&output_format=mp3_44100_128",
            header={"xi-api-key": key}, timeout=20)
        ws.send(json.dumps({"voices": [voice]}))
        ws.send(json.dumps({"inputs": [{"text": text, "voice_id": voice}]}, ensure_ascii=False))
        ws.send(json.dumps({"close_socket": True}))
        chunks = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("等待完整音频超时")
            ws.settimeout(remaining)
            raw = ws.recv()
            if not raw:
                raise ValueError("连接在完整音频返回前关闭")
            message = json.loads(raw)
            if message.get("error"):
                raise ValueError(f"{message['error']}：{message.get('message', '')}")
            if message.get("audio"):
                chunks.append(base64.b64decode(message["audio"], validate=True))
            if message.get("is_final"):
                if not chunks:
                    raise ValueError("服务端未返回音频")
                return b"".join(chunks)
    except Exception as e:
        detail = re.sub(r"https?://\S+", "[已隐藏 URL]", str(e).replace(key, "[已隐藏 Key]"))[:600]
        raise ValueError(f"Eleven v4 Turbo 请求失败：{detail}") from None
    finally:
        if ws is not None:
            ws.close()


def synth(text, voice, model=MODEL):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", voice):
        raise ValueError("请先为 Eleven v4 收藏并选择默认音色")
    if not text.strip() or len(text) > 2000:
        raise ValueError("Eleven v4 每次朗读限制为 2000 字符")
    if model not in MODELS:
        raise ValueError("不支持的 ElevenLabs 模型")
    if model == TURBO_MODEL:
        return synth_turbo(text, voice)
    # 按 Text to Dialogue 接口建议限制长度；单人旁白仅发送一项输入。
    return request("/v1/text-to-dialogue?output_format=mp3_44100_128", {
        "model_id": MODEL, "inputs": [{"text": text, "voice_id": voice}],
    })
