"""驱动一个 headless Claude Code 会话连发 5 轮，配合 effort-probe mod 验证逐轮切档是否保留缓存。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
RUN = f"{ROOT}/dev/probe-run"
os.makedirs(RUN, exist_ok=True)
model = sys.argv[1]
log_path = f"{RUN}/probe-log.jsonl"
if os.path.exists(log_path):
    os.remove(log_path)

env = dict(os.environ, CLAUDE_CODE_ENABLE_FUNCTION_HOOKS="1", AUTO_EFFORT_PROBE_LOG=log_path)
proc = subprocess.Popen(
    ["claude", "-p", "--plugin-dir", f"{ROOT}/dev/effort-probe", "--model", model, "--effort", "medium",
     "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
     "--tools", "Read", "--allowedTools", "Read"],
    cwd=RUN, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
)

events = []
def read_until_result(timeout=240):
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(ev)
        if ev.get("type") == "system" and ev.get("subtype") in ("init", "per_turn_effort_changed"):
            keep = {k: ev.get(k) for k in ("subtype", "model", "per_turn_effort_active", "effort", "plugins") if k in ev}
            print("SYSTEM", json.dumps(keep, ensure_ascii=False)[:600])
        if ev.get("type") == "assistant":
            u = ev.get("message", {}).get("usage", {})
            print("ASSISTANT usage", {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")})
        if ev.get("type") == "result":
            return ev
    return None

PROMPTS = [
    "Use the Read tool to read note.txt in the current directory, then reply with its first word only.",
    "Do not use tools. How many prime numbers are there below 60? Reply with the number only.",
    "Use the Read tool to read note.txt again, then reply with its last word only.",
    "Do not use tools. How many prime numbers are there below 70? Reply with the number only.",
    "Do not use tools. How many prime numbers are there below 80? Reply with the number only.",
]
for i, text in enumerate(PROMPTS, 1):
    msg = {"type": "user", "message": {"role": "user", "content": text}}
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    res = read_until_result()
    if res is None:
        print("NO RESULT for turn", i)
        break
    u = res.get("usage", {})
    print(f"RESULT turn {i}: {str(res.get('result'))[:40]!r} cost={res.get('total_cost_usd')} usage=", {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")})

proc.stdin.close()
try:
    proc.wait(timeout=60)
except subprocess.TimeoutExpired:
    proc.kill()
err = proc.stderr.read()
if err.strip():
    print("STDERR:", err[-1500:])
if os.path.exists(log_path):
    shutil.copy(log_path, f"{RUN}/probe-log-{model}.jsonl")
    print("PROBE LOG:")
    print(open(log_path).read())
else:
    print("NO PROBE LOG (mod not loaded?)")
