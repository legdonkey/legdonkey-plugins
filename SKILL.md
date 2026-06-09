---
name: privatize-fork
description: 把一个 clone 下来的开源项目 fork 私有化的脚手架工作流——配置 upstream 只读跟踪+禁推、建立 private/ 目录与维护规范、内联完成 upstream 初始化与文档翻译（无需再装 slash 命令）、写 CLAUDE.md/AGENTS.md 指针。跨 Claude Code 与 Codex（SKILL.md 开放标准）。内置实战提炼的方法论：先勘察（.gitignore/版本号/本地状态文件）→ 私有隔离 → 本地定型 → 最后一次性发布。
disable-model-invocation: true
---

# privatize-fork — 开源 fork 私有化脚手架

把当前目录（一个 clone 下来的开源项目 fork）一次性私有化：配 git 远端、建私有目录与维护规范，**并由 skill 自己内联完成 upstream 初始化与文档翻译**（不再往 fork 里装 slash 命令）。**不替用户 push 或打 tag**——基建在本地就绪，发布留给用户确认后一次性做。

模板文件都在本 skill 的 `references/` 下，按需读取并做占位符替换。

> **跨平台**：本 skill 用 `SKILL.md` 开放标准，CC（`~/.claude/skills/`）与 Codex（`~/.codex/skills/`）通用。正文提到的交互/并发工具按 agent 取等价物，逻辑不变：
> - **结构化选项弹窗**：CC = `AskUserQuestion`；Codex = `request_user_input`（分页问卷弹窗，**仅在 `/plan` 模式下生效**，默认模式会静默用默认值——故 Codex 用户建议先 `/plan` 再跑本 skill）；都没有则退化为普通问答。
> - **并行子任务**：CC = `Task`；不支持的 agent 顺序执行即可。

## 三条铁律（贯穿全程，先记住）

1. **私有内容零混入**：所有私有文件只进 `private/`（指针段除外，写进 `CLAUDE.md`/`AGENTS.md`），绝不混进 upstream 维护的目录。
2. **动手前先读 `.gitignore`**：upstream 的忽略规则会误伤你将生成的文件，也会暴露它「故意跟踪」的特殊文件。
3. **重入安全（幂等）**：本 skill 可能被重复执行。所有写操作前必须 `test -f` 检查——**已存在的文件一律不覆盖**（用户可能已手动改过规范、登记过台账）；追加类操作（`CLAUDE.md`/`AGENTS.md` 指针）先 `grep` 去重。git 远端配置本就幂等。重复执行只补缺失，绝不破坏已有内容。**重跑本 skill = 重配 upstream（幂等）+ 增量刷新翻译**——这正是用户后续维护时该做的，无需任何额外命令。

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
  - **若启用了翻译模块**：照阶段 5 做增量刷新（只重译 upstream 有变动的文档）。这一步替代了过去的 `/translate-docs`。
  - 动手补齐前，先把「检测到已初始化 + 打算补哪些」告诉用户，确认后再动。
- **`FRESH`** → 全新项目，正常走完整流程。

## 阶段 1 · 勘察（只读，自动跑，结果汇报给用户）

按顺序收集，**这一步只读不改**：

```bash
# 1. 现有远端与协议（SSH 还是 HTTPS）
git remote -v
# 2. upstream 的 .gitignore：找"故意跟踪"的特殊文件 + 可能误伤的通配规则
grep -nE 'intentionally|tracked|\*' .gitignore 2>/dev/null
# 3. 版本号位置（按存在与否探测）
for f in package.json .claude-plugin/plugin.json pyproject.toml Cargo.toml VERSION; do [ -f "$f" ] && echo "found: $f"; done
grep -m1 '"version"' package.json .claude-plugin/plugin.json 2>/dev/null
# 4. 本地状态文件（UI/缓存，应 skip-worktree 而非提交私有改动）
git status --short
ls -d .obsidian .idea .vscode 2>/dev/null
# 5. upstream 最新正式 tag（upstream 未配时给出提示，不静默空白）
git remote get-url upstream >/dev/null 2>&1 \
  && git ls-remote --tags upstream 2>/dev/null | grep -v '\^{}' | tail -5 \
  || echo "(upstream 尚未配置，阶段3 配好后再查 tag)"
```

汇报勘察结论，重点标出：
- **故意跟踪的文件**（如 `.gitignore` 注释含 "intentionally tracked"）→ 勿删勿 ignore。
- **通配误伤风险**（如 `WIKI*.md`、`*.zh.md` 之类规则会挡住你将生成的文件）→ 记下来，生成时用 `git add -f`。
- **官方版本号**在哪个文件/字段，当前值多少。
- **本地状态文件**清单（候选 skip-worktree 对象）。

