#!/usr/bin/env python3
"""跨平台上下文审计：用官方 CLI 治理入口盘点 Claude Code 与 Codex 的插件 / MCP / 市场源，
技能因两平台都没有 CLI（官方设计为文件式）而走目录治理入口，并可对照当前会话可见态。

设计原则：CLI 优先。插件 / 市场 / MCP 一律调 `claude` / `codex` 的官方命令再解析输出；
只有「技能」没有任何 CLI 列举命令，按官方文档的唯一治理方式——列技能目录——来盘点。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

JsonDict = dict[str, Any]

# CLI 调用默认超时（秒）。`claude mcp list` 会做联网健康检查，给得宽一些。
DEFAULT_TIMEOUT = 30
MCP_LIST_TIMEOUT = 60
# 逐插件 details / 逐 MCP get 会做健康检查、偏慢，给宽超时并并发跑（见 parallel_map）。
DETAIL_TIMEOUT = 60
# `mcp get` 仅为补「类型」列（nice-to-have），健康检查可能很慢，单独给较短上限，慢就放弃该列。
MCP_GET_TIMEOUT = 20
MAX_WORKERS = 8
# 插件 always-on token 超过此阈值，提示「开销偏大」。
TOKEN_HEAVY_THRESHOLD = 1000

# 当前 inventory 的 schema 版本：2 = 层级化（市场→插件→组件）+ 排行 + 翻译键。
SCHEMA_VERSION = 2


# --------------------------------------------------------------------------- #
# 翻译缓存：脚本不调 LLM，只「登记」待译英文文本（key=源文本 sha256），
# 由技能里的 Claude 填中文写回，渲染时查表。缓存放用户级目录，不进 git。
# --------------------------------------------------------------------------- #
def translation_cache_path() -> Path:
    return Path.home() / ".cache" / "context-doctor" / "translations.json"


def load_translation_cache(path: Path | None = None) -> JsonDict:
    path = path or translation_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 1)
    entries = data.get("entries")
    if not isinstance(entries, dict):
        data["entries"] = {}
    return data


def save_translation_cache(cache: JsonDict, path: Path | None = None) -> None:
    path = path or translation_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass  # 缓存写失败不致命：渲染会回退英文


def sha256_key(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def register_translatable(cache: JsonDict, text: str, kind: str) -> str:
    """登记一段待译英文文本，返回其 key（空文本返回 ""）。已存在则保留原译文。"""
    text = (text or "").strip()
    if not text:
        return ""
    key = sha256_key(text)
    entries = cache["entries"]
    if key not in entries:
        entries[key] = {"src": text, "zh": "", "kind": kind}
    return key


def collect_referenced_keys(node: Any) -> set[str]:
    """收集 inventory 里所有 `*description_key` 引用到的 key（用于只统计当前报告实际待译的条目）。"""
    keys: set[str] = set()

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                if k.endswith("description_key") and isinstance(v, str) and v:
                    keys.add(v)
                walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)

    walk(node)
    return keys


def pending_translation_count(cache: JsonDict, referenced: set[str] | None = None) -> int:
    """统计待译条目数。给了 referenced（当前 inventory 引用到的 key 集）时只统计这些，
    避免旧插件遗留的孤儿空条目让「待译 N」虚高。"""
    entries = cache["entries"]
    keys = referenced if referenced is not None else entries.keys()
    return sum(1 for k in keys if isinstance(entries.get(k), dict) and not entries[k].get("zh"))


def _register_component_descriptions(cache: JsonDict, components: JsonDict) -> None:
    """给带 description 的组件（如 Codex 清单读出的技能）登记翻译并写 description_key。

    Claude 的组件无逐项描述，此函数对其为 no-op。原地修改 components。
    """
    for items in components.values():
        if not isinstance(items, list):
            continue
        for comp in items:
            if isinstance(comp, dict) and comp.get("description"):
                comp["description_key"] = register_translatable(cache, comp["description"], "component_desc")


def resolve_translations(inventory: JsonDict, cache: JsonDict) -> JsonDict:
    """深拷贝 inventory，并在每个 `*_description_key` 旁补 `<前缀>_description_zh`（中文或回退英文）。"""
    entries = cache.get("entries") or {}

    def resolved(key: str) -> tuple[str, bool]:
        """返回 (展示文本, 是否回退英文)。zh 为空时回退 src 并标 pending。"""
        e = entries.get(key)
        if isinstance(e, dict):
            zh = str(e.get("zh") or "")
            if zh:
                return zh, False
            return str(e.get("src") or ""), True
        return "", False

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out: JsonDict = {}
            for k, v in node.items():
                out[k] = walk(v)
                if k.endswith("description_key") and isinstance(v, str) and v:
                    text, pending = resolved(v)
                    prefix = k[: -len("_key")]
                    out[prefix + "_zh"] = text
                    out[prefix + "_pending"] = pending
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(inventory)


# --------------------------------------------------------------------------- #
# 通用 helper
# --------------------------------------------------------------------------- #
def run_cli(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[str | None, bool]:
    """运行一个 CLI 命令，返回 (stdout, ok)。任何失败都降级为 (None, False)，绝不抛。"""
    exe = shutil.which(args[0])
    if not exe:
        return None, False
    try:
        proc = subprocess.run(
            [exe, *args[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, False
    if proc.returncode != 0:
        # 即便非零，有些命令仍把可用内容打到 stdout；交给调用方判断。
        return proc.stdout or None, False
    return proc.stdout, True


def run_cli_json(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> Any:
    out, ok = run_cli(args, timeout=timeout)
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def run_cli_retry(args: list[str], timeout: int = DEFAULT_TIMEOUT, tries: int = 2) -> tuple[str | None, bool]:
    """重试版 run_cli：并发跑 details 时偶发超时/失败会丢数据，失败再试一次。

    重试在前一批占满的 worker 释放后才跑，负载更轻、通常能恢复，代价仅是那一项多花一次。
    """
    out: str | None = None
    ok = False
    for _ in range(max(1, tries)):
        out, ok = run_cli(args, timeout=timeout)
        if ok and out:
            return out, ok
    return out, ok


def cli_available(name: str) -> bool:
    return shutil.which(name) is not None


def _as_int(value: Any) -> int | None:
    """把可能是 int / 数字字符串 / 其它的值规范化为 int 或 None（防御 CLI 返回意外类型）。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def plugin_lists(data: Any) -> tuple[list[JsonDict], list[JsonDict]]:
    """从 `plugin list --json` 结果安全取出 (installed, available)。

    CLI 偶发返回非 dict（list/字符串/None）会让 `.get()` 抛 AttributeError——这里统一降级为空列表。
    """
    data = data if isinstance(data, dict) else {}
    inst = data.get("installed")
    avail = data.get("available")
    return (
        inst if isinstance(inst, list) else [],
        avail if isinstance(avail, list) else [],
    )


