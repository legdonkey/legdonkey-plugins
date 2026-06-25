#!/usr/bin/env python3
"""Audit local Codex extensions and optional current-session snapshots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    tomllib = None  # type: ignore[assignment]


JsonDict = dict[str, Any]


def read_json(path: Path) -> JsonDict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_toml(path: Path) -> JsonDict:
    if tomllib is None or not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def parse_skill_header(path: Path) -> JsonDict:
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


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def unique_sorted(values: list[str] | set[str]) -> list[str]:
    return sorted({value for value in values if value})


def find_plugin_manifests(codex_home: Path) -> list[Path]:
    roots = [
        codex_home / "plugins" / "cache",
        codex_home / "plugins" / "local-marketplaces",
    ]
    manifests: list[Path] = []
    for root in roots:
        if root.exists():
            manifests.extend(root.rglob(".codex-plugin/plugin.json"))
    return sorted(manifests)


def infer_plugin_source(plugin_root: Path, codex_home: Path) -> JsonDict:
    cache_root = codex_home / "plugins" / "cache"
    local_root = codex_home / "plugins" / "local-marketplaces"

    try:
        parts = plugin_root.relative_to(cache_root).parts
        marketplace = parts[0] if len(parts) >= 1 else "unknown"
        disk_slug = parts[1] if len(parts) >= 2 else plugin_root.name
        version_dir = parts[2] if len(parts) >= 3 else plugin_root.name
        return {
            "marketplace": marketplace,
            "disk_slug": disk_slug,
            "version_dir": version_dir,
            "source_class": "plugin-cache",
        }
    except ValueError:
        pass

    try:
        parts = plugin_root.relative_to(local_root).parts
        marketplace = parts[0] if len(parts) >= 1 else "local"
        disk_slug = parts[2] if len(parts) >= 3 and parts[1] == "plugins" else plugin_root.name
        return {
            "marketplace": marketplace,
            "disk_slug": disk_slug,
            "version_dir": plugin_root.name,
            "source_class": "local-marketplace",
        }
    except ValueError:
        pass

    return {
        "marketplace": "unknown",
        "disk_slug": plugin_root.name,
        "version_dir": plugin_root.name,
        "source_class": "unknown",
    }


def ui_bucket_for_plugin(marketplace: str, source_class: str) -> str:
    if source_class == "local-marketplace":
        return "marketplace-local-or-hidden"
    if marketplace in {"openai-primary-runtime", "openai-bundled", "openai-curated-remote"}:
        return "plugin-page-candidate"
    if marketplace == "openai-curated":
        return "legacy-cache-or-hidden"
    return "unknown"


def resolve_manifest_relative(plugin_root: Path, value: Any, fallback: str) -> Path:
    if isinstance(value, str) and value:
        return (plugin_root / value).resolve()
    return plugin_root / fallback


def load_plugin_app_declarations(plugin: JsonDict) -> list[JsonDict]:
    path = Path(plugin["app_manifest_path"])
    data = read_json(path)
    declarations: list[JsonDict] = []
    for alias, app in (data.get("apps") or {}).items():
        if not isinstance(app, dict):
            continue
        connector_id = app.get("id")
        if not connector_id:
            continue
        declarations.append(
            {
                "alias": alias,
                "connector_id": connector_id,
                "required": bool(app.get("required")),
                "optional": bool(app.get("optional")),
                "plugin_id": plugin["id"],
                "plugin_display_name": plugin["display_name"],
            }
        )
    return declarations


def load_plugin_mcp_declarations(plugin: JsonDict) -> list[JsonDict]:
    path = Path(plugin["mcp_manifest_path"])
    data = read_json(path)
    declarations: list[JsonDict] = []
    for name, server in (data.get("mcpServers") or {}).items():
        if not isinstance(server, dict):
            continue
        declarations.append(
            {
                "id": f"{name}@{plugin['id']}",
                "name": name,
                "origin": "plugin",
                "plugin_id": plugin["id"],
                "plugin_display_name": plugin["display_name"],
                "server_type": server.get("type") or ("command" if server.get("command") else "unknown"),
                "command": server.get("command"),
                "url": server.get("url"),
                "path": str(path),
            }
        )
    return declarations


def collect_plugin_skills(plugin: JsonDict) -> list[JsonDict]:
    skills_dir = Path(plugin["skills_path"])
    if not skills_dir.exists():
        return []
    skills: list[JsonDict] = []
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        header = parse_skill_header(skill_file)
        raw_name = str(header.get("name") or skill_file.parent.name)
        qualified_name = f"{plugin['name']}:{raw_name}"
        skills.append(
            {
                "name": qualified_name,
                "raw_name": raw_name,
                "origin": "plugin",
                "plugin_id": plugin["id"],
                "plugin_display_name": plugin["display_name"],
                "description": str(header.get("description") or ""),
                "path": str(skill_file),
            }
        )
    return skills


def collect_plugins(codex_home: Path, config: JsonDict) -> tuple[list[JsonDict], list[JsonDict], list[JsonDict], list[JsonDict]]:
    configured_plugins = config.get("plugins") or {}
    plugins: list[JsonDict] = []
    all_app_declarations: list[JsonDict] = []
    all_mcp_declarations: list[JsonDict] = []
    all_plugin_skills: list[JsonDict] = []
    seen_ids: dict[str, int] = {}

    for manifest_path in find_plugin_manifests(codex_home):
        plugin_root = manifest_path.parent.parent
        manifest = read_json(manifest_path)
        name = str(manifest.get("name") or plugin_root.name)
        source = infer_plugin_source(plugin_root, codex_home)
        marketplace = source["marketplace"]
        base_id = f"{name}@{marketplace}"
        duplicate_count = seen_ids.get(base_id, 0)
        seen_ids[base_id] = duplicate_count + 1
        plugin_id = base_id if duplicate_count == 0 else f"{base_id}#{duplicate_count + 1}"
        interface = manifest.get("interface") if isinstance(manifest.get("interface"), dict) else {}

        config_entry = configured_plugins.get(base_id)
        config_enabled = None
        if isinstance(config_entry, dict) and "enabled" in config_entry:
            config_enabled = bool(config_entry.get("enabled"))

        app_manifest_path = resolve_manifest_relative(plugin_root, manifest.get("apps"), ".app.json")
        mcp_manifest_path = resolve_manifest_relative(
            plugin_root, manifest.get("mcpServers"), ".mcp.json"
        )
        skills_path = resolve_manifest_relative(plugin_root, manifest.get("skills"), "skills")
        remote_install = plugin_root.parent / ".codex-remote-plugin-install.json"

        plugin = {
            "id": plugin_id,
            "config_key": base_id,
            "name": name,
            "display_name": str(interface.get("displayName") or name),
            "description": str(manifest.get("description") or ""),
            "version": str(manifest.get("version") or source.get("version_dir") or ""),
            "marketplace": marketplace,
            "source_class": source["source_class"],
            "ui_bucket": ui_bucket_for_plugin(marketplace, source["source_class"]),
            "path": str(plugin_root),
            "manifest_path": str(manifest_path),
            "skills_path": str(skills_path),
            "app_manifest_path": str(app_manifest_path),
            "mcp_manifest_path": str(mcp_manifest_path),
            "has_app_manifest": app_manifest_path.exists(),
            "has_mcp_manifest": mcp_manifest_path.exists(),
            "remote_install_cached": remote_install.exists(),
            "config_enabled": config_enabled,
            "config_state": "enabled" if config_enabled is True else "disabled" if config_enabled is False else "not-configured",
        }

        app_declarations = load_plugin_app_declarations(plugin)
        mcp_declarations = load_plugin_mcp_declarations(plugin)
        plugin_skills = collect_plugin_skills(plugin)

        plugin["skill_count"] = len(plugin_skills)
        plugin["app_count"] = len(app_declarations)
        plugin["mcp_count"] = len(mcp_declarations)

        plugins.append(plugin)
        all_app_declarations.extend(app_declarations)
        all_mcp_declarations.extend(mcp_declarations)
        all_plugin_skills.extend(plugin_skills)

    return plugins, all_app_declarations, all_mcp_declarations, all_plugin_skills


def collect_standalone_skills(home: Path) -> list[JsonDict]:
    codex_skills = home / ".codex" / "skills"
    agents_skills = home / ".agents" / "skills"
    skill_files: list[tuple[Path, str]] = []

    for root, kind in [(codex_skills / ".system", "system"), (codex_skills, "standalone"), (agents_skills, "agents")]:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            skill_path = child / "SKILL.md"
            if skill_path.exists():
                if kind == "standalone" and child.name == ".system":
                    continue
                skill_files.append((skill_path, kind))

    skills: list[JsonDict] = []
    seen_paths: set[str] = set()
    for skill_file, kind in skill_files:
        resolved = str(skill_file.resolve())
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        header = parse_skill_header(skill_file)
        name = str(header.get("name") or skill_file.parent.name)
        skills.append(
            {
                "name": name,
                "raw_name": name,
                "origin": "standalone" if kind != "system" else "system",
                "skill_root": kind,
                "description": str(header.get("description") or ""),
                "path": str(skill_file),
            }
        )
    return sorted(skills, key=lambda item: item["name"])


def collect_app_tool_cache(codex_home: Path) -> dict[str, JsonDict]:
    cache_root = codex_home / "cache" / "codex_apps_tools"
    grouped: dict[str, JsonDict] = {}
    if not cache_root.exists():
        return grouped

    for cache_file in sorted(cache_root.glob("*.json")):
        data = read_json(cache_file)
        for tool in data.get("tools") or []:
            if not isinstance(tool, dict):
                continue
            connector_id = tool.get("connector_id")
            if not connector_id:
                continue
            item = grouped.setdefault(
                connector_id,
                {
                    "connector_id": connector_id,
                    "connector_name": tool.get("connector_name") or connector_id,
                    "tool_names": [],
                    "tool_namespaces": [],
                    "plugin_display_names": [],
                    "cache_files": [],
                },
            )
            item["tool_names"].append(str(tool.get("tool_name") or ""))
            item["tool_namespaces"].append(str(tool.get("tool_namespace") or ""))
            item["plugin_display_names"].extend(tool.get("plugin_display_names") or [])
            item["cache_files"].append(str(cache_file))

    for item in grouped.values():
        item["tool_names"] = unique_sorted(item["tool_names"])
        item["tool_namespaces"] = unique_sorted(item["tool_namespaces"])
        item["plugin_display_names"] = unique_sorted(item["plugin_display_names"])
        item["cache_files"] = unique_sorted(item["cache_files"])
        item["cached_tool_count"] = len(item["tool_names"])
    return grouped


def collect_app_directory(codex_home: Path, connector_ids: set[str]) -> dict[str, JsonDict]:
    directory_root = codex_home / "cache" / "codex_app_directory"
    result: dict[str, JsonDict] = {}
    if not directory_root.exists() or not connector_ids:
        return result
    for directory_file in sorted(directory_root.glob("*.json")):
        data = read_json(directory_file)
        for connector in data.get("connectors") or []:
            if not isinstance(connector, dict):
                continue
            connector_id = connector.get("id")
            if connector_id in connector_ids:
                result[connector_id] = {
                    "name": connector.get("name"),
                    "description": connector.get("description"),
                    "distribution_channel": connector.get("distributionChannel"),
                    "directory_enabled": connector.get("isEnabled"),
                    "directory_accessible": connector.get("isAccessible"),
                    "directory_cache_file": str(directory_file),
                }
    return result


def collect_apps(
    codex_home: Path,
    config: JsonDict,
    app_declarations: list[JsonDict],
    session_snapshot: JsonDict,
) -> list[JsonDict]:
    config_apps = config.get("apps") or {}
    tool_cache = collect_app_tool_cache(codex_home)

    connector_ids = {decl["connector_id"] for decl in app_declarations}
    connector_ids.update(config_apps.keys())
    connector_ids.update(tool_cache.keys())
    directory = collect_app_directory(codex_home, connector_ids)

    session_tools = session_snapshot.get("tools") or []
    session_connector_ids = {
        str(tool.get("connector_id"))
        for tool in session_tools
        if isinstance(tool, dict) and tool.get("connector_id")
    }
    session_namespaces = {
        str(tool.get("namespace") or tool.get("tool_namespace") or "")
        for tool in session_tools
        if isinstance(tool, dict)
    }

    by_connector: dict[str, JsonDict] = {}
    for connector_id in connector_ids:
        config_entry = config_apps.get(connector_id)
        config_enabled = None
        if isinstance(config_entry, dict) and "enabled" in config_entry:
            config_enabled = bool(config_entry.get("enabled"))
        cached = tool_cache.get(connector_id, {})
        directory_item = directory.get(connector_id, {})
        name = (
            cached.get("connector_name")
            or directory_item.get("name")
            or connector_id
        )
        by_connector[connector_id] = {
            "connector_id": connector_id,
            "name": name,
            "origin": "unknown",
            "config_enabled": config_enabled,
            "declared_by_plugins": [],
            "declaration_aliases": [],
            "required_by_plugins": [],
            "optional_by_plugins": [],
            "cached_tool_count": int(cached.get("cached_tool_count") or 0),
            "tool_namespaces": cached.get("tool_namespaces") or [],
            "tool_names": cached.get("tool_names") or [],
            "plugin_display_names_from_cache": cached.get("plugin_display_names") or [],
            "visible_in_session": connector_id in session_connector_ids,
            **directory_item,
        }

    for decl in app_declarations:
        item = by_connector.setdefault(
            decl["connector_id"],
            {
                "connector_id": decl["connector_id"],
                "name": decl["connector_id"],
                "origin": "plugin-declaration",
                "config_enabled": None,
                "declared_by_plugins": [],
                "declaration_aliases": [],
                "required_by_plugins": [],
                "optional_by_plugins": [],
                "cached_tool_count": 0,
                "tool_namespaces": [],
                "tool_names": [],
                "plugin_display_names_from_cache": [],
                "visible_in_session": False,
            },
        )
        item["declared_by_plugins"].append(decl["plugin_id"])
        item["declaration_aliases"].append(decl["alias"])
        if decl.get("required"):
            item["required_by_plugins"].append(decl["plugin_id"])
        if decl.get("optional"):
            item["optional_by_plugins"].append(decl["plugin_id"])

    for item in by_connector.values():
        item["declared_by_plugins"] = unique_sorted(item["declared_by_plugins"])
        item["declaration_aliases"] = unique_sorted(item["declaration_aliases"])
        item["required_by_plugins"] = unique_sorted(item["required_by_plugins"])
        item["optional_by_plugins"] = unique_sorted(item["optional_by_plugins"])
        if item["declared_by_plugins"] and item["cached_tool_count"]:
            item["origin"] = "plugin-declaration+app-tool-cache"
        elif item["declared_by_plugins"]:
            item["origin"] = "plugin-declaration"
        elif item["cached_tool_count"]:
            item["origin"] = "app-tool-cache"
        elif item["config_enabled"] is not None:
            item["origin"] = "config"

        normalized_app_name = normalize_name(str(item.get("name") or ""))
        if not item["visible_in_session"]:
            item["visible_in_session"] = any(normalized_app_name and normalized_app_name in ns for ns in session_namespaces)

    return sorted(by_connector.values(), key=lambda app: str(app["name"]).lower())


def collect_mcp_servers(
    config: JsonDict,
    plugin_mcp_declarations: list[JsonDict],
    session_snapshot: JsonDict,
) -> list[JsonDict]:
    servers: list[JsonDict] = []
    for name, server in (config.get("mcp_servers") or {}).items():
        if not isinstance(server, dict):
            continue
        enabled = True if "enabled" not in server else bool(server.get("enabled"))
        servers.append(
            {
                "id": name,
                "name": name,
                "origin": "config",
                "config_enabled": enabled,
                "server_type": server.get("type") or ("command" if server.get("command") else "unknown"),
                "command": server.get("command"),
                "url": server.get("url"),
                "plugin_id": None,
                "path": "~/.codex/config.toml",
            }
        )
    servers.extend(plugin_mcp_declarations)

    namespaces = [
        str(tool.get("namespace") or tool.get("tool_namespace") or "")
        for tool in (session_snapshot.get("tools") or [])
        if isinstance(tool, dict)
    ]
    for server in servers:
        normalized = normalize_name(str(server.get("name") or ""))
        server["visible_in_session"] = any(
            namespace.startswith(f"mcp__{server['name']}") or (normalized and normalized in namespace)
            for namespace in namespaces
        )
    return sorted(servers, key=lambda server: (server["origin"], server["id"]))


def mark_visible_skills(skills: list[JsonDict], session_snapshot: JsonDict) -> None:
    visible_names = {
        str(skill.get("name"))
        for skill in session_snapshot.get("skills") or []
        if isinstance(skill, dict) and skill.get("name")
    }
    for skill in skills:
        aliases = {skill["name"], skill.get("raw_name", "")}
        skill["visible_in_session"] = bool(aliases & visible_names)


def collect_marketplaces(codex_home: Path, config: JsonDict) -> list[JsonDict]:
    marketplaces: dict[str, JsonDict] = {}
    for name, item in (config.get("marketplaces") or {}).items():
        marketplaces[name] = {
            "name": name,
            "origin": "config",
            "source_type": item.get("source_type") if isinstance(item, dict) else None,
            "source": item.get("source") if isinstance(item, dict) else None,
            "last_updated": item.get("last_updated") if isinstance(item, dict) else None,
            "path_exists": Path(item.get("source", "")).expanduser().exists() if isinstance(item, dict) and item.get("source") else None,
        }

    local_root = codex_home / "plugins" / "local-marketplaces"
    if local_root.exists():
        for child in sorted(local_root.iterdir()):
            if child.is_dir():
                marketplaces.setdefault(
                    child.name,
                    {
                        "name": child.name,
                        "origin": "disk-local-marketplace",
                        "source_type": "local",
                        "source": str(child),
                        "last_updated": None,
                        "path_exists": True,
                    },
                )
    return sorted(marketplaces.values(), key=lambda item: item["name"])


def duplicate_plugins(plugins: list[JsonDict]) -> JsonDict:
    by_name: dict[str, list[str]] = defaultdict(list)
    for plugin in plugins:
        by_name[plugin["name"]].append(plugin["id"])
    return {
        name: sorted(ids)
        for name, ids in sorted(by_name.items())
        if len(ids) > 1
    }


def build_recommendations(plugins: list[JsonDict], apps: list[JsonDict], mcp_servers: list[JsonDict]) -> list[JsonDict]:
    recommendations: list[JsonDict] = []

    for name, ids in duplicate_plugins(plugins).items():
        recommendations.append(
            {
                "severity": "review",
                "area": "plugin",
                "subject": name,
                "reason": "同名插件存在于多个来源",
                "evidence": ", ".join(ids),
                "action": "先禁用旧版或不用的实例；重启验证没有工作流依赖后，再考虑清理缓存",
            }
        )

    for plugin in plugins:
        if plugin["config_enabled"] is True and plugin["ui_bucket"] == "legacy-cache-or-hidden":
            recommendations.append(
                {
                    "severity": "review",
                    "area": "plugin",
                    "subject": plugin["id"],
                    "reason": "配置中启用，但当前插件页可能不显示",
                    "evidence": plugin["path"],
                    "action": "如果远程版或内置版已经覆盖同类工作流，可以先关闭它",
                }
            )
        if plugin["config_enabled"] is False and plugin["skill_count"]:
            recommendations.append(
                {
                    "severity": "info",
                    "area": "plugin",
                    "subject": plugin["id"],
                    "reason": "配置中已禁用，但插件文件和技能仍保留在磁盘上",
                    "evidence": f"{plugin['skill_count']} skills under {plugin['path']}",
                    "action": "这是正常缓存状态；除非会话快照显示可见，否则不要按活跃能力计算",
                }
            )

    for app in apps:
        if app.get("origin") == "app-tool-cache" and app.get("config_enabled") is None:
            recommendations.append(
                {
                    "severity": "review",
                    "area": "app",
                    "subject": app["connector_id"],
                    "reason": "连接器工具在本地有缓存，但没有匹配的 [apps.*] 配置或插件声明",
                    "evidence": f"{app.get('cached_tool_count', 0)} cached tools",
                    "action": "优先在 Codex App 界面管理；手写配置项是否生效取决于当前 Codex 版本",
                }
            )
        if app.get("config_enabled") is False and app.get("declared_by_plugins"):
            recommendations.append(
                {
                    "severity": "info",
                    "area": "app",
                    "subject": app["connector_id"],
                    "reason": "连接器已禁用，但仍被已安装插件声明为可选或必需 App",
                    "evidence": ", ".join(app.get("declared_by_plugins") or []),
                    "action": "通常只会阻断依赖该连接器的动作，不一定影响整个插件运行",
                }
            )

    for server in mcp_servers:
        if server.get("origin") == "plugin" and not server.get("plugin_id"):
            continue
        if server.get("origin") == "plugin" and server.get("visible_in_session"):
            recommendations.append(
                {
                    "severity": "info",
                    "area": "mcp",
                    "subject": server["id"],
                    "reason": "插件声明的 MCP 在提供的会话快照中可见",
                    "evidence": server.get("plugin_id") or "",
                    "action": "只在当前线程确实需要这个插件工作流时保持启用",
                }
            )

    return recommendations


def summarize_session(session_snapshot: JsonDict) -> JsonDict:
    tools = session_snapshot.get("tools") or []
    skills = session_snapshot.get("skills") or []
    tool_namespaces = unique_sorted(
        [
            str(tool.get("namespace") or tool.get("tool_namespace") or "")
            for tool in tools
            if isinstance(tool, dict)
        ]
    )
    return {
        "snapshot_provided": bool(session_snapshot),
        "tool_count": len(tools),
        "skill_count": len(skills),
        "tool_namespaces": tool_namespaces,
    }


def build_inventory(
    home: Path | None = None,
    session_snapshot: JsonDict | None = None,
) -> JsonDict:
    home = (home or Path.home()).expanduser()
    session_snapshot = session_snapshot or {}
    codex_home = home / ".codex"
    config_path = codex_home / "config.toml"
    config = read_toml(config_path)

    plugins, app_declarations, plugin_mcp_declarations, plugin_skills = collect_plugins(
        codex_home, config
    )
    standalone_skills = collect_standalone_skills(home)
    skills = sorted(plugin_skills + standalone_skills, key=lambda skill: skill["name"])
    mark_visible_skills(skills, session_snapshot)

    apps = collect_apps(codex_home, config, app_declarations, session_snapshot)
    mcp_servers = collect_mcp_servers(config, plugin_mcp_declarations, session_snapshot)
    marketplaces = collect_marketplaces(codex_home, config)
    recommendations = build_recommendations(plugins, apps, mcp_servers)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "home": str(home),
        "codex_home": str(codex_home),
        "config_path": str(config_path),
        "counts": {
            "plugins": len(plugins),
            "apps": len(apps),
            "mcp_servers": len(mcp_servers),
            "skills": len(skills),
            "marketplaces": len(marketplaces),
        },
        "session": summarize_session(session_snapshot),
        "marketplaces": marketplaces,
        "plugins": plugins,
        "apps": apps,
        "mcp_servers": mcp_servers,
        "skills": skills,
        "duplicates": {
            "plugins_by_name": duplicate_plugins(plugins),
        },
        "recommendations": recommendations,
        "notes": [
            "磁盘态和配置态来自本地文件直接扫描。",
            "当前会话可见态只对 --session-snapshot 中提供的工具和技能精确。",
            "Codex Host 目前没有公开的本地 API 让脚本直接读取模型上下文窗口。",
            "技能数量包含磁盘上找到的所有 SKILL.md，包括插件内部的嵌套辅助技能；界面计数可能使用不同过滤规则。",
        ],
    }


def yes_no_unknown(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未知"


def label(value: Any, mapping: dict[str, str]) -> str:
    return mapping.get(str(value), str(value))


CONFIG_STATE_LABELS = {
    "enabled": "已启用",
    "disabled": "已禁用",
    "not-configured": "未配置",
}

SOURCE_CLASS_LABELS = {
    "plugin-cache": "插件缓存",
    "local-marketplace": "本地市场",
    "unknown": "未知",
}

UI_BUCKET_LABELS = {
    "plugin-page-candidate": "可能显示在插件页",
    "legacy-cache-or-hidden": "旧缓存或界面隐藏",
    "marketplace-local-or-hidden": "本地市场或界面隐藏",
    "unknown": "未知",
}

ORIGIN_LABELS = {
    "config": "配置",
    "plugin": "插件声明",
    "plugin-declaration": "插件声明",
    "app-tool-cache": "App 工具缓存",
    "plugin-declaration+app-tool-cache": "插件声明 + App 工具缓存",
    "unknown": "未知",
    "system": "系统技能",
    "standalone": "独立技能",
    "agents": "Agents 技能",
    "disk-local-marketplace": "磁盘本地市场",
}

SERVER_TYPE_LABELS = {
    "command": "本地命令",
    "http": "HTTP",
    "unknown": "未知",
}

SEVERITY_LABELS = {
    "review": "需检查",
    "info": "提示",
}

AREA_LABELS = {
    "plugin": "插件",
    "app": "App/连接器",
    "mcp": "MCP",
}


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        clean = [str(cell).replace("\n", " ").replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(clean) + " |")
    return "\n".join(lines)


def render_markdown(inventory: JsonDict) -> str:
    lines: list[str] = []
    counts = inventory["counts"]
    session = inventory["session"]
    lines.append("# Codex Context Doctor 上下文审计报告")
    lines.append("")
    lines.append(f"- 生成时间：`{inventory['generated_at']}`")
    lines.append(f"- Codex 目录：`{inventory['codex_home']}`")
    lines.append(f"- 配置文件：`{inventory['config_path']}`")
    lines.append(
        f"- 统计：插件 `{counts['plugins']}`，App/连接器 `{counts['apps']}`，MCP 服务器 `{counts['mcp_servers']}`，技能 `{counts['skills']}`，市场源 `{counts['marketplaces']}`"
    )
    lines.append(
        f"- 会话快照：`{yes_no_unknown(session['snapshot_provided'])}`；工具 `{session['tool_count']}`，技能 `{session['skill_count']}`"
    )
    lines.append("")
    lines.append("## 阅读说明")
    lines.append("")
    lines.append(
        "这份报告把磁盘安装态、`config.toml` 配置态、App 工具缓存、可选的当前会话可见态分开。"
        "前三类来自本地文件，当前会话可见态只有在提供 `--session-snapshot` 时才是精确的。"
    )
    lines.append("")

    duplicates = inventory["duplicates"]["plugins_by_name"]
    if duplicates:
        lines.append("## 重名插件")
        lines.append("")
        rows = [[name, ", ".join(ids)] for name, ids in duplicates.items()]
        lines.append(md_table(["插件名", "实例"], rows))
        lines.append("")

    recommendations = inventory.get("recommendations") or []
    if recommendations:
        lines.append("## 上下文卫生建议")
        lines.append("")
        lines.append(
            md_table(
                ["级别", "范围", "对象", "原因", "建议动作"],
                [
                    [
                        label(item.get("severity", ""), SEVERITY_LABELS),
                        label(item.get("area", ""), AREA_LABELS),
                        item.get("subject", ""),
                        item.get("reason", ""),
                        item.get("action", ""),
                    ]
                    for item in recommendations
                ],
            )
        )
        lines.append("")

    lines.append("## 市场源")
    lines.append("")
    lines.append(
        md_table(
            ["名称", "来源", "源类型", "路径存在", "路径"],
            [
                [
                    item.get("name", ""),
                    label(item.get("origin", ""), ORIGIN_LABELS),
                    label(item.get("source_type", ""), {"local": "本地"}),
                    yes_no_unknown(item.get("path_exists")),
                    item.get("source", ""),
                ]
                for item in inventory["marketplaces"]
            ],
        )
    )
    lines.append("")

    lines.append("## 插件")
    lines.append("")
    lines.append(
        md_table(
            [
                "插件 ID",
                "显示名",
                "版本",
                "配置",
                "来源",
                "界面判断",
                "技能/App/MCP",
                "路径",
            ],
            [
                [
                    item["id"],
                    item["display_name"],
                    item["version"],
                    label(item["config_state"], CONFIG_STATE_LABELS),
                    label(item["source_class"], SOURCE_CLASS_LABELS),
                    label(item["ui_bucket"], UI_BUCKET_LABELS),
                    f"{item['skill_count']}/{item['app_count']}/{item['mcp_count']}",
                    item["path"],
                ]
                for item in inventory["plugins"]
            ],
        )
    )
    lines.append("")

    lines.append("## App 和连接器")
    lines.append("")
    lines.append(
        md_table(
            [
                "连接器 ID",
                "名称",
                "配置",
                "来源",
                "缓存工具数",
                "声明它的插件",
                "会话可见",
            ],
            [
                [
                    app["connector_id"],
                    app.get("name", ""),
                    yes_no_unknown(app.get("config_enabled")),
                    label(app.get("origin", ""), ORIGIN_LABELS),
                    app.get("cached_tool_count", 0),
                    ", ".join(app.get("declared_by_plugins") or []),
                    yes_no_unknown(app.get("visible_in_session")),
                ]
                for app in inventory["apps"]
            ],
        )
    )
    lines.append("")

    lines.append("## MCP 服务器")
    lines.append("")
    lines.append(
        md_table(
            ["ID", "名称", "来源", "配置", "类型", "插件", "会话可见"],
            [
                [
                    mcp["id"],
                    mcp["name"],
                    label(mcp["origin"], ORIGIN_LABELS),
                    yes_no_unknown(mcp.get("config_enabled")),
                    label(mcp.get("server_type", ""), SERVER_TYPE_LABELS),
                    mcp.get("plugin_id") or "",
                    yes_no_unknown(mcp.get("visible_in_session")),
                ]
                for mcp in inventory["mcp_servers"]
            ],
        )
    )
    lines.append("")

    lines.append("## 技能")
    lines.append("")
    lines.append(
        md_table(
            ["名称", "来源", "插件/根目录", "会话可见", "路径"],
            [
                [
                    skill["name"],
                    label(skill["origin"], ORIGIN_LABELS),
                    skill.get("plugin_id") or skill.get("skill_root") or "",
                    yes_no_unknown(skill.get("visible_in_session")),
                    skill["path"],
                ]
                for skill in inventory["skills"]
            ],
        )
    )
    lines.append("")

    lines.append("## 会话工具命名空间")
    lines.append("")
    if session["tool_namespaces"]:
        for namespace in session["tool_namespaces"]:
            lines.append(f"- `{namespace}`")
    else:
        lines.append("- 未提供会话快照。")
    lines.append("")

    lines.append("## 边界")
    lines.append("")
    for note in inventory["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def load_session_snapshot(path: Path | None) -> JsonDict:
    if not path:
        return {}
    return read_json(path.expanduser())


def session_snapshot_template() -> JsonDict:
    return {
        "tools": [
            {
                "namespace": "mcp__example",
                "tool": "tool_name",
                "connector_id": "connector_optional_when_known",
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
        description="Audit local Codex plugins, apps, MCP servers, skills, and optional session visibility."
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory to inspect.")
    parser.add_argument("--session-snapshot", type=Path, help="Optional JSON snapshot of tools/skills visible in the current Codex session.")
    parser.add_argument("--json", type=Path, help="Write full inventory JSON to this path.")
    parser.add_argument("--markdown", type=Path, help="Write Markdown report to this path.")
    parser.add_argument("--print-session-snapshot-template", action="store_true", help="Print the optional session snapshot JSON shape and exit.")
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
