#!/usr/bin/env python3
"""跨平台上下文审计：用官方 CLI 治理入口盘点 Claude Code 与 Codex 的插件 / MCP / 市场源，
技能因两平台都没有 CLI（官方设计为文件式）而走目录治理入口，并可对照当前会话可见态。

设计原则：CLI 优先。插件 / 市场 / MCP 一律调 `claude` / `codex` 的官方命令再解析输出；
只有「技能」没有任何 CLI 列举命令，按官方文档的唯一治理方式——列技能目录——来盘点。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

# CLI 调用默认超时（秒）。`claude mcp list` 会做联网健康检查，给得宽一些。
DEFAULT_TIMEOUT = 30
MCP_LIST_TIMEOUT = 60
# 插件 always-on token 超过此阈值，提示「开销偏大」。
TOKEN_HEAVY_THRESHOLD = 1000


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


def cli_available(name: str) -> bool:
    return shutil.which(name) is not None


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
    data: JsonDict = {}
    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
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
    """当前目录到 repo 根，沿途所有 <rel> 目录（rel 如 .claude/skills、.codex/skills、.agents/skills）。"""
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
        # 末尾 " - <状态>"（状态里可能含 ✔ / ⏸ / ✗ 等符号）
        m = re.search(r"\s-\s([^-]+)$", rest)
        if m:
            status = m.group(1).strip()
            target = rest[: m.start()].strip()
        servers.append(
            {
                "name": name.strip(),
                "target": target,
                "status": status,
                "source": "cli",
            }
        )
    return servers


def parse_claude_details(text: str) -> JsonDict:
    """解析 `claude plugin details <name>`：取插件自带技能名列表与 always-on token。"""
    skills: list[str] = []
    always_on: int | None = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"Skills\s*\((\d+)\)\s+(.*)$", line)
        if m and m.group(2):
            skills = [s.strip() for s in m.group(2).split(",") if s.strip()]
            continue
        m = re.match(r"Always-on:\s*~?([\d.]+)\s*([kK]?)\s*tok", line)
        if m:
            value = float(m.group(1))
            if m.group(2).lower() == "k":
                value *= 1000
            always_on = int(value)
    return {"bundled_skills": skills, "always_on_tokens": always_on}


def collect_claude(home: Path, cwd: Path) -> JsonDict:
    section: JsonDict = {
        "platform": "claude",
        "label": "Claude Code",
        "cli_present": cli_available("claude"),
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
        data = run_cli_json(["claude", "plugin", "list", "--json", "--available"])
        installed = (data or {}).get("installed") or []
        available = (data or {}).get("available") or []
        for item in installed:
            if not isinstance(item, dict):
                continue
            plugin_id = str(item.get("id") or "")
            name, _, marketplace = plugin_id.partition("@")
            entry: JsonDict = {
                "id": plugin_id,
                "name": name or plugin_id,
                "marketplace": marketplace,
                "version": str(item.get("version") or ""),
                "scope": item.get("scope"),
                "enabled": item.get("enabled"),
                "source": "cli",
                "bundled_skills": [],
                "always_on_tokens": None,
            }
            # 逐已装插件取 details（自带技能 + token 成本）。只对已装调，控制开销。
            out, ok = run_cli(["claude", "plugin", "details", plugin_id])
            if ok and out:
                parsed = parse_claude_details(out)
                entry["bundled_skills"] = parsed["bundled_skills"]
                entry["always_on_tokens"] = parsed["always_on_tokens"]
            section["plugins"].append(entry)
        for item in available:
            if not isinstance(item, dict):
                continue
            section["available_plugins"].append(
                {
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or item.get("id") or ""),
                    "marketplace": str(item.get("marketplace") or ""),
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
                    "repo": str(item.get("repo") or item.get("installLocation") or ""),
                    "source": "cli",
                }
            )

        # MCP（无 --json，解析文本）
        out, _ = run_cli(["claude", "mcp", "list"], timeout=MCP_LIST_TIMEOUT)
        if out:
            section["mcp_servers"] = parse_claude_mcp_list(out)

    # 技能：个人级 + 项目级（目录治理入口）
    roots = [(home / ".claude" / "skills", "personal")]
    roots.extend((d, "project") for d in project_skill_dirs(cwd, Path(".claude") / "skills"))
    section["skills"] = collect_skills_from_dirs(roots)
    section["notes"].append(
        "技能来自目录扫描：Claude Code 没有列举技能的 CLI，目录即官方治理入口。"
        "插件自带技能与 token 成本来自 `claude plugin details`。"
    )
    return section


# --------------------------------------------------------------------------- #
# Codex 采集器（CLI 优先）
# --------------------------------------------------------------------------- #
def parse_codex_marketplace_list(text: str) -> list[JsonDict]:
    """解析 `codex plugin marketplace list` 的表格（MARKETPLACE / ROOT，两列按多空格分隔）。"""
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
        rows.append({"name": name, "repo": root, "source_type": "local", "source": "cli"})
    return rows


def collect_codex(home: Path, cwd: Path) -> JsonDict:
    section: JsonDict = {
        "platform": "codex",
        "label": "Codex",
        "cli_present": cli_available("codex"),
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
        data = run_cli_json(["codex", "plugin", "list", "--json", "--available"])
        installed = (data or {}).get("installed") or []
        available = (data or {}).get("available") or []
        for item in installed:
            if not isinstance(item, dict):
                continue
            section["plugins"].append(
                {
                    "id": str(item.get("pluginId") or item.get("name") or ""),
                    "name": str(item.get("name") or ""),
                    "marketplace": str(item.get("marketplaceName") or ""),
                    "version": str(item.get("version") or ""),
                    "enabled": item.get("enabled"),
                    "source": "cli",
                }
            )
        for item in available:
            if not isinstance(item, dict):
                continue
            section["available_plugins"].append(
                {
                    "id": str(item.get("pluginId") or item.get("name") or ""),
                    "name": str(item.get("name") or ""),
                    "marketplace": str(item.get("marketplaceName") or ""),
                    "source": "cli",
                }
            )

        # 市场源（无 --json，解析文本表格）
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
    visible_skill_names = {
        str(s.get("name"))
        for s in (session_snapshot.get("skills") or [])
        if isinstance(s, dict) and s.get("name")
    }
    namespaces = [
        str(t.get("namespace") or t.get("tool_namespace") or "")
        for t in (session_snapshot.get("tools") or [])
        if isinstance(t, dict)
    ]
    for skill in section["skills"]:
        skill["visible_in_session"] = skill["name"] in visible_skill_names
    for server in section["mcp_servers"]:
        name = server.get("name") or ""
        server["visible_in_session"] = any(
            ns.startswith(f"mcp__{name}") for ns in namespaces
        )


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
# 组装与渲染
# --------------------------------------------------------------------------- #
def build_inventory(
    home: Path | None = None,
    cwd: Path | None = None,
    platform: str = "both",
    session_snapshot: JsonDict | None = None,
) -> JsonDict:
    home = (home or Path.home()).expanduser()
    cwd = cwd or Path.cwd()
    session_snapshot = session_snapshot or {}

    sections: list[JsonDict] = []
    if platform in ("both", "claude"):
        sections.append(collect_claude(home, cwd))
    if platform in ("both", "codex"):
        sections.append(collect_codex(home, cwd))

    for section in sections:
        mark_visibility(section, session_snapshot)

    recommendations = build_recommendations(sections)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "home": str(home),
        "cwd": str(cwd),
        "platform_filter": platform,
        "session": {
            "snapshot_provided": bool(session_snapshot),
            "tool_count": len(session_snapshot.get("tools") or []),
            "skill_count": len(session_snapshot.get("skills") or []),
        },
        "platforms": {section["platform"]: section for section in sections},
        "recommendations": recommendations,
        "notes": [
            "插件 / 市场 / MCP 经各平台官方 CLI 治理命令获取；技能经目录获取（无 CLI，官方设计）。",
            "当前会话可见态只对 --session-snapshot 中提供的内容精确，且仅对宿主平台有意义。",
            "Claude 的插件 token 成本来自 `claude plugin details`；Codex 暂无等价命令。",
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

    # 市场源
    lines.append(f"### 市场源（{len(section['marketplaces'])}）")
    lines.append("")
    if section["marketplaces"]:
        lines.append(
            md_table(
                ["名称", "类型", "来源/仓库"],
                [[m.get("name"), m.get("source_type") or "", m.get("repo") or ""] for m in section["marketplaces"]],
            )
        )
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
AREA_LABELS = {"plugin": "插件", "mcp": "MCP", "marketplace": "市场源"}


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
    parser.add_argument("--json", type=Path, help="把完整 inventory JSON 写到此路径。")
    parser.add_argument("--markdown", type=Path, help="把 Markdown 报告写到此路径。")
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

    inventory = build_inventory(
        home=args.home,
        cwd=args.cwd,
        platform=args.platform,
        session_snapshot=load_session_snapshot(args.session_snapshot),
    )
    markdown = render_markdown(inventory)

    if args.json:
        write_text(args.json, json.dumps(inventory, indent=2, ensure_ascii=False))
    if args.markdown:
        write_text(args.markdown, markdown)
    if not args.json and not args.markdown:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
