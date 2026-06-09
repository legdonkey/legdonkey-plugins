---
name: privatize-fork
description: 把一个 clone 下来的开源项目 fork 私有化的脚手架工作流——配置 upstream 只读跟踪+禁推、建立 private/ 目录与维护规范、内联完成 upstream 初始化与文档翻译、写 CLAUDE.md/AGENTS.md 指针。跨 Claude Code 与 Codex（SKILL.md 开放标准）。内置实战提炼的方法论：先勘察（.gitignore/版本号/本地状态文件）→ 私有隔离 → 本地定型 → 最后一次性发布。
disable-model-invocation: true
---

# privatize-fork — 开源 fork 私有化脚手架

把当前目录（一个 clone 下来的开源项目 fork）一次性私有化：配 git 远端、建私有目录与维护规范，**并由 skill 自己内联完成 upstream 初始化与文档翻译**。**不替用户 push 或打 tag**——基建在本地就绪，发布留给用户确认后一次性做。

模板文件都在本 skill 的 `references/` 下，按需读取并做占位符替换。

> **跨平台**：本 skill 用 `SKILL.md` 开放标准，CC（`~/.claude/skills/`）与 Codex（`~/.codex/skills/`）通用。正文提到的交互/并发工具按 agent 取等价物，逻辑不变：
> - **结构化选项弹窗**：CC = `AskUserQuestion`；Codex = `request_user_input`（分页问卷弹窗，**仅在 `/plan` 模式下生效**，默认模式会静默用默认值——故 Codex 用户建议先 `/plan` 再跑本 skill）；都没有则退化为普通问答。
> - **并行子任务**：CC = `Task`；不支持的 agent 顺序执行即可。

## 三条铁律（贯穿全程，先记住）

1. **私有内容尽量隔离，必改上游的登记入账**：新增的私有文件/资料一律进 `private/`（指针段除外，写进 `CLAUDE.md`/`AGENTS.md`），不往 upstream 维护的目录里新建私有文件。确需直接改 upstream 文件（改配置、打补丁等）时不强求隔离，但**必须登记到 `private/CHANGES-REGISTRY.md` 并定好升级冲突策略**——这类文件正是「高冲突清单」要盯的。
2. **动手前先读 `.gitignore`**：upstream 的忽略规则会误伤你将生成的文件，也会暴露它「故意跟踪」的特殊文件。
3. **重入安全（幂等）**：本 skill 可能被重复执行。所有写操作前必须 `test -f` 检查——**已存在的文件一律不覆盖**（用户可能已手动改过规范、登记过台账）；追加类操作（`CLAUDE.md`/`AGENTS.md` 指针）先 `grep` 去重。git 远端配置本就幂等。重复执行只补缺失，绝不破坏已有内容。**重跑本 skill = 重配 upstream（幂等）+ 增量刷新翻译**——这正是用户后续维护时该做的。

> 另一条操作约定：**本 skill 只做到「本地就绪」，绝不替用户 push 或打 tag**——发布交给用户确认无误后手动做（详见阶段 8）。

---

## 阶段 0 · 前置检查与重入守卫

```bash
git rev-parse --is-inside-work-tree 2>/dev/null || echo "NOT_A_GIT_REPO"
git remote -v
test -f private/README.md && echo "ALREADY_INITIALIZED" || echo "FRESH"
```

- **不是 git 仓库** → 告知用户，停止。
- **没有 `origin`** → 问用户这个 fork 的私有仓库地址，先 `git remote add origin <url>`。
- **`ALREADY_INITIALIZED`（`private/README.md` 已存在）→ 进入「安全/增量模式」（重入保护核心）**：
  - **绝不覆盖任何已存在的文件**——用户可能已手动改过 `private/README.md`、登记过 `CHANGES-REGISTRY.md`。
  - 逐项检查缺什么（`private/` 文件齐不齐、`CLAUDE.md`/`AGENTS.md` 指针在不在），**只补缺失项**，每个已存在的逐条报告「已存在，跳过」。
  - git 远端配置可安全重跑（幂等，等于重新初始化 upstream）。
  - **若启用了翻译模块**：照阶段 5 做增量刷新（只重译 upstream 有变动的文档）。
  - 动手补齐前，先把「检测到已初始化 + 打算补哪些」告诉用户，确认后再动。