## 阶段 2 · 引导问答（一次性问清，之后自动跑）

一次性问清以下决策（CC 用 `AskUserQuestion`、Codex 用 `request_user_input`（需 `/plan` 模式才弹窗）、其它退化为普通问答；能从勘察推断的给默认值）：

1. **upstream 仓库地址**（原作者仓库；勘察没找到才问）。
2. **私有 tag 格式**：默认 `v<官方版本>-private.<N>`，确认或自定义。
3. **remote 协议**：默认跟随现有 `origin`；若 `origin` 是 HTTPS 但用户惯用 SSH（`gh auth` 是 ssh），建议统一成 SSH。
4. **是否启用翻译模块**：项目文档多、团队要中文参考 → 启用（skill 内联翻译，产出 `private/translations/`）；纯代码库 → 不装。
5. **团队用哪个 agent**：CC / Codex / 两者（默认两者）。决定阶段 6 的指针段写进 `CLAUDE.md`（CC）还是 `AGENTS.md`（Codex）还是都写。
6. **确认高冲突文件清单**：默认 `README/CHANGELOG` + 勘察到的版本号文件 + `CLAUDE.md`/`AGENTS.md`（若存在），让用户增删。

## 阶段 3 · 配置 git 远端（自动）

> 这一步就是 upstream 初始化本身（过去那个 `/private-init` 命令做的事，现在由 skill 直接做、且幂等可重跑）。

```bash
UPSTREAM_URL="<阶段2确认的地址>"
git remote get-url upstream >/dev/null 2>&1 && git remote set-url upstream "$UPSTREAM_URL" || git remote add upstream "$UPSTREAM_URL"
git remote set-url --push upstream DISABLED   # 从 git 层面杜绝误推 upstream
git fetch upstream --tags
# 若用户选了统一 SSH：git remote set-url origin git@github.com:<slug>.git
git remote -v   # 确认 upstream push = DISABLED
```

## 阶段 4 · 建 private/ 骨架（自动）

**每个文件写入前先 `test -f`，已存在则跳过并报告「已存在，不覆盖」**（重入保护）。读 `references/maintenance-readme.template.md` 和 `references/changes-registry.template.md`，做占位符替换后写入：

- `private/README.md` ← maintenance-readme 模板。替换占位符：
  `{{ORIGIN_SLUG}}`、`{{UPSTREAM_SLUG}}`、`{{ORIGIN_URL}}`、`{{UPSTREAM_URL}}`、`{{BASE_VERSION}}`（勘察到的官方版本）、`{{TAG_FORMAT}}`（阶段2确认的私有 tag 格式，默认 `v<官方版本>-private.<N>`）、`{{HIGH_CONFLICT_LIST}}`（阶段2确认）、`{{VERSION_FILES}}`（版本号所在文件）、`{{VERIFY_CMD}}`（项目自带的测试/检查命令，没有就写「（本项目无自动化测试，靠人工验证）」）。
- `private/CHANGES-REGISTRY.md` ← changes-registry 模板，预填本次脚手架引入的文件。

## 阶段 5 · 翻译（若启用，skill 内联做；不再装任何命令）

upstream 初始化已在阶段 3 完成。**本阶段不往 fork 里写任何 slash 命令文件**——这是去掉 `/private-init`、`/translate-docs` 后的核心变化。

- **未启用翻译模块** → 跳过本阶段。
- **启用了翻译模块**：
  1. 写 `private/translations/CONVENTIONS.md` ← `references/translations-conventions.template.md`（替换 `{{BASE_VERSION}}`；`test -f`，已存在不覆盖）。
  2. 读 `references/translate-docs.md`，**按其流程内联执行翻译**：先判断待翻清单（缺失/源文件有变动的），再翻译（支持并行子任务的 agent 如 CC 的 `Task` 并行做，否则顺序做）。**增量更新**——已最新的译文跳过。
  3. 提示用户：翻译白名单需按目标项目实际文档调整（见 `references/translate-docs.md` 第 2 步），以后**重跑本 skill 即做增量刷新**，无需任何额外命令。

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

这个 skill 的价值不在「自动化」，而在**顺序**：先勘察（把项目的暗礁——.gitignore 误伤、故意跟踪的文件、版本号位置、本地状态文件——全摸清）→ 再设计（私有内容彻底隔离）→ 本地定型 → 最后由用户确认后一次性发布。把顺序走对，绝大部分弯路都能避开。
