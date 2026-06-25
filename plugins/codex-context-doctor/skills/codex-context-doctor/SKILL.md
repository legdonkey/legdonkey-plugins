---
name: codex-context-doctor
description: 仅当用户明确说 $codex-context-doctor、codex-context-doctor，或要求运行 Codex Context Doctor / 上下文审计技能时使用。普通编码、泛泛询问 Codex、随口提到插件时不要使用。
disable-model-invocation: true
---

# Codex Context Doctor

这是一个只在手动点名时运行的 Codex 上下文审计技能，用来检查插件、App/连接器、MCP、技能、市场源，以及可选的当前会话可见态。

## 运行

先把 `skill_dir` 解析为当前 `SKILL.md` 所在目录，然后运行：

```bash
bash "$skill_dir/scripts/run.sh"
```

脚本会在带时间戳的临时目录下写入 `report.md` 和 `inventory.json`。对话里只返回输出路径和脚本打印的短摘要。除非用户明确要求，不要把完整报告粘贴到聊天里。

## 会话快照

脚本可以精确扫描磁盘、配置和缓存状态，但不能直接读取 Codex Host 的模型上下文窗口。

如果用户明确要求判断当前会话可见态，先在临时目录创建一个精简 JSON，只包含可见工具命名空间、工具名和技能名，然后运行：

```bash
bash "$skill_dir/scripts/run.sh" --session-snapshot /path/to/session-snapshot.json
```

快照必须保持精简：不要写工具 schema、技能描述或长 prompt。

## 输出规则

默认输出到临时目录。只有用户要求持久保存时，才复制或重新生成到当前工作区的 `outputs/` 目录。