- **`FRESH`** → 全新项目，正常走完整流程。

## 阶段 1 · 勘察（调脚本，只读，结果汇报给用户）

**这一步只读不改**，固化成脚本保证每条命令都真跑、不漏项：

```bash
SKILL_DIR=""; for d in ~/.claude/skills/privatize-fork ~/.codex/skills/privatize-fork; do [ -d "$d" ] && { SKILL_DIR="$d"; break; }; done
bash "$SKILL_DIR/scripts/recon.sh"
```

> 兜底：若 `$SKILL_DIR` 探测为空，退回手动只读命令——`git remote -v`、`grep -nE 'intentionally|tracked|\*' .gitignore`、探测版本号文件、`git status --short`、`git ls-remote --tags upstream`、`git ls-files '*.md'`。

脚本分 6 节只读输出：现有远端与协议 / `.gitignore` 的「故意跟踪」标记与通配规则 / 版本号位置与当前值 / 本地状态文件 / upstream 最新 tag / 文档清单（markdown）。**判断仍归模型**——据脚本输出汇报勘察结论，重点标出：
- **故意跟踪的文件**（如 `.gitignore` 注释含 "intentionally tracked"）→ 勿删勿 ignore。
- **通配误伤风险**（如 `WIKI*.md`、`*.zh.md` 之类规则会挡住你将生成的文件）→ 记下来，生成时用 `git add -f`。
- **官方版本号**在哪个文件/字段，当前值多少。
- **本地状态文件**清单（候选 skip-worktree 对象）。
- **文档清单**：upstream 跟踪的 markdown 文件（数量 + 路径）→ 阶段2启用翻译时，据此自动预分类白/黑名单。

## 阶段 2 · 引导问答（一次性问清，之后自动跑）

一次性问清以下决策（CC 用 `AskUserQuestion`、Codex 用 `request_user_input`（需 `/plan` 模式才弹窗）、其它退化为普通问答；能从勘察推断的给默认值）：

1. **upstream 仓库地址**（原作者仓库；勘察没找到才问）。
2. **私有 tag 格式**：默认 `v<官方版本>-private.<N>`，确认或自定义。
3. **remote 协议**：默认跟随现有 `origin`；若 `origin` 是 HTTPS 但用户惯用 SSH（`gh auth` 是 ssh），建议统一成 SSH。
4. **是否启用翻译模块**：项目文档多、团队要中文参考 → 启用（skill 内联翻译，产出 `private/translations/`）；纯代码库 → 不装。
   - **启用后立即弹「翻译范围」选择框（关键交互）**：拿阶段1扫到的文档清单做**自动预分类**——
     - *建议翻译（白名单）*：面向用户的文档，如 `README*`、`CONTRIBUTING*`、`docs/` 下的指南类、顶层介绍类 `*.md`。
     - *建议排除（黑名单）*：变更/历史记录（`CHANGELOG*`/`HISTORY*`/含 `audit` 的）、正文本就是中文的文档（抽样含大量中日韩字符）、`private/` 下的、纯模板（如 `.github/` issue 模板）。
     - *AI 指令文件*（`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`）默认归黑名单，但提示用户「团队要参考可勾入，译文为 `.zh.md` 放 `private/translations/`，在子目录、改了名，不会被 AI 当指令加载」。
   - 把预分类结果（建议翻译 N 篇 / 建议排除 M 篇，各列文件名）连同四个选项弹给用户（CC=`AskUserQuestion` 单选、Codex=`request_user_input` 需 `/plan`、其它退化为普通问答）：
     1. **采用建议清单**（默认）。
     2. **逐个调整**：把两组清单完整列出，用普通问答让用户报「加哪个、删哪个」，得到最终白名单。
     3. **全部文档都翻**：白名单 = 扫到的全部文档。
     4. **这些都不翻**：等同关闭翻译模块（回到「不装」）。
   - 最终确认的**白名单 + 显式排除清单**记下来，阶段5写进 `private/translations/CONVENTIONS.md`，作为以后增量刷新的依据（不再要用户手改模板）。
   - **增量模式（重跑）**：若 `CONVENTIONS.md` 已存在，**沿用其中既有白名单、不重新弹窗**；仅当扫到「既不在白、也不在黑名单」的新文档时，才提示用户是否纳入。
