<p align="center">
  <img src="assets/banner.svg" alt="context-doctor — 跨平台审计上下文" width="100%">
</p>

# context-doctor

> 一个跨 **Claude Code** 与 **Codex** 的插件（基于开放标准 [skill](https://agentskills.io)）：用各平台**官方 CLI 治理入口**盘点装了哪些插件 / MCP / 市场源，技能走目录治理入口，并给出卫生建议。
>
> ← 返回[仓库总览](../../README.md) ｜ 姊妹插件：[privatize-fork](../privatize-fork/)

装多了之后，常分不清「现在到底加载了什么、谁和谁重名、哪些禁用了还占着 token」。这个插件调 `claude` / `codex` 的官方治理命令，把两个平台的上下文构成摊开给你看，输出一份**自包含、可离线打开、可交互的单文件 HTML 报告**。只在你手动点名时才跑。

报告里有：

- **层级树**：平台 tab → 市场 → 插件（已装/可装）→ 组件（skills/agents/hooks/mcp/lsp/apps），每个组件带中文用途与 token 占用条。
- **最贵组件排行**：最贵技能 / 最贵 agent / 最贵插件（标来源插件；仅 Claude 有 token，Codex 无成本不计入）。
- **会话可见对照**（默认开启）：标出每项在本次会话「真加载了没」——`●` 可见 / `○` 不可见 / `-` 未对照（仅宿主平台有意义）。
- **中文用途**：插件/技能/组件用途经缓存翻译成中文，缺失回退英文。
- **交互**：已装/可装过滤、搜索、暗色/浅色主题切换、可排序排行榜。

## 审计什么

<p align="center">
  <img src="assets/audit-overview.svg" alt="审计什么：插件 / MCP / 市场源 / 技能，两平台一份报告" width="100%">
</p>

| 对象 | 数据来源 |
|------|---------|
| **插件 Plugins** | `claude plugin list --json --available` / `codex plugin list --json --available`：已装 + 可装、版本、启停、**安装范围 scope**、市场、可装热度。Claude 侧另经 `claude plugin details` 取**完整组件清单（skills/agents/hooks/mcp/lsp）与逐组件 token 成本**；Codex 无 details，改读插件本地目录：`.codex-plugin/plugin.json`（版本/用途/源码链接）+ 扫 `skills/` + 读 `.mcp.json`（自带 MCP）/ `.app.json`（apps 连接器）得组件清单（无 token） |
| **市场源 Marketplaces** | `claude plugin marketplace list --json` / `codex plugin marketplace list --json`，保留真实源类型（github / git / 本地等） |
| **MCP 服务器** | `claude mcp list` + 逐个 `claude mcp get` 补类型/scope（只读 Type/Scope，**绝不读 Environment 防泄密**）/ `codex mcp list --json`（含启用 + 鉴权方式）。插件自带的 MCP（`plugin:<插件>:<mcp>`）会归到对应插件名下，不混在独立列表里 |
| **技能 Skills** | 两平台都**没有列举技能的 CLI**（官方设计为文件式），故扫描技能目录（用户级 + 项目级，项目级从当前目录逐级向上到 repo 根）：Claude Code `~/.claude/skills`、项目 `.claude/skills`；Codex `~/.codex/skills`、`~/.agents/skills`、项目 `.codex/skills`、项目 `.agents/skills` |
| **卫生建议** | 同名插件多来源、**同名技能跨级覆盖**（按平台区分措辞）、已装但禁用、always-on token 开销偏大等 |

> 设计原则：**CLI 优先**。插件 / 市场 / MCP 一律走官方命令；技能因官方无 CLI 而走目录——这是技能官方治理的唯一方式，不是绕开 CLI。某平台 CLI 不在 PATH 时自动跳过并标注。

## 安装

插件名 `context-doctor@legdonkey`。**完整安装方式**（含桌面端图形界面、一键脚本 `install-plugins.sh`）见[根 README 的安装区](../../README.md#安装)。命令行速记：

```bash
# Claude Code
/plugin marketplace add legdonkey/legdonkey-plugins
/plugin install context-doctor@legdonkey

# Codex
codex plugin marketplace add legdonkey/legdonkey-plugins --ref main
codex plugin add context-doctor@legdonkey
```

装完重启对应客户端。触发名：**Claude Code** 用 `/context-doctor`（插件命名空间下 `/context-doctor:context-doctor`）；**Codex** 用 `$context-doctor`。**不会自动调用**——CC 靠 frontmatter `disable-model-invocation: true`、Codex 靠 `agents/openai.yaml` 的 `allow_implicit_invocation: false`，只能由你手动点名。

## 用法

手动触发（Claude Code 用 `/`、Codex 用 `$`）：

```
/context-doctor      # Claude Code
$context-doctor      # Codex
```

它在带时间戳的临时目录写出 `report.html`（**主产物**：交互式层级报告）、`inventory.json`（完整数据）和 `report.md`（无浏览器时的回退），对话里只回**输出路径 + 一行短摘要**，提示用浏览器打开 HTML。除非你明确要求，不会把完整报告糊进聊天。只想看一个平台时，脚本可加 `--platform claude` 或 `--platform codex`（默认 both）。

**三段式与中文翻译**：插件/技能/组件的中文用途经用户级缓存 `~/.cache/context-doctor/translations.json` 翻译。流程是 ①采集（脚本登记待译英文）→ ②翻译（技能里由模型把缺失项译成中文写回缓存，条目多时按批**并行 subagent** 提效）→ ③`--render-only` 二次渲染出含中文的 HTML。缓存只增不删、命中不重译，缺失时回退英文。源描述本就是中文的不当待译。采集约 1–2 分钟（逐插件 details + MCP 健康检查，均带重试防偶发超时丢数据）。

**会话快照（默认开启）**：脚本读不到 Host 的上下文窗口，不能直接知道「这轮对话里大模型看到了哪些工具/技能」。所以运行采集前，由「跑技能的模型」根据当前会话实际暴露给自己的工具名、技能名生成一份精简 JSON 快照，再带 `--session-snapshot <快照路径>` 跑；报告用这份快照和本机扫描到的插件 / 技能 / MCP 清单做匹配，标出每项是否 `visible_in_session`。

这不是脚本偷读模型上下文，而是模型按本轮可见清单自报：`●` 表示该技能 / Agent / MCP 名称出现在本轮模型可见清单里，模型知道它存在；`○` 表示本机有但本轮未暴露给模型；`-` 表示未对照。**会话可见不等于允许自动调用**，例如禁自动调用的技能仍可能是 `●`。快照**仅对宿主平台有意义**（在 Claude 里跑只标 Claude 那侧，Codex 侧为 `-` 未对照；反之亦然）。UUID 命名空间的连接器（如 claude.ai HyperFrames）可在快照里加 `source_hint` 兜底匹配。

## 输出规则

- 默认只写**临时目录**（`${CONTEXT_DOCTOR_OUTDIR:-$TMPDIR}/context-doctor/<时间戳>/`）。
- 只有你明确要求持久保存时，才复制 / 重新生成到当前工作区的 `outputs/`。

## 实现

- **CLI 优先、只读**：插件 / 市场 / MCP 调各平台官方治理命令，不读配置文件；技能扫目录（官方无 CLI）。不改任何东西。
- **零第三方依赖**：纯 Python 3 标准库 + Bash，通过 `subprocess` 调 `claude` / `codex`。某平台 CLI 缺失则降级跳过。
- **诚实边界**（报告内有「审计边界」区显式列出）：Codex 无 `plugin details`，组件清单改读本地清单、**全程无 token 成本**，故最贵组件排行只含 Claude；MCP 两平台都无 token 成本，不进排行；未安装插件无法展开完整 details（CLI 报 not found），只给中文用途 + 热度 + 源码链接，成本「装后可见」；hooks（harness-only）/ lsp（out-of-process）无模型成本；技能仅覆盖个人级与项目级，企业 / managed 级与子目录 nested 技能未覆盖；**claude.ai / 桌面版的账号级技能为云端管理、不落本地文件，不在覆盖范围**（技能官方按 surface 隔离、不跨端同步）；Claude Desktop、Codex Desktop、claude.ai、Codex App 的账号级连接器、产品开关、实验功能、窗口状态、授权弹窗和运行时临时工具等宿主 UI 面也不在 CLI / 本地目录审计范围内。报告显式标注，不静默丢。

### 插件结构

```text
plugins/context-doctor/
├── .claude-plugin/plugin.json      # CC 插件清单
├── .codex-plugin/plugin.json       # Codex 插件清单（skills 指向 ./skills/）
└── skills/context-doctor/
    ├── SKILL.md                    # 入口（禁自动调用，只手动点名才跑）
    ├── agents/openai.yaml          # Codex 专属元数据
    └── scripts/
        ├── run.sh                  # 包装：建临时输出目录、调 Python、打印短摘要
        ├── context_doctor.py       # 调官方 CLI 生成 report.html / inventory.json / report.md
        └── report_template.html    # 交互式报告的静态模板（/frontend-design 设计，脚本注入 JSON）
```
