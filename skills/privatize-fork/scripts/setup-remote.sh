#!/usr/bin/env bash
#
# privatize-fork · 阶段3「配置 git 远端」的确定性实现
#
# 为什么固化成脚本：这一步含「禁止 push upstream」的安全闸——一行写错或漏掉，
# 私有改动就可能被误推回开源上游，且不可逆。把它从「模型手敲」换成「脚本执行 + 自检」，
# 杜绝靠自觉。幂等：可重复运行，已配则更新。
#
# 用法：
#   setup-remote.sh <upstream_url> [--ssh-origin <owner/repo>]
#
#   <upstream_url>          原作者（上游）仓库地址，配为只读跟踪的 upstream
#   --ssh-origin <slug>     可选：把 origin 统一改成 SSH（git@github.com:<slug>.git）
#
set -euo pipefail

# --- 参数解析 ------------------------------------------------------------
UPSTREAM_URL=""
SSH_ORIGIN_SLUG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ssh-origin) SSH_ORIGIN_SLUG="${2:-}"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "未知参数：$1" >&2; exit 2 ;;
    *) UPSTREAM_URL="$1"; shift ;;
  esac
done

if [ -z "$UPSTREAM_URL" ]; then
  echo "✗ 缺少 upstream 地址。用法：setup-remote.sh <upstream_url> [--ssh-origin <owner/repo>]" >&2
  exit 2
fi

# --- 前置：必须在 git 仓库内 ---------------------------------------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ 当前目录不是 git 仓库，终止。" >&2
  exit 1
fi

# --- 1. 配 upstream（幂等：已存在则改地址，否则新增）---------------------
if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$UPSTREAM_URL"
  echo "↻ 已更新 upstream → $UPSTREAM_URL"
else
  git remote add upstream "$UPSTREAM_URL"
  echo "✓ 已新增 upstream → $UPSTREAM_URL"
fi

# --- 2. 安全闸：从 git 层面禁止 push upstream ----------------------------
git remote set-url --push upstream DISABLED

# --- 3. 可选：把 origin 统一改成 SSH ------------------------------------
if [ -n "$SSH_ORIGIN_SLUG" ]; then
  git remote set-url origin "git@github.com:${SSH_ORIGIN_SLUG}.git"
  echo "✓ 已把 origin 改为 SSH → git@github.com:${SSH_ORIGIN_SLUG}.git"
fi

# --- 4. 拉 upstream tag（失败不致命，仅告警）----------------------------
if git fetch upstream --tags >/dev/null 2>&1; then
  echo "✓ 已 fetch upstream --tags"
else
  echo "!  fetch upstream 失败（网络或地址问题？），远端已配好，可稍后手动 git fetch upstream --tags"
fi

# --- 5. 自检：防误推闸必须真的生效，否则报错退出 ------------------------
PUSHURL="$(git config --get remote.upstream.pushurl || true)"
if [ "$PUSHURL" != "DISABLED" ]; then
  echo "✗ 安全自检失败：upstream 的 push 地址应为 DISABLED，实际为「${PUSHURL:-（空）}」。" >&2
  echo "  请手动执行：git remote set-url --push upstream DISABLED" >&2
  exit 1
fi

echo
echo "—— 远端配置完成，防误推闸已生效 ——"
git remote -v
