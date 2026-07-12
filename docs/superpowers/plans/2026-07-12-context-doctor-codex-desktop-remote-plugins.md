# Context Doctor Codex 桌面端远程插件修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Context Doctor 同时审计 CLI 插件与 Codex 桌面端远程技能插件，正确识别远程已安装状态，并把 catalog 中所有带 Skills 的插件加入报告。

**Architecture:** 保留现有 CLI 采集链路，新增独立的远程 catalog/缓存采集器。远程缓存只覆盖远程 catalog 内部的同 ID 节点；CLI 与远程同名但不同市场的插件同时保留。HTML 使用友好名称并把安装状态扩展为三态。

**Tech Stack:** Python 3 标准库、`unittest`、Bash、原生 HTML/CSS/JavaScript。

## Global Constraints

- 默认输出和文档使用简体中文。
- 不增加第三方依赖。
- 不提交、不推送、不修改版本号。
- 不读取鉴权信息或远程私有状态。
- catalog 只加入 `release.skills` 非空的插件。
- 远程插件使用 `release.description` 完整描述并进入翻译缓存。
- CLI 与远程同名插件分别保留；仅完整 ID 相同时去重。
- 远程缓存只能证明已安装，`enabled` 必须为 `null`。

---

### Task 1: 建立远程 catalog 与缓存的失败测试

**Files:**
- Create: `plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py`
- Test: `plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py`

**Interfaces:**
- Consumes: 现有 `context_doctor.py`。
- Produces: 对 `collect_codex_desktop_remote_plugins(home, cache)` 和 `merge_codex_remote_plugins(section, remote)` 的行为约束。

- [ ] **Step 1: 创建测试夹具与导入方式**

测试文件直接位于脚本目录，通过 `import context_doctor as doctor` 导入生产代码。使用 `tempfile.TemporaryDirectory()` 构造隔离的 home，并提供以下辅助方法：

```python
def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")

def write_catalog(home: Path, plugins: list[dict], name: str = "catalog.json") -> Path:
    path = home / ".codex/cache/remote_plugin_catalog" / name
    write_json(path, {"schema_version": 1, "plugins": plugins})
    return path

def catalog_plugin(name: str, *, skills: int = 1, description: str = "完整描述") -> dict:
    return {
        "name": name,
        "installation_policy": "AVAILABLE",
        "release": {
            "display_name": name.replace("-", " ").title(),
            "version": "1.0.0",
            "description": description,
            "interface": {"short_description": "短描述"},
            "skills": [{"name": f"skill-{i}"} for i in range(skills)],
            "app_ids": ["connector_demo"],
        },
    }
```

- [ ] **Step 2: 写 catalog 过滤、完整描述和重名测试**

```python
def test_remote_catalog_keeps_only_skill_plugins_and_full_description(self):
    write_catalog(self.home, [
        catalog_plugin("with-skill", description="应使用这段完整描述"),
        catalog_plugin("app-only", skills=0),
    ])
    remote, notes = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)
    self.assertEqual([p["name"] for p in remote], ["with-skill"])
    self.assertEqual(remote[0]["description"], "应使用这段完整描述")
    self.assertIn(remote[0]["description_key"], self.cache["entries"])
```

```python
def test_remote_catalog_keeps_first_duplicate_name(self):
    first = catalog_plugin("metabase", description="新版本")
    second = catalog_plugin("metabase", description="旧版本")
    write_catalog(self.home, [first, second])
    remote, _ = doctor.collect_codex_desktop_remote_plugins(self.home, self.cache)
    self.assertEqual(len(remote), 1)
    self.assertEqual(remote[0]["description"], "新版本")
```

- [ ] **Step 3: 写远程缓存安装状态测试**

构造：

```text
~/.codex/plugins/cache/openai-curated-remote/demo/1.0.0/.codex-plugin/plugin.json
~/.codex/plugins/cache/openai-curated-remote/demo/1.0.0/skills/example/SKILL.md
```

断言 `demo@openai-curated-remote` 为 `installed=true`、`enabled=null`、`install_state_source=desktop-cache`，且组件包含 `demo:example`。

- [ ] **Step 4: 写 CLI/远程合并测试**

```python
def test_merge_preserves_same_name_from_different_marketplaces(self):
    section = {
        "plugins": [],
        "available_plugins": [{
            "id": "demo@openai-curated", "name": "demo",
            "marketplace": "openai-curated", "installed": False,
        }],
        "marketplaces": [],
    }
    remote = [{
        "id": "demo@openai-curated-remote", "name": "demo",
        "marketplace": "openai-curated-remote", "installed": True,
    }]
    doctor.merge_codex_remote_plugins(section, remote)
    self.assertEqual(len(section["plugins"]), 1)
    self.assertEqual(len(section["available_plugins"]), 1)
```

另写一个测试：CLI 与远程完整 ID 都为 `demo@openai-curated-remote` 时，只保留远程记录。

- [ ] **Step 5: 运行测试确认 RED**

Run:

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: `AttributeError`，提示 `collect_codex_desktop_remote_plugins` 或 `merge_codex_remote_plugins` 尚不存在。

