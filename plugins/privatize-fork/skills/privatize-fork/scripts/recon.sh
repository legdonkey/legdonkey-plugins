#!/usr/bin/env bash
#
# privatize-fork · 阶段1「勘察」的确定性实现（只读，绝不改动仓库）
#
# 为什么固化成脚本：勘察是一组只读命令，模型容易「凭印象跳过某条」。固化后保证
# 每次都真跑、不漏项，输出结构化结果交给模型解读（哪些是故意跟踪、哪些通配会误伤、
# 版本号在哪）。脚本只负责老实把料备齐，判断仍归模型。
#
# 用法：在目标项目根目录运行：recon.sh
#
# 注意：本脚本通篇只读，不含任何写操作——这正是它能放心固化的前提。
#
set -uo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ 当前目录不是 git 仓库，终止。" >&2
  exit 1
fi

echo "## 1. 现有远端与协议（看 SSH 还是 HTTPS）"
git remote -v || echo "（无远端）"
echo

echo "## 2. .gitignore 的「故意跟踪」标记 + 通配规则（可能误伤将生成的文件）"
if [ -f .gitignore ]; then
  grep -nE 'intentionally|tracked|\*' .gitignore 2>/dev/null || echo "（无匹配）"
else
  echo "（无 .gitignore）"
fi
echo

echo "## 3. 版本号位置与当前值"
found_ver=0
for f in package.json .claude-plugin/plugin.json pyproject.toml Cargo.toml VERSION; do
  if [ -f "$f" ]; then echo "found: $f"; found_ver=1; fi
done
[ "$found_ver" = 0 ] && echo "（常见版本号文件均未找到，需人工确认）"
grep -m1 '"version"' package.json .claude-plugin/plugin.json 2>/dev/null || true
echo

echo "## 4. 本地状态文件（候选 skip-worktree 对象）"
git status --short || true
found_state=0
for d in .obsidian .idea .vscode; do [ -e "$d" ] && { echo "found: $d"; found_state=1; }; done
[ "$found_state" = 0 ] && echo "（未见 .obsidian/.idea/.vscode）"
echo

echo "## 5. upstream 最新正式 tag"
if git remote get-url upstream >/dev/null 2>&1; then
  git ls-remote --tags upstream 2>/dev/null | grep -v '\^{}' | tail -5 || echo "（拉取 tag 失败）"
else
  echo "（upstream 尚未配置，阶段3 配好后再查 tag）"
fi
echo

echo "## 6. 文档清单（markdown，供阶段2 翻译白名单预分类用）"
git ls-files '*.md' ':!:private/**' 2>/dev/null | sort || echo "（无跟踪的 markdown）"
