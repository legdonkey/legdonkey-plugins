"""宣传片媒体路由：只测本地HTTP，不读用户配置或调用云端。"""
import http.client
import importlib.util
import io
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

spec = importlib.util.spec_from_file_location('tts_media_test', Path(__file__).with_name('tts.py'))
tts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tts)


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = bytes(range(256)) * 513  # 超过64KiB，覆盖流式分块。
        root = Path(cls.temp.name)
        (root / 'promo.mp4').write_bytes(cls.data)
        (root / 'promo-cover.webp').write_bytes(b'RIFF-webp-test')
        (root / 'promo.zh.vtt').write_bytes(b'WEBVTT\n\n')
        cls.ui = tts.LocalUI('studio.html')
        cls.ui.asset_dir = str(root)
        ready = threading.Event()
        def opened(url):
            cls.port = urlsplit(url).port
            ready.set()
        cls.thread = threading.Thread(target=cls.ui.serve, args=('测试', {}, SimpleNamespace(port=0, no_open=False)), daemon=True)
        with patch('webbrowser.open', side_effect=opened), patch('sys.stdout', new=io.StringIO()):
            cls.thread.start()
            if not ready.wait(5):
                raise RuntimeError('本地测试服务没有启动')

    @classmethod
    def tearDownClass(cls):
        connection = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=5)
        connection.request('POST', '/done?t=' + cls.ui.token)
        connection.getresponse().read()
        connection.close()
        cls.thread.join(5)
        cls.temp.cleanup()

    def request(self, path='/promo/video', method='GET', headers=None, authenticated=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        query = '?t=' + (self.ui.token if authenticated else 'wrong')
        try:
            connection.request(method, path + query, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), response.read()
        finally:
            connection.close()

    def test_full_video_and_head(self):
        status, headers, data = self.request()
        self.assertEqual((status, data), (200, self.data))
        self.assertEqual(headers['content-type'], 'video/mp4')
        self.assertEqual(headers['accept-ranges'], 'bytes')
        self.assertEqual(int(headers['content-length']), len(self.data))
        status, headers, data = self.request(method='HEAD', headers={'Range': 'bytes=0-1'})
        self.assertEqual((status, data), (200, b''))
        self.assertEqual(int(headers['content-length']), len(self.data))

    def test_byte_ranges(self):
        size = len(self.data)
        for request, start, end in [('bytes=0-31', 0, 31), ('bytes=65530-65550', 65530, 65550),
                                    ('bytes=100-', 100, size - 1), ('bytes=-20', size - 20, size - 1),
                                    (f'bytes=10-{size+100}', 10, size - 1), (f'bytes=-{size+10}', 0, size-1)]:
            with self.subTest(request=request):
                status, headers, data = self.request(headers={'Range': request})
                self.assertEqual((status, data), (206, self.data[start:end+1]))
                self.assertEqual(headers['content-range'], f'bytes {start}-{end}/{size}')
                self.assertEqual(int(headers['content-length']), end-start+1)

    def test_invalid_ranges(self):
        for value in ['bytes=999999-', 'bytes=20-10', 'bytes=-0', 'bytes=-', 'bytes=0-1,4-5',
                      'bytes=abc', 'items=0-1', 'bytes=' + '9' * 100 + '-']:
            with self.subTest(value=value):
                status, headers, body = self.request(headers={'Range': value})
                self.assertEqual((status, body), (416, b''))
                self.assertEqual(headers['content-range'], f'bytes */{len(self.data)}')

    def test_assets_require_token_and_paths_are_allowlisted(self):
        for path in ['/promo/video', '/promo/poster', '/promo/captions']:
            self.assertEqual(self.request(path, authenticated=False)[0], 403)
            self.assertEqual(self.request(path, method='HEAD', authenticated=False)[0], 403)
        for path in ['/promo/../scripts/tts.py', '/promo/%2e%2e/promo.mp4', '/assets/studio.html', '/promo/promo-media.json']:
            self.assertEqual(self.request(path)[0], 404)

    def test_poster_captions_and_missing_asset(self):
        self.assertEqual(self.request('/promo/poster')[1]['content-type'], 'image/webp')
        status, headers, data = self.request('/promo/captions')
        self.assertEqual(status, 200)
        self.assertEqual(headers['content-type'], 'text/vtt; charset=utf-8')
        self.assertTrue(data.startswith(b'WEBVTT'))
        with patch.object(self.ui, 'asset_dir', self.temp.name + '/missing'):
            self.assertEqual(self.request()[0], 404)

    def test_shipping_assets_and_lazy_markup(self):
        assets = Path(tts.__file__).resolve().parent.parent / 'assets'
        self.assertTrue((assets / 'promo.mp4').is_file())
        self.assertTrue((assets / 'promo-cover.webp').is_file())
        self.assertTrue((assets / 'promo.zh.vtt').read_text().startswith('WEBVTT\n'))
        markup = (assets / 'studio.html').read_text()
        video = markup.split('<video id="hPromoVideo"', 1)[1].split('>', 1)[0]
        self.assertIn('preload="none"', video)
        self.assertNotIn('autoplay', video)
        self.assertNotIn('src=', video)
        self.assertIn('querySelectorAll("audio, video")', markup)


if __name__ == '__main__':
    unittest.main()
