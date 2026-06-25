#!/usr/bin/env bash
#
# 一键把 privatize-fork 插件装进 Claude Code 与 Codex。
#
# 每个平台的 CLI 与桌面端共享同一份配置（CC=~/.claude，Codex=~/.codex），
# 所以每个平台用 CLI 装一次，就同时覆盖了它的命令行和桌面端。
#
# 前提：本机有 claude 和/或 codex CLI；Codex 插件需 Codex ≥ 0.142.0。
# 幂等：已添加/已安装时只提示、不中断。装完可能需重启对应客户端。
#
# 用法：./install-plugins.sh
set -uo pipefail

REPO="legdonkey/privatize-fork"
PLUGIN="privatize-fork"
MARKETPLACE="legdonkey"
REF="main"

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
  run "安装插件 $PLUGIN@$MARKETPLACE" claude plugin install "$PLUGIN@$MARKETPLACE"
  installed_any=1
else
  echo "Claude Code：未检测到 claude CLI，跳过"
fi

# --- Codex ---
if command -v codex >/dev/null 2>&1; then
  ver="$(codex --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  ok=1
  if [ -n "$ver" ] && [ "$(printf '%s\n%s\n' "$ver" "0.142.0" | sort -V | head -1)" != "0.142.0" ]; then
    ok=0
  fi
  if [ "$ok" = "0" ]; then
    echo "Codex：检测到 $ver < 0.142.0，本仓库的「仓库根即插件」布局需 ≥ 0.142.0，跳过。"
    echo "       请升级 Codex，或用 README 里的 Codex 命令行方式手动装。"
  else
    echo "Codex：从市场安装插件（覆盖 CLI + 桌面端，版本 ${ver:-未知}）"
    run "添加市场 $REPO@$REF" codex plugin marketplace add "$REPO" --ref "$REF"
    run "安装插件 $PLUGIN@$MARKETPLACE" codex plugin add "$PLUGIN@$MARKETPLACE"
    installed_any=1
  fi
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
