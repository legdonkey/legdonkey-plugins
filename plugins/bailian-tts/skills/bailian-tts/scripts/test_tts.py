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
    def test_generation_dispatches_selected_model(self):
        for model in (tts.MODEL, tts.NEXT_MODEL, *tts.eleven.MODELS):
            args = SimpleNamespace(synth_settings={"model": model}, rate=1.0, pitch=1.0, volume=50)
            with self.subTest(model=model), patch.object(tts, "synth", return_value=b"flash") as flash, patch.object(tts, "synth_next", return_value=b"next") as next_call, patch.object(tts.eleven, "synth", return_value=b"eleven") as eleven_call, patch.object(tts, "normalize") as normalize, patch.object(tts, "duration", return_value=1):
                tts.synth_to_file("voice123", "你好", None, args, "out.wav")
                expected = b"flash" if model == tts.MODEL else b"next" if model == tts.NEXT_MODEL else b"eleven"
                normalize.assert_called_once_with(expected, "out.wav")
                self.assertEqual(flash.call_count + next_call.call_count + eleven_call.call_count, 1)

    def test_generation_cli_uses_model_favorites(self):
        for command, extra in (("gen", ["--text", "你好", "--out", "out.wav"]), ("preview", []), ("script", ["input.txt", "--out-dir", "dub"])):
            for model, voice in ((tts.NEXT_MODEL, ""), (tts.eleven.MODEL, "eleven123"), (tts.eleven.TURBO_MODEL, "eleven123")):
                with self.subTest(command=command, model=model), patch.object(tts, "load_settings", return_value={"model": model}), patch.object(tts.eleven, "favorites", return_value=[{"voice": "eleven123"}]), patch.object(tts, "default_voice") as flash, patch.object(tts, "cmd_" + command) as handler, patch.object(sys, "argv", ["tts.py", command, *extra]):
                    tts.main()
                    self.assertEqual(handler.call_args.args[0].voice, voice)
                    self.assertEqual(handler.call_args.args[0].synth_settings["model"], model)
                    flash.assert_not_called()

    def test_incompatible_options_fail_before_synthesis(self):
        args = SimpleNamespace(synth_settings={"model": tts.NEXT_MODEL}, rate=1.0, pitch=1.0, volume=50, emotion=None)
        for voice, text, instr in (("longanhuan_v3.1", "你好", None), ("", "你好", "开心"), ("", "甲" * 2801, None)):
            with self.assertRaises(SystemExit):
                tts.validate_synthesis(voice, text, instr, args)
        args.synth_settings["model"] = tts.eleven.MODEL
        for voice in ("", "longanhuan_v3.1"):
            with self.assertRaises(SystemExit):
                tts.validate_synthesis(voice, "你好", None, args)
        tts.validate_synthesis("eleven123", "你好", None, args)

    def test_script_preflight_and_manifest_model(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "script.txt"
            source.write_text("第一段\n@instruct 开心\n第二段", encoding="utf-8")
            args = SimpleNamespace(file=str(source), voice="eleven123", instruct=None, emotion=None, rate=1.0, pitch=1.0, volume=50, synth_settings={"model": tts.eleven.MODEL}, out_dir=root + "/dub", gap=0.3)
            with patch.object(tts, "synth_to_file") as synth:
                with self.assertRaises(SystemExit):
                    tts.cmd_script(args)
                synth.assert_not_called()
            source.write_text("第一段\n第二段", encoding="utf-8")
            def fake_audio(voice, text, instr, args, out):
                with tts.wave.open(out, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(24000)
                    wav.writeframes(b"\x00\x00" * 240)
                return 0.01
            with patch.object(tts, "synth_to_file", side_effect=fake_audio):
                tts.cmd_script(args)
            manifest = json.loads((Path(args.out_dir) / "manifest.json").read_text())
            self.assertEqual(manifest["model"], tts.eleven.MODEL)
            self.assertEqual(len(manifest["segments"]), 2)
            self.assertTrue((Path(args.out_dir) / "subtitles.srt").exists())

    def test_ui_flash_preview_keeps_explicit_flash_settings(self):
        with tempfile.TemporaryDirectory() as root:
            ui = tts.LocalUI("studio.html")
            import shutil
            self.addCleanup(shutil.rmtree, ui.workdir)
            def fake_audio(voice, text, instr, args, path):
                self.assertEqual(args.synth_settings["model"], tts.MODEL)
                Path(path).write_bytes(b"audio")
                return 1
            with patch.object(tts, "synth_to_file", side_effect=fake_audio):
                self.assertEqual(ui.say("longanhuan_v3.1", "你好")[1], 1)

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

    def test_say_logs_and_notifies_when_ffmpeg_missing(self):
        import contextlib, signal
        a = SimpleNamespace(synth_settings={"model": tts.MODEL}, rate=1, pitch=1, volume=50)
        err = io.StringIO()
        with patch.object(tts, "say_session", lambda: contextlib.nullcontext(0)), patch.object(signal, "signal"), patch.object(tts, "synth", return_value=b"x"), patch.object(tts, "normalize", side_effect=FileNotFoundError("ffmpeg")), patch.object(tts, "notify") as notify, patch.object(sys, "stderr", err):
            self.assertFalse(tts.speak_segments(["测试"], "voice", None, a))
        self.assertIn("ffmpeg", err.getvalue())
        notify.assert_called_once()

    def test_say_check_and_last_trigger(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "SAY_LOG", root + "/say.log"):
            self.assertEqual(tts.last_triggers(), {"按键触发": "", "快捷键触发": ""})
            Path(tts.SAY_LOG).write_text("\n--- 2026-10-30 10:00:00 按键触发\n\n--- 2026-10-30 10:00:01 qwen 3 字\n"
                                         "\n--- 2026-10-30 10:00:05 快捷键触发\n\n--- 2026-10-30 10:00:06 按键触发\n")
            # 两种来源分开记:「快捷键触发」不能被当成鼠标的「按键触发」
            self.assertEqual(tts.last_triggers(), {"按键触发": "2026-10-30 10:00:06", "快捷键触发": "2026-10-30 10:00:05"})
        with patch.object(tts, "load_settings", return_value={"model": tts.MODEL}), patch.object(tts, "deps_status", return_value={"ffmpeg": False, "dashscope": True}), patch.object(tts, "key_status", return_value={"configured": True}), patch.dict(os.environ, {"PATH": "/usr/bin"}):
            with self.assertRaises(SystemExit) as e:
                tts.say_check()
            self.assertIn("ffmpeg", str(e.exception.code))

    def test_say_respects_model_limit_and_interface_boundary(self):
        for model, configured, override, expected in [(tts.NEXT_MODEL, 20, None, 22), (tts.NEXT_MODEL, 20, 10, 12), (tts.eleven.MODEL, 2000, None, 2000)]:
            with self.subTest(model=model, configured=configured, override=override):
                args = SimpleNamespace(install=False, check=False, save=False, clipboard=False, text="甲" * 3000,
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
        args = SimpleNamespace(install=False, check=False, save=False, clipboard=False, text=raw,
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

    def test_clipboard_closes_stdout_after_restoring(self):
        # 快捷键小助手靠 stdout 关闭判断剪贴板已还原,所以必须先还原、再关、再合成
        args = SimpleNamespace(install=False, check=False, save=False, clipboard=True, text=None,
                               max=1500, voice=None, instruct=None, emotion=None)
        order = []
        stdout, stderr = sys.stdout, sys.stderr
        with tempfile.TemporaryDirectory() as root, patch.object(tts.sys, "platform", "darwin"), patch.object(tts, "SAY_DIR", root), \
                patch.object(tts, "SAY_CLIP", root + "/clip.txt"), patch.object(tts, "SAY_LOG", root + "/say.log"), \
                patch.object(tts, "pb_paste", return_value="选中的字"), patch.object(tts, "pb_copy", side_effect=lambda t: order.append(("copy", t))), \
                patch.object(tts.os, "open", return_value=99), patch.object(tts.os, "dup2", side_effect=lambda a, b: order.append(("dup2", b))), \
                patch.object(tts, "load_settings", return_value={"model": tts.NEXT_MODEL}), \
                patch.object(tts, "speak_segments", side_effect=lambda *a: order.append(("speak",))):
            Path(tts.SAY_CLIP).write_text("原剪贴板")
            try:
                tts.cmd_say(args)
            finally:
                sys.stdout, sys.stderr = stdout, stderr
        self.assertEqual(order, [("copy", "原剪贴板"), ("dup2", 1), ("speak",)])


class HotkeyTests(unittest.TestCase):
    """全局快捷键小助手:只测本地判断,不编译、不碰 launchctl。"""

    def test_status_survives_broken_agent_plist(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "HOTKEY_AGENT", root + "/agent.plist"), \
                patch.object(tts, "HOTKEY_STATUS", root + "/status.json"), patch.object(tts, "HOTKEY_ERR", root + "/err.log"), \
                patch.object(tts, "_launchctl", return_value=SimpleNamespace(stdout="", returncode=113)):
            self.assertFalse(tts.hotkey_status()["installed"])
            Path(tts.HOTKEY_AGENT).write_text("不是 plist")
            st = tts.hotkey_status()  # 启动项坏了也要返回状态,页面才能显示「移除」
            self.assertEqual((st["installed"], st["running"], st["key"], st["label"]), (True, False, "", ""))

    def test_status_reads_key_from_agent(self):
        import plistlib
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "HOTKEY_AGENT", root + "/agent.plist"), \
                patch.object(tts, "HOTKEY_STATUS", root + "/status.json"), patch.object(tts, "HOTKEY_ERR", root + "/err.log"), \
                patch.object(tts, "_launchctl", return_value=SimpleNamespace(stdout="state = running", returncode=0)):
            Path(tts.HOTKEY_AGENT).write_bytes(plistlib.dumps({"ProgramArguments": ["bin", str(tts.KEYCODES["s"]), "st"]}))
            Path(tts.HOTKEY_STATUS).write_text('{"registered": true, "trusted": true}')
            st = tts.hotkey_status()
            self.assertEqual((st["key"], st["label"], st["running"], st["trusted"]), ("s", "⌃⌥⌘S", True, True))

    def test_install_rejects_bad_letter_and_taken_combo(self):
        with self.assertRaises(SystemExit):
            tts.hotkey_install("1")
        # 修饰键顺序不同也算同一个组合
        with patch.object(tts, "_pbs_status", return_value={"(null) - 切换 - runWorkflowAsService": {"key_equivalent": "^~@d"}}), \
                patch.object(tts.subprocess, "run", return_value=SimpleNamespace(stdout="")), \
                patch.object(tts, "write_say_wrapper") as wrapper, self.assertRaises(SystemExit) as e:
            tts.hotkey_install("d")
        self.assertIn("切换", str(e.exception.code))
        wrapper.assert_not_called()

    def test_keycodes_cover_alphabet(self):
        self.assertEqual(sorted(tts.KEYCODES), list("abcdefghijklmnopqrstuvwxyz"))
        self.assertEqual(len(set(tts.KEYCODES.values())), 26)


if __name__ == "__main__":
    unittest.main()
