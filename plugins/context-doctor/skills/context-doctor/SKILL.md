---
name: context-doctor
description: 仅当用户明确说 $context-doctor、context-doctor，或要求运行 Context Doctor / 跨平台上下文审计 / 体检插件技能 MCP 时使用。普通编码、泛泛询问插件、随口提到 MCP 时不要使用。
disable-model-invocation: true
---

# Context Doctor

只在手动点名时运行的**跨平台上下文审计**技能。用各平台官方 CLI 治理命令盘点 **Claude Code 与 Codex** 的插件、MCP、市场源；技能因两平台都没有 CLI（官方设计为文件式）而扫描技能目录。产出一个**自包含、可离线打开、可交互的单文件 HTML 报告**（市场 → 插件 → 组件层级树 + token 占用 + 最贵组件排行），并附 `inventory.json` 与回退用的 `report.md`。

## 三段式流程（重要）

报告里的「中文用途」需要翻译，但采集脚本不能调模型，所以分三步：**采集 → 翻译 → 二次渲染**。

### ① 采集

先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录，再运行（**采集会逐插件 `details`、逐 MCP 健康检查，约 2–3 分钟，务必给足超时**，例如 Bash 工具 timeout 设到 480000 毫秒）：

```bash
bash "$skill_dir/scripts/run.sh"
```

脚本在带时间戳的临时目录写入 `report.html`（主产物）、`inventory.json`、`report.md`，并把待译英文登记进用户级缓存 `~/.cache/context-doctor/translations.json`。短摘要会打印各平台「已装/可装/市场/MCP/技能」计数、**待译条目数 `待译中文=N`**、缓存路径。

只想看某一个平台时加 `--platform claude` 或 `--platform codex`（默认 both）。

### ② 翻译（仅当 `待译中文 > 0`）

中文用途经缓存翻译，缺失时报告回退英文。若摘要显示待译 > 0：

1. Read 缓存文件（摘要里的「翻译缓存」路径），取出 `entries` 里所有 `zh` 为空的条目的 `{key, src}`。
2. 条目多时（>30）用 **`superpowers:dispatching-parallel-agents`** 提效：把待译条目按每批约 40 条**拆批**，**并行**派多个 subagent，每个只把自己那批的 `src` 译成简体中文、以 `{key: 中文}` 形式**返回**（subagent 不写文件，避免并发写冲突）；主流程合并所有返回。条目少时直接自己译。
3. 把译文写回缓存：**只填空的 `zh`，不动已填的、不改 `key`/`src`**。缓存只增不删，下次命中不重译。

### ③ 二次渲染

翻译写回后，重渲 HTML（很快，不重新采集）：

```bash
python3 -B "$skill_dir/scripts/context_doctor.py" --render-only \
  --json /path/to/inventory.json --html /path/to/report.html
```

对话里只返回输出路径和短摘要，提示「浏览器打开 report.html」。除非用户明确要求，不要把完整报告贴进聊天。

## 报告内容与边界

- **层级**：平台 tab → 市场 → 插件（已装/可装）→ 组件（skills/agents/hooks/mcp/lsp/apps）。已装插件展开有 token 占用条；可装插件只有**中文用途 + 热度 + 直达源码链接**，成本标「装后可见」（未装无法展开 details，CLI 报 not found）。
- **排行**：最贵技能 / 最贵 agent / 最贵插件，每条标来源插件。**只有 Claude 有 token 成本**；Codex 全程无 token（组件来自本地清单，仅列名）；MCP 两平台都无成本，不进榜。报告「审计边界」区会显式说明。

## 数据来源（重要）

- 插件 / 市场 / MCP：调各平台官方 CLI（`claude plugin/marketplace/mcp`、`codex plugin/mcp`），不读配置文件。某平台 CLI 不在 PATH 时自动跳过并标注。
- Claude 插件组件与 token 成本来自 `claude plugin details`（逐插件、并发调用）。Codex 无 details 命令，改读插件本地目录的 `.codex-plugin/plugin.json` 清单 + 扫 `skills/` 目录得组件清单（无 token）。
- 技能：两平台都没有列举技能的 CLI（官方设计为文件式），故扫描技能目录。

## 会话快照

脚本读不到 Host 的模型上下文窗口。若用户明确要求判断当前会话可见态，先在临时目录创建一个精简 JSON，只含可见工具命名空间、工具名和技能名，再运行：

```bash
bash "$skill_dir/scripts/run.sh" --session-snapshot /path/to/session-snapshot.json
```

快照必须精简：不要写工具 schema、技能描述或长 prompt。会话可见态仅对宿主平台有意义。

某些连接器（如 claude.ai 的 HyperFrames）工具命名空间是 UUID，与 `claude mcp list` 给的显示名对不上，按命名空间前缀匹配会漏判。给这类工具在快照里加 `source_hint`（填该 MCP 的显示名），脚本会按 `source_hint` 兜底匹配，正确标成会话可见。

## /frontend-design 协作

HTML 的视觉来自模板 `scripts/report_template.html`（用 `/frontend-design` 设计的一次性产物），脚本每次把 JSON 注入模板的 `/*__INVENTORY_JSON__*/` 占位符。**要改报告外观就改模板，不要改 Python 脚本**；模板自带 mock 数据，可直接用浏览器预览。

## 输出规则

默认输出到临时目录。只有用户要求持久保存时，才把自包含的 `report.html`（整文件即可）复制到当前工作区的 `outputs/` 目录。
