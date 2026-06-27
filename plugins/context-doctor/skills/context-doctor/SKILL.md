---
name: context-doctor
description: 仅当用户明确说 $context-doctor、context-doctor，或要求运行 Context Doctor / 跨平台上下文审计 / 体检插件技能 MCP 时使用。普通编码、泛泛询问插件、随口提到 MCP 时不要使用。
disable-model-invocation: true
---

# Context Doctor

只在手动点名时运行的**跨平台上下文审计**技能。用各平台官方 CLI 治理命令盘点 **Claude Code 与 Codex** 的插件、MCP、市场源；技能因两平台都没有 CLI（官方设计为文件式）而扫描技能目录。可选对照当前会话可见态。

## 运行

先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录，然后运行：

```bash
bash "$skill_dir/scripts/run.sh"
```

脚本会在带时间戳的临时目录下写入 `report.md` 和 `inventory.json`，报告含 Claude Code 与 Codex 两个分区。对话里只返回输出路径和脚本打印的短摘要。除非用户明确要求，不要把完整报告粘贴到聊天里。

只想看某一个平台时，直接调脚本加 `--platform claude` 或 `--platform codex`（默认 both）。

## 数据来源（重要）

- 插件 / 市场 / MCP：调各平台官方 CLI（`claude plugin/marketplace/mcp`、`codex plugin/mcp`），不读配置文件。某平台 CLI 不在 PATH 时，自动跳过该平台并在报告里标注。
- 技能：两平台都没有列举技能的 CLI（官方设计为文件式），故扫描技能目录——这是技能官方治理的唯一方式。Claude 的插件自带技能与 token 成本另经 `claude plugin details` 获取。

## 会话快照

脚本读不到 Host 的模型上下文窗口。若用户明确要求判断当前会话可见态，先在临时目录创建一个精简 JSON，只含可见工具命名空间、工具名和技能名，再运行：

```bash
bash "$skill_dir/scripts/run.sh" --session-snapshot /path/to/session-snapshot.json
```

快照必须精简：不要写工具 schema、技能描述或长 prompt。会话可见态仅对宿主平台有意义。

## 输出规则

默认输出到临时目录。只有用户要求持久保存时，才复制或重新生成到当前工作区的 `outputs/` 目录。
