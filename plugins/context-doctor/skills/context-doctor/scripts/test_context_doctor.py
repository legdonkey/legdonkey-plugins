#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import context_doctor as doctor


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def catalog_plugin(
    name: str,
    *,
    skills: int = 1,
    description: str = "完整描述",
    display_name: str | None = None,
    version: str = "1.0.0",
) -> dict:
    return {
        "name": name,
        "installation_policy": "AVAILABLE",
        "release": {
            "display_name": display_name or name.replace("-", " ").title(),
            "version": version,
            "description": description,
            "interface": {"short_description": "短描述"},
            "skills": [{"name": f"skill-{i}"} for i in range(skills)],
            "app_ids": ["connector_demo"],
        },
    }


class CodexDesktopRemotePluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = Path(self.tempdir.name)
        self.cache = {"version": 1, "entries": {}}

    def write_catalog(self, plugins: list[dict], name: str = "catalog.json") -> Path:
        path = self.home / ".codex" / "cache" / "remote_plugin_catalog" / name
        write_json(path, {"schema_version": 1, "plugins": plugins})
        return path

    def write_cached_plugin(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "本地清单描述",
    ) -> Path:
        root = (
            self.home
            / ".codex"
            / "plugins"
            / "cache"
            / "openai-curated-remote"
            / name
            / version
        )
        write_json(
            root / ".codex-plugin" / "plugin.json",
            {
                "name": name,
                "version": version,
                "description": description,
                "skills": "./skills/",
            },
        )
        skill_dir = root / "skills" / "example"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: example\ndescription: 示例技能\n---\n",
            encoding="utf-8",
        )
        return root

    def test_remote_catalog_keeps_only_skill_plugins_and_full_description(self) -> None:
        self.write_catalog(
            [
                catalog_plugin("with-skill", description="应使用这段完整描述"),
                catalog_plugin("app-only", skills=0),
            ]
        )

        remote, notes = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)

        self.assertEqual([p["name"] for p in remote], ["with-skill"])
        self.assertEqual(remote[0]["description"], "应使用这段完整描述")
        self.assertEqual(remote[0]["skill_count"], 1)
        self.assertEqual(remote[0]["app_count"], 1)
        self.assertIn(remote[0]["description_key"], self.cache["entries"])
        self.assertEqual(notes, [])

    def test_remote_catalog_keeps_first_duplicate_name(self) -> None:
        self.write_catalog(
            [
                catalog_plugin("metabase", description="新版本", version="2.0.0"),
                catalog_plugin("metabase", description="旧版本", version="1.0.0"),
            ]
        )

        remote, _ = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)

        self.assertEqual(len(remote), 1)
        self.assertEqual(remote[0]["description"], "新版本")
        self.assertEqual(remote[0]["version"], "2.0.0")

    def test_cached_plugin_becomes_installed_with_unknown_enabled_state(self) -> None:
        self.write_catalog(
            [catalog_plugin("demo", description="远程完整描述", display_name="Demo Desktop")]
        )
        self.write_cached_plugin("demo")

        remote, _ = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)
        plugin = next(p for p in remote if p["name"] == "demo")

        self.assertTrue(plugin["installed"])
        self.assertIsNone(plugin["enabled"])
        self.assertEqual(plugin["install_state_source"], "desktop-cache")
        self.assertEqual(plugin["display_name"], "Demo Desktop")
        self.assertEqual(plugin["description"], "远程完整描述")
        self.assertEqual(plugin["components"]["skills"][0]["name"], "demo:example")

    def test_newest_cached_manifest_wins(self) -> None:
        old = self.write_cached_plugin("demo", version="1.0.0")
        new = self.write_cached_plugin("demo", version="2.0.0")
        os.utime(old / ".codex-plugin" / "plugin.json", (1, 1))
        os.utime(new / ".codex-plugin" / "plugin.json", (2, 2))

        remote, _ = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)
        plugin = next(p for p in remote if p["name"] == "demo")

        self.assertEqual(plugin["real_version"], "2.0.0")

    def test_cache_is_collected_when_catalog_is_missing(self) -> None:
        self.write_cached_plugin("cache-only")

        remote, notes = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)

        self.assertEqual([p["name"] for p in remote], ["cache-only"])
        self.assertTrue(any("catalog" in note for note in notes))

    def test_merge_preserves_same_name_from_different_marketplaces(self) -> None:
        section = {
            "plugins": [],
            "available_plugins": [
                {
                    "id": "demo@openai-curated",
                    "name": "demo",
                    "marketplace": "openai-curated",
                    "installed": False,
                }
            ],
            "marketplaces": [],
        }
        remote = [
            {
                "id": "demo@openai-curated-remote",
                "name": "demo",
                "marketplace": "openai-curated-remote",
                "installed": True,
            }
        ]

        doctor.merge_codex_remote_plugins(section, remote, self.home)

        self.assertEqual(len(section["plugins"]), 1)
        self.assertEqual(len(section["available_plugins"]), 1)
        self.assertEqual(section["available_plugins"][0]["id"], "demo@openai-curated")
        self.assertEqual(section["marketplaces"][-1]["name"], "openai-curated-remote")

    def test_merge_replaces_exact_remote_id(self) -> None:
        section = {
            "plugins": [],
            "available_plugins": [
                {
                    "id": "demo@openai-curated-remote",
                    "name": "demo",
                    "marketplace": "openai-curated-remote",
                    "installed": False,
                    "source": "cli",
                }
            ],
            "marketplaces": [],
        }
        remote = [
            {
                "id": "demo@openai-curated-remote",
                "name": "demo",
                "marketplace": "openai-curated-remote",
                "installed": True,
                "source": "desktop-cache",
            }
        ]

        doctor.merge_codex_remote_plugins(section, remote, self.home)

        self.assertEqual(section["available_plugins"], [])
        self.assertEqual(len(section["plugins"]), 1)
        self.assertEqual(section["plugins"][0]["source"], "desktop-cache")

    def test_report_template_has_unknown_enabled_installed_badge(self) -> None:
        template = Path(doctor.__file__).with_name("report_template.html").read_text(encoding="utf-8")

        self.assertIn('pl.enabled===true', template)
        self.assertIn('已安装</span>', template)

    def test_report_template_shows_remote_catalog_component_counts(self) -> None:
        template = Path(doctor.__file__).with_name("report_template.html").read_text(encoding="utf-8")

        self.assertIn('pl.skill_count', template)
        self.assertIn('Skills ${pl.skill_count}', template)
        self.assertIn('Apps ${pl.app_count}', template)

    def test_collect_codex_includes_cli_and_desktop_remote_plugins(self) -> None:
        self.write_catalog(
            [catalog_plugin("demo", description="远程完整描述", display_name="Demo Desktop")]
        )
        self.write_cached_plugin("demo")

        def fake_cli(args, **_kwargs):
            if args[:3] == ["codex", "plugin", "list"]:
                return {
                    "installed": [],
                    "available": [
                        {
                            "pluginId": "demo@openai-curated",
                            "name": "demo",
                            "marketplaceName": "openai-curated",
                            "version": "1.0.0",
                            "source": {},
                        }
                    ],
                }
            if args[:4] == ["codex", "plugin", "marketplace", "list"]:
                return {
                    "marketplaces": [
                        {
                            "name": "openai-curated",
                            "root": "/tmp/openai-curated",
                        }
                    ]
                }
            if args[:3] == ["codex", "mcp", "list"]:
                return []
            self.fail(f"未预期的 CLI 调用：{args}")

        with patch.object(doctor, "cli_available", return_value=True), patch.object(
            doctor, "run_cli_json", side_effect=fake_cli
        ):
            section = doctor.collect_codex(self.home, self.home, self.cache)

        self.assertEqual(
            {plugin["id"] for plugin in section["plugins"]},
            {"demo@openai-curated-remote"},
        )
        self.assertIn(
            "demo@openai-curated",
            {plugin["id"] for plugin in section["available_plugins"]},
        )
        self.assertIn(
            "openai-curated-remote",
            {market["name"] for market in section["marketplaces"]},
        )

    def test_reassigns_uniquely_declared_bare_mcp_to_installed_plugin(self) -> None:
        section = {
            "platform": "codex",
            "plugins": [
                {
                    "id": "github@openai-curated",
                    "name": "github",
                    "marketplace": "openai-curated",
                    "components": {
                        "mcp": [
                            {
                                "name": "github",
                                "server_type": "http",
                                "target": "https://api.githubcopilot.com/mcp/",
                            }
                        ]
                    },
                }
            ],
            "mcp_servers": [
                {
                    "name": "github",
                    "server_type": "streamable_http",
                    "target": "https://api.githubcopilot.com/mcp/",
                    "auth_status": "bearer_token",
                },
                {"name": "node_repl", "server_type": "stdio", "target": "node_repl"},
            ],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual([server["name"] for server in section["mcp_servers"]], ["node_repl"])
        component = section["plugins"][0]["components"]["mcp"][0]
        self.assertEqual(component["server_type"], "streamable_http")
        self.assertEqual(component["status"], "bearer_token")
        self.assertEqual(component["full_name"], "github")

    def test_keeps_ambiguous_bare_mcp_independent_without_owner_evidence(self) -> None:
        section = {
            "platform": "codex",
            "plugins": [
                {
                    "id": "plugin-a@market-a",
                    "name": "plugin-a",
                    "marketplace": "market-a",
                    "components": {"mcp": [{"name": "shared", "target": "node"}]},
                },
                {
                    "id": "plugin-b@market-b",
                    "name": "plugin-b",
                    "marketplace": "market-b",
                    "components": {"mcp": [{"name": "shared", "target": "node"}]},
                },
            ],
            "mcp_servers": [{"name": "shared", "server_type": "stdio", "target": "node"}],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual([server["name"] for server in section["mcp_servers"]], ["shared"])
        self.assertNotIn("full_name", section["plugins"][0]["components"]["mcp"][0])
        self.assertNotIn("full_name", section["plugins"][1]["components"]["mcp"][0])

    def test_uses_source_cwd_to_disambiguate_bare_mcp_owner(self) -> None:
        section = {
            "platform": "codex",
            "plugins": [
                {
                    "id": "plugin-a@market-a",
                    "name": "plugin-a",
                    "marketplace": "market-a",
                    "components": {"mcp": [{"name": "shared", "target": "node"}]},
                },
                {
                    "id": "plugin-b@market-b",
                    "name": "plugin-b",
                    "marketplace": "market-b",
                    "components": {"mcp": [{"name": "shared", "target": "node"}]},
                },
            ],
            "mcp_servers": [
                {
                    "name": "shared",
                    "server_type": "stdio",
                    "target": "node",
                    "source_cwd": "/Users/demo/.codex/plugins/cache/market-b/plugin-b/1.0.0/.",
                }
            ],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual(section["mcp_servers"], [])
        self.assertNotIn("full_name", section["plugins"][0]["components"]["mcp"][0])
        self.assertEqual(
            section["plugins"][1]["components"]["mcp"][0]["full_name"],
            "shared",
        )

    def test_uses_target_to_disambiguate_bare_mcp_owner(self) -> None:
        section = {
            "platform": "codex",
            "plugins": [
                {
                    "id": "plugin-a@market-a",
                    "name": "plugin-a",
                    "marketplace": "market-a",
                    "components": {
                        "mcp": [{"name": "shared-http", "target": "https://a.example/mcp"}]
                    },
                },
                {
                    "id": "plugin-b@market-b",
                    "name": "plugin-b",
                    "marketplace": "market-b",
                    "components": {
                        "mcp": [{"name": "shared-http", "target": "https://b.example/mcp"}]
                    },
                },
            ],
            "mcp_servers": [
                {
                    "name": "shared-http",
                    "server_type": "streamable_http",
                    "target": "https://b.example/mcp",
                    "auth_status": "oauth",
                }
            ],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual(section["mcp_servers"], [])
        self.assertNotIn("full_name", section["plugins"][0]["components"]["mcp"][0])
        self.assertEqual(
            section["plugins"][1]["components"]["mcp"][0]["full_name"],
            "shared-http",
        )

    def test_does_not_reassign_bare_mcp_by_manifest_on_claude(self) -> None:
        section = {
            "platform": "claude",
            "plugins": [
                {
                    "id": "plugin-a@market-a",
                    "name": "plugin-a",
                    "marketplace": "market-a",
                    "components": {"mcp": [{"name": "shared", "target": "node"}]},
                }
            ],
            "mcp_servers": [{"name": "shared", "server_type": "stdio", "target": "node"}],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual([server["name"] for server in section["mcp_servers"]], ["shared"])
        self.assertNotIn("full_name", section["plugins"][0]["components"]["mcp"][0])

    def test_keeps_legacy_prefixed_mcp_reassignment_on_claude(self) -> None:
        section = {
            "platform": "claude",
            "plugins": [
                {
                    "id": "plugin-a@market-a",
                    "name": "plugin-a",
                    "components": {"mcp": [{"name": "internal", "target": "node"}]},
                }
            ],
            "mcp_servers": [
                {
                    "name": "plugin:plugin-a:internal",
                    "server_type": "stdio",
                    "target": "node",
                }
            ],
        }

        doctor.reassign_plugin_mcps(section)

        self.assertEqual(section["mcp_servers"], [])
        self.assertEqual(
            section["plugins"][0]["components"]["mcp"][0]["full_name"],
            "plugin:plugin-a:internal",
        )

    def test_collect_codex_preserves_mcp_source_cwd_for_owner_matching(self) -> None:
        def fake_cli(args, **_kwargs):
            if args[:3] == ["codex", "plugin", "list"]:
                return {"installed": [], "available": []}
            if args[:4] == ["codex", "plugin", "marketplace", "list"]:
                return {"marketplaces": []}
            if args[:3] == ["codex", "mcp", "list"]:
                return [
                    {
                        "name": "shared",
                        "enabled": True,
                        "transport": {
                            "type": "stdio",
                            "command": "node",
                            "cwd": "/Users/demo/.codex/plugins/cache/market/plugin/1.0.0/.",
                        },
                        "auth_status": "unsupported",
                    }
                ]
            self.fail(f"未预期的 CLI 调用：{args}")

        with patch.object(doctor, "cli_available", return_value=True), patch.object(
            doctor, "run_cli_json", side_effect=fake_cli
        ):
            section = doctor.collect_codex(self.home, self.home, self.cache)

        self.assertEqual(
            section["mcp_servers"][0]["source_cwd"],
            "/Users/demo/.codex/plugins/cache/market/plugin/1.0.0/.",
        )


class PluginComponentDescTests(unittest.TestCase):
    """read_plugin_component_descs：details 只给组件名，描述得从插件目录里翻出来。"""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def write_md(self, rel: str, description: str, name: str | None = None) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        front = [f"name: {name}"] if name else []
        front.append(f"description: {description}")
        path.write_text("---\n" + "\n".join(front) + "\n---\n正文\n", encoding="utf-8")

    def write_manifest(self, **fields: object) -> None:
        write_json(self.root / ".claude-plugin" / "plugin.json", {"name": "demo", **fields})

    def test_default_skills_dir_scans_one_level(self) -> None:
        """官方默认位置是 `skills/<name>/SKILL.md` 一层，分层放的不会被自动发现。"""
        self.write_md("skills/flat/SKILL.md", "一层技能")
        self.write_md("skills/engineering/tdd/SKILL.md", "分层技能")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["flat"], "一层技能")
        self.assertNotIn("tdd", descs["skills"])

    def test_manifest_skills_add_to_default_scan(self) -> None:
        """`skills` 字段是追加语义：默认目录照扫，manifest 列出的一并加载。"""
        self.write_md("skills/flat/SKILL.md", "一层技能")
        self.write_md("skills/engineering/tdd/SKILL.md", "测试驱动开发")
        self.write_md("skills/deprecated/tdd/SKILL.md", "废弃版")
        self.write_manifest(skills=["./skills/engineering/tdd"])
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["flat"], "一层技能")
        # 只有 manifest 点名的那个被加载，同名的 deprecated 版不参与
        self.assertEqual(descs["skills"]["tdd"], "测试驱动开发")

    def test_manifest_skills_can_point_at_parent_dir(self) -> None:
        """manifest 条目也可以指向装着若干技能的父目录。"""
        self.write_md("skills/engineering/tdd/SKILL.md", "测试驱动开发")
        self.write_md("skills/engineering/triage/SKILL.md", "分诊")
        self.write_manifest(skills="./skills/engineering")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["tdd"], "测试驱动开发")
        self.assertEqual(descs["skills"]["triage"], "分诊")

    def test_manifest_paths_outside_plugin_are_ignored(self) -> None:
        self.write_md("skills/ok/SKILL.md", "正常技能")
        self.write_manifest(skills=["../外面", "/etc"])
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"], {"ok": "正常技能"})

    def test_commands_count_as_skills(self) -> None:
        """`claude plugin details` 把 commands 也算进 Skills 一栏。"""
        self.write_md("commands/review.md", "审查改动")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["review"], "审查改动")
        # commands 无 frontmatter name 时不能拿父目录名建键
        self.assertNotIn("commands", descs["skills"])

    def test_manifest_commands_replace_default_dir(self) -> None:
        """`commands` 是替换语义：manifest 写了就不再扫默认 commands/。"""
        self.write_md("commands/review.md", "默认目录里的")
        self.write_md("extras/deploy.md", "自定义路径里的")
        self.write_manifest(commands=["./extras/deploy.md"])
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"], {"deploy": "自定义路径里的"})

    def test_same_name_across_component_types_not_mixed(self) -> None:
        """同名的 skill 与 agent 各归各的，混表会让 agent 领到 skill 的描述。"""
        self.write_md("skills/rescue/SKILL.md", "技能版救援")
        self.write_md("agents/rescue.md", "Agent 版救援")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["rescue"], "技能版救援")
        self.assertEqual(descs["agents"]["rescue"], "Agent 版救援")

    def test_unlisted_sibling_skill_never_wins(self) -> None:
        """真实布局：deprecated/tdd 与 engineering/tdd 同深度，只有 manifest 点名的算数。

        递归扫描时按字母序 deprecated 会抢先占位，这正是这次要根治的错配。
        """
        self.write_md("skills/deprecated/tdd/SKILL.md", "废弃版")
        self.write_md("skills/engineering/tdd/SKILL.md", "正牌版")
        self.write_manifest(skills=["./skills/engineering/tdd"])
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["tdd"], "正牌版")

    def test_explicit_skill_name_also_indexed(self) -> None:
        """SKILL.md 的 frontmatter name 与目录名不同时，两个键都能查到。"""
        self.write_md("skills/dir-name/SKILL.md", "带前缀的技能", name="plugin:dir-name")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"]["dir-name"], "带前缀的技能")
        self.assertEqual(descs["skills"]["plugin:dir-name"], "带前缀的技能")

    def test_dependency_trees_are_not_scanned(self) -> None:
        """依赖树 / 版本库里的同名组件文件不该被当成插件组件。"""
        self.write_md("skills/node_modules/pkg/tdd/SKILL.md", "依赖树里的假货")
        self.write_md("skills/.git/tdd/SKILL.md", "版本库里的假货")
        self.write_md("node_modules/pkg/skills/tdd/SKILL.md", "根依赖树里的假货")
        descs = doctor.read_plugin_component_descs(str(self.root))
        self.assertEqual(descs["skills"], {})

    def test_missing_path_returns_empty_groups(self) -> None:
        descs = doctor.read_plugin_component_descs("")
        self.assertEqual(descs, {"skills": {}, "agents": {}})
        descs = doctor.read_plugin_component_descs(str(self.root / "不存在"))
        self.assertEqual(descs, {"skills": {}, "agents": {}})


if __name__ == "__main__":
    unittest.main()