---

### Task 2: 实现远程 catalog 与缓存采集器

**Files:**
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py`
- Test: `plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py`

**Interfaces:**
- Produces: `collect_codex_desktop_remote_plugins(home: Path, cache: JsonDict) -> tuple[list[JsonDict], list[str]]`
- Produces: `merge_codex_remote_plugins(section: JsonDict, remote: list[JsonDict]) -> None`

- [ ] **Step 1: 实现最新有效 catalog 选择**

新增常量：

```python
CODEX_REMOTE_MARKETPLACE = "openai-curated-remote"
```

新增 `_latest_valid_remote_catalog(home)`：按文件修改时间倒序读取 `~/.codex/cache/remote_plugin_catalog/*.json`，返回第一个包含 `plugins` 数组的对象；损坏文件跳过。

- [ ] **Step 2: 实现 catalog 节点构造**

遍历 catalog：

```python
release = item.get("release") if isinstance(item.get("release"), dict) else {}
skills = release.get("skills") if isinstance(release.get("skills"), list) else []
if not name or not skills or name in seen:
    continue
description = str(release.get("description") or interface.get("short_description") or "")
```

构造 `name@openai-curated-remote` 可装节点，写入 `display_name`、完整描述、版本、`skill_count`、`app_count`、`installation_policy` 和翻译 key；`components` 保持空组，避免复制 catalog 组件明细。

- [ ] **Step 3: 实现远程缓存扫描**

扫描 `~/.codex/plugins/cache/openai-curated-remote/*/*/.codex-plugin/plugin.json`。每个插件名选择清单修改时间最新的有效版本，用现有 `read_codex_plugin_manifest()` 读取完整组件，并构造：

```python
{
    "id": f"{name}@openai-curated-remote",
    "installed": True,
    "enabled": None,
    "install_state_source": "desktop-cache",
    "source": "desktop-cache",
}
```

catalog 中存在同名条目时沿用 catalog 的 `display_name` 和完整描述；不存在时退回本地 manifest。

- [ ] **Step 4: 实现精确 ID 合并**

`merge_codex_remote_plugins()` 先从 `section.plugins` 与 `section.available_plugins` 中删除和远程记录完整 ID 相同的节点，再按 `installed` 分别追加。不同市场但同名的节点不删除。

发现远程记录时补充：

```python
{
    "name": "openai-curated-remote",
    "repo": "~/.codex/cache/remote_plugin_catalog",
    "source_type": "desktop-remote-catalog",
    "source": "filesystem",
}
```

- [ ] **Step 5: 运行测试确认 GREEN**

Run:

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: 所有远程采集与合并测试通过。

---

### Task 3: 接入 Codex 主采集流程与报告呈现

**Files:**
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py`
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/report_template.html`
- Test: `plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py`

**Interfaces:**
- Consumes: Task 2 的远程采集与合并函数。
- Produces: CLI 与远程双市场 inventory、友好名称和三态安装徽标。

- [ ] **Step 1: 写主流程集成失败测试**

通过 `unittest.mock.patch` 替换 `cli_available`、`run_cli_json`，让 CLI 返回 `demo@openai-curated`，临时 home 返回 `demo@openai-curated-remote`。调用 `collect_codex()` 后断言两者同时存在，远程节点状态正确，marketplace 中包含 `openai-curated-remote`。

- [ ] **Step 2: 在 `collect_codex()` 接入远程采集**

CLI 插件和市场解析完成后，无论 CLI 是否存在，都调用：

```python
remote_plugins, remote_notes = collect_codex_desktop_remote_plugins(home, cache)
merge_codex_remote_plugins(section, remote_plugins)
section["notes"].extend(remote_notes)
```

确保远程缓存/catalog 在 CLI 缺失时仍可生成报告。

- [ ] **Step 3: 更新会话可见态与搜索展示**

现有 `mark_visibility()` 已遍历 `section.plugins`，远程已装节点接入后自动获得组件可见态。模板中的名称改为：

```javascript
const title = pl.display_name || pl.name || pl.id;
```

搜索字段同时包含 `display_name`、`name`、`id` 和 marketplace。

- [ ] **Step 4: 更新三态徽标与说明**

插件徽标改为：

```javascript
pl.installed
  ? (pl.enabled===true
      ? `<span class="badge on">已启用</span>`
      : pl.enabled===false
        ? `<span class="badge off">已禁用</span>`
        : `<span class="badge on">已安装</span>`)
  : `<span class="badge avail">可装</span>`
```

状态说明同步增加“已安装表示桌面缓存证明插件包存在，但启用状态未知”。

- [ ] **Step 5: 运行测试确认 GREEN**

Run:

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: 单元与集成测试全部通过。

---

### Task 4: 更新技能说明、README 与审计边界

**Files:**
- Modify: `plugins/context-doctor/skills/context-doctor/SKILL.md`
- Modify: `plugins/context-doctor/README.md`
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py`

**Interfaces:**
- Produces: 与真实采集行为一致的用户说明。

- [ ] **Step 1: 更新数据来源说明**

明确 Codex 插件有两组来源：

