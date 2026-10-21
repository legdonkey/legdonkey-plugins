"""启动器离线测试：不联网、不安装依赖、不读取真实用户配置。"""
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import run as runtime


class RuntimeTests(unittest.TestCase):
    def test_noninteractive_use_never_consumes_text_or_installs(self):
        class Input(io.StringIO):
            def read(self, *args):
                raise AssertionError("不得读取朗读文本")
            def readline(self, *args):
                raise AssertionError("不得读取朗读文本")
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"BAILIAN_TTS_VENV": root + "/env"}), patch.object(runtime, "ready", return_value=False), patch.object(runtime.sys, "stdin", Input("待朗读文字")), patch.object(runtime, "setup") as setup:
            with self.assertRaisesRegex(RuntimeError, "--setup --yes"):
                runtime.ensure_runtime()
            setup.assert_not_called()

    def test_ready_environment_does_not_install(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"BAILIAN_TTS_VENV": root + "/env"}), patch.object(runtime, "ready", return_value=True), patch.object(runtime, "setup") as setup:
            self.assertEqual(runtime.ensure_runtime(), Path(root + "/env"))
            setup.assert_not_called()

    def test_cancelled_setup_has_no_install(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"BAILIAN_TTS_VENV": root + "/env"}), patch.object(runtime, "ready", return_value=False), patch.object(runtime.sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="n"), patch.object(runtime, "setup") as setup:
            with self.assertRaisesRegex(RuntimeError, "已取消"):
                runtime.ensure_runtime()
            setup.assert_not_called()

    def test_failed_install_releases_lock_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "env"
            with patch.object(runtime, "ready", return_value=False), patch.object(runtime.venv.EnvBuilder, "create"), patch.object(runtime.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")):
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.setup(root)
            self.assertFalse(root.with_name(root.name + ".setup-lock").exists())

    def test_wrapper_uses_launcher_and_handles_spaces(self):
        import tts
        with tempfile.TemporaryDirectory(prefix="tts test ") as tmp, patch.object(tts, "SAY_WRAPPER", tmp + "/bailian-say"):
            tts.write_say_wrapper()
            text = Path(tts.SAY_WRAPPER).read_text()
            self.assertIn('/run.py" say', text)
            self.assertTrue(tts.say_wrapper_status()["current"])
            subprocess.run(["sh", "-n", tts.SAY_WRAPPER], check=True)


if __name__ == "__main__":
    unittest.main()
