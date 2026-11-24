"""模型配置、Flash / Plus 音色隔离与合成请求契约测试，全部离线。"""
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("tts", Path(__file__).with_name("tts.py"))
tts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tts)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for module, name, filename in ((tts, "SETTINGS_PATH", "settings.json"),
                                       (tts, "FAV_PATH", "favorites.txt"),
                                       (tts, "PLUS_FAV_PATH", "plus-favorites.txt"),
                                       (tts, "KEY_PATH", "bailian.key"),
                                       (tts.eleven, "KEY_PATH", "elevenlabs.key"),
                                       (tts.eleven, "FAV_PATH", "elevenlabs-favorites.json")):
            p = patch.object(module, name, self.tmp.name + "/" + filename)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_generation_dispatches_selected_model(self):
        for model in (*tts.BAILIAN_VOICE_MODELS, tts.NEXT_MODEL, *tts.eleven.MODELS):
            args = SimpleNamespace(synth_settings={"model": model}, rate=1.0, pitch=1.0, volume=50)
            with self.subTest(model=model), patch.object(tts, "synth", return_value=b"flash") as flash, patch.object(tts, "synth_next", return_value=b"next") as next_call, patch.object(tts.eleven, "synth", return_value=b"eleven") as eleven_call, patch.object(tts, "normalize") as normalize, patch.object(tts, "duration", return_value=1):
                tts.synth_to_file("voice123", "你好", None, args, "out.wav")
                expected = b"flash" if model in tts.BAILIAN_VOICE_MODELS else b"next" if model == tts.NEXT_MODEL else b"eleven"
                normalize.assert_called_once_with(expected, "out.wav")
                self.assertEqual(flash.call_count + next_call.call_count + eleven_call.call_count, 1)
                if model in tts.BAILIAN_VOICE_MODELS:
                    flash.assert_called_once_with("voice123", "你好", None, 1.0, 1.0, 50, model)

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

    def test_local_ui_say_uses_settings_or_explicit_bailian_model(self):
        ui = tts.LocalUI("studio.html")
        self.addCleanup(shutil.rmtree, ui.workdir)
        for options, model in (({}, tts.MODEL), ({"settings": {"model": tts.PLUS_MODEL}}, tts.PLUS_MODEL),
                               ({"model": tts.PLUS_MODEL}, tts.PLUS_MODEL),
                               ({"settings": {"model": tts.NEXT_MODEL}, "model": tts.PLUS_MODEL}, tts.PLUS_MODEL),
                               ({"settings": {"model": tts.eleven.MODEL}, "model": tts.MODEL}, tts.MODEL)):
            def fake_audio(voice, text, instr, args, path):
                self.assertEqual(args.synth_settings["model"], model)
                Path(path).write_bytes(b"audio")
                return 1
            with self.subTest(options=options), patch.object(tts, "synth_to_file", side_effect=fake_audio), patch.object(tts, "synth_next") as next_call, patch.object(tts.eleven, "synth") as eleven_call:
                self.assertEqual(ui.say("longanhuan_v3.1", "你好", **options)[1], 1)
                next_call.assert_not_called()
                eleven_call.assert_not_called()

    def test_settings_roundtrip_and_environment(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "SETTINGS_PATH", root + "/settings.json"), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(tts.load_settings()["model"], tts.MODEL)
            for model in (tts.NEXT_MODEL, tts.PLUS_MODEL):
                saved = tts.save_settings({"model": model, "workspace_id": "llm-test", "description": "沉稳女声"})
                self.assertEqual(saved["model"], model)
                self.assertEqual(saved, tts.load_settings())
                self.assertEqual(saved["read_limits"][tts.PLUS_MODEL], 1500)
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
            saved = tts.save_settings(dict(base, read_limits={tts.eleven.TURBO_MODEL: 500, tts.PLUS_MODEL: 20000}))
            self.assertEqual(saved["read_limits"][tts.MODEL], 4000)
            self.assertEqual(saved["read_limits"][tts.eleven.MODEL], 1000)
            self.assertEqual(saved["read_limits"][tts.eleven.TURBO_MODEL], 500)
            self.assertEqual(saved["read_limits"][tts.PLUS_MODEL], 20000)
            self.assertEqual(tts.save_settings(base), saved)
            for limits in ([1], {"unsupported": 10}, {tts.MODEL: True}, {tts.MODEL: "10"}, {tts.MODEL: 1.5}, {tts.MODEL: 0}, {tts.PLUS_MODEL: 0}, {tts.PLUS_MODEL: 20001}, {tts.PLUS_MODEL: True}, {tts.eleven.MODEL: 2001}):
                with self.subTest(limits=limits), self.assertRaises(ValueError):
                    tts.save_settings(dict(base, read_limits=limits))
                self.assertEqual(tts.load_settings(), saved)

    def test_read_limit_configuration_and_cli_priority(self):
        settings = {"model": tts.eleven.TURBO_MODEL, "read_limits": {tts.MODEL: 5000, tts.eleven.TURBO_MODEL: 800}}
        self.assertEqual(tts.read_limit(settings), 800)
        self.assertEqual(tts.read_limit(settings, 1000), 1000)
        self.assertEqual(tts.read_limit({"model": tts.MODEL}), 1500)
        plus = {"model": tts.PLUS_MODEL, "read_limits": {tts.PLUS_MODEL: 20000}}
        self.assertEqual(tts.read_limit({"model": tts.PLUS_MODEL}), 1500)
        self.assertEqual(tts.read_limit(plus), 20000)
        self.assertEqual(tts.read_limit(plus, 1), 1)
        for limit in (0, 20001, True, "100"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                tts.read_limit(plus, limit)
        with self.assertRaises(ValueError):
            tts.read_limit(settings, 0)
        with self.assertRaises(ValueError):
            tts.read_limit(settings, 2001)

    def test_say_logs_and_notifies_when_ffmpeg_missing(self):
        import contextlib, signal
        for model in tts.BAILIAN_VOICE_MODELS:
            a = SimpleNamespace(synth_settings={"model": model}, rate=1, pitch=1, volume=50)
            err = io.StringIO()
            with self.subTest(model=model), patch.object(tts, "say_session", lambda: contextlib.nullcontext(0)), patch.object(signal, "signal"), patch.object(tts, "synth", return_value=b"x") as synth, patch.object(tts, "normalize", side_effect=FileNotFoundError("ffmpeg")), patch.object(tts, "notify") as notify, patch.object(sys, "stderr", err):
                self.assertFalse(tts.speak_segments(["测试"], "voice", None, a))
                synth.assert_called_once_with("voice", "测试", None, 1, 1, 50, model)
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
        for model, configured, override, expected in [(tts.PLUS_MODEL, 20000, None, 3000), (tts.PLUS_MODEL, 20, None, 22), (tts.NEXT_MODEL, 20, None, 22), (tts.NEXT_MODEL, 20, 10, 12), (tts.eleven.MODEL, 2000, None, 2000)]:
            with self.subTest(model=model, configured=configured, override=override):
                args = SimpleNamespace(install=False, check=False, save=False, clipboard=False, text="甲" * 3000,
                                       max=override, voice=tts.DEFAULT_VOICE if model == tts.PLUS_MODEL else "voice123", instruct=None, emotion=None)
                settings = {"model": model, "read_limits": {model: configured}}
                stdout, stderr = sys.stdout, sys.stderr
                with tempfile.TemporaryDirectory() as root, patch.object(tts.sys, "platform", "darwin"), patch.object(tts, "SAY_DIR", root), patch.object(tts, "SAY_LOG", root + "/say.log"), patch.object(tts, "stop_previous_say"), patch.object(tts, "load_settings", return_value=settings), patch.object(tts, "speak_segments") as speak:
                    try:
                        tts.cmd_say(args)
                    finally:
                        sys.stdout, sys.stderr = stdout, stderr
                    self.assertEqual(len(speak.call_args.args[0]), 1)
                    self.assertEqual(len(speak.call_args.args[0][0]), expected)
                    self.assertEqual(speak.call_args.args[0][0].endswith("……"), expected < 3000)

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

    def test_load_catalog_filters_only_plus_flagship_voices(self):
        flagship = ["longanhuan_v3.1", "longanlingxin_v3.1", "longanfengyue_v3.1", "xunanchuan_v3.1"]
        self.assertEqual(len(tts.load_catalog()), 68)
        self.assertEqual(len(tts.load_catalog(tts.MODEL)), 68)
        self.assertEqual([v["voice"] for v in tts.load_catalog(tts.PLUS_MODEL)], flagship)
        self.assertIsNone(tts.voice_entry("yuxiaoyun_v3.1", tts.PLUS_MODEL))

    def test_plus_favorites_inherit_without_writing_then_save_independently(self):
        flash_clone = tts.MODEL + "-ygd-" + "a" * 16
        flash = ["yuxiaoyun_v3.1", "xunanchuan_v3.1", flash_clone, "longanhuan_v3.1"]
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), [])
        tts.save_favorites(flash)
        original = Path(tts.FAV_PATH).read_bytes()
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), ["xunanchuan_v3.1", "longanhuan_v3.1"])
        self.assertEqual(tts.default_voice(tts.PLUS_MODEL), ("xunanchuan_v3.1", "Plus 收藏第 1 个"))
        self.assertFalse(Path(tts.PLUS_FAV_PATH).exists())
        plus_clone = tts.PLUS_MODEL + "-ygd-" + "b" * 32
        tts.save_favorites([plus_clone], tts.PLUS_MODEL)
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), [plus_clone])
        self.assertEqual(tts.default_voice(tts.PLUS_MODEL), (plus_clone, "Plus 收藏第 1 个"))
        self.assertEqual(Path(tts.FAV_PATH).read_bytes(), original)
        tts.save_favorites([], tts.PLUS_MODEL)
        self.assertEqual(Path(tts.PLUS_FAV_PATH).read_bytes(), b"")
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), [])
        self.assertEqual(tts.default_voice(tts.PLUS_MODEL), (tts.DEFAULT_VOICE, "内置默认"))
        self.assertEqual(Path(tts.FAV_PATH).read_bytes(), original)
        with patch.object(sys, "stdout", new=io.StringIO()) as out:
            tts.print_favorites_summary(tts.PLUS_MODEL)
        self.assertEqual(out.getvalue(), "当前收藏:无\n")

    def test_check_voice_allows_only_matching_bailian_model(self):
        plus_clone = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        flash_clone = tts.MODEL + "-ygd-" + "b" * 32
        for v in [entry["voice"] for entry in tts.load_catalog(tts.PLUS_MODEL)] + [plus_clone]:
            with self.subTest(voice=v), patch.object(sys, "stderr", new=io.StringIO()) as err:
                tts.check_voice(v, tts.PLUS_MODEL)
                self.assertEqual(err.getvalue(), "")
        for model, voice in ((tts.PLUS_MODEL, "yuxiaoyun_v3.1"), (tts.PLUS_MODEL, flash_clone),
                             (tts.MODEL, plus_clone), (tts.PLUS_MODEL, tts.MODEL + "-official-language"),
                             (tts.MODEL, tts.PLUS_MODEL + "-short")):
            with self.subTest(model=model, voice=voice), self.assertRaises(SystemExit) as raised:
                tts.check_voice(voice, model)
            self.assertIn("不能用于 " + model, str(raised.exception))
        with patch.object(sys, "stderr", new=io.StringIO()) as err:
            tts.check_voice(tts.MODEL + "-official-language")
            self.assertEqual(err.getvalue(), "")
            tts.check_voice("new-unknown-voice", tts.PLUS_MODEL)
            self.assertIn("⚠ new-unknown-voice 不在 " + tts.PLUS_MODEL, err.getvalue())

    def test_validate_synthesis_plus_voice_and_length_boundaries(self):
        args = SimpleNamespace(synth_settings={"model": tts.PLUS_MODEL}, rate=1.0, pitch=1.0, volume=50, emotion=None)
        plus_clone = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        for voice in [v["voice"] for v in tts.load_catalog(tts.PLUS_MODEL)] + [plus_clone]:
            tts.validate_synthesis(voice, "你好", "请用重庆话表达。", args)
        for model, voice in ((tts.PLUS_MODEL, "yuxiaoyun_v3.1"),
                             (tts.PLUS_MODEL, tts.MODEL + "-ygd-" + "a" * 16),
                             (tts.MODEL, plus_clone), *[(m, plus_clone) for m in tts.eleven.MODELS]):
            args.synth_settings["model"] = model
            with self.subTest(model=model, voice=voice), self.assertRaises(SystemExit):
                tts.validate_synthesis(voice, "你好", None, args)
        for model in tts.BAILIAN_VOICE_MODELS:
            args.synth_settings["model"] = model
            tts.validate_synthesis(tts.DEFAULT_VOICE, "甲" * 20000, None, args)
            with self.assertRaisesRegex(SystemExit, "单段正文不能超过 20000 字符"):
                tts.validate_synthesis(tts.DEFAULT_VOICE, "甲" * 20001, None, args)
            with self.assertRaisesRegex(SystemExit, "指令过长"):
                tts.validate_synthesis(tts.DEFAULT_VOICE, "你好", "甲" * 51, args)

    def test_synth_passes_requested_bailian_model_to_sdk(self):
        sdk = SimpleNamespace(SpeechSynthesizer=MagicMock(), AudioFormat=SimpleNamespace(WAV_24000HZ_MONO_16BIT="wav"))
        sdk.SpeechSynthesizer.return_value.call.return_value = b"a" * 2100
        for model in tts.BAILIAN_VOICE_MODELS:
            with self.subTest(model=model), patch.dict(sys.modules, {"dashscope.audio.tts_v2": sdk}), patch.object(tts, "init_dashscope"):
                self.assertEqual(tts.synth(tts.DEFAULT_VOICE, "你好", "开心", model=model), b"a" * 2100)
                self.assertEqual(sdk.SpeechSynthesizer.call_args.kwargs["model"], model)
                self.assertEqual(sdk.SpeechSynthesizer.call_args.kwargs["instruction"], "开心")

    def test_main_uses_plus_favorite_for_every_synthesis_command(self):
        favorite = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        tts.save_favorites(["yuxiaoyun_v3.1"])
        tts.save_favorites([favorite], tts.PLUS_MODEL)
        for command, extra in (("gen", ["--text", "你好", "--out", "out.wav"]), ("preview", []),
                               ("script", ["input.txt", "--out-dir", "dub"]), ("say", ["--text", "你好"])):
            for explicit in (False, True):
                argv = ["tts.py", command, *extra] + (["-v", "xunanchuan_v3.1"] if explicit else [])
                with self.subTest(command=command, explicit=explicit), patch.object(tts, "load_settings", return_value={"model": tts.PLUS_MODEL}), patch.object(tts, "cmd_" + command) as handler, patch.object(sys, "argv", argv), patch.object(sys, "stderr", new=io.StringIO()):
                    tts.main()
                args = handler.call_args.args[0]
                self.assertEqual(args.voice, "xunanchuan_v3.1" if explicit else favorite)
                self.assertEqual(args.synth_settings["model"], tts.PLUS_MODEL)

    def test_main_voice_management_requires_bailian_default_or_explicit_model(self):
        for command, extra in (("voices", []), ("fav", []), ("clone", ["sample.wav", "--prefix", "ygd"])):
            for model in (*tts.BAILIAN_VOICE_MODELS, tts.NEXT_MODEL, *tts.eleven.MODELS):
                for explicit in (None, tts.PLUS_MODEL, tts.MODEL):
                    argv = ["tts.py", command, *extra] + (["--model", explicit] if explicit else [])
                    with self.subTest(command=command, model=model, explicit=explicit), patch.object(tts, "load_settings", return_value={"model": model}), patch.object(tts, "cmd_" + command) as handler, patch.object(sys, "argv", argv), patch.object(sys, "stderr", new=io.StringIO()) as err:
                        if explicit is None and model not in tts.BAILIAN_VOICE_MODELS:
                            with self.assertRaisesRegex(SystemExit, "不使用百炼音色库与声音复刻") as raised:
                                tts.main()
                            self.assertIn(model, str(raised.exception))
                            self.assertIn("显式传 --model", str(raised.exception))
                            handler.assert_not_called()
                        else:
                            tts.main()
                            self.assertEqual(handler.call_args.args[0].target_model, explicit or model)
                            self.assertIn("百炼音色管理使用:" + (explicit or model), err.getvalue())

    def test_parse_script_rejects_cross_model_voice_before_synthesis(self):
        source = Path(self.tmp.name) / "script.txt"
        source.write_text("第一段\n@voice yuxiaoyun_v3.1\n第二段", encoding="utf-8")
        args = SimpleNamespace(file=str(source), voice=tts.DEFAULT_VOICE, instruct=None, emotion=None,
                               synth_settings={"model": tts.PLUS_MODEL}, rate=1, pitch=1, volume=50)
        with patch.object(tts, "synth_to_file") as synth, self.assertRaises(SystemExit):
            tts.cmd_script(args)
        synth.assert_not_called()
        source.write_text("第一段\n@voice " + tts.PLUS_MODEL + "-ygd-" + "a" * 16 + "\n第二段", encoding="utf-8")
        self.assertEqual(len(tts.parse_script(str(source), tts.DEFAULT_VOICE, None, tts.PLUS_MODEL)), 2)
        with self.assertRaises(SystemExit):
            tts.parse_script(str(source), tts.DEFAULT_VOICE, None, tts.MODEL)

    def test_clone_voice_passes_target_model_to_sdk_and_cli(self):
        voice_id = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        service = MagicMock()
        service.create_voice.return_value = voice_id
        service.query_voice.return_value = {"status": "OK"}
        sdk = SimpleNamespace(VoiceEnrollmentService=MagicMock(return_value=service))
        with patch.dict(sys.modules, {"dashscope.audio.tts_v2": sdk}), patch.object(tts, "init_dashscope"), patch.object(sys, "stdout", new=io.StringIO()):
            self.assertEqual(tts.clone_voice("https://example.test/record.wav", "YGD", target_model=tts.PLUS_MODEL), (voice_id, True))
        self.assertEqual(service.create_voice.call_args.kwargs["target_model"], tts.PLUS_MODEL)
        self.assertEqual(service.create_voice.call_args.kwargs["prefix"], "ygd")
        args = SimpleNamespace(source="sample.wav", prefix="ygd", lang="zh", max_seconds=10.0,
                               denoise=False, target_model=tts.PLUS_MODEL)
        with patch.object(tts, "clone_voice", return_value=(voice_id, True)) as clone, patch.object(sys, "stdout", new=io.StringIO()):
            tts.cmd_clone(args)
        clone.assert_called_once_with("sample.wav", "ygd", "zh", 10.0, False, target_model=tts.PLUS_MODEL)

    def test_cmd_voices_and_list_mine_use_target_model(self):
        tts.save_favorites(["xunanchuan_v3.1"], tts.PLUS_MODEL)
        args = SimpleNamespace(target_model=tts.PLUS_MODEL, mine=False, gender=None, scene=None)
        with patch.object(sys, "stdout", new=io.StringIO()) as out:
            tts.cmd_voices(args)
        self.assertIn(tts.PLUS_MODEL + " 系统音色(共 4 个", out.getvalue())
        self.assertIn("★xunanchuan_v3.1", out.getvalue())
        self.assertNotIn("yuxiaoyun_v3.1", out.getvalue())
        rows = [{"voice_id": "plus-id", "target_model": tts.PLUS_MODEL}, {"voice_id": "flash-id", "target_model": tts.MODEL}]
        with patch.object(tts, "fetch_custom_voices", return_value=rows), patch.object(sys, "stdout", new=io.StringIO()) as out:
            tts.list_mine(tts.PLUS_MODEL)
        usable, other = out.getvalue().split("【不可用 · 属于其它模型】")
        self.assertIn("【可用 · " + tts.PLUS_MODEL + "】", usable)
        self.assertIn("plus-id", usable)
        self.assertNotIn("flash-id", usable)
        self.assertIn("flash-id", other)
        args.mine = True
        with patch.object(tts, "list_mine") as mine:
            tts.cmd_voices(args)
        mine.assert_called_once_with(tts.PLUS_MODEL)

    def test_cmd_fav_writes_only_target_model_and_displays_path(self):
        tts.save_favorites(["yuxiaoyun_v3.1"])
        args = SimpleNamespace(target_model=tts.PLUS_MODEL, action="add", voices=["xunanchuan_v3.1"])
        with patch.object(sys, "stdout", new=io.StringIO()) as out:
            tts.cmd_fav(args)
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), ["xunanchuan_v3.1"])
        self.assertEqual(tts.load_favorites(), ["yuxiaoyun_v3.1"])
        self.assertIn(tts.PLUS_FAV_PATH, out.getvalue())
        args.voices = ["yuxiaoyun_v3.1"]
        with self.assertRaises(SystemExit):
            tts.cmd_fav(args)
        args.action, args.voices = "rm", ["xunanchuan_v3.1"]
        with patch.object(sys, "stdout", new=io.StringIO()) as out:
            tts.cmd_fav(args)
        self.assertIn(tts.PLUS_FAV_PATH, out.getvalue())
        self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), [])

    def studio_routes(self):
        with patch.object(tts.LocalUI, "serve", autospec=True) as serve, patch.object(sys, "stdout", new=io.StringIO()):
            tts.cmd_ui(SimpleNamespace(page="voices", port=0, no_open=True))
        ui, _, routes, *_ = serve.call_args.args
        self.addCleanup(shutil.rmtree, ui.workdir)
        return ui, routes

    def test_ui_state_returns_only_current_model_catalog_and_favorites(self):
        tts.save_favorites(["yuxiaoyun_v3.1"])
        tts.save_favorites(["xunanchuan_v3.1"], tts.PLUS_MODEL)
        _, routes = self.studio_routes()
        for model, count, favorite in ((tts.MODEL, 68, ["yuxiaoyun_v3.1"]), (tts.PLUS_MODEL, 4, ["xunanchuan_v3.1"]),
                                        (tts.NEXT_MODEL, 0, []), *[(m, 0, []) for m in tts.eleven.MODELS]):
            settings = {"model": model}
            with self.subTest(model=model), patch.object(tts, "load_settings", return_value=settings), patch.object(tts, "load_catalog", wraps=tts.load_catalog) as catalog, patch.object(tts, "load_favorites", wraps=tts.load_favorites) as favorites:
                state = routes["GET", "/state"]({}, b"", "")
                self.assertEqual(state["model"], model)
                self.assertEqual(state["settings"], settings)
                self.assertEqual(len(state["catalog"]), count)
                self.assertEqual(state["favorites"], favorite)
                if model not in tts.BAILIAN_VOICE_MODELS:
                    catalog.assert_not_called()
                    favorites.assert_not_called()

    def test_ui_bailian_management_rejects_next_and_eleven_before_side_effects(self):
        ui, routes = self.studio_routes()
        for model in (tts.NEXT_MODEL, *tts.eleven.MODELS):
            for method, path, payload in (("GET", "/mine", {}), ("POST", "/fav", {"voice": tts.DEFAULT_VOICE, "action": "add"}),
                                          ("POST", "/clone", {}), ("POST", "/say", {"voice": tts.DEFAULT_VOICE, "text": "你好", "clone": True}),
                                          ("POST", "/say", {"voice": tts.DEFAULT_VOICE, "text": "", "clone": True})):
                with self.subTest(model=model, path=path), patch.object(tts, "load_settings", return_value={"model": model}), patch.object(tts, "fetch_custom_voices") as fetch, patch.object(tts, "clone_voice") as clone, patch.object(tts, "save_favorites") as save, patch.object(ui, "say") as say:
                    with self.assertRaisesRegex(SystemExit, "当前默认模型不支持百炼音色管理或声音复刻，请先在顶部切换为 Flash 或 Plus"):
                        routes[method, path]({}, json.dumps(payload).encode(), "audio/wav" if path == "/clone" else "")
                    fetch.assert_not_called()
                    clone.assert_not_called()
                    save.assert_not_called()
                    say.assert_not_called()
                    self.assertEqual(list(Path(ui.workdir).iterdir()), [])

    def test_ui_plus_mine_favorites_and_clone_use_plus_model(self):
        tts.save_settings({"model": tts.PLUS_MODEL})
        tts.save_favorites(["yuxiaoyun_v3.1", "longanhuan_v3.1"])
        ui, routes = self.studio_routes()
        voice_id = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        rows = [{"voice_id": voice_id, "target_model": tts.PLUS_MODEL}, {"voice_id": "flash-id", "target_model": tts.MODEL}]
        with patch.object(tts, "fetch_custom_voices", return_value=rows):
            self.assertEqual([v["voice"] for v in routes["GET", "/mine"]({}, b"", "")["voices"]], [voice_id])
        body = lambda action, voice: json.dumps({"voice": voice, "action": action}).encode()
        self.assertEqual(routes["POST", "/fav"]({}, body("default", voice_id), "")["favorites"], [voice_id, "longanhuan_v3.1"])
        with self.assertRaises(SystemExit):
            routes["POST", "/fav"]({}, body("add", "yuxiaoyun_v3.1"), "")
        self.assertEqual(tts.load_favorites(), ["yuxiaoyun_v3.1", "longanhuan_v3.1"])
        with patch.object(tts, "clone_voice", return_value=(voice_id, True)) as clone, patch.object(ui, "say", return_value=("/audio", 1)) as say:
            result = routes["POST", "/clone"]({"prefix": "ygd", "denoise": "1"}, b"fake-recording", "audio/wav")
        self.assertEqual(result["voice_id"], voice_id)
        self.assertEqual(clone.call_args.kwargs, {"denoise": True, "target_model": tts.PLUS_MODEL})
        self.assertEqual(say.call_args.kwargs, {"model": tts.PLUS_MODEL})

    def test_ui_say_dispatch_and_clone_cache_include_current_model(self):
        ui, routes = self.studio_routes()
        with patch.object(ui, "say", return_value=("/audio", 1)) as say:
            for model in tts.BAILIAN_VOICE_MODELS:
                settings = {"model": model}
                request = {"voice": tts.DEFAULT_VOICE, "text": "你好", "clone": True, "model": model}
                with patch.object(tts, "load_settings", return_value=settings):
                    first = routes["POST", "/say"]({}, json.dumps(request).encode(), "")
                    second = routes["POST", "/say"]({}, json.dumps({"voice": tts.DEFAULT_VOICE, "text": "你好", "model": model}).encode(), "")
                self.assertFalse(first["cached"])
                self.assertTrue(second["cached"])
                say.assert_called_with(tts.DEFAULT_VOICE, "你好", None, settings)
            self.assertEqual(say.call_count, 2)
        for model in (*tts.BAILIAN_VOICE_MODELS, tts.NEXT_MODEL, *tts.eleven.MODELS):
            settings = {"model": model}
            voice = "eleven123" if model in tts.eleven.MODELS else tts.DEFAULT_VOICE
            request = {"voice": voice, "text": "新句子", "model": model}
            with self.subTest(model=model), patch.object(tts, "load_settings", return_value=settings), patch.object(ui, "say", return_value=("/audio", 1)) as say:
                routes["POST", "/say"]({}, json.dumps(request).encode(), "")
                say.assert_called_once_with(voice, "新句子", None, settings)
        for model in tts.eleven.MODELS:
            for bad_voice in (tts.DEFAULT_VOICE, tts.PLUS_MODEL + "-ygd-" + "a" * 16):
                with patch.object(tts, "load_settings", return_value={"model": model}), patch.object(ui, "say") as say:
                    out = routes["POST", "/say"]({}, json.dumps({"voice": bad_voice, "text": "你好", "model": model}).encode(), "")
                    self.assertEqual(out["error"], "ElevenLabs 不能使用百炼音色 ID")
                    say.assert_not_called()
        with patch.object(tts, "load_settings", return_value={"model": tts.PLUS_MODEL}), patch.object(ui, "say") as say:
            for voice, model in (("yuxiaoyun_v3.1", tts.PLUS_MODEL), (tts.DEFAULT_VOICE, tts.MODEL)):
                request = {"voice": voice, "text": "你好", "model": model}
                if model == tts.PLUS_MODEL:
                    with self.assertRaises(SystemExit):
                        routes["POST", "/say"]({}, json.dumps(request).encode(), "")
                else:
                    self.assertIn("默认模型已在其他工作台更改", routes["POST", "/say"]({}, json.dumps(request).encode(), "")["error"])
            say.assert_not_called()

    def test_cmd_say_validates_cross_model_and_logs_clipboard_errors(self):
        plus_clone = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        for argv, model in ((["tts.py", "say", "-v", plus_clone, "--text", "你好"], tts.NEXT_MODEL),
                            (["tts.py", "say", "--instruct", "开心", "--text", "你好"], tts.NEXT_MODEL),
                            (["tts.py", "say", "-v", plus_clone, "--text", "你好"], tts.eleven.MODEL),
                            (["tts.py", "say", "--instruct", "开心", "--text", "你好"], tts.eleven.MODEL)):
            with self.subTest(argv=argv, model=model), patch.object(tts.sys, "platform", "darwin"),                     patch.object(tts, "stop_previous_say"), patch.object(tts, "load_settings", return_value={"model": model}),                     patch.object(tts.eleven, "favorites", return_value=[{"voice": "eleven123"}]),                     patch.object(tts, "speak_segments") as speak, patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    tts.main()
                speak.assert_not_called()
        args = SimpleNamespace(install=False, check=False, save=False, clipboard=True, text=None,
                               max=1500, voice="yuxiaoyun_v3.1", instruct=None, emotion=None)
        with tempfile.TemporaryDirectory() as root, patch.object(tts.sys, "platform", "darwin"),                 patch.object(tts, "SAY_DIR", root), patch.object(tts, "SAY_CLIP", root + "/clip.txt"),                 patch.object(tts, "SAY_LOG", root + "/say.log"), patch.object(tts, "pb_paste", return_value="选中文字"),                 patch.object(tts, "pb_copy"), patch.object(tts.os, "open", return_value=99), patch.object(tts.os, "dup2"),                 patch.object(tts, "load_settings", return_value={"model": tts.PLUS_MODEL}),                 patch.object(tts, "notify") as notify, patch.object(tts, "speak_segments") as speak:
            tts.cmd_say(args)
            self.assertIn("yuxiaoyun_v3.1", Path(tts.SAY_LOG).read_text())
            notify.assert_called_once()
            speak.assert_not_called()

    def test_ui_delete_cleans_both_favorites_without_creating_plus_file(self):
        _, routes = self.studio_routes()
        voice_id = tts.PLUS_MODEL + "-ygd-" + "a" * 16
        service = MagicMock()
        sdk = SimpleNamespace(VoiceEnrollmentService=MagicMock(return_value=service))
        for plus_exists in (False, True):
            tts.save_favorites([voice_id, "yuxiaoyun_v3.1"])
            if plus_exists:
                tts.save_favorites([voice_id, "longanhuan_v3.1"], tts.PLUS_MODEL)
            with self.subTest(plus_exists=plus_exists), patch.dict(sys.modules, {"dashscope.audio.tts_v2": sdk}), patch.object(tts, "init_dashscope"):
                self.assertEqual(routes["POST", "/delete"]({}, json.dumps({"voice": voice_id}).encode(), ""), {"deleted": voice_id})
            service.delete_voice.assert_called_with(voice_id)
            self.assertEqual(tts.load_favorites(), ["yuxiaoyun_v3.1"])
            self.assertEqual(Path(tts.PLUS_FAV_PATH).exists(), plus_exists)
            if plus_exists:
                self.assertEqual(tts.load_favorites(tts.PLUS_MODEL), ["longanhuan_v3.1"])

    def test_ui_say_state_uses_current_model_default_or_next_description(self):
        tts.save_favorites(["yuxiaoyun_v3.1"])
        tts.save_favorites(["xunanchuan_v3.1"], tts.PLUS_MODEL)
        tts.eleven.save_favorites([{"voice": "eleven123", "name": "Eleven"}])
        _, routes = self.studio_routes()
        for model, voice, name in ((tts.MODEL, "yuxiaoyun_v3.1", "于小云"),
                                    (tts.PLUS_MODEL, "xunanchuan_v3.1", "许南川"),
                                    (tts.NEXT_MODEL, "", "Next 描述声音（沉稳女声）"),
                                    *[(m, "eleven123", "Eleven") for m in tts.eleven.MODELS]):
            with self.subTest(model=model), patch.object(tts, "load_settings", return_value={"model": model, "description": "沉稳女声"}), patch.object(tts, "say_wrapper_status", return_value={}), patch.object(tts, "openlogi_status", return_value={}), patch.object(tts, "say_env_check"), patch.object(tts, "last_triggers", return_value={tts.SAY_TRIGGER: "", tts.HOTKEY_TRIGGER: ""}), patch.object(tts, "say_log_tail", return_value=[]), patch.object(tts, "hotkey_status", return_value={}):
                result = routes["GET", "/say-state"]({}, b"", "")
            self.assertEqual(result["voice"], voice)
            self.assertIn(name, result["voice_name"])

    def test_eleven_onboarding_uses_eleven_key_even_when_bailian_is_configured(self):
        for model in tts.eleven.MODELS:
            with self.subTest(model=model), patch.object(tts, "load_settings", return_value={"model": model}), patch.object(tts, "key_status", return_value={"configured": True}) as bailian_key, patch.object(tts.eleven, "key_status", return_value={"configured": False}), patch.object(sys, "stdout", new=io.StringIO()) as out:
                tts.cmd_status(None)
                self.assertIn("onboarding: 需要,运行 ui 在顶部模型设置中配置 ElevenLabs API Key", out.getvalue())
                with patch.object(tts.LocalUI, "serve", autospec=True) as serve:
                    tts.cmd_ui(SimpleNamespace(page="voices", port=0, no_open=True))
                self.addCleanup(shutil.rmtree, serve.call_args.args[0].workdir)
                self.assertEqual(serve.call_args.args[-1], "home")
                bailian_key.assert_not_called()

    def test_status_and_ui_exit_report_only_current_model_config(self):
        tts.save_favorites(["flash-only"])
        tts.save_favorites(["plus-only"], tts.PLUS_MODEL)
        tts.eleven.save_favorites([{"voice": "eleven-only", "name": "Eleven"}])
        for model, expected, absent in ((tts.MODEL, "flash-only", ["plus-only", "eleven-only"]),
                                        (tts.PLUS_MODEL, "plus-only", ["flash-only", "eleven-only"]),
                                        (tts.NEXT_MODEL, "声音描述:沉稳女声", ["flash-only", "plus-only", "eleven-only"]),
                                        *[(m, "eleven-only", ["flash-only", "plus-only"]) for m in tts.eleven.MODELS]):
            settings = {"model": model, "description": "沉稳女声", "workspace_id": "llm-test"}
            for command in ("status", "ui"):
                with self.subTest(model=model, command=command), patch.object(tts, "load_settings", return_value=settings), patch.object(tts, "deps_status", return_value={"dashscope": True, "ffmpeg": True}), patch.object(tts, "key_status", return_value={"configured": False}) as bailian_key, patch.object(tts.eleven, "key_status", return_value={"configured": True, "masked": "mock-key", "source": "env"}), patch.object(sys, "stdout", new=io.StringIO()) as out:
                    if command == "status":
                        tts.cmd_status(None)
                        self.assertEqual(out.getvalue().splitlines()[-1].startswith("onboarding: "), True)
                        if model in tts.eleven.MODELS:
                            self.assertEqual(out.getvalue().splitlines()[-1], "onboarding: 不需要")
                    else:
                        with patch.object(tts.LocalUI, "serve", autospec=True) as serve:
                            tts.cmd_ui(SimpleNamespace(page="voices", port=0, no_open=True))
                        self.addCleanup(shutil.rmtree, serve.call_args.args[0].workdir)
                    self.assertIn(expected, out.getvalue())
                    self.assertIn("默认模型:" + model, out.getvalue())
                    for value in absent:
                        self.assertNotIn(value, out.getvalue())
                    if model in tts.eleven.MODELS:
                        bailian_key.assert_not_called()


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