```text
CLI marketplace snapshots：codex plugin list --json --available
桌面远程技能插件：remote_plugin_catalog 中 release.skills 非空的条目 + openai-curated-remote 缓存
```

- [ ] **Step 2: 更新边界与翻译说明**

说明：CLI 与远程同名插件分别保留；远程缓存证明安装但不证明启用；远程技能插件使用 catalog 完整描述；首次可能新增约 85 条翻译。

- [ ] **Step 3: 更新 `build_boundaries()`**

把原“Codex Desktop 不在覆盖范围”的笼统表述改为：远程技能插件的 catalog 与本地安装缓存已覆盖，但账号级实时启用开关、授权状态和纯 App catalog 仍不覆盖。

---

### Task 5: 完整验证与实际数据抽查

**Files:**
- Verify only; no new files.

**Interfaces:**
- Verifies: 新功能、旧功能和仓库约定。

- [ ] **Step 1: 运行单元测试**

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: 全部测试通过，0 failures。

- [ ] **Step 2: 运行 Python 与 Shell 基线检查**

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py --help
shellcheck plugins/context-doctor/skills/context-doctor/scripts/run.sh
```

Expected: 两条命令退出码均为 0，shellcheck 零告警。

- [ ] **Step 3: 运行仓库规定验证**

```bash
shellcheck install-plugins.sh assets/build-svg.sh plugins/*/skills/*/scripts/*.sh
for f in .claude-plugin/marketplace.json .agents/plugins/marketplace.json plugins/*/.claude-plugin/plugin.json plugins/*/.codex-plugin/plugin.json; do python3 -m json.tool "$f" >/dev/null; done
```

Expected: 所有命令退出码为 0。

- [ ] **Step 4: 用真实 home 做 Codex-only 采集抽查**

运行 `context_doctor.py --platform codex --github-stars off` 输出临时 inventory，验证：

- `openai-curated-remote` 远程唯一插件数为 85。
- 8 个远程缓存插件为已安装、`enabled=null`。
- `openai-developers@openai-curated` 与 `openai-developers@openai-curated-remote` 同时存在。
- 纯 App 条目 `asana` 不因 remote catalog 被新增；若 CLI 自身返回，则仍按 CLI 来源保留。
- `description` 使用完整描述。

- [ ] **Step 5: 检查工作区并报告，不提交**

```bash
git diff --check
git status --short
```

Expected: 只有本次设计、计划、测试、实现和文档文件发生变化；不创建 commit。

---

### Task 6: 修复裸名称插件 MCP 的归属

**Files:**
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py`
- Modify: `plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py`

**Interfaces:**
- Consumes: 已安装插件节点的 `components.mcp`、CLI MCP 的 `name`、`target`、`source_cwd`。
- Produces: `reassign_plugin_mcps(section)` 对旧式前缀和新版裸名称都能保守归属。

- [ ] **Step 1: 写唯一裸名称归属失败测试**

构造一个已安装插件声明 `github` MCP，以及独立列表中的裸名称 `github` 和 `node_repl`。调用 `reassign_plugin_mcps()` 后断言 `github` 被移除并补充插件组件，`node_repl` 保留。

- [ ] **Step 2: 写歧义保护失败测试**

构造两个已安装插件都声明 `shared`。当 `source_cwd` 和 `target` 都不能唯一匹配时，断言 `shared` 仍留在独立列表；再构造 `source_cwd` 指向其中一个插件缓存路径，断言只归入该插件。

- [ ] **Step 3: 运行测试确认 RED**

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: 裸名称 MCP 仍在独立列表，新增测试失败。

- [ ] **Step 4: 最小实现候选索引与判定**

在 `reassign_plugin_mcps()` 中建立 `MCP 名称 -> [(插件, 组件)]` 索引。显式前缀优先；裸名称按“唯一声明 → cwd 唯一 → target 唯一”的顺序判定。无法唯一判定时继续加入 `keep`。

采集 Codex MCP 时额外保存：

```python
"source_cwd": str(transport.get("cwd") or "")
```

- [ ] **Step 5: 运行测试确认 GREEN**

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/test_context_doctor.py
```

Expected: 新旧 MCP 归属测试及现有测试全部通过。

### Task 7: 真实报告回归验证

**Files:**
- Verify only; no new files.

**Interfaces:**
- Verifies: 本机 5 个插件 MCP 不再出现在独立列表，真正的非插件 MCP 保留。

- [ ] **Step 1: 重新生成 Codex-only inventory**

```bash
python3 -B plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py \
  --platform codex --github-stars off \
  --json /private/tmp/context-doctor-mcp-owner-inventory.json \
  --html /private/tmp/context-doctor-mcp-owner-report.html
```

- [ ] **Step 2: 核对归属与总数**

断言独立列表只保留 `claudeCodeDocs`、`node_repl`、`openaiDeveloperDocs`；5 个插件 MCP 分别存在于正确插件的 `components.mcp`，且没有重复。

- [ ] **Step 3: 运行完整仓库验证**

重新运行单元测试、`shellcheck`、JSON 清单验证、`git diff --check`，全部退出码为 0。
