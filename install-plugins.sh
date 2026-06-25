#!/usr/bin/env bash
#
# 一键把 legdonkey 市场里的两个插件装进 Claude Code 与 Codex。
#
# 收录插件：privatize-fork、codex-context-doctor（各 1 个技能）。
# 每个平台的 CLI 与桌面端共享同一份配置（CC=~/.claude，Codex=~/.codex），
# 所以每个平台用 CLI 装一次，就同时覆盖了它的命令行和桌面端。
#
# 前提：本机有 claude 和/或 codex CLI。
# 安装命令直接跑、输出实时流式打印（若插件需 ON_INSTALL 交互认证，提示能即时显示、
# 可应答，不会假死）；成败以命令退出码为准，非 0 时再用 `plugin list` 兜底区分
# 「已存在」与真失败。装完可能需重启客户端。
#
# 用法：./install-plugins.sh
set -uo pipefail

REPO="legdonkey/privatize-fork"
MARKETPLACE="legdonkey"
REF="main"
PLUGINS=(privatize-fork codex-context-doctor)

ok=0
fail=0
did_cc=0
did_codex=0

# install_one <cli> <安装子命令: install|add> <plugin>
# 直接跑安装命令（输出流式、stdin 连终端，交互认证提示可见可答），退出码 0 即就位；
# 非 0 再用 plugin list 兜底区分「已存在」与真失败。
install_one() {
  local cli="$1" sub="$2" p="$3" rc
  "$cli" plugin "$sub" "$p@$MARKETPLACE"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  ✓ ${p} 已就位"
    ok=$((ok + 1))
  elif "$cli" plugin list 2>/dev/null | grep -q "$p"; then
    echo "  ✓ ${p} 已就位（已存在）"
    ok=$((ok + 1))
  else
    echo "  ✗ ${p} 未就位（上面的命令输出里有原因：认证 / 网络 / 版本等）"
    fail=$((fail + 1))
  fi
}

# --- Claude Code ---
if command -v claude >/dev/null 2>&1; then
  did_cc=1
  echo "Claude Code：添加市场 + 安装插件（覆盖 CLI + 桌面端）"
  claude plugin marketplace add "$REPO" || true
  for p in "${PLUGINS[@]}"; do
    install_one claude install "$p"
  done
else
  echo "Claude Code：未检测到 claude CLI，跳过"
fi

# --- Codex ---
if command -v codex >/dev/null 2>&1; then
  did_codex=1
  echo "Codex：添加市场 + 安装插件（覆盖 CLI + 桌面端）"
  codex plugin marketplace add "$REPO" --ref "$REF" || true
  for p in "${PLUGINS[@]}"; do
    install_one codex add "$p"
  done
else
  echo "Codex：未检测到 codex CLI，跳过"
fi

echo
if [ "$did_cc" = 0 ] && [ "$did_codex" = 0 ]; then
  echo "未检测到 claude 或 codex CLI，未安装任何插件。"
  exit 1
fi

echo "—— 就位 ${ok}，失败 ${fail} ——"
if [ "$fail" -gt 0 ]; then
  echo "有插件未就位，请按上面每条命令的输出排查后重跑。"
fi
echo "触发方式（重启对应客户端后手动触发，技能不会自动调用）："
[ "$did_cc" = 1 ] && echo "  Claude Code：/privatize-fork    /codex-context-doctor"
[ "$did_codex" = 1 ] && echo "  Codex：      \$privatize-fork   \$codex-context-doctor"

[ "$fail" -gt 0 ] && exit 1
exit 0
