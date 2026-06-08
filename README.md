<p align="center">
  <img src="assets/banner.png" alt="privatize-fork — 开源 fork 一次性私有化脚手架" width="100%">
</p>

# privatize-fork

> 一个 Claude Code [skill](https://docs.claude.com/en/docs/claude-code/skills)：把 clone 下来的开源项目 fork **一次性私有化**。

配好 upstream 只读跟踪 + 禁推、建立 `private/` 维护规范与改动台账、安装 `/private-init` 等私有命令、写好 `CLAUDE.md` 指针——让一个私有 fork 能长期跟踪上游稳定版，同时把私有定制干净隔离、可维护。

内置了从实战中提炼的方法论：**先勘察 → 私有隔离 → 本地定型 → 最后一次性发布**。

## 解决什么问题

团队基于某个开源项目做私有定制，常见的坑：

- 私有改动和 upstream 文件混在一起，升级时冲突地狱；
- 误把私有改动推到了原作者仓库（upstream）；
- 基建还没定型就打 tag + push，结果反复 `force-push` 移动已发布 tag；
- `.gitignore` 的通配规则悄悄挡掉了你新建的文件，或误删了上游「故意跟踪」的特殊文件。

这个 skill 把上述坑整理成一套有**固定顺序**的脚手架流程，一次走完。

## 安装

skill 靠目录里的 `SKILL.md` 被 Claude Code 识别。把本仓库软链到用户级 skills 目录即可：

```bash
git clone <this-repo> ~/Projects/privatize-fork
ln -s ~/Projects/privatize-fork ~/.claude/skills/privatize-fork
```

> 本 skill 带 `disable-model-invocation: true` —— **Claude 不会自动调用它**，只能由你手动触发。私有化是有副作用的操作，刻意设计成「人点头才跑」。

## 使用

1. clone 你的私有 fork 到本地（`origin` 指向你的 fork）；
2. 在**该项目目录**里打开 Claude Code，手动输入：

```
/privatize-fork
```

skill 会带你走完整个流程，最后把私有化基建留在**本地就绪**状态——**不替你 push、不替你打 tag**，发布留给你确认无误后手动做。

## 它会做什么（8 个阶段）

| 阶段 | 动作 |
|------|------|
| 0 | 前置检查 + 重入守卫（已初始化则进增量模式，只补缺失、绝不覆盖） |
| 1 | 勘察（只读）：远端协议、`.gitignore` 暗礁、版本号位置、本地状态文件、upstream tag |
| 2 | 引导问答：upstream 地址、私有 tag 格式、协议、是否启用翻译模块、高冲突文件清单 |
| 3 | 配 git 远端：upstream 只读跟踪 + `push = DISABLED` |
| 4 | 建 `private/`：维护规范 `README.md` + 改动台账 `CHANGES-REGISTRY.md` |
| 5 | 装私有命令：`/private-init`（+ 可选 `/translate-docs` 文档翻译模块） |
| 6 | 写 `CLAUDE.md` 指针段（仅当仓库已有 `CLAUDE.md`） |
| 7 | 本地状态文件按需 `skip-worktree`（逐个征得同意） |
| 8 | 收尾：汇总产物，给出发布命令但**不自动执行** |

## 四条铁律

1. **私有内容零混入**：私有文件只进 `private/` 和 `.claude/commands/`，绝不混进 upstream 维护的目录。
2. **动手前先读 `.gitignore`**：上游忽略规则会误伤你将生成的文件，也会暴露它「故意跟踪」的特殊文件。
3. **重入安全（幂等）**：可重复执行，已存在的文件一律不覆盖，只补缺失。
4. **本地定型后再发布**：skill 只做到「本地就绪」，push 和打 tag 留给你确认无误后手动做。

## 仓库结构

```text
SKILL.md                                      # skill 入口（给 Claude 执行用），唯一被识别的文件
references/                                    # 按需读取的模板，做占位符替换后写入目标项目
├── maintenance-readme.template.md            #  → private/README.md（维护规范）
├── changes-registry.template.md              #  → private/CHANGES-REGISTRY.md（改动台账）
├── private-init.command.md                   #  → .claude/commands/private-init.md
├── translate-docs.command.md                 #  → .claude/commands/translate-docs.md（翻译模块）
└── translations-conventions.template.md      #  → private/translations/CONVENTIONS.md（翻译模块）
README.md                                     # 本文件（给人看的门面，不影响 skill 运行）
```

## 方法论内核

这个 skill 的价值不在「自动化」，而在**顺序**：先勘察（把项目的暗礁全摸清）→ 再设计（私有内容彻底隔离）→ 本地定型 → 最后一次性发布。把顺序走对，就能少走绝大部分弯路。
