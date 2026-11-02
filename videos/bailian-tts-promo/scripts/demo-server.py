"""只提供原始界面与隔离演示数据，不代理云端，不接触用户配置。"""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / 'plugins/bailian-tts/skills/bailian-tts'
MODEL = 'qwen-audio-3.1-tts-flash'
STATE = {
    'version': '', 'platform': 'darwin',
    'favorites': ['xunanchuan_v3.1', 'yuxiaoyun_v3.1'],
    'settings': {'model': MODEL, 'workspace_id': '', 'description': '', 'read_limits': {}},
    'read_limit_caps': {MODEL: 20000, 'qwen-audio-3.1-tts-next': 2800, 'eleven_v4': 2000, 'eleven_v4_turbo': 2000},
    'eleven_key': {'configured': False}, 'eleven_favorites': [],
    'key': {'configured': True, 'masked': '演示环境 · 无真实密钥', 'path': '演示环境', 'source': 'file'},
    'deps': {'dashscope': True, 'ffmpeg': True}, 'console': '#',
    'catalog': json.loads((SOURCE / 'references/voices.json').read_text())['voices'],
    'sample': '把文字，交给声音。让你的想法，被听见。',
}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        payload = None
        if path == '/state': payload = STATE
        elif path == '/mine': payload = {'voices': [], 'mine': []}
        elif path == '/key': payload = {'key': STATE['key']}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
        elif path == '/':
            data = (SOURCE / 'assets/studio.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(data)
        else:
            super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path == '/say':
            length = int(self.headers.get('Content-Length', 0))
            if length > 4096:
                self.send_error(413); return
            data = json.loads(self.rfile.read(length))
            manifest = json.loads((ROOT/'public/audio/demos/manifest.json').read_text())
            item = next((s for s in manifest['segments'] if s['voice'] == data.get('voice')), None)
            if item and data.get('text') == '让想法，被听见。':
                payload = json.dumps({'audio': '/public/audio/demos/'+item['file'], 'duration': item['duration'], 'cached': True}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(payload); return
        self.send_error(403, 'Demo: cloud operations disabled')

if __name__ == '__main__':
    assert len(STATE['catalog']) == 68
    assert all(not key.lower().endswith('token') for key in STATE)
    ThreadingHTTPServer(('127.0.0.1', 4318), Handler).serve_forever()