def parallel_map(func: Callable[[Any], Any], items: list[Any], workers: int = MAX_WORKERS) -> list[Any]:
    """并发对 items 跑 func，按输入顺序返回结果。底层是 subprocess（释放 GIL），线程即可提速。

    单项异常降级为 None，绝不让一项失败拖垮整批。空列表直接返回。
    """
    if not items:
        return []

    def safe(x: Any) -> Any:
        try:
            return func(x)
        except Exception:  # noqa: BLE001 — 采集层一律降级，绝不抛
            return None

    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(safe, items))


def parse_skill_header(path: Path) -> JsonDict:
    """解析 SKILL.md 顶部 frontmatter（name / description）。从原实现迁移复用。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"name": path.parent.name, "description": ""}
    if not text.startswith("---"):
        return {"name": path.parent.name, "description": ""}
    end = text.find("\n---", 3)
    if end == -1:
        return {"name": path.parent.name, "description": ""}
    header = text[3:end]
    lines = header.splitlines()
    data: JsonDict = {}
    block_indicators = {">", "|", ">-", "|-", ">+", "|+"}
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in block_indicators:
            # YAML 块标量（description: > / |）：把后续更深缩进的行收成正文，
            # 否则旧逻辑会把 ">" 本身当描述。> 折叠成空格，| 保留换行。
            key_indent = len(raw) - len(raw.lstrip())
            block: list[str] = []
            while i < len(lines):
                bl = lines[i]
                if bl.strip() and (len(bl) - len(bl.lstrip())) <= key_indent:
                    break
                block.append(bl.strip())
                i += 1
            joiner = "\n" if value.startswith("|") else " "
            value = joiner.join(block).strip()
        else:
            value = value.strip("\"'")
        data[key] = value
    data.setdefault("name", path.parent.name)
    data.setdefault("description", "")
    return data


def collect_skills_from_dirs(roots: list[tuple[Path, str]]) -> list[JsonDict]:
    """从给定的技能根目录列表收集独立技能。roots: [(目录, 归类标签)]。"""
    skills: list[JsonDict] = []
    seen: set[str] = set()
    for root, scope in roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            skill_file = child / "SKILL.md"
            if not skill_file.exists():
                continue
            resolved = str(skill_file.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            header = parse_skill_header(skill_file)
            name = str(header.get("name") or child.name)
            skills.append(
                {
                    "name": name,
                    "scope": scope,
                    "source": "filesystem",  # 技能无 CLI，目录即官方治理入口
                    "description": str(header.get("description") or ""),
                    "path": str(skill_file),
                }
            )
    return sorted(skills, key=lambda s: (s["scope"], s["name"]))


def repo_root_from(cwd: Path) -> Path:
    """从 cwd 向上找含 .git 的目录（子目录启动也能命中），找不到退回 cwd。"""
    return next((d for d in [cwd, *cwd.parents] if (d / ".git").exists()), cwd)


def project_skill_dirs(cwd: Path, rel: Path) -> list[Path]:
    """当前目录到 repo 根，沿途所有 <rel> 目录（rel 如 .claude/skills、.codex/skills、.agents/skills）。

    与官方一致：plain 技能从启动目录向上遍历到仓库根（不同于 `@skills-dir` 插件——后者只在启动目录）。
    """
    root = repo_root_from(cwd)
    dirs: list[Path] = []
    here = cwd
    while True:
        candidate = here / rel
        if candidate.exists():
            dirs.append(candidate)
        if here == root or here == here.parent:
            break
        here = here.parent
    return dirs


# --------------------------------------------------------------------------- #
# Claude Code 采集器（CLI 优先）
# --------------------------------------------------------------------------- #
def parse_claude_mcp_list(text: str) -> list[JsonDict]:
    """解析 `claude mcp list` 的纯文本（无 --json）：`name: target - status` 行。"""
    servers: list[JsonDict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.endswith("…") or line.startswith("Checking"):
            continue
        if ": " not in line:
            continue
        name, rest = line.split(": ", 1)
        status = ""
        target = rest
        # 末尾 " - <状态>"：取最后一个 " - " 之后的全部作状态，覆盖任意状态文字
        # （✔ Connected / ⏸ Pending approval / ✗ Rejected / ! Needs authentication / Failed…）。
        # 不用符号白名单——那会漏掉 needs-auth / failed 这类用户最该看到的状态；MCP 表不
        # 展示 target，故即便 target 罕见地含 " - " 被误切也无副作用。
        if " - " in rest:
            target, status = (part.strip() for part in rest.rsplit(" - ", 1))
        servers.append(
            {
                "name": name.strip(),
                "target": target,
                "status": status,
                "source": "cli",
            }
        )
    return servers


def parse_claude_mcp_get(text: str) -> JsonDict:
    """解析 `claude mcp get <name>`：只取 Type 与 Scope。

    `claude mcp list` 文本不含传输类型，但 `mcp get` 有（Type: stdio / http / sse…）。
    安全约束：该命令会连带打印 Environment 里的密钥（AccessKey 等），这里只读 Type/Scope
    两行，绝不解析 Command / Args / Environment，避免把任何机密带进审计产物。
    """
    server_type = ""
    scope = ""
    for raw in text.splitlines():
        line = raw.strip()
        # 命中 Environment 段即停，后续都是敏感的 KEY=VALUE，绝不读取
        if line.startswith("Environment"):
            break
        m = re.match(r"Type:\s*(.+)$", line)
        if m:
            server_type = m.group(1).strip()
            continue
        m = re.match(r"Scope:\s*(.+)$", line)
        if m:
            scope = m.group(1).strip()
    return {"server_type": server_type, "scope": scope}


def _parse_tok(num: str, unit: str) -> int:
    value = float(num)
    if unit.lower() == "k":
        value *= 1000
    return int(value)


_DETAIL_CATEGORIES = ("Skills", "Agents", "Hooks", "MCP servers", "LSP servers")
_DETAIL_SECTIONS = ("Component inventory", "Projected token cost", "Per-component", "Source:")
_COST_NOTE = {"hooks": "harness-only", "mcp": "not-metered", "lsp": "out-of-process"}


def parse_claude_details(text: str) -> JsonDict:
    """解析 `claude plugin details <name>` 纯文本（无 --json）。

    返回完整组件清单 + 逐组件 token 成本 + 插件描述：
      {description, always_on_tokens, components:{skills,agents,hooks,mcp,lsp}}
    其中 skills/agents 项带 always_on/on_invoke（从 Per-component 表查），
    hooks/mcp/lsp 无模型成本，只记 name + cost_note。容错：缺字段填 None，绝不抛。
    安全：遇敏感段一律不读（本命令无 Environment，但与 mcp_get 同纪律）。
    """
    lines = text.splitlines()

    # ① 标题行后第一条缩进描述（排除 Source: 行）。
    description = ""
    title_seen = False
    for raw in lines:
        if not raw.strip():
            continue
        if not title_seen:
            title_seen = True  # 第一行是 "name version"
            continue
        s = raw.strip()
        if s.startswith("Source:") or s.startswith("Component inventory"):
            break
        description = s
        break

    # ② Component inventory：各类组件名（支持换行续行）。
    cat_names: dict[str, list[str]] = {c: [] for c in _DETAIL_CATEGORIES}
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = re.match(r"(Skills|Agents|Hooks|MCP servers|LSP servers)\s*\((\d+)\)\s*(.*)$", s)
        if m:
            label, rest = m.group(1), m.group(3)
            buf = [rest]
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if re.match(r"(Skills|Agents|Hooks|MCP servers|LSP servers)\s*\(\d+\)", nxt):
                    break
                if any(nxt.startswith(sec) for sec in _DETAIL_SECTIONS):
                    break
                buf.append(nxt)
                j += 1
            joined = " ".join(b for b in buf if b)
            # 去掉尾部括号注释（如 "(harness-only — no model context cost)"）。
            joined = re.split(r"\s{2,}\(", joined)[0]
            names = [n.strip() for n in joined.split(",") if n.strip()]
            cat_names[label] = names
            i = j
            continue
        i += 1

    # ③ Per-component 表：name -> (always_on, on_invoke)。
    per: dict[str, tuple[int | None, int | None]] = {}
    in_table = False
    for raw in lines:
        s = raw.strip()
        if s.startswith("Per-component"):
            in_table = True
            continue
        if not in_table:
            continue
        if not s or s.startswith("component") or s.startswith("On-invoke") or s.startswith("Token counts"):
            continue
        m = re.match(r"(.+?)\s+~?([\d.]+)\s*([kK]?)\s+~?([\d.]+)\s*([kK]?)\s*$", s)
        if m:
            per[m.group(1).strip()] = (
                _parse_tok(m.group(2), m.group(3)),
                _parse_tok(m.group(4), m.group(5)),
            )

    # ④ Always-on 总额。
    always_on: int | None = None
    for raw in lines:
        m = re.match(r"Always-on:\s*~?([\d.]+)\s*([kK]?)\s*tok", raw.strip())
        if m:
            always_on = _parse_tok(m.group(1), m.group(2))
            break

    def costed(names: list[str]) -> list[JsonDict]:
        out = []
        for n in names:
            a, o = per.get(n, (None, None))
            out.append({"name": n, "always_on_tokens": a, "on_invoke_tokens": o})
        return out

    def noted(names: list[str], note: str) -> list[JsonDict]:
        return [{"name": n, "cost_note": note} for n in names]

    components = {
        "skills": costed(cat_names["Skills"]),
        "agents": costed(cat_names["Agents"]),
        "hooks": noted(cat_names["Hooks"], _COST_NOTE["hooks"]),
        "mcp": noted(cat_names["MCP servers"], _COST_NOTE["mcp"]),
        "lsp": noted(cat_names["LSP servers"], _COST_NOTE["lsp"]),
    }
    return {
        "description": description,
        "always_on_tokens": always_on,
        "components": components,
        "bundled_skills": cat_names["Skills"],  # 向后兼容旧字段
    }


def read_codex_plugin_manifest(item: JsonDict) -> JsonDict:
    """从 Codex 插件本地目录手搓 details 等价物（Codex 无 plugin details 命令）。

    顺 `source.path` 读 `<path>/.codex-plugin/plugin.json`（真 version、description）
    + 扫 `<path>/skills/*/` 得技能名（拼 <plugin>:<skill>）。全无 token 成本。
    路径/清单缺失或解析失败 → 降级返回空组件 + note，绝不抛。
    """
    name = str(item.get("name") or "")
    result: JsonDict = {
        "description": "",
        "real_version": "",
        "components": {"skills": [], "hooks": [], "apps": []},
        "components_source": "manifest",
        "note": "",
    }
    src = item.get("source") if isinstance(item.get("source"), dict) else {}
    path_str = str(src.get("path") or "")
    if not path_str:
        result["note"] = "无 source.path，未能读取插件清单。"
        return result
    base = Path(path_str)
    manifest = base / ".codex-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict):
        result["description"] = str(data.get("description") or "")
        result["real_version"] = str(data.get("version") or "")
        for key in ("hooks", "apps"):
            decl = data.get(key)
            if isinstance(decl, list):
                result["components"][key] = [
                    {"name": str(x.get("name") if isinstance(x, dict) else x), "cost_note": "not-metered"}
                    for x in decl
                ]
    else:
        result["note"] = "未找到或无法解析 .codex-plugin/plugin.json。"
    skills_dir = base / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if (child / "SKILL.md").exists():
                header = parse_skill_header(child / "SKILL.md")
                result["components"]["skills"].append(
                    {
                        "name": f"{name}:{child.name}" if name else child.name,
                        "description": str(header.get("description") or ""),
                        "always_on_tokens": None,
                        "on_invoke_tokens": None,
                    }
                )
    return result


def read_plugin_component_descs(install_path: str) -> dict[str, str]:
    """从插件本地目录读各组件描述：`claude plugin details` 只给组件名，描述写在
    `<installPath>/skills/<name>/SKILL.md` 与 `<installPath>/agents/<name>.md` 的 frontmatter 里。

    返回 名字 -> 描述 的映射（同时按 frontmatter name 与目录/文件名建键，便于匹配）。绝不抛。
    """
    out: dict[str, str] = {}
    if not install_path:
        return out
    base = Path(install_path)
    sdir = base / "skills"
    if sdir.is_dir():
        for child in sorted(sdir.iterdir()):
            f = child / "SKILL.md"
            if f.exists():
                header = parse_skill_header(f)
                desc = str(header.get("description") or "")
                if desc:
                    out.setdefault(str(header.get("name") or child.name), desc)
                    out.setdefault(child.name, desc)
    adir = base / "agents"
    if adir.is_dir():
        for f in sorted(adir.glob("*.md")):
            header = parse_skill_header(f)
            desc = str(header.get("description") or "")
            if desc:
                out.setdefault(str(header.get("name") or f.stem), desc)
                out.setdefault(f.stem, desc)
    return out


def collect_claude(home: Path, cwd: Path, cache: JsonDict) -> JsonDict:
    section: JsonDict = {
        "platform": "claude",
        "label": "Claude Code",
        "cli_present": cli_available("claude"),
        "supports_token_cost": True,  # Claude 有 plugin details，能算 token
        "plugins": [],
        "available_plugins": [],
        "marketplaces": [],
        "mcp_servers": [],
        "skills": [],
        "notes": [],
    }
    if not section["cli_present"]:
        section["notes"].append("未检测到 `claude` CLI，跳过 Claude Code 的 CLI 审计。")

    # 插件（已装 + 可装）
    if section["cli_present"]:
        installed, available = plugin_lists(
            run_cli_json(["claude", "plugin", "list", "--json", "--available"])
        )
        entries: list[JsonDict] = []
        for item in installed:
            if not isinstance(item, dict):
                continue
            plugin_id = str(item.get("id") or "")
            name, _, marketplace = plugin_id.partition("@")
            entries.append({
                "id": plugin_id,
                "name": name or plugin_id,
                "marketplace": marketplace,
                "installed": True,
                "version": str(item.get("version") or ""),
                "scope": item.get("scope"),
                "enabled": item.get("enabled"),
                "source": "cli",
                "source_ref": {"installPath": str(item.get("installPath") or "")},
                "last_updated": str(item.get("lastUpdated") or ""),
                "bundled_skills": [],
                "always_on_tokens": None,
                "components": {"skills": [], "agents": [], "hooks": [], "mcp": [], "lsp": []},
                "description": "",
                "description_key": "",
            })
        # 逐已装插件取 details（完整组件 + token 成本 + 描述）。并发跑——details 会做健康检查、
        # 串行 11 个易超时丢数据；并发后墙钟≈单次最慢。只对已装调，控制开销。
        details = parallel_map(
            lambda e: run_cli_retry(["claude", "plugin", "details", e["id"]], timeout=DETAIL_TIMEOUT),
            entries,
        )
        for entry, res in zip(entries, details):
            out, ok = res if res else (None, False)
            if ok and out:
                parsed = parse_claude_details(out)
                entry["bundled_skills"] = parsed["bundled_skills"]
                entry["always_on_tokens"] = parsed["always_on_tokens"]
                entry["components"] = parsed["components"]
                entry["description"] = parsed["description"]
                entry["description_key"] = register_translatable(cache, parsed["description"], "plugin_desc")
                # details 只给组件名，去插件目录读每个 skill/agent 的描述补上（中文经缓存翻译）
                descs = read_plugin_component_descs(entry["source_ref"].get("installPath", ""))
                for grp in ("skills", "agents"):
                    for comp in entry["components"].get(grp, []):
                        d = descs.get(comp.get("name", ""))
                        if d:
                            comp["description"] = d
                _register_component_descriptions(cache, entry["components"])
            section["plugins"].append(entry)
        for item in available:
            if not isinstance(item, dict):
                continue
            # available 对象的键与 installed 不同：pluginId / marketplaceName / version
            # （旧实现误用 id / marketplace，导致市场列全空、id 丢 @market 后缀）。保留旧键回退。
            plugin_id = str(item.get("pluginId") or item.get("id") or "")
            description = str(item.get("description") or "")
            src = item.get("source") if isinstance(item.get("source"), dict) else {}
            section["available_plugins"].append(
                {
                    "id": plugin_id,
                    "name": str(item.get("name") or plugin_id),
                    "marketplace": str(item.get("marketplaceName") or item.get("marketplace") or ""),
                    "installed": False,
                    "version": str(item.get("version") or ""),
                    "install_count": _as_int(item.get("installCount")),
                    "description": description,
                    "description_key": register_translatable(cache, description, "plugin_desc"),
                    "source_ref": {
                        "url": str(src.get("url") or ""),
                        "path": str(src.get("path") or ""),
                        "ref": str(src.get("ref") or ""),
                        "sha": str(src.get("sha") or ""),
                    },
                    "source": "cli",
                }
            )

        # 市场源
        mkts = run_cli_json(["claude", "plugin", "marketplace", "list", "--json"]) or []
        for item in mkts:
            if not isinstance(item, dict):
                continue
            section["marketplaces"].append(
                {
                    "name": str(item.get("name") or ""),
                    "source_type": str(item.get("source") or ""),
                    # GitHub 源用 repo，git/URL 源用 url，本地源用 path
                    "repo": str(
                        item.get("repo")
                        or item.get("url")
                        or item.get("path")
                        or item.get("installLocation")
                        or ""
                    ),
                    # GitHub/git 源 pin 了分支或 tag 时才有
                    "ref": str(item.get("ref") or ""),
                    "source": "cli",
                }
            )

        # MCP（无 --json，解析文本）
        out, _ = run_cli(["claude", "mcp", "list"], timeout=MCP_LIST_TIMEOUT)
        if out:
            section["mcp_servers"] = parse_claude_mcp_list(out)
            # `mcp list` 不含传输类型，逐个 `mcp get` 补 Type/Scope（与逐插件 details 同思路）。
            # 解析器只取 Type/Scope，不读 Environment，避免泄露密钥。并发跑（get 也做健康检查、偏慢）。
            named = [s for s in section["mcp_servers"] if s.get("name")]
            gets = parallel_map(
                lambda s: run_cli(["claude", "mcp", "get", s["name"]], timeout=MCP_GET_TIMEOUT),
                named,
            )
            for server, res in zip(named, gets):
                detail, ok = res if res else (None, False)
                if ok and detail:
                    parsed = parse_claude_mcp_get(detail)
                    server["server_type"] = parsed["server_type"]
                    server["scope"] = parsed["scope"]

    # 技能：个人级 + 项目级（目录治理入口）
    roots = [(home / ".claude" / "skills", "personal")]
    roots.extend((d, "project") for d in project_skill_dirs(cwd, Path(".claude") / "skills"))
    section["skills"] = collect_skills_from_dirs(roots)
    section["notes"].append(
        "技能来自目录扫描：Claude Code 没有列举技能的 CLI，目录即官方治理入口。"
        "插件自带技能与 token 成本来自 `claude plugin details`。"
    )
    section["notes"].append(
        "仅覆盖个人级（~/.claude/skills）与项目级（启动目录到仓库根的 .claude/skills）；"
        "企业 / managed 级技能与子目录按需加载的 nested 技能未覆盖（已知缩减项）。"
    )
    return section


# --------------------------------------------------------------------------- #
# Codex 采集器（CLI 优先）
# --------------------------------------------------------------------------- #
def parse_codex_marketplace_list(text: str) -> list[JsonDict]:
    """解析 `codex plugin marketplace list` 的表格（MARKETPLACE / ROOT，两列按多空格分隔）。

    这是老版本 Codex 无 `--json` 时的回退路径：文本表格只有名称与路径，拿不到真实
    源类型，故记为 unknown（标 local 会把 git/ssh 远程源误判为本地，反而误导）。
    """
    rows: list[JsonDict] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("MARKETPLACE"):
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if not parts:
            continue
        name = parts[0].strip()
        root = parts[1].strip() if len(parts) > 1 else ""
        rows.append({"name": name, "repo": root, "source_type": "unknown", "source": "cli"})
    return rows


def parse_codex_marketplace_json(data: JsonDict) -> list[JsonDict]:
    """解析 `codex plugin marketplace list --json`，保留真实源类型（local/git/…）。

    `marketplaceSource` 可能缺失（如内置 curated 源），缺失时源类型记为 unknown。
    """
    rows: list[JsonDict] = []
    for m in data.get("marketplaces", []):
        if not isinstance(m, dict):
            continue
        src = m.get("marketplaceSource") if isinstance(m.get("marketplaceSource"), dict) else {}
        rows.append(
            {
                "name": str(m.get("name") or ""),
                "repo": str(src.get("source") or m.get("root") or ""),
                "source_type": str(src.get("sourceType") or "unknown"),
                "source": "cli",
            }
        )
    return rows


def collect_codex(home: Path, cwd: Path, cache: JsonDict) -> JsonDict:
    section: JsonDict = {
        "platform": "codex",
        "label": "Codex",
        "cli_present": cli_available("codex"),
        "supports_token_cost": False,  # Codex 无 token 计算，组件只列清单
        "plugins": [],
        "available_plugins": [],
        "marketplaces": [],
        "mcp_servers": [],
        "skills": [],
        "notes": [],
    }
    if not section["cli_present"]:
        section["notes"].append("未检测到 `codex` CLI，跳过 Codex 的 CLI 审计。")

    if section["cli_present"]:
        installed, available = plugin_lists(
            run_cli_json(["codex", "plugin", "list", "--json", "--available"])
        )
        for item in installed:
            if not isinstance(item, dict):
                continue
            manifest = read_codex_plugin_manifest(item)
            _register_component_descriptions(cache, manifest["components"])
            section["plugins"].append(
                {
                    "id": str(item.get("pluginId") or item.get("name") or ""),
                    "name": str(item.get("name") or ""),
                    "marketplace": str(item.get("marketplaceName") or ""),
                    "installed": True,
                    "version": str(item.get("version") or ""),
                    "real_version": manifest["real_version"],
                    "enabled": item.get("enabled"),
                    "always_on_tokens": None,  # Codex 无 token
                    "components": manifest["components"],
                    "components_source": manifest["components_source"],
                    "description": manifest["description"],
                    "description_key": register_translatable(cache, manifest["description"], "plugin_desc"),
                    "note": manifest["note"],
                    "source": "cli",
                }
            )
        for item in available:
            if not isinstance(item, dict):
                continue
            manifest = read_codex_plugin_manifest(item)
            # 可装插件只译「插件级用途」供浏览，不译每个组件描述（177 插件 × 多技能会让待译量爆炸）。
            section["available_plugins"].append(
                {
                    "id": str(item.get("pluginId") or item.get("name") or ""),
                    "name": str(item.get("name") or ""),
                    "marketplace": str(item.get("marketplaceName") or ""),
                    "installed": False,
                    "version": str(item.get("version") or ""),
                    "real_version": manifest["real_version"],
                    "install_count": None,  # Codex 列表无热度
                    "components": manifest["components"],
                    "components_source": manifest["components_source"],
                    "description": manifest["description"],
                    "description_key": register_translatable(cache, manifest["description"], "plugin_desc"),
                    "note": manifest["note"],
                    "source": "cli",
                }
            )

        # 市场源（--json 保留真实源类型；老版本无 --json 时退回文本解析）
        mdata = run_cli_json(["codex", "plugin", "marketplace", "list", "--json"])
        if isinstance(mdata, dict) and mdata.get("marketplaces") is not None:
            section["marketplaces"] = parse_codex_marketplace_json(mdata)
        else:
            out, _ = run_cli(["codex", "plugin", "marketplace", "list"])
            if out:
                section["marketplaces"] = parse_codex_marketplace_list(out)

        # MCP（有 --json）
        mcp = run_cli_json(["codex", "mcp", "list", "--json"]) or []
        for item in mcp:
            if not isinstance(item, dict):
                continue
            transport = item.get("transport") if isinstance(item.get("transport"), dict) else {}
            section["mcp_servers"].append(
                {
                    "name": str(item.get("name") or ""),
                    "enabled": item.get("enabled"),
                    "server_type": str(transport.get("type") or "unknown"),
                    "target": str(transport.get("command") or transport.get("url") or ""),
                    "auth_status": str(item.get("auth_status") or ""),
                    "source": "cli",
                }
            )

        section["notes"].append(
            "Codex 无 `plugin details` 命令，插件自带技能与 token 成本未逐插件展开（已知缩减项）。"
        )

    # 技能：独立目录治理入口（用户级 + 项目级，逐级向上到 repo 根）
    roots = [
        (home / ".codex" / "skills" / ".system", "codex-system"),
        (home / ".codex" / "skills", "codex"),
        (home / ".agents" / "skills", "agents"),
    ]
    roots.extend((d, "codex-project") for d in project_skill_dirs(cwd, Path(".codex") / "skills"))
    roots.extend((d, "agents-project") for d in project_skill_dirs(cwd, Path(".agents") / "skills"))
    section["skills"] = collect_skills_from_dirs(roots)
    section["notes"].append(
        "技能来自目录扫描：Codex 没有列举技能的 CLI，目录即官方治理入口。"
    )
    section["notes"].append(
        "App / 连接器全量审计在 CLI 模式下暂不覆盖（Codex 无对应 list --json 命令）。"
    )
    return section


# --------------------------------------------------------------------------- #
# 会话可见态对照（仅对宿主平台精确）
# --------------------------------------------------------------------------- #
def mark_visibility(section: JsonDict, session_snapshot: JsonDict) -> None:
    tools = [t for t in (session_snapshot.get("tools") or []) if isinstance(t, dict)]
    visible_skill_names = {
        str(s.get("name"))
        for s in (session_snapshot.get("skills") or [])
        if isinstance(s, dict) and s.get("name")
    }
    namespaces = [str(t.get("namespace") or t.get("tool_namespace") or "") for t in tools]
    # source_hint 兜底：claude.ai 连接器等的工具命名空间是 UUID，与 MCP 显示名对不上，
    # 故快照可在 source_hint 里写显示名，这里按它匹配（不区分大小写）。
    source_hints = {str(t.get("source_hint") or "").strip().lower() for t in tools if t.get("source_hint")}
    for skill in section["skills"]:
        skill["visible_in_session"] = skill["name"] in visible_skill_names
    for server in section["mcp_servers"]:
        name = str(server.get("name") or "")
        by_ns = any(ns.startswith(f"mcp__{name}") for ns in namespaces)
        by_hint = bool(name) and name.strip().lower() in source_hints
        server["visible_in_session"] = bool(name) and (by_ns or by_hint)


# --------------------------------------------------------------------------- #
# 卫生建议
# --------------------------------------------------------------------------- #
def duplicate_names(items: list[JsonDict], key: str = "name") -> JsonDict:
    by_name: dict[str, list[str]] = defaultdict(list)
    for item in items:
        by_name[item.get(key, "")].append(item.get("id") or item.get("name") or "")
    return {n: sorted(ids) for n, ids in sorted(by_name.items()) if n and len(ids) > 1}


def build_recommendations(sections: list[JsonDict]) -> list[JsonDict]:
    recs: list[JsonDict] = []
    for section in sections:
        platform = section["label"]

        # 同名技能覆盖：官方按 enterprise > personal > project 覆盖，向上遍历时同为 project
        # 的多层目录也只有一个生效。按「实例数」判断而非 scope 集合——否则同 scope 多目录
        # （子目录与 repo 根都有同名技能）会被 set 折叠而漏报。技能走目录、不依赖 CLI，
        # 故放在 cli_present 判断之前。
        instances_by_skill: dict[str, list[JsonDict]] = defaultdict(list)
        for sk in section["skills"]:
            name = str(sk.get("name") or "")
            if name:
                instances_by_skill[name].append(sk)
        for name, insts in sorted(instances_by_skill.items()):
            if len(insts) > 1:
                scopes = sorted({str(s.get("scope") or "") for s in insts})
                where = "、".join(scopes) if len(scopes) > 1 else f"{scopes[0]} ×{len(insts)}"
                # 措辞按平台区分：Claude 同名是官方明确覆盖；Codex 当前实现下同名技能
                # 可能两个都可见（已知问题，precedence 是设计意图），不能断言「只有一个生效」。
                if section["platform"] == "claude":
                    reason = f"同名技能存在 {len(insts)} 处（{where}），按官方覆盖顺序只有最高优先级的一个生效"
                    action = "确认是否有意覆盖，删掉多余的以免混淆"
                else:
                    reason = f"同名技能存在 {len(insts)} 处（{where}），Codex 当前可能同时可见或按优先级解析（行为有歧义）"
                    action = "确认是否有意；需要时在配置中对低优先级路径设 enabled=false"
                recs.append(
                    {
                        "severity": "review",
                        "platform": platform,
                        "area": "skill",
                        "subject": name,
                        "reason": reason,
                        "action": action,
                    }
                )

        if not section["cli_present"]:
            continue
        # 同名插件多来源
        for name, ids in duplicate_names(section["plugins"]).items():
            recs.append(
                {
                    "severity": "review",
                    "platform": platform,
                    "area": "plugin",
                    "subject": name,
                    "reason": "同名插件存在于多个来源",
                    "action": "禁用旧版或不用的实例，确认无依赖后清理",
                }
            )
        for plugin in section["plugins"]:
            if plugin.get("enabled") is False:
                recs.append(
                    {
                        "severity": "info",
                        "platform": platform,
                        "area": "plugin",
                        "subject": plugin.get("id") or plugin.get("name"),
                        "reason": "已安装但当前禁用",
                        "action": "确认不再需要可卸载以省磁盘与 always-on token",
                    }
                )
            tokens = plugin.get("always_on_tokens")
            if isinstance(tokens, int) and tokens >= TOKEN_HEAVY_THRESHOLD:
                recs.append(
                    {
                        "severity": "review",
                        "platform": platform,
                        "area": "plugin",
                        "subject": plugin.get("id") or plugin.get("name"),
                        "reason": f"always-on token 开销偏大（约 {tokens} tok，每次会话都加）",
                        "action": "若不常用，考虑禁用以降低每次会话的固定开销",
                    }
                )
    return recs


# --------------------------------------------------------------------------- #
# 层级化 / 排行 / 边界
# --------------------------------------------------------------------------- #
def build_rankings(platforms: dict[str, JsonDict]) -> JsonDict:
    """成本排行：只遍历 supports_token_cost 平台（Claude）。Codex 无 token，不进榜。"""
    skills: list[JsonDict] = []
    agents: list[JsonDict] = []
    plugins: list[JsonDict] = []
    for section in platforms.values():
        if not section.get("supports_token_cost"):
            continue
        platform = section["platform"]
        for plugin in section.get("plugins", []):
            pid = plugin.get("id") or plugin.get("name")
            tot = plugin.get("always_on_tokens")
            if isinstance(tot, int):
                plugins.append({"id": pid, "platform": platform, "always_on_tokens": tot})
            comps = plugin.get("components") or {}
            for comp in comps.get("skills", []):
                skills.append({"name": comp.get("name"), "plugin": pid, "platform": platform,
                               "always_on_tokens": comp.get("always_on_tokens"),
                               "on_invoke_tokens": comp.get("on_invoke_tokens")})
            for comp in comps.get("agents", []):
                agents.append({"name": comp.get("name"), "plugin": pid, "platform": platform,
                               "always_on_tokens": comp.get("always_on_tokens"),
                               "on_invoke_tokens": comp.get("on_invoke_tokens")})

    def by_invoke(x: JsonDict) -> int:
        return x.get("on_invoke_tokens") or x.get("always_on_tokens") or 0

    return {
        "top_skills_by_cost": sorted(skills, key=by_invoke, reverse=True),
        "top_agents_by_cost": sorted(agents, key=by_invoke, reverse=True),
        "top_plugins_by_cost": sorted(plugins, key=lambda x: x.get("always_on_tokens") or 0, reverse=True),
        "basis": "claude_plugin_details_per_component（on-invoke 优先，回退 always-on）",
    }


def build_boundaries() -> list[JsonDict]:
    return [
        {"scope": "codex", "limit": "Codex 无 plugin details 命令，插件组件来自本地清单，全程无 token 成本，仅列清单。"},
        {"scope": "mcp", "limit": "MCP 服务器在两平台都无 token 成本数据，按数量/列表展示，不排成本。"},
        {"scope": "available", "limit": "未安装插件无法展开完整 details（CLI 报 not found），只提供中文用途 + 热度 + 源码链接，成本装后可见。"},
        {"scope": "claude-hooks", "limit": "Hooks 为 harness-only，不进模型上下文，无 token 成本。"},
        {"scope": "claude-lsp", "limit": "LSP 为 out-of-process 工具，不进模型上下文，无 token 成本。"},
        {"scope": "skills-dir", "limit": "技能经目录扫描，未覆盖 enterprise/managed 与子目录按需加载的 nested 技能。"},
    ]


# --------------------------------------------------------------------------- #
# 组装与渲染
# --------------------------------------------------------------------------- #
def build_inventory(
    home: Path | None = None,
    cwd: Path | None = None,
    platform: str = "both",
    session_snapshot: JsonDict | None = None,
    cache: JsonDict | None = None,
) -> JsonDict:
    home = (home or Path.home()).expanduser()
    cwd = cwd or Path.cwd()
    session_snapshot = session_snapshot or {}
    cache = cache if cache is not None else load_translation_cache()

    sections: list[JsonDict] = []
    if platform in ("both", "claude"):
        sections.append(collect_claude(home, cwd, cache))
    if platform in ("both", "codex"):
        sections.append(collect_codex(home, cwd, cache))

    for section in sections:
        mark_visibility(section, session_snapshot)
        # 独立技能描述也登记翻译
        for skill in section["skills"]:
            skill["description_key"] = register_translatable(cache, skill.get("description") or "", "skill_desc")

    recommendations = build_recommendations(sections)
    platforms = {section["platform"]: section for section in sections}
    # 只统计当前 inventory 实际引用到的 key，避免孤儿条目让「待译 N」虚高
    referenced_keys = collect_referenced_keys(platforms)

    # 采集结束回写翻译缓存（脚本只登记英文，中文由技能里的 Claude 填）
    save_translation_cache(cache)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "home": str(home),
        "cwd": str(cwd),
        "platform_filter": platform,
        "session": {
            "snapshot_provided": bool(session_snapshot),
            "tool_count": len(session_snapshot.get("tools") or []),
            "skill_count": len(session_snapshot.get("skills") or []),
        },
        "platforms": platforms,
        "rankings": build_rankings(platforms),
        "boundaries": build_boundaries(),
        "recommendations": recommendations,
        "pending_translation_count": pending_translation_count(cache, referenced_keys),
        "translation_cache_path": str(translation_cache_path()),
        "notes": [
            "插件 / 市场 / MCP 经各平台官方 CLI 治理命令获取；技能经目录获取（无 CLI，官方设计）。",
            "当前会话可见态只对 --session-snapshot 中提供的内容精确，且仅对宿主平台有意义。",
            "Claude 的插件 token 成本来自 `claude plugin details`；Codex 暂无等价命令。",
            "插件/技能的中文用途经 ~/.cache/context-doctor/translations.json 缓存翻译，缺失时回退英文。",
        ],
    }


def yes_no_unknown(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未知"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        clean = [str(cell).replace("\n", " ").replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(clean) + " |")
    return "\n".join(lines)


def render_platform_section(section: JsonDict) -> list[str]:
    lines: list[str] = []
    lines.append(f"## {section['label']}")
    lines.append("")
    if not section["cli_present"]:
        lines.append(f"> 未检测到 `{section['platform']}` CLI，本平台仅列出目录中的技能（如有）。")
        lines.append("")

    # 插件
    lines.append(f"### 插件（已装 {len(section['plugins'])} / 可装 {len(section['available_plugins'])}）")
    lines.append("")
    if section["plugins"]:
        rows = []
        for p in section["plugins"]:
            extras = []
            if p.get("bundled_skills"):
                extras.append(f"{len(p['bundled_skills'])} 技能")
            if isinstance(p.get("always_on_tokens"), int):
                extras.append(f"~{p['always_on_tokens']} tok")
            rows.append(
                [
                    p.get("id") or p.get("name"),
                    p.get("version") or "",
                    yes_no_unknown(p.get("enabled")),
                    p.get("marketplace") or "",
                    " / ".join(extras) or "—",
                ]
            )
        lines.append(md_table(["插件 ID", "版本", "启用", "市场", "自带技能/token"], rows))
    else:
        lines.append("（无已装插件，或 CLI 不可用）")
    lines.append("")

    # 可装插件（市场提供、当前未装）——清单可能很长，折叠展示
    avail = section["available_plugins"]
    if avail:
        lines.append("<details>")
        lines.append(f"<summary>可装插件（{len(avail)}）——市场提供、当前未装</summary>")
        lines.append("")
        lines.append(
            md_table(
                ["插件 ID", "市场"],
                [[a.get("id") or a.get("name"), a.get("marketplace") or ""] for a in avail],
            )
        )
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # 市场源
    lines.append(f"### 市场源（{len(section['marketplaces'])}）")
    lines.append("")
    if section["marketplaces"]:
        rows = []
        for m in section["marketplaces"]:
            origin = m.get("repo") or ""
            ref = m.get("ref") or ""
            if origin and ref:
                origin = f"{origin} @{ref}"
            rows.append([m.get("name"), m.get("source_type") or "", origin])
        lines.append(md_table(["名称", "类型", "来源/仓库"], rows))
    else:
        lines.append("（无）")
    lines.append("")

    # MCP
    lines.append(f"### MCP 服务器（{len(section['mcp_servers'])}）")
    lines.append("")
    if section["mcp_servers"]:
        rows = []
        for s in section["mcp_servers"]:
            status = s.get("status") or s.get("auth_status") or ""
            rows.append(
                [
                    s.get("name"),
                    s.get("server_type") or "",
                    yes_no_unknown(s["enabled"]) if "enabled" in s else "—",
                    status,
                    yes_no_unknown(s.get("visible_in_session")),
                ]
            )
        lines.append(md_table(["名称", "类型", "启用", "状态", "会话可见"], rows))
    else:
        lines.append("（无）")
    lines.append("")

    # 技能（独立目录）
    lines.append(f"### 独立技能 · 目录（{len(section['skills'])}）")
    lines.append("")
    if section["skills"]:
        lines.append(
            md_table(
                ["名称", "范围", "来源", "会话可见", "路径"],
                [
                    [
                        s.get("name"),
                        s.get("scope") or "",
                        s.get("source") or "",
                        yes_no_unknown(s.get("visible_in_session")),
                        s.get("path") or "",
                    ]
                    for s in section["skills"]
                ],
            )
        )
    else:
        lines.append("（无独立技能）")
    lines.append("")

    if section.get("notes"):
        for note in section["notes"]:
            lines.append(f"> {note}")
        lines.append("")
    return lines


SEVERITY_LABELS = {"review": "需检查", "info": "提示"}
AREA_LABELS = {"plugin": "插件", "mcp": "MCP", "marketplace": "市场源", "skill": "技能"}


def render_markdown(inventory: JsonDict) -> str:
    lines: list[str] = []
    lines.append("# Context Doctor 跨平台上下文审计报告")
    lines.append("")
    lines.append(f"- 生成时间：`{inventory['generated_at']}`")
    lines.append(f"- 工作目录：`{inventory['cwd']}`")
    session = inventory["session"]
    lines.append(
        f"- 会话快照：`{yes_no_unknown(session['snapshot_provided'])}`"
        f"（工具 `{session['tool_count']}`，技能 `{session['skill_count']}`）"
    )
    # 每平台一行小结
    for platform in inventory["platforms"].values():
        if not platform["cli_present"] and not platform["skills"]:
            continue
        lines.append(
            f"- {platform['label']}：插件 `{len(platform['plugins'])}`，"
            f"市场 `{len(platform['marketplaces'])}`，MCP `{len(platform['mcp_servers'])}`，"
            f"独立技能 `{len(platform['skills'])}`"
        )
    lines.append("")

    recs = inventory.get("recommendations") or []
    if recs:
        lines.append("## 上下文卫生建议")
        lines.append("")
        lines.append(
            md_table(
                ["级别", "平台", "范围", "对象", "原因", "建议动作"],
                [
                    [
                        SEVERITY_LABELS.get(r.get("severity", ""), r.get("severity", "")),
                        r.get("platform", ""),
                        AREA_LABELS.get(r.get("area", ""), r.get("area", "")),
                        r.get("subject", ""),
                        r.get("reason", ""),
                        r.get("action", ""),
                    ]
                    for r in recs
                ],
            )
        )
        lines.append("")

    for section in inventory["platforms"].values():
        lines.extend(render_platform_section(section))

    lines.append("## 边界")
    lines.append("")
    for note in inventory["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def default_template_path() -> Path:
    return Path(__file__).resolve().parent / "report_template.html"


def render_html(inventory: JsonDict, cache: JsonDict, template_path: Path | None = None) -> str:
    """把（已查表补中文的）inventory 注入静态 HTML 模板，生成自包含单文件报告。"""
    template_path = template_path or default_template_path()
    resolved = resolve_translations(inventory, cache)
    payload = json.dumps(resolved, ensure_ascii=False)
    # 防止内嵌 JSON 里的 </script> / </ 提前闭合脚本块（JSON.parse 仍能正确还原 \/）。
    payload = payload.replace("</", "<\\/")
    template = Path(template_path).read_text(encoding="utf-8")
    return template.replace("/*__INVENTORY_JSON__*/", payload)


def short_summary(inventory: JsonDict) -> str:
    parts: list[str] = []
    for platform in inventory["platforms"].values():
        if not platform["cli_present"] and not platform["skills"]:
            continue
        parts.append(
            f"{platform['label']}: 插件 {len(platform['plugins'])}、"
            f"市场 {len(platform['marketplaces'])}、MCP {len(platform['mcp_servers'])}、"
            f"独立技能 {len(platform['skills'])}"
        )
    rec_n = len(inventory.get("recommendations") or [])
    parts.append(f"建议 {rec_n} 条")
    return "；".join(parts)


# --------------------------------------------------------------------------- #
# 会话快照与 CLI 入口
# --------------------------------------------------------------------------- #
def load_session_snapshot(path: Path | None) -> JsonDict:
    if not path:
        return {}
    try:
        return json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def session_snapshot_template() -> JsonDict:
    return {
        "tools": [
            {
                "namespace": "mcp__example",
                "tool": "tool_name",
                "source_hint": "optional free text",
            }
        ],
        "skills": [
            {
                "name": "plugin:skill-name or standalone-skill-name",
                "path": "/absolute/path/to/SKILL.md",
            }
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="用官方 CLI 治理入口审计 Claude Code 与 Codex 的插件 / MCP / 市场源，技能走目录。"
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help="要检查的 home 目录（默认当前用户）。")
    parser.add_argument("--cwd", type=Path, default=None, help="项目级技能扫描的起始目录（默认当前工作目录）。")
    parser.add_argument(
        "--platform",
        choices=["both", "claude", "codex"],
        default="both",
        help="审计哪个平台（默认 both）。",
    )
    parser.add_argument("--session-snapshot", type=Path, help="可选：当前会话可见工具/技能的 JSON 快照。")
    parser.add_argument("--json", type=Path, help="采集模式：把完整 inventory JSON 写到此路径；--render-only 模式：从此路径读 inventory。")
    parser.add_argument("--markdown", type=Path, help="把 Markdown 报告写到此路径。")
    parser.add_argument("--html", type=Path, help="把单文件交互式 HTML 报告写到此路径。")
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="只读现有 --json inventory + 翻译缓存渲染 HTML，不重新采集（翻译完后二次渲染用）。",
    )
    parser.add_argument("--template", type=Path, default=None, help="HTML 模板路径（默认脚本同目录 report_template.html）。")
    parser.add_argument(
        "--print-session-snapshot-template",
        action="store_true",
        help="打印会话快照 JSON 形状并退出。",
    )
    return parser.parse_args(argv)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.print_session_snapshot_template:
        print(json.dumps(session_snapshot_template(), indent=2, ensure_ascii=False))
        return 0

    # 只渲染：读现有 inventory + 最新翻译缓存，重渲 HTML（翻译完二次渲染用），不重新采集。
    if args.render_only:
        if not args.json or not args.html:
            print("--render-only 需要同时给 --json（输入 inventory）与 --html（输出）。", file=sys.stderr)
            return 2
        try:
            inventory = json.loads(args.json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"读取 inventory 失败：{exc}", file=sys.stderr)
            return 2
        cache = load_translation_cache()
        write_text(args.html, render_html(inventory, cache, args.template))
        return 0

    cache = load_translation_cache()
    inventory = build_inventory(
        home=args.home,
        cwd=args.cwd,
        platform=args.platform,
        session_snapshot=load_session_snapshot(args.session_snapshot),
        cache=cache,
    )
    markdown = render_markdown(inventory)

    if args.json:
        write_text(args.json, json.dumps(inventory, indent=2, ensure_ascii=False))
    if args.markdown:
        write_text(args.markdown, markdown)
    if args.html:
        write_text(args.html, render_html(inventory, cache, args.template))
    if not args.json and not args.markdown and not args.html:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
