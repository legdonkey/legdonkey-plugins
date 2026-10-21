#!/usr/bin/env python3
"""隔离安装验收：真实创建虚拟环境并下载依赖；不使用 Key 或提交合成。"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit, parse_qs


def verify(root, use_codex, use_claude=False):
    home = root / "new user"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in (
        "DASHSCOPE_API_KEY", "ELEVENLABS_API_KEY", "SFM_WORKSPACE_ID", "BAILIAN_TTS_VENV", "VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR")}
    env.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / ".codex"),
               CLAUDE_CONFIG_DIR=str(home / ".claude"), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    source = root / "market"
    plugin = source / "plugins" / "bailian-tts"
    shutil.copytree(Path(__file__).resolve().parents[3], plugin,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if use_codex:
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("没有找到 codex CLI")
        (home / ".codex").mkdir()
        manifest = source / ".agents/plugins/marketplace.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "tts-runtime-smoke", "plugins": [{"name": "bailian-tts", "source": {"source": "local", "path": "./plugins/bailian-tts"}, "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}}]}))
        subprocess.run([codex, "plugin", "marketplace", "add", str(source), "--json"], env=env, check=True)
        installed = json.loads(subprocess.check_output([codex, "plugin", "add", "bailian-tts@tts-runtime-smoke", "--json"], env=env, text=True))
        plugin = Path(installed["installedPath"])
        assert str(plugin).startswith(str(home.resolve())), "插件必须安装在临时用户目录"
    elif use_claude:
        claude = shutil.which("claude")
        if not claude:
            raise RuntimeError("没有找到 claude CLI")
        manifest = source / ".claude-plugin/marketplace.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "tts-runtime-smoke", "owner": {"name": "本地验收"}, "plugins": [{"name": "bailian-tts", "source": "./plugins/bailian-tts"}]}))
        subprocess.run([claude, "plugin", "marketplace", "add", str(source), "--json"], env=env, check=True)
        subprocess.run([claude, "plugin", "install", "bailian-tts@tts-runtime-smoke", "--json"], env=env, check=True)
        matches = list((home / ".claude/plugins/cache/tts-runtime-smoke/bailian-tts").glob("*/skills/bailian-tts/scripts/run.py"))
        assert len(matches) == 1, "必须使用临时用户的 Claude 插件安装副本"
        plugin = matches[0].parents[3]
    else:
        cache = home / ".claude/plugins/cache/test/bailian-tts/2.8.0"
        shutil.copytree(plugin, cache)
        plugin = cache
    run = plugin / "skills/bailian-tts/scripts/run.py"
    def command(*args, check=True):
        return subprocess.run([sys.executable, "-I", str(run), *args], env=env, stdin=subprocess.DEVNULL,
                              text=True, capture_output=True, check=check)
    initial = command("status", check=False)
    assert initial.returncode != 0 and "--setup --yes" in initial.stderr
    assert not (home / ".bailian-tts-venv").exists(), "未确认时不能创建环境"
    print("通过：全新用户未确认初始化时不安装、不读取标准输入", flush=True)
    result = command("--setup", "--yes", check=False)
    if result.returncode:
        raise RuntimeError(result.stderr)
    state = json.loads(command("--check").stdout)
    assert state["ready"] and Path(state["environment"]) == home / ".bailian-tts-venv"
    print("通过：真实创建专用虚拟环境并从镜像安装依赖", flush=True)
    packages = Path(state["environment"])
    before = (packages / "pyvenv.cfg").stat().st_mtime_ns
    status = command("status")
    assert "onboarding: 需要" in status.stdout and "API key 未配置" in status.stdout
    direct = subprocess.run([sys.executable, "-I", str(run.with_name("tts.py")), "status"], env=env,
                            capture_output=True, text=True)
    # -I 的直接入口在子进程中也必须能够找到相邻模块。
    if direct.returncode:
        raise RuntimeError("直接启动 tts.py 失败：" + direct.stderr)
    command("--setup", "--yes")
    assert before == (packages / "pyvenv.cfg").stat().st_mtime_ns
    print("通过：普通 Python 启动会转交专用环境，重复初始化复用环境", flush=True)
    if sys.platform == "darwin":
        command("say", "--install")
        wrapper = home / ".local/bin/bailian-say"
        subprocess.run([str(wrapper), "--install"], env=env, capture_output=True, check=True)
        moved = plugin.with_name("2.8.1")
        shutil.move(str(plugin), moved)
        subprocess.run([str(wrapper), "--install"], env=env, capture_output=True, check=True)
        run = moved / "skills/bailian-tts/scripts/run.py"
        print("通过：中键入口、含空格路径和插件升级后的缓存回退", flush=True)
    log = root / "ui.log"
    with log.open("w") as out:
        process = subprocess.Popen([sys.executable, "-I", str(run), "ui", "--no-open"], env=env,
                                   stdout=out, stderr=out, stdin=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        url = None
        while time.monotonic() < deadline:
            match = re.search(r"http://127\.0\.0\.1:\d+/\?t=[\w-]+", log.read_text())
            if match:
                url = match.group(0)
                break
            if process.poll() is not None:
                raise RuntimeError(log.read_text())
            time.sleep(0.1)
        if not url:
            raise RuntimeError("工作台启动超时")
        parsed = urlsplit(url)
        token = parse_qs(parsed.query)["t"][0]
        base = f"http://{parsed.netloc}"
        with urllib.request.urlopen(f"{base}/state?t={token}", timeout=10) as response:
            state = json.load(response)
        assert state["deps"]["dashscope"] and not state["key"]["configured"] and not state["eleven_key"]["configured"]
        urllib.request.urlopen(urllib.request.Request(f"{base}/done?t={token}", data=b"{}"), timeout=10).close()
        process.wait(timeout=10)
        assert process.returncode == 0
        print("通过：首次用户工作台可打开，Key 未配置，关闭后服务退出", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--codex", action="store_true", help="通过真实 Codex 市场命令安装到隔离 CODEX_HOME")
    group.add_argument("--claude", action="store_true", help="通过真实 Claude Code 市场命令安装到隔离 CLAUDE_CONFIG_DIR")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tts-install-smoke-") as tmp:
        verify(Path(tmp), args.codex, args.claude)
