#!/usr/bin/env python3
"""一次性启动器：准备专用 Python 环境后执行 TTS，不提供常驻服务。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import venv

SCRIPTS = Path(__file__).resolve().parent
MIRROR = "https://mirrors.aliyun.com/pypi/simple/"


def environment():
    return Path(os.environ.get("BAILIAN_TTS_VENV", str(Path.home() / ".bailian-tts-venv"))).expanduser().absolute()


def python_path(root):
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements():
    return dict(line.strip().split("==", 1) for line in (SCRIPTS / "requirements.txt").read_text().splitlines() if line.strip())


def ready(root):
    python = python_path(root)
    if not python.is_file():
        return False
    probe = "import dashscope,websocket,json;from importlib.metadata import version;print(json.dumps({k:version(k) for k in " + repr(list(requirements())) + "}))"
    try:
        result = subprocess.run([str(python), "-I", "-c", probe], capture_output=True, text=True, timeout=20)
        return result.returncode == 0 and json.loads(result.stdout) == requirements()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def setup(root):
    """通过锁目录避免并发运行 pip；中断遗留的锁不自动删除。"""
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = root.with_name(root.name + ".setup-lock")
    deadline = time.monotonic() + 120
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"等待其他初始化进程超时。确认没有安装任务后，可删除锁目录：{lock}")
            time.sleep(0.5)
    try:
        if ready(root):
            return
        print(f"正在准备专用环境：{root}\n依赖来源：阿里云 PyPI 镜像 {MIRROR}", file=sys.stderr, flush=True)
        if not python_path(root).is_file():
            venv.EnvBuilder(with_pip=True).create(str(root))
        subprocess.run([str(python_path(root)), "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
                        "--index-url", MIRROR, "--timeout", "30", "--retries", "1", "-r", str(SCRIPTS / "requirements.txt")],
                       stdout=sys.stderr, check=True)
        if not ready(root):
            raise RuntimeError("安装后依赖检查未通过，请检查 Python 环境并重新运行初始化")
    finally:
        lock.rmdir()


def ensure_runtime(yes=False):
    root = environment()
    plugin = SCRIPTS.parents[2]
    if root.resolve() == plugin or plugin in root.resolve().parents:
        raise RuntimeError("虚拟环境不能放在插件目录中，请使用用户目录")
    if not ready(root):
        if not yes:
            message = f"需要创建或修复专用环境 {root}，并从阿里云 PyPI 镜像安装依赖。"
            if not sys.stdin.isatty():
                raise RuntimeError(message + f"\n请确认后执行：python3 \"{SCRIPTS / 'run.py'}\" --setup --yes\n不会读取朗读正文作为确认输入。")
            print(message, file=sys.stderr)
            if input("是否继续？[y/N] ").strip().lower() not in ("y", "yes"):
                raise RuntimeError("已取消初始化，未安装依赖")
        setup(root)
    return root


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        root = environment()
        ok = ready(root)
        print(json.dumps({"ready": ok, "environment": str(root), "python": str(python_path(root))}, ensure_ascii=False))
        return 0 if ok else 1
    setup_only = bool(args and args[0] == "--setup")
    if setup_only and args not in (["--setup"], ["--setup", "--yes"]):
        raise RuntimeError("用法：run.py --setup [--yes]，或 run.py <tts 子命令>")
    root = ensure_runtime(yes=setup_only and "--yes" in args)
    if setup_only:
        print(f"依赖已就绪：{python_path(root)}")
        return 0
    if Path(sys.prefix).resolve() != root.resolve() or not sys.flags.isolated:
        os.execv(str(python_path(root)), [str(python_path(root)), "-I", str(SCRIPTS / "run.py"), *args])
    sys.path.insert(0, str(SCRIPTS))
    import tts
    tts.main()
    return 0


def cli():
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        print(f"启动失败：{e}\n请解决后重新运行初始化；无需 sudo，不要在系统 Python 中安装依赖。", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
