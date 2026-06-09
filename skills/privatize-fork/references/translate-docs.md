# 文档翻译流程

> privatize-fork skill 在启用翻译模块时读取并执行本流程；用户重跑 skill 即做增量刷新。

把 upstream 官方文档翻译成中文，产出到 `private/translations/`。
**增量更新**：已最新的译文跳过，只翻缺失的和源文件有变动的。
**执行方式**：先做「判断清单」（轻活），再翻全文。若当前 agent 支持并行子任务（如 CC 的 `Task` 工具），把翻译重活并行派给子任务、不把原文/译文堆进主上下文；否则顺序逐个翻译——判断与增量逻辑完全一致。

## 第 0 步：读约定

读 `private/translations/CONVENTIONS.md`，记住命名约定（`<原名去扩展>.zh.md`）和 frontmatter 格式（`source` / `source_version` / `translated_at`）。

## 第 1 步：确定 upstream 基线

```bash
git describe --tags --abbrev=0 upstream/main 2>/dev/null || echo "（无 tag，先 git fetch upstream --tags）"
```

作为本轮所有译文的 `source_version`。

## 第 2 步：翻译范围（白名单 —— 按本项目实际文档调整！）

只翻面向用户的文档。**首次启用后请改成你项目的实际文档清单**，例如：

- `README.md`、`CONTRIBUTING.md`、`docs/*.md` 等

**显式排除**：变更/历史记录（CHANGELOG、audits）、本就是中文的私有文档。
（AI 指令文件 CLAUDE.md / AGENTS.md / GEMINI.md：若团队要参考可纳入；译文为 `.zh.md` 放 `private/translations/`，在子目录、改了名，不会被 AI 当指令加载。）

## 第 3 步：判断待翻清单（轻活，先别翻全文）

对白名单每个源文件 `<src>`，目标 `private/translations/<basename>.zh.md`：
- 译文不存在 → 「待翻译」。
- 译文已存在：读 frontmatter 的 `source_version`，跑 `git diff --stat <旧版本>..<当前基线> -- <src>`；非空→「待重译」，空→「跳过」。

清单为空 → 报告「全部最新」并结束，不翻译。

## 第 4 步：翻译（并行优先，否则顺序）

对清单里每个文档执行翻译——**支持并行子任务的 agent（如 CC 的 `Task`）一次性并行派出；不支持的顺序逐个做**。每个翻译任务：

- 任务：把 `<src>` 译成简体中文，写到 `private/translations/<basename>.zh.md`（先读源文件 → 翻译 → 写出）。
- frontmatter：`source: <src>` / `source_version: <基线>` / `translated_at: <今天日期>`。
- 翻译要求：忠实通顺简体中文；**保留原文不译**——代码块、命令、路径、配置字段、API 名、URL、包名、模型名、产品名；保留标题层级。
- 并行派子任务时，子任务回执只返回一行（翻了哪个文件、成功与否、行数），不要把全文堆回主上下文。

## 第 5 步：汇总报告

报告翻译/重译/跳过情况 + 文件路径，提醒未提交需自行 commit。

> 注意：若某译文名匹配 upstream `.gitignore` 的通配规则（如 `WIKI*.md`），首次 `git add` 会被忽略，需 `git add -f`。
