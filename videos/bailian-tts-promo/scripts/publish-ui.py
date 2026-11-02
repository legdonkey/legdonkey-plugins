"""把最新版成片、封面与可选字幕发布到插件；全部生成成功后再替换。"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parents[1] / 'plugins/bailian-tts/skills/bailian-tts/assets'
VIDEO = ROOT / 'out/bailian-tts-promo-remake.mp4'
SUBTITLES = ROOT / 'out/bailian-tts-promo-remake.srt'
assert VIDEO.is_file() and SUBTITLES.is_file(), '请先渲染最新版视频并生成对应 SRT'
with tempfile.TemporaryDirectory(prefix='.promo-publish-', dir=DEST) as temp:
    work = Path(temp)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(VIDEO), '-c', 'copy',
                    '-movflags', '+faststart', str(work / 'promo.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-sseof', '-1.2', '-i', str(VIDEO),
                    '-frames:v', '1', '-vf', 'scale=1280:-2', str(work / 'cover.png')], check=True)
    subprocess.run(['cwebp', '-quiet', '-q', '85', str(work / 'cover.png'), '-o', str(work / 'promo-cover.webp')], check=True)
    (work / 'cover.png').unlink()
    vtt = 'WEBVTT\n\n' + re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', SUBTITLES.read_text(encoding='utf-8'))
    (work / 'promo.zh.vtt').write_text(vtt, encoding='utf-8')
    (work / 'promo-media.json').write_text(json.dumps({
        'source_project': 'videos/bailian-tts-promo',
        'source_video': 'out/bailian-tts-promo-remake.mp4',
        'poster': '成片结束前1.2秒抽帧，缩放到1280×720；非AI生成图片',
        'music': {'title': 'House Vibez', 'artist': 'Lily J',
                  'license': 'Mixkit Stock Music Free License', 'url': 'https://mixkit.co/license/#musicFree',
                  'limits': '仅随视频使用，不独立分发音乐；不用于电视/广播、游戏或CD/DVD'},
        'sfx': '原创短音效；木质扫声来自 Joao_Janz / Freesound 485279 / CC0-1.0',
        'ranking_checked_at': '2026-11-02',
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for path in work.iterdir():
        assert path.stat().st_size > 0
        os.replace(path, DEST / path.name)
print(f'已更新宣传素材：{DEST}')
