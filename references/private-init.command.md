---
description: 私有 fork 一次性初始化（配 upstream 只读跟踪 + 禁推）
---

私有 fork 的一次性环境初始化。**幂等**，可重复运行。

## 第 1 步：配置 upstream 远端（只读跟踪 + 禁推）

```bash
UPSTREAM_URL="{{UPSTREAM_URL}}"
if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$UPSTREAM_URL"
else
  git remote add upstream "$UPSTREAM_URL"
fi
git remote set-url --push upstream DISABLED   # 从 git 层面杜绝误推 upstream
git fetch upstream --tags || echo "（fetch 失败，可能无网络；稍后手动 git fetch upstream --tags）"
git remote -v
```

确认输出里 upstream 的 push 一行显示 `DISABLED`。

## 第 2 步（可选，若本项目启用了翻译模块）

检查 `private/translations/` 下是否已有 `*.zh.md`：已有则跳过；没有则运行 `/translate-docs` 生成首批译文。

## 第 3 步：汇报

报告 upstream 配置结果（确认 push = DISABLED），并提醒：生成的内容是未提交改动，参照 `private/README.md` 的版本号与发布约定自行提交。