5. **团队用哪个 agent**：CC / Codex / 两者（默认两者）。决定阶段 6 的指针段写进 `CLAUDE.md`（CC）还是 `AGENTS.md`（Codex）还是都写。
6. **确认高冲突文件清单**：默认 `README/CHANGELOG` + 勘察到的版本号文件 + `CLAUDE.md`/`AGENTS.md`（若存在），让用户增删。

## 阶段 3 · 配置 git 远端（调脚本，自动）

> 这一步就是 upstream 初始化本身：含「禁止 push upstream」的安全闸——写错或漏掉会把私有改动误推回开源上游，且不可逆。故**不手敲命令，改调本 skill 自带的确定性脚本**（幂等、自带安全自检），杜绝靠自觉。

```bash
# 先定位本 skill 目录（软链/复制安装都适用），再调脚本
SKILL_DIR=""; for d in ~/.claude/skills/privatize-fork ~/.codex/skills/privatize-fork; do [ -d "$d" ] && { SKILL_DIR="$d"; break; }; done

# 配 upstream + 设防误推闸 + fetch tag + 自检；地址用阶段2确认的 upstream 地址
bash "$SKILL_DIR/scripts/setup-remote.sh" "<阶段2确认的upstream地址>"
# 若用户选了统一 SSH，追加 --ssh-origin <owner/repo>：
#   bash "$SKILL_DIR/scripts/setup-remote.sh" "<url>" --ssh-origin <owner/repo>
```

脚本会幂等地：配 `upstream`（已存在则改地址）→ `set-url --push upstream DISABLED`（防误推闸）→ 可选把 `origin` 改 SSH → `fetch upstream --tags`（失败仅告警）→ **自检 push 地址确为 `DISABLED`，不对就非零退出**。结束会打印 `git remote -v`，把结果汇报给用户。

> 兜底：若 `$SKILL_DIR` 探测为空（少见的非标准安装），退回手动等价命令——`git remote add/set-url upstream <url>` → `git remote set-url --push upstream DISABLED` → `git fetch upstream --tags`，并自行确认 push=DISABLED。

## 阶段 4 · 建 private/ 骨架（自动）

**每个文件写入前先 `test -f`，已存在则跳过并报告「已存在，不覆盖」**（重入保护）。读 `references/maintenance-readme.template.md` 和 `references/changes-registry.template.md`，做占位符替换后写入：

- `private/README.md` ← maintenance-readme 模板。替换占位符：
  `{{ORIGIN_SLUG}}`、`{{UPSTREAM_SLUG}}`、`{{ORIGIN_URL}}`、`{{UPSTREAM_URL}}`、`{{BASE_VERSION}}`（勘察到的官方版本）、`{{TAG_FORMAT}}`（阶段2确认的私有 tag 格式，默认 `v<官方版本>-private.<N>`）、`{{HIGH_CONFLICT_LIST}}`（阶段2确认）、`{{VERSION_FILES}}`（版本号所在文件）、`{{VERIFY_CMD}}`（项目自带的测试/检查命令，没有就写「（本项目无自动化测试，靠人工验证）」）。
- `private/CHANGES-REGISTRY.md` ← changes-registry 模板，预填本次脚手架引入的文件。

## 阶段 5 · 翻译（若启用，skill 内联执行）

