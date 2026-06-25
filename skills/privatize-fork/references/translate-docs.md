# 文档翻译流程

> privatize-fork skill 在启用翻译模块时读取并执行本流程；用户重跑 skill 即做增量刷新。

把 upstream 官方文档翻译成中文，产出到 `private/translations/`。
**增量更新**：已最新的译文跳过，只翻缺失的和源文件有变动的。
**执行方式**：先做「判断清单」（轻活），再翻全文。若当前 agent 有并行子任务能力（CC 的 `Agent`、Codex 的 subagent 等），用其原生原语把翻译重活并行派给子任务、不把原文/译文堆进主上下文；**只有确实没有并行能力时才顺序逐个翻译**（别因工具名不同就自判为不支持）——判断与增量逻辑完全一致。

## 第 0 步：读约定

读 `private/translations/CONVENTIONS.md`，记住命名约定（`<原名去扩展>.zh.md`）和 frontmatter 格式（`source` / `source_version` / `translated_at`）。

## 第 1 步：确定 upstream 基线（已并入第3步脚本，无需手动）

本轮所有译文的 `source_version` 都对齐到 upstream 最新 tag。该值由第3步的 `translate-plan.sh` 自动求出——它会**探测 upstream 默认分支（main 或 master 都支持，不硬编码）**再取最新 tag，等价于：

```bash
git describe --tags --abbrev=0 "$(git rev-parse --abbrev-ref upstream/HEAD)" 2>/dev/null || echo "（无 tag，先 git fetch upstream --tags）"
```

## 第 2 步：翻译范围（读 CONVENTIONS.md 的白名单，不再手改模板）

翻译范围以 `private/translations/CONVENTIONS.md` 的「翻译范围（白名单）」区块为准——该清单在 skill 阶段2由「翻译范围选择框」扫描本项目文档后确认并落地。**直接读它**：白名单逐个翻、黑名单一律跳过。

需要增删范围时，改 `CONVENTIONS.md` 的白名单区块即可（不要改本流程文件），重跑 skill 照此刷新。

> 兜底：若 `CONVENTIONS.md` 尚无该区块（老版本初始化的项目），退回默认——翻面向用户的文档（`README.md`、`CONTRIBUTING.md`、`docs/*.md` 等）与 AI 指令文件（`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`），排除变更/历史记录（CHANGELOG、audits）与本就中文的文档。
> （AI 指令文件 CLAUDE.md / AGENTS.md / GEMINI.md：**默认纳入翻译**；译文为 `.zh.md` 放 `private/translations/`，在子目录、改了名，不会被 AI 当指令加载。）

## 第 3 步：判断待翻清单（调脚本，先别翻全文）

这步要读每篇译文 frontmatter 的 `source_version` 再跑 `git diff` 跟基线比对——模型最易在此偷懒（凭印象说「没变」），故固化成脚本：

```bash
SKILL_DIR=""; for d in ~/.claude/skills/privatize-fork ~/.codex/skills/privatize-fork; do [ -d "$d" ] && { SKILL_DIR="$d"; break; }; done
# 入参为第2步白名单里的源文件；脚本对每个判出状态
bash "$SKILL_DIR/scripts/translate-plan.sh" README.md CONTRIBUTING.md docs/setup.md
```

脚本对每个源文件输出状态：`TRANSLATE`（译文缺失，待翻）/ `RETRANSLATE`（源文件较基线有改动，待重译）/ `SKIP`（已最新）/ `NEEDS-CHECK`（无基线无法比对）/ `MISSING-SRC`（源文件不存在）。**只翻 `TRANSLATE` 和 `RETRANSLATE`**，`SKIP` 跳过。

汇总行显示各类计数；待翻 + 待重译 + 待确认均为 0 → 报告「全部最新」并结束，不翻译。

> 第1步「确定 upstream 基线」已并入本脚本（内部跑 `git describe --tags --abbrev=0 upstream/main`），无需单独执行。

## 第 4 步：翻译（并行优先，否则顺序）

对清单里每个文档执行翻译——**有并行子任务能力的 agent（CC 的 `Agent`、Codex 的 subagent 等）一次性并行派出；确无并行能力的才顺序逐个做**。每个翻译任务：

- 任务：把 `<src>` 译成简体中文，写到 `private/translations/<basename>.zh.md`（先读源文件 → 翻译 → 写出）。
- frontmatter：`source: <src>` / `source_version: <基线>` / `translated_at: <今天日期>`。
- 翻译要求：忠实通顺简体中文；**保留原文不译**——代码块、命令、配置字段、API 名、URL、包名、模型名、产品名；保留标题层级。
- **重写资源相对路径（重要，否则图片/资源裂掉）**：译文落在 `private/translations/` 下，与源文件目录不同，markdown 里指向图片/资源/同仓库文件的**相对路径**会失效。把这类相对引用改写成从译文位置仍能命中原始资源的路径——前缀 = `../../` + 源文件所在目录。
  - 例：源 `docs/setup.md` 里的 `![图](images/x.png)` → 译文写 `![图](../../docs/images/x.png)`；
  - 例：源根目录 `README.md` 里的 `![](assets/logo.png)` → `![](../../assets/logo.png)`。
  - **只改相对路径**；绝对 URL（`http(s)://`）、绝对路径（`/` 开头）、纯锚点（`#...`）、`mailto:` 等一律不动。
  - 覆盖 markdown 图片 `![](…)`、链接 `[](…)`，以及内联 HTML 的 `<img src="…">`、`<a href="…">`。
- 并行派子任务时，子任务回执只返回一行（翻了哪个文件、成功与否、行数），不要把全文堆回主上下文。

## 第 5 步：汇总报告

报告翻译/重译/跳过情况 + 文件路径，提醒未提交需自行 commit。

> 注意：若某译文名匹配 upstream `.gitignore` 的通配规则（如 `WIKI*.md`），首次 `git add` 会被忽略，需 `git add -f`。
