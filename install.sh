#!/usr/bin/env bash
#
# privatize-fork 一键安装脚本
#
# 把本 skill 同时装进 Claude Code 与 Codex 的个人级 skills 目录（默认软链）。
# 幂等：可重复运行，已正确安装则跳过，遇到非本仓库的同名目录只警告不覆盖。
#
# 两种用法：
#   本地（首选）：  git clone https://github.com/legdonkey/privatize-fork
#                  cd privatize-fork && ./install.sh
#   远程（便捷）：  curl -fsSL https://raw.githubusercontent.com/legdonkey/privatize-fork/main/install.sh | bash
#
# 选项：
#   --copy        用复制代替软链（软链可随 git pull 自动更新，复制则是快照）
#
# 环境变量：
#   PRIVATIZE_FORK_HOME   远程安装时仓库 clone 到的位置（默认 ~/.local/share/privatize-fork）
#
set -euo pipefail

REPO_URL="https://github.com/legdonkey/privatize-fork"
SKILL_NAME="privatize-fork"
USE_COPY=0

for arg in "$@"; do
  case "$arg" in
    --copy) USE_COPY=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$arg（可用：--copy）" >&2; exit 2 ;;
  esac
done

# --- 1. 定位 skill 源目录 -------------------------------------------------
# skill 在仓库里的子路径（同时也是 CC plugin 的 skills/<name> 约定布局）。
SKILL_SUBPATH="skills/$SKILL_NAME"

# 优先用脚本所在仓库（本地 clone 场景）；脚本旁没有该 skill 说明是 curl 远程
# 执行（脚本在临时管道里），此时 clone 仓库到 PRIVATIZE_FORK_HOME。
# 返回的是 skill 目录（仓库/$SKILL_SUBPATH），软链它即可。
resolve_src() {
  # 解析脚本自身的真实路径（兼容软链）
  local src="${BASH_SOURCE[0]:-}"
  if [ -n "$src" ]; then
    local dir
    dir="$(cd "$(dirname "$src")" >/dev/null 2>&1 && pwd)" || dir=""
    if [ -n "$dir" ] && [ -f "$dir/$SKILL_SUBPATH/SKILL.md" ]; then
      printf '%s\n' "$dir/$SKILL_SUBPATH"
      return 0
    fi
  fi

  # 远程场景：clone（或更新）到 PRIVATIZE_FORK_HOME
  local home="${PRIVATIZE_FORK_HOME:-$HOME/.local/share/privatize-fork}"
  if [ -d "$home/.git" ]; then
    echo "↻ 更新已有仓库：$home" >&2
    git -C "$home" pull --ff-only >&2 || echo "  （pull 失败，沿用现有版本）" >&2
  else
    echo "⇣ clone 仓库到：$home" >&2
    mkdir -p "$(dirname "$home")"
    git clone --depth 1 "$REPO_URL" "$home" >&2
  fi
  printf '%s\n' "$home/$SKILL_SUBPATH"
}

SRC="$(resolve_src)"
if [ ! -f "$SRC/SKILL.md" ]; then
  echo "✗ 找不到 skill 源（$SRC 下无 SKILL.md），安装中止。" >&2
  exit 1
fi
echo "skill 源目录：$SRC"

# --- 2. 逐个 agent 安装 ---------------------------------------------------
installed=0
skipped=0
missing=0

install_for() {
  local agent="$1" agent_home="$HOME/.$1"
  if [ ! -d "$agent_home" ]; then
    echo "·  未检测到 ${agent}（无 ${agent_home}），跳过"
    missing=$((missing + 1))
    return 0
  fi

  local skills_dir="$agent_home/skills"
  local target="$skills_dir/$SKILL_NAME"
  mkdir -p "$skills_dir"

  # 已存在：判断是否已是指向本源的软链
  if [ -L "$target" ]; then
    local cur
    cur="$(cd "$(dirname "$target")" && readlink "$target")"
    # 解析为绝对真实路径再比对
    local cur_real target_real src_real
    src_real="$(cd "$SRC" && pwd -P)"
    target_real="$(cd "$target" >/dev/null 2>&1 && pwd -P || true)"
    if [ "$target_real" = "$src_real" ]; then
      echo "✓  ${agent}：已安装（软链 → ${SRC}），跳过"
      skipped=$((skipped + 1))
      return 0
    fi
    echo "!  ${agent}：${target} 是指向别处的软链（${cur}），不覆盖。如需重装请先删除它。"
    skipped=$((skipped + 1))
    return 0
  elif [ -e "$target" ]; then
    echo "!  ${agent}：${target} 已存在且不是本仓库软链，不覆盖。如需重装请先移走它。"
    skipped=$((skipped + 1))
    return 0
  fi

  # 全新安装
  if [ "$USE_COPY" = "1" ]; then
    cp -R "$SRC" "$target"
    echo "✓  ${agent}：已复制安装 → ${target}"
  else
    ln -s "$SRC" "$target"
    echo "✓  ${agent}：已软链安装 → ${target}"
  fi
  installed=$((installed + 1))
}

echo
for agent in claude codex; do
  install_for "$agent"
done

# --- 3. 汇总 --------------------------------------------------------------
echo
echo "—— 安装汇总：新增 ${installed}，跳过 ${skipped}，未检测到 ${missing} ——"
if [ "$installed" = "0" ] && [ "$skipped" = "0" ]; then
  echo "⚠ 没找到 Claude Code（~/.claude）或 Codex（~/.codex）的任何安装。"
  echo "  请先安装其一，或手动把本目录软链到对应的 skills/ 下。"
  exit 1
fi
echo "完成。重启 CC / Codex 后，skill「${SKILL_NAME}」即可用（需手动触发，不会自动调用）。"
