---
name: context-doctor
description: 仅当用户明确说 $context-doctor、context-doctor，或要求运行 Context Doctor / 跨平台上下文审计 / 体检插件技能 MCP 时使用。普通编码、泛泛询问插件、随口提到 MCP 时不要使用。
disable-model-invocation: true
---

# Context Doctor

只在手动点名时运行的**跨平台上下文审计**技能。用官方治理入口盘点 **Claude Code 与 Codex** 的插件、MCP、市场源与技能：Codex 的 OpenAI 公共目录按 CLI/Desktop 投影分开，其他 marketplace、插件、MCP 与文件技能归本地共享层。产出一个**自包含、可离线打开、可交互的单文件 HTML 报告**，并附 `inventory.json` 与回退用的 `report.md`。

## 三段式流程（重要）

报告里的「中文用途」需要翻译，但采集脚本不能调模型，所以分三步：**采集 → 翻译 → 二次渲染**。

### ① 采集（默认带会话快照）

先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录。**默认就对照本次会话可见态**：运行前，先把当前会话里你（模型）能看到的工具与技能写成一份精简快照 JSON（格式见下「会话快照」节），存到临时目录（如 `$snapshot`）。然后运行（**采集会逐插件 `details`、逐 MCP 健康检查，约 2–3 分钟，务必给足超时**，例如 Bash 工具 timeout 设到 480000 毫秒）：

```bash
bash "$skill_dir/scripts/run.sh" --session-snapshot "$snapshot"
```

脚本在带时间戳的临时目录写入 `report.html`（主产物）、`inventory.json`、`report.md`，并把待译英文登记进用户级缓存 `~/.cache/context-doctor/translations.json`。短摘要会分别打印 Claude Code、Codex CLI、Codex Desktop、Codex 本地共享的计数、**待译条目数 `待译中文=N`**、缓存路径。

只想看某一个平台时加 `--platform claude` 或 `--platform codex`（默认 both）。确实无可见态可报时（少见）才省略 `--session-snapshot`，报告其余部分照常。

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

- **层级**：Claude Code / Codex CLI / Codex Desktop / Codex 本地共享 tab。CLI 与 Desktop 分别展示 OpenAI 公共目录的本地投影；共享域按市场 → 插件（已装/可装）→ 组件展开，并列出 MCP 与独立文件技能。
- **排行**：最贵技能 / 最贵 agent / 最贵插件，每条标来源插件。**只有明确启用的 Claude 插件计入当前 token 总量与排行**；禁用或启用未知的插件只展示“启用后预计”成本。Codex 全程无 token；MCP 两平台都无成本，不进榜。

## 数据来源（重要）

- Claude Code 与 Codex 的插件 / 市场 / MCP 调各自官方 CLI（`claude plugin/marketplace/mcp`、`codex plugin/mcp`），不直接解析配置文件。Codex CLI 的 `openai-curated` 单列，其他 CLI marketplace、插件与 MCP 归本地共享。
- Codex Desktop 公共目录单独展示：`~/.codex/cache/remote_plugin_catalog/*.json` 只取 `release.skills` 非空的插件，`~/.codex/plugins/cache/openai-curated-remote/` 提供安装证据与完整组件。Desktop 公共目录没有独立开关，缓存中已安装的插件按默认启用记录并显示「已启用」。
- Claude 插件组件与启用后预计 token 成本来自 `claude plugin details`；当前总量、排行与高开销建议只计算 `enabled=true`。Codex 无 details 命令，已装插件优先从 `~/.codex/plugins/cache/<market>/<plugin>/<version>/` 读取清单和组件（无 token）。
- `codex mcp list --json` 返回的插件 MCP 可能只有裸服务名；报告会与已安装插件声明交叉核对，唯一匹配时归入插件，存在歧义时仍保留为独立 MCP。
- 独立技能：两平台都没有列举文件技能的 CLI；Codex 文件技能与共享插件同列为 CLI/Desktop 本地共享层，避免重复计数。

## 会话快照（默认开启）

脚本读不到 Host 的模型上下文窗口，会话可见态只能由「跑这个技能的模型」自报。**默认每次都做**：采集前，你（模型）把当前会话可见的内容写成精简 JSON，再用 `--session-snapshot` 传给脚本（见步骤 ①）。形状（也可用 `--print-session-snapshot-template` 打印）：

```json
{
  "host_platform": "codex",
  "host_surface": "desktop",
  "tools": [{ "namespace": "mcp__<server>", "tool": "<tool>", "source_hint": "<MCP 显示名，可选>" }],
  "skills": [{ "name": "<可见技能名，含插件自带技能>" }]
}
```

约定与边界：

- **`host_platform` 必填**：填你（模型）正在运行的平台（`claude` / `codex`）。
- **Codex 的 `host_surface` 必填**：填 `desktop` 或 `cli`。只有对应的公共目录投影和「Codex 本地共享」会映射会话可见态；缺失时 CLI/Desktop 都显示「—」。Claude 可省略此字段。
- 只列**可见工具的命名空间/工具名**与**可见技能名**（含插件自带技能，便于给插件组件标可见）；快照必须精简——**不要**写工具 schema、技能描述或长 prompt。
- 某些连接器（如 claude.ai 的 HyperFrames）工具命名空间是 UUID，与 `mcp list` 的显示名对不上：给这类工具加 `source_hint`（填该 MCP 的显示名），脚本会按 `source_hint` 兜底匹配。
- 技能按名字匹配（自动兼容 `插件:技能` 与裸名），MCP 按 `source_hint`/命名空间匹配，两者跨平台通用。

## /frontend-design 协作

HTML 的视觉来自模板 `scripts/report_template.html`（用 `/frontend-design` 设计的一次性产物），脚本每次把 JSON 注入模板的 `/*__INVENTORY_JSON__*/` 占位符。**要改报告外观就改模板，不要改 Python 脚本**；模板自带 mock 数据，可直接用浏览器预览。

## 输出规则

默认输出到临时目录。只有用户要求持久保存时，才把自包含的 `report.html`（整文件即可）复制到当前工作区的 `outputs/` 目录。
