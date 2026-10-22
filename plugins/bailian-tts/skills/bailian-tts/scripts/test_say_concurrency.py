"""使用真实进程组、文件锁与模拟播放器验证单路播放；不访问模型接口。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import tts


class SayIdentityTests(unittest.TestCase):
    def test_new_and_legacy_entries_are_recognized(self):
        scripts = str(Path(tts.__file__).parent)
        self.assertTrue(tts.is_say_command(f'python3 -I "{scripts}/run.py" say --clipboard'))
        self.assertTrue(tts.is_say_command(f'python3 "{scripts}/tts.py" say --text hello'))
        self.assertTrue(tts.is_say_command('python3 -I /tmp/user name/skills/bailian-tts/scripts/run.py say'))
        for command in ('python3 /other/run.py say', 'python3 -c "tts.py say"', f'python3 "{scripts}/run.py" ui', 'bash -c "tts.py say"'):
            self.assertFalse(tts.is_say_command(command), command)

    def test_unrelated_process_and_nonleader_are_not_killed(self):
        with tempfile.TemporaryDirectory() as root, patch.object(tts, "SAY_DIR", root), patch.object(tts, "SAY_PID", root + "/reader.pid"), patch.object(tts.os, "killpg") as kill:
            Path(tts.SAY_PID).write_text("999999")
            for cmd, group in [('python3 /other/run.py say', 999999), (f'python3 "{Path(tts.__file__).parent}/run.py" say', 123)]:
                with patch.object(tts.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=cmd)), patch.object(tts.os, "getpgid", return_value=group):
                    tts.stop_previous_say()
            kill.assert_not_called()


@unittest.skipUnless(os.name == "posix", "进程组与 macOS 朗读锁需要 POSIX")
class SayProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tts concurrency ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.children = []
        self.addCleanup(self.stop_children)
        self.runner = self.root / "skills/bailian-tts/scripts/run.py"
        self.runner.parent.mkdir(parents=True)
        self.runner.write_text('''import sys,os,time,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[4])
import tts
root=Path(sys.argv[3]); name=sys.argv[2]; delay=float(sys.argv[5])
tts.SAY_DIR=str(root/'say'); tts.SAY_PID=str(root/'say/reader.pid')
def event(value):
    with open(root/'events','a') as f:f.write(json.dumps([name,value])+"\\n")
def synth(*args):
    event('synth');time.sleep(delay);return b'fake'
tts.synth=synth
tts.normalize=lambda raw,path:Path(path).write_bytes(raw)
original=tts.subprocess.run
def run(args,**kw):
    if args[0]=='afplay':return original([sys.executable,str(root/'player.py'),name,str(root)],**kw)
    return original(args,**kw)
tts.subprocess.run=run
# 同时覆盖 --save/热键提前停止，以及 --clipboard 在启动时再次交接播放锁。
if name.startswith('hotkey'):tts.stop_previous_say()
a=SimpleNamespace(synth_settings={'model':tts.MODEL},rate=1,pitch=1,volume=50)
tts.speak_segments(['测试'], 'fake', None, a)
''')
        (self.root / "player.py").write_text('''import sys,time,json,fcntl
from pathlib import Path
name=sys.argv[1];root=Path(sys.argv[2])
with open(root/'active.lock','a') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);state='play'
    except BlockingIOError:state='overlap'
    with open(root/'events','a') as f:f.write(json.dumps([name,state])+"\\n")
    if state=='overlap':raise SystemExit(2)
    time.sleep(0.1 if name=='short' else 30)
''')

    def stop_children(self):
        for p in self.children:
            try:os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:pass
        for p in self.children:
            p.wait(timeout=5)

    def start(self, name, delay=0):
        p = subprocess.Popen([sys.executable, str(self.runner), "say", name, str(self.root), str(Path(tts.__file__).parent), str(delay)],
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(p)
        return p

    def events(self):
        p = self.root / "events"
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def wait_event(self, name, state):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if [name, state] in self.events():return
            time.sleep(0.02)
        self.fail(f"等待事件超时：{name} {state}，已发生：{self.events()}")

    def test_hotkey_interrupts_mouse_playback(self):
        first = self.start("mouse")
        self.wait_event("mouse", "play")
        second = self.start("hotkey")
        self.wait_event("hotkey", "play")
        first.wait(timeout=5)
        self.assertIsNone(second.poll())
        self.assertFalse(any(state == "overlap" for _, state in self.events()))

    def test_pending_synthesis_is_cancelled(self):
        first = self.start("mouse", delay=10)
        self.wait_event("mouse", "synth")
        self.start("hotkey")
        self.wait_event("hotkey", "play")
        first.wait(timeout=5)
        self.assertNotIn(["mouse", "play"], self.events())

    def test_finished_reader_releases_lock_and_pid(self):
        first = self.start("short")
        self.wait_event("short", "play")
        self.assertEqual(first.wait(timeout=5), 0)
        self.assertFalse((self.root / "say/reader.pid").exists())
        self.start("mouse-next")
        self.wait_event("mouse-next", "play")
        self.assertFalse(any(state == "overlap" for _, state in self.events()))

    def test_simultaneous_triggers_leave_only_one_reader(self):
        for i in range(4):self.start(f"mouse-{i}")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if sum(p.poll() is None for p in self.children) == 1 and any(s == "play" for _, s in self.events()):break
            time.sleep(0.02)
        self.assertEqual(sum(p.poll() is None for p in self.children), 1)
        self.assertFalse(any(state == "overlap" for _, state in self.events()))


if __name__ == "__main__":
    unittest.main()
