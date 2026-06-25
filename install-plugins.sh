#!/usr/bin/env bash
#
# 一键把 legdonkey 市场里的两个插件装进 Claude Code 与 Codex。
#
# 收录插件：privatize-fork、codex-context-doctor（各 1 个技能）。
# 每个平台的 CLI 与桌面端共享同一份配置（CC=~/.claude，Codex=~/.codex），
# 所以每个平台用 CLI 装一次，就同时覆盖了它的命令行和桌面端。
#
# 前提：本机有 claude 和/或 codex CLI。
# 幂等：已添加/已安装时只提示、不中断。装完可能需重启对应客户端。
#
# 用法：./install-plugins.sh
set -uo pipefail

REPO="legdonkey/privatize-fork"
MARKETPLACE="legdonkey"
REF="main"
PLUGINS=(privatize-fork codex-context-doctor)

# run <描述> <命令...>：成功打 ✓，失败（多半是已存在）打 ·，都不中断。
run() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  ✓ $desc"
  else
    echo "  · $desc（已存在或跳过）"
  fi
}

installed_any=0

# --- Claude Code ---
if command -v claude >/dev/null 2>&1; then
  echo "Claude Code：从市场安装插件（覆盖 CLI + 桌面端）"
  run "添加市场 $REPO" claude plugin marketplace add "$REPO"
  for p in "${PLUGINS[@]}"; do
    run "安装插件 $p@$MARKETPLACE" claude plugin install "$p@$MARKETPLACE"
  done
  installed_any=1
else
  echo "Claude Code：未检测到 claude CLI，跳过"
fi

# --- Codex ---
if command -v codex >/dev/null 2>&1; then
  echo "Codex：从市场安装插件（覆盖 CLI + 桌面端）"
  run "添加市场 $REPO@$REF" codex plugin marketplace add "$REPO" --ref "$REF"
  for p in "${PLUGINS[@]}"; do
    run "安装插件 $p@$MARKETPLACE" codex plugin add "$p@$MARKETPLACE"
  done
  installed_any=1
else
  echo "Codex：未检测到 codex CLI，跳过"
fi

echo
if [ "$installed_any" = "1" ]; then
  echo "完成。重启 Claude Code / Codex 后，/privatize-fork 与 /codex-context-doctor 即可手动触发。"
else
  echo "未检测到 claude 或 codex CLI，未安装任何插件。"
  exit 1
fi