upstream 初始化已在阶段 3 完成；本阶段只在启用翻译模块时处理翻译。

- **未启用翻译模块** → 跳过本阶段。
- **启用了翻译模块**：
  1. 写 `private/translations/CONVENTIONS.md` ← `references/translations-conventions.template.md`（替换 `{{BASE_VERSION}}`，并把阶段2确认的白名单填入 `{{WHITELIST}}`、显式排除填入 `{{BLACKLIST}}`；`test -f`，已存在不覆盖——重跑时沿用既有清单）。
  2. 读 `references/translate-docs.md`，**按其流程内联执行翻译**：其中**「判断待翻清单」一步改调脚本**（这步要读每篇译文 frontmatter 再跑 git diff 比对，模型最易偷懒）——从 `CONVENTIONS.md` 白名单读出源文件后 `bash "$SKILL_DIR/scripts/translate-plan.sh" <白名单文件...>`，据其输出的 `TRANSLATE`/`RETRANSLATE` 再翻译（支持并行子任务的 agent 如 CC 的 `Task` 并行做，否则顺序做）。**增量更新**——脚本标 `SKIP` 的译文跳过。
  3. 提示用户：翻译白名单需按目标项目实际文档调整（见 `references/translate-docs.md` 第 2 步），以后**重跑本 skill 即做增量刷新**。

## 阶段 6 · 指针段（自动，跨 CC / Codex）

让 AI 维护本项目时自动遵循私有规范，需要在指令文件里加一段「私有维护规范」指针（指向 `private/README.md` + 三条红线 + 登记台账提示）。按阶段 2 选定的 agent 写入对应文件，**先 `grep -q "私有维护规范" <文件>` 去重，已有则跳过不重复追加**：

- **团队用 CC** → 目标 `CLAUDE.md`。
- **团队用 Codex** → 目标 `AGENTS.md`。
- **两者** → 两个文件都写（同一段指针内容）。

目标文件不存在时：可按需创建（只放指针段），或提示用户「不建该文件则规范不会被 AI 自动遵循」。两个文件都没有、团队也不确定用哪个 → 默认建 `AGENTS.md`（开放标准，CC 与 Codex 都逐渐支持读取），并说明原因。

## 阶段 7 · 本地状态文件（按勘察 + 用户确认）

对阶段1检测到的本地状态文件（`.obsidian/workspace.json`、`.idea/`、`.vscode/` 等已被 upstream 跟踪、但每台机器不同的文件）：
- 若 upstream **故意跟踪**它 → 不删不 ignore，建议 `git update-index --skip-worktree <file>` 让本机忽略其变化。
- 逐个征得用户同意再设。

## 阶段 8 · 收尾（不 push、不打 tag）

汇总本次脚手架创建/修改的文件，然后**明确提示用户**（不要自动执行）：

> 私有化基建已在本地就绪。请先验证（跑项目自带测试 / 在编辑器里打开确认），**确认无误后**再一次性发布：
> ```bash
> git add private/ CLAUDE.md AGENTS.md   # 按实际改动（指针段文件按团队 agent 二选一或都有）
> git commit -m "feat(private): 建立私有 fork 维护规范"
> git tag v<官方版本>-private.1
> git push origin main && git push origin v<官方版本>-private.1
> ```
> 之所以留给你手动做：发布前你需要亲自确认基建无误，避免基建还没定型就匆忙发布。

最后提醒：每做一处后续私有定制，登记到 `private/CHANGES-REGISTRY.md`；升级 upstream 前读 `private/README.md` 的升级流程。

## 如何思考（方法论内核）

这个 skill 的价值不在「自动化」，而在**顺序**：先勘察（把项目的暗礁——.gitignore 误伤、故意跟踪的文件、版本号位置、本地状态文件——全摸清）→ 再设计（私有内容尽量隔离，必改上游的登记入账）→ 本地定型 → 最后由用户确认后一次性发布。把顺序走对，绝大部分弯路都能避开。
