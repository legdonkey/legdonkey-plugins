<p align="center">
  <img src="assets/banner.svg" alt="context-doctor — 跨平台审计上下文" width="100%">
</p>

# context-doctor

> 一个跨 **Claude Code** 与 **Codex** 的插件（基于开放标准 [skill](https://agentskills.io)）：用各平台**官方 CLI 治理入口**盘点装了哪些插件 / MCP / 市场源，技能走目录治理入口，并给出卫生建议。
>
> ← 返回[仓库总览](../../README.md) ｜ 姊妹插件：[privatize-fork](../privatize-fork/)

装多了之后，常分不清「现在到底加载了什么、谁和谁重名、哪些禁用了还占着 token」。这个插件调 `claude` / `codex` 的官方治理命令，把两个平台的上下文构成摊开给你看，输出**一份含 Claude Code 与 Codex 两个分区**的报告，只在你手动点名时才跑。

## 审计什么

<p align="center">
  <img src="assets/audit-overview.svg" alt="审计什么：插件 / MCP / 市场源 / 技能，两平台一份报告" width="100%">
</p>

| 对象 | 数据来源 |
|------|---------|
| **插件 Plugins** | `claude plugin list --json --available` / `codex plugin list --json --available`：已装 + 可装、版本、启停、市场。Claude 侧另经 `claude plugin details` 取插件自带技能与 **token 成本** |
| **市场源 Marketplaces** | `claude plugin marketplace list --json` / `codex plugin marketplace list --json`（老版本无 `--json` 时回退文本解析）。保留真实源类型（github / git / 本地等） |
| **MCP 服务器** | `claude mcp list`（文本，含连通 / 认证等状态）/ `codex mcp list --json` |
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

它会调两个平台的官方 CLI、在带时间戳的临时目录写出 `report.md`（人类可读报告）和 `inventory.json`（完整数据），对话里只回**输出路径 + 一行短摘要**。除非你明确要求，不会把完整报告糊进聊天。只想看一个平台时，脚本可加 `--platform claude` 或 `--platform codex`（默认 both）。

**可选会话快照**：想对照「装了什么 vs 本次会话真正可见什么」，让它先写一个精简的会话工具/技能 JSON 再带 `--session-snapshot` 跑，报告里会标出每项是否 `visible_in_session`（仅对宿主平台有意义）。

## 输出规则

- 默认只写**临时目录**（`${CONTEXT_DOCTOR_OUTDIR:-$TMPDIR}/context-doctor/<时间戳>/`）。
- 只有你明确要求持久保存时，才复制 / 重新生成到当前工作区的 `outputs/`。

## 实现

- **CLI 优先、只读**：插件 / 市场 / MCP 调各平台官方治理命令，不读配置文件；技能扫目录（官方无 CLI）。不改任何东西。
- **零第三方依赖**：纯 Python 3 标准库 + Bash，通过 `subprocess` 调 `claude` / `codex`。某平台 CLI 缺失则降级跳过。
- **已知缩减项**：Codex 无 `plugin details`，其插件自带技能与 token 成本未逐插件展开；Codex 的 App / 连接器全量审计在 CLI 模式下暂不覆盖（无对应 `list --json` 命令）；技能仅覆盖个人级与项目级，企业 / managed 级与子目录 nested 技能未覆盖。报告会显式标注，不静默丢。

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
        └── context_doctor.py       # 调官方 CLI 生成 report.md / inventory.json
```
