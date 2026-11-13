"""实测自动判档、逐消息 effort 与缓存；日志不保存消息或回答原文。"""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2")
PROMPTS = (
    "感谢。只回复一个字。",
    "法国首都是哪里？只回复城市名，不用工具。",
    "设计一个多设备离线同步协议，只用一句话概括你的方案，不用工具。",
    "ok",
    "验证当前目录 note.txt 中的算式。必须使用 Read 读取文件，并跑通其中的测试才算完成，最后只回复一句话。",
)


class Session:
    def __init__(self, model, run, options, budget, resume=None):
        self.events = queue.Queue()
        self.errors = []
        self.commands = []
        settings = {"pluginConfigs": {"auto-effort": {"options": options}}}
        self.proc = subprocess.Popen([
            "claude", "-p", "--plugin-dir", str(ROOT), "--model", model, "--effort", "medium",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", str(budget), "--settings", json.dumps(settings),
            "--tools", "Read,Bash", "--allowedTools", "Read,Bash",
            *(["--resume", resume] if resume else []),
        ], cwd=run, env=dict(os.environ, CLAUDE_CODE_ENABLE_FUNCTION_HOOKS="1"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        threading.Thread(target=self._stdout, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()

    def _stdout(self):
        for line in self.proc.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                pass
        self.events.put(None)

    def _stderr(self):
        # 只保留是否有 stderr，不保存引擎或服务端自由文本。
        for _ in self.proc.stderr:
            self.errors.append(True)

    def send(self, text):
        self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
        self.proc.stdin.flush()

    def result(self, timeout=600):
        deadline = time.monotonic() + timeout
        requests = []
        while time.monotonic() < deadline:
            event = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            if event is None:
                raise RuntimeError("Claude Code 在返回结果前退出")
            if event.get("type") == "assistant":
                requests.append(event.get("message", {}).get("usage", {}))
            if event.get("type") == "system" and event.get("subtype") == "init":
                print(json.dumps({"kind": "init", "model": event.get("model"), "per_turn_effort_active": event.get("per_turn_effort_active")}, ensure_ascii=False), flush=True)
            if event.get("type") == "result":
                event["request_usages"] = requests
                return event
        raise RuntimeError("等待结果超时")

    def close(self):
        if not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def status_of(session):
    session.send("/auto-effort status")
    result = session.result()
    if result.get("is_error"):
        raise RuntimeError("状态命令返回错误")
    output = result.get("result", "")
    return result, json.loads(output[output.index('{'):output.rindex('}') + 1])


def resume_check(model, run, options, summary_path):
    """两个独立进程验证恢复与 Fable 继续升档；仅保存脱敏状态。"""
    sessions = []
    rows = []
    failed = []
    try:
        first = Session(model, run, options, 0.55)
        sessions.append(first)
        for _ in range(2):
            first.send("法国首都是哪里？只回复城市名，不用工具。")
            result = first.result()
            rows.append({"session_id": result.get("session_id"), "total_cost_usd": result.get("total_cost_usd"),
                         "usage": result.get("usage"), "is_error": result.get("is_error")})
            if result.get("is_error"):
                raise RuntimeError("首进程返回错误")
        _, before = status_of(first)
        rows.append({"before": before})
        session_id = rows[0]["session_id"]
        if len(before["decisions"]) != 2 or before["lastFinal"] not in ("low", "medium"):
            raise RuntimeError("首进程未产生两次可升档决策")
        first.close()
        second = Session(model, run, options, 0.55, resume=session_id)
        sessions.append(second)
        result, restored = status_of(second)
        rows.append({"resumed_session_id": result.get("session_id"), "restored": restored})
        if result.get("session_id") != session_id:
            failed.append("恢复后 session id 变化")
        for field in ("lastFinal", "lastDecision", "summary"):
            if restored.get(field) != before.get(field):
                failed.append(f"恢复后的 {field} 与首进程不一致")
        second.send("继续")
        result = second.result()
        _, after = status_of(second)
        rows.append({"after": after, "total_cost_usd": result.get("total_cost_usd"),
                     "usage": result.get("usage"), "is_error": result.get("is_error")})
        decision = after["decisions"][-1]
        if result.get("is_error") or decision.get("reason") != "Fable 继续任务升档" or decision.get("final") != "high":
            failed.append("恢复后未触发 Fable 继续升档")
        if decision.get("previousFinal") != restored.get("lastFinal"):
            failed.append("继续升档没有使用恢复出的档位")
    except (RuntimeError, queue.Empty, json.JSONDecodeError, OSError, ValueError, KeyError, IndexError):
        failed.append("恢复实测的会话、命令或断言失败")
    finally:
        for session in sessions:
            session.close()
            if session.proc.returncode:
                failed.append(f"headless 进程退出码 {session.proc.returncode}")
        summary = {"mode": "resume", "model": model, "rows": rows, "failures": failed,
                   "exit_codes": [session.proc.returncode for session in sessions]}
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"summary_path": str(summary_path), "failures": failed}, ensure_ascii=False), flush=True)
    if failed:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=MODELS)
    parser.add_argument("--bench", action="store_true", help="在 headless 会话执行 /auto-effort bench all")
    parser.add_argument("--jev", action="store_true", help="用 /auto-effort test 实测 Jev")
    parser.add_argument("--insertion", action="store_true", help="实测工具运行期间插入消息")
    parser.add_argument("--resume", action="store_true", help="使用两个进程实测 Fable 恢复与继续升档")
    parser.add_argument("--judge", default="haiku", choices=["haiku", "jev", "d1-ultra", "mammoth-27b", "decider"], help="--bench 使用的判档器")
    args = parser.parse_args()
    if args.resume and (args.model != "claude-fable-5-2" or args.bench or args.jev or args.insertion):
        parser.error("--resume 只支持 claude-fable-5-2，且不与其他实测模式组合")
    mode = "resume" if args.resume else "bench" if args.bench else "jev" if args.jev else "insertion" if args.insertion else "e2e"
    run = ROOT / "dev" / "e2e-run"
    run.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    stem = f"{stamp}-{mode}-{args.judge if args.bench else ''}{'-' if args.bench else ''}{args.model}"
    log = run / f"{stem}-requests.jsonl"
    summary_path = run / f"{stem}-summary.json"
    if args.resume:
        resume_check(args.model, run, {"debugLogPath": str(log), "judge": "haiku"}, summary_path)
        return
    (run / "note.txt").write_text("测试：使用 Bash 运行 python3 -c 'assert 2 + 2 == 4'，成功后回复测试通过。\n", encoding="utf-8")
    session = Session(args.model, run, {"debugLogPath": str(log), "judge": "jev" if args.jev else args.judge}, 0.6)
    rows = []
    failed = []
    previous_cost = 0
    try:
        if args.bench or args.jev:
            session.send("/auto-effort bench all" if args.bench else "/auto-effort test 法国首都是哪里？")
            result = session.result(timeout=1200)
            # 命令只返回脱敏后的分类或测评结果，不保存测试文本。
            rows.append({"command_output": result.get("result"), "total_cost_usd": result.get("total_cost_usd"), "is_error": result.get("is_error")})
            if result.get("is_error"):
                failed.append("命令返回错误")
            output = result.get("result", "")
            start, end = output.find('{'), output.rfind('}')
            answer = json.loads(output[start:end + 1]) if start >= 0 else {}
            if args.bench and len(answer.get("summaries", [])) != 3:
                failed.append("测评未返回三个模型的汇总")
            if args.jev and (answer.get("judge") != "jev" or not answer.get("result")):
                failed.append("Jev 实测未返回有效结果")
        elif args.insertion:
            session.send("使用 Bash 运行 sleep 3，随后只回复已完成。")
            # 等到工具调用开始再插入，避免把两个输入合并为首轮提示。
            while True:
                event = session.events.get(timeout=120)
                if event is None:
                    raise RuntimeError("会话提前退出")
                if event.get("type") == "assistant" and any(b.get("type") == "tool_use" for b in event.get("message", {}).get("content", [])):
                    session.send("设计一个多设备离线同步协议，只用一句话概括方案，不再调用工具。")
                    break
            result = session.result()
            rows.append({"total_cost_usd": result.get("total_cost_usd"), "usage": result.get("usage"), "is_error": result.get("is_error")})
            session.send("/auto-effort status")
            output = session.result().get("result", "")
            start, end = output.find('{'), output.rfind('}')
            decisions = json.loads(output[start:end + 1]).get("decisions", []) if start >= 0 else []
            rows.append({"decisions": decisions})
            requests = [json.loads(line) for line in log.read_text().splitlines() if json.loads(line).get("model") == args.model] if log.exists() else []
            inserted = next((d for d in decisions if d["index"] > 0), None)
            if not inserted or len(requests) < 2:
                failed.append("插入消息未产生非首步判档记录")
            else:
                row = {"insertion_per_message_supported": bool(requests[-1]["perMessageEffort"] and requests[-1]["perMessageEffort"][-1][1] == inserted["final"]), "requests": requests}
                rows.append(row)
                if requests[-1]["topEffort"] != inserted["final"]:
                    failed.append("插入消息的请求档位不匹配")
        else:
            for turn, prompt in enumerate(PROMPTS, 1):
                before = len(log.read_text().splitlines()) if log.exists() else 0
                session.send(prompt)
                result = session.result()
                requests = [json.loads(line) for line in log.read_text().splitlines()[before:]] if log.exists() else []
                requests = [row for row in requests if row.get("model") == args.model]
                cost = result.get("total_cost_usd", 0)
                row = {"turn": turn, "usage": result.get("usage"), "request_usages": result["request_usages"],
                       "requests": requests, "total_cost_usd": cost, "incremental_cost_usd": cost - previous_cost,
                       "is_error": result.get("is_error")}
                previous_cost = cost
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if result.get("is_error"):
                    failed.append(f"第 {turn} 轮返回错误")
                    break
                if cost > 0.5:
                    failed.append("本次运行触及预算保留线")
                    break
            session.send("/auto-effort status")
            status_result = session.result()
            status = status_result.get("result", "")
            # headless 命令输出可能包在 <local-command-stdout> 中。
            start, end = status.find('{'), status.rfind('}')
            decisions = json.loads(status[start:end + 1]).get("decisions", []) if start >= 0 else []
            if len(decisions) != 5:
                failed.append(f"预期 5 次决策，实际 {len(decisions)} 次")
            previous_read = 0
            for row, decision in zip(rows, decisions):
                row["decision"] = decision
                requests = row["requests"]
                if not requests or requests[0]["topEffort"] != decision.get("final") or (requests[0]["perMessageEffort"] and requests[0]["perMessageEffort"][-1][1] != decision.get("final")):
                    failed.append(f"第 {row['turn']} 轮逐消息 effort 不匹配")
                # 逐请求比较，避免把一轮内多个工具步的累计读缓存误作下一轮基线。
                for usage in row["request_usages"]:
                    read = usage.get("cache_read_input_tokens", 0)
                    if read < previous_read:
                        failed.append(f"第 {row['turn']} 轮缓存读取下降")
                    if row["turn"] > 1 and usage.get("cache_creation_input_tokens", 0) >= 2000:
                        failed.append(f"第 {row['turn']} 轮缓存写入超过上限")
                    previous_read = read
    except (RuntimeError, queue.Empty, json.JSONDecodeError, OSError):
        failed.append("会话、命令输出或日志读取失败")
    finally:
        session.close()
        summary = {"mode": mode, "model": args.model, "rows": rows, "failures": failed, "stderr_present": bool(session.errors), "exit_code": session.proc.returncode}
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"summary_path": str(summary_path), "failures": failed}, ensure_ascii=False), flush=True)
    if failed or session.proc.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
