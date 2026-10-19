"""本地模型配置与 Next 请求契约测试，不调用付费接口。"""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("tts", Path(__file__).with_name("tts.py"))
tts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tts)


class ModelTests(unittest.TestCase):
    def test_settings_roundtrip_and_environment(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "SETTINGS_PATH", root + "/settings.json"), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(tts.load_settings()["model"], tts.MODEL)
            saved = tts.save_settings({"model": tts.NEXT_MODEL, "workspace_id": "llm-test", "description": "沉稳女声"})
            self.assertEqual(saved, tts.load_settings())
            self.assertEqual(os.stat(tts.SETTINGS_PATH).st_mode & 0o777, 0o600)
            with patch.dict(os.environ, {"SFM_WORKSPACE_ID": "llm-env"}):
                self.assertEqual(tts.load_settings()["workspace_id"], "llm-env")
            with self.assertRaises(ValueError):
                tts.save_settings({"model": tts.NEXT_MODEL, "workspace_id": "https://bad", "description": "女声"})
            self.assertEqual(tts.load_settings(), saved)

    def test_per_model_read_limits_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "SETTINGS_PATH", root + "/settings.json"), patch.dict(os.environ, {}, clear=True):
            Path(tts.SETTINGS_PATH).write_text(json.dumps({"model": tts.MODEL}))
            self.assertEqual(set(tts.load_settings()["read_limits"].values()), {1500})
            base = {"model": tts.MODEL, "description": "女声", "workspace_id": ""}
            tts.save_settings(dict(base, read_limits={tts.MODEL: 4000, tts.eleven.MODEL: 1000}))
            saved = tts.save_settings(dict(base, read_limits={tts.eleven.TURBO_MODEL: 500}))
            self.assertEqual(saved["read_limits"][tts.MODEL], 4000)
            self.assertEqual(saved["read_limits"][tts.eleven.MODEL], 1000)
            self.assertEqual(saved["read_limits"][tts.eleven.TURBO_MODEL], 500)
            self.assertEqual(tts.save_settings(base), saved)
            for limits in ([1], {"unsupported": 10}, {tts.MODEL: True}, {tts.MODEL: "10"}, {tts.MODEL: 1.5}, {tts.MODEL: 0}, {tts.eleven.MODEL: 2001}):
                with self.subTest(limits=limits), self.assertRaises(ValueError):
                    tts.save_settings(dict(base, read_limits=limits))
                self.assertEqual(tts.load_settings(), saved)

    def test_read_limit_configuration_and_cli_priority(self):
        settings = {"model": tts.eleven.TURBO_MODEL, "read_limits": {tts.MODEL: 5000, tts.eleven.TURBO_MODEL: 800}}
        self.assertEqual(tts.read_limit(settings), 800)
        self.assertEqual(tts.read_limit(settings, 1000), 1000)
        self.assertEqual(tts.read_limit({"model": tts.MODEL}), 1500)
        with self.assertRaises(ValueError):
            tts.read_limit(settings, 0)
        with self.assertRaises(ValueError):
            tts.read_limit(settings, 2001)

    def test_say_respects_model_limit_and_interface_boundary(self):
        for model, configured, override, expected in [(tts.NEXT_MODEL, 20, None, 22), (tts.NEXT_MODEL, 20, 10, 12), (tts.eleven.MODEL, 2000, None, 2000)]:
            with self.subTest(model=model, configured=configured, override=override):
                args = SimpleNamespace(install=False, save=False, clipboard=False, text="甲" * 3000,
                                       max=override, voice="voice123", instruct=None, emotion=None)
                settings = {"model": model, "read_limits": {model: configured}}
                stdout, stderr = sys.stdout, sys.stderr
                with tempfile.TemporaryDirectory() as root, patch.object(tts.sys, "platform", "darwin"), patch.object(tts, "SAY_DIR", root), patch.object(tts, "SAY_LOG", root + "/say.log"), patch.object(tts, "stop_previous_say"), patch.object(tts, "load_settings", return_value=settings), patch.object(tts, "speak_segments") as speak:
                    try:
                        tts.cmd_say(args)
                    finally:
                        sys.stdout, sys.stderr = stdout, stderr
                    self.assertEqual(len(speak.call_args.args[0]), 1)
                    self.assertEqual(len(speak.call_args.args[0][0]), expected)
                    self.assertTrue(speak.call_args.args[0][0].endswith("……"))

    def test_next_request_contract(self):
        settings = {"workspace_id": "llm-test", "description": "沉稳女声"}
        result = {"output": {"audio": {"url": "https://example.com/audio.wav"}}}
        with patch.object(tts, "get_key", return_value="test-key"), patch("urllib.request.urlopen", side_effect=[io.BytesIO(json.dumps(result).encode()), io.BytesIO(b"audio")]) as call:
            self.assertEqual(tts.synth_next("你好", settings), b"audio")
            request = call.call_args_list[0].args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload["model"], tts.NEXT_MODEL)
            self.assertNotIn("voice", payload["input"])
            self.assertIn("沉稳女声", payload["input"]["text_prompt"])
            self.assertEqual(call.call_args_list[1].args[0], "https://example.com/audio.wav")
        with self.assertRaises(ValueError):
            tts.synth_next("字" * 3000, settings)

    def test_next_http_download_uses_https_and_preserves_signature(self):
        settings = {"workspace_id": "llm-test", "description": "女声"}
        url = "http://example.com/audio.wav?Expires=123&Signature=a%2Bb%3D"
        result = {"output": {"audio": {"url": url}}}
        with patch.object(tts, "get_key", return_value="test-key"), patch("urllib.request.urlopen", side_effect=[io.BytesIO(json.dumps(result).encode()), io.BytesIO(b"audio")]) as call:
            self.assertEqual(tts.synth_next("你好", settings), b"audio")
            self.assertEqual(call.call_args_list[1].args[0], url.replace("http:", "https:", 1))

    def test_next_rejects_invalid_download_urls(self):
        settings = {"workspace_id": "llm-test", "description": "女声"}
        for url in ("file:///etc/passwd", "data:audio/wav;base64,AAAA", "https:///audio.wav", "https://user:pass@example.com/audio.wav"):
            with self.subTest(url=url):
                result = {"output": {"audio": {"url": url}}}
                with patch.object(tts, "get_key", return_value="test-key"), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(result).encode())) as call:
                    with self.assertRaisesRegex(ValueError, "无效的音频地址"):
                        tts.synth_next("你好", settings)
                    self.assertEqual(call.call_count, 1)

    def test_next_http_error_preserves_reason_without_credentials(self):
        from urllib.error import HTTPError
        settings = {"workspace_id": "llm-test", "description": "女声"}
        body = {"code": "CLIENT_ERROR", "message": "invalid parameter test-key https://example.com/?Signature=secret", "request_id": "req-test"}
        error = HTTPError("https://example.com", 400, "Bad Request", None, io.BytesIO(json.dumps(body).encode()))
        with patch.object(tts, "get_key", return_value="test-key"), patch("urllib.request.urlopen", side_effect=error) as call:
            with self.assertRaises(ValueError) as raised:
                tts.synth_next("你好", settings)
            message = str(raised.exception)
            self.assertIn("CLIENT_ERROR", message)
            self.assertIn("req-test", message)
            self.assertNotIn("test-key", message)
            self.assertNotIn("Signature=secret", message)
            self.assertEqual(call.call_count, 1)

    def test_say_cli_uses_eleven_favorite_without_flash_default(self):
        favorite = {"voice": "eleven123", "name": "Siqi Liu"}
        for model in tts.eleven.MODELS:
            with self.subTest(model=model), patch.object(tts, "load_settings", return_value={"model": model}), patch.object(tts.eleven, "favorites", return_value=[favorite]), patch.object(tts, "default_voice") as flash, patch.object(tts, "cmd_say") as say, patch.object(sys, "argv", ["tts.py", "say", "--text", "你好"]):
                tts.main()
                self.assertEqual(say.call_args.args[0].voice, "eleven123")
                flash.assert_not_called()

    def test_say_uses_whole_truncated_text(self):
        raw = "甲" * 1000 + "。" + "乙" * 1000
        args = SimpleNamespace(install=False, save=False, clipboard=False, text=raw,
                               max=1500, voice="flash-voice", instruct=None, emotion=None)
        settings = {"model": tts.NEXT_MODEL, "workspace_id": "llm-test", "description": "女声"}
        stdout, stderr = sys.stdout, sys.stderr
        with tempfile.TemporaryDirectory() as root, patch.object(tts.sys, "platform", "darwin"), patch.object(tts, "SAY_DIR", root), patch.object(tts, "SAY_LOG", root + "/say.log"), patch.object(tts, "stop_previous_say"), patch.object(tts, "load_settings", return_value=settings), patch.object(tts, "check_voice") as check, patch.object(tts, "speak_segments") as speak:
            try:
                tts.cmd_say(args)
            finally:
                sys.stdout, sys.stderr = stdout, stderr
            self.assertEqual(speak.call_args.args[0], ["甲" * 1000 + "。"])
            self.assertEqual(args.synth_settings, settings)
            check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
