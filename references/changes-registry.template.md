# 私有改动台账

记录本 fork 相对 upstream 的私有定制。**只记 git 看不出的东西** —— 「为什么改」和「升级冲突时怎么处理」。
文件清单用 git 命令即可（把基线版本替换进去）：

```bash
git diff --stat upstream/{{BASE_VERSION}}...main
```

每做一处私有定制就在此登记；升级合并冲突时按此表逐条核对，优先保留私有版再并入 upstream 新内容。

| 改动 | 涉及文件/目录 | 为什么 | 升级冲突策略 | 引入版本 |
|------|--------------|--------|--------------|----------|
| 私有维护规范 | `private/README.md` | fork 维护流程，upstream 没有 | 保私有版 | {{BASE_VERSION}}-private.1 |
| 私有目录 | `private/` | 台账/规范（可选译文），与 upstream 隔离 | upstream 无此目录，不冲突 | {{BASE_VERSION}}-private.1 |
| 私有 slash 命令 | `.claude/commands/` | `/private-init` 等私有命令 | upstream 一般不动 `.claude/commands/`，低冲突 | {{BASE_VERSION}}-private.1 |
| CLAUDE.md 指针段 | `CLAUDE.md`（若存在） | 让 CC 遵循私有规范 | 保私有段，再并入 upstream 新内容 | {{BASE_VERSION}}-private.1 |

## 高冲突文件清单

以下文件最容易和 upstream 撞车，升级合并时重点检查，默认「保私有 + 手动并入 upstream 新内容」：

{{HIGH_CONFLICT_LIST}}

## 本项目的特殊坑（勘察阶段发现，逐条记录）

- （示例）某文件被 upstream 故意跟踪 → 勿删勿 ignore。
- （示例）某 `.gitignore` 通配规则误伤生成文件 → 需 `git add -f`。
- （示例）某本地状态文件已设 `skip-worktree`。
