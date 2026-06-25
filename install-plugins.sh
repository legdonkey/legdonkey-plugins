#!/usr/bin/env bash
#
# 一键把 legdonkey 市场里的两个插件装进 Claude Code 与 Codex。
#
# 收录插件：privatize-fork、codex-context-doctor（各 1 个技能）。
# 每个平台的 CLI 与桌面端共享同一份配置（CC=~/.claude，Codex=~/.codex），
# 所以每个平台用 CLI 装一次，就同时覆盖了它的命令行和桌面端。
#
# 前提：本机有 claude 和/或 codex CLI。
# 安装命令的输出会原样打印（认证/网络等真失败能看到），随后用 `plugin list`
# 实测是否真就位——以此判断成败，而不是靠 add 命令的退出码。装完可能需重启客户端。
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

# verify_and_report <cli> <plugin>：以 plugin list 实测是否就位（已装/刚装都算 ✓；真没装上算 ✗）
verify_and_report() {
  if "$1" plugin list 2>/dev/null | grep -q "$2"; then
    echo "  ✓ $2 已就位"
    ok=$((ok + 1))
  else
    echo "  ✗ $2 未就位（上面的命令输出里有原因：认证 / 网络 / 版本等）"
    fail=$((fail + 1))
  fi
}

# --- Claude Code ---
if command -v claude >/dev/null 2>&1; then
  did_cc=1
  echo "Claude Code：添加市场 + 安装插件（覆盖 CLI + 桌面端）"
  claude plugin marketplace add "$REPO" 2>&1 | sed 's/^/  /' || true
  for p in "${PLUGINS[@]}"; do
    claude plugin install "$p@$MARKETPLACE" 2>&1 | sed 's/^/  /' || true
    verify_and_report claude "$p"
  done
else
  echo "Claude Code：未检测到 claude CLI，跳过"
fi

# --- Codex ---
if command -v codex >/dev/null 2>&1; then
  did_codex=1
  echo "Codex：添加市场 + 安装插件（覆盖 CLI + 桌面端）"
  codex plugin marketplace add "$REPO" --ref "$REF" 2>&1 | sed 's/^/  /' || true
  for p in "${PLUGINS[@]}"; do
    codex plugin add "$p@$MARKETPLACE" 2>&1 | sed 's/^/  /' || true
    verify_and_report codex "$p"
  done
else
  echo "Codex：未检测到 codex CLI，跳过"
fi

echo
if [ "$did_cc" = 0 ] && [ "$did_codex" = 0 ]; then
  echo "未检测到 claude 或 codex CLI，未安装任何插件。"
  exit 1
fi

echo "—— 就位 $ok，失败 $fail ——"
if [ "$fail" -gt 0 ]; then
  echo "有插件未就位，请按上面每条命令的输出排查后重跑。"
fi
echo "触发方式（重启对应客户端后手动触发，技能不会自动调用）："
[ "$did_cc" = 1 ] && echo "  Claude Code：/privatize-fork    /codex-context-doctor"
[ "$did_codex" = 1 ] && echo "  Codex：      \$privatize-fork   \$codex-context-doctor"

[ "$fail" -gt 0 ] && exit 1
exit 0
