#!/usr/bin/env bash
#
# privatize-fork 一键安装脚本
#
# 把本仓库的所有 skill 同时装进 Claude Code 与 Codex 的个人级 skills 目录（默认软链）。
# 当前仓库收录：privatize-fork、codex-context-doctor。
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

# --- 1. 定位仓库根目录 ----------------------------------------------------
# 仓库根含 skills/<name>/SKILL.md 布局（既是 CC plugin 约定，也是软链来源）。
#
# 优先用脚本所在仓库（本地 clone 场景）；脚本旁没有 skills/ 说明是 curl 远程
# 执行（脚本在临时管道里），此时 clone 仓库到 PRIVATIZE_FORK_HOME。
resolve_repo_root() {
  # 解析脚本自身的真实路径（兼容软链）
  local src="${BASH_SOURCE[0]:-}"
  if [ -n "$src" ]; then
    local dir
    dir="$(cd "$(dirname "$src")" >/dev/null 2>&1 && pwd)" || dir=""
    if [ -n "$dir" ] && compgen -G "$dir/skills/*/SKILL.md" >/dev/null 2>&1; then
      printf '%s\n' "$dir"
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
  printf '%s\n' "$home"
}

REPO_ROOT="$(resolve_repo_root)"

# 发现仓库内所有 skill（含 SKILL.md 的目录）。
SKILL_DIRS=()
for d in "$REPO_ROOT"/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  SKILL_DIRS+=("${d%/}")
done

if [ "${#SKILL_DIRS[@]}" -eq 0 ]; then
  echo "✗ 在 $REPO_ROOT/skills 下找不到任何含 SKILL.md 的 skill，安装中止。" >&2
  exit 1
fi

echo "仓库根目录：$REPO_ROOT"
echo "发现 skill：$(for s in "${SKILL_DIRS[@]}"; do basename "$s"; done | paste -sd' ' -)"

# --- 2. 逐个 skill × agent 安装 ------------------------------------------
installed=0
skipped=0
missing=0

# install_for <agent> <skill_name> <src_dir>
install_for() {
  local agent="$1" skill_name="$2" src_dir="$3"
  local agent_home="$HOME/.$agent"
  if [ ! -d "$agent_home" ]; then
    # 未检测到该 agent：只在第一个 skill 时各计一次，避免重复刷屏。
    return 0
  fi

  local skills_dir="$agent_home/skills"
  local target="$skills_dir/$skill_name"
  mkdir -p "$skills_dir"

  # 已存在：判断是否已是指向本源的软链
  if [ -L "$target" ]; then
    local cur cur_real target_real src_real
    cur="$(cd "$(dirname "$target")" && readlink "$target")"
    src_real="$(cd "$src_dir" && pwd -P)"
    target_real="$(cd "$target" >/dev/null 2>&1 && pwd -P || true)"
    if [ "$target_real" = "$src_real" ]; then
      echo "✓  ${agent}/${skill_name}：已安装（软链 → ${src_dir}），跳过"
      skipped=$((skipped + 1))
      return 0
    fi
    echo "!  ${agent}/${skill_name}：${target} 是指向别处的软链（${cur}），不覆盖。如需重装请先删除它。"
    skipped=$((skipped + 1))
    return 0
  elif [ -e "$target" ]; then
    echo "!  ${agent}/${skill_name}：${target} 已存在且不是本仓库软链，不覆盖。如需重装请先移走它。"
    skipped=$((skipped + 1))
    return 0
  fi

  # 全新安装
  if [ "$USE_COPY" = "1" ]; then
    cp -R "$src_dir" "$target"
    echo "✓  ${agent}/${skill_name}：已复制安装 → ${target}"
  else
    ln -s "$src_dir" "$target"
    echo "✓  ${agent}/${skill_name}：已软链安装 → ${target}"
  fi
  installed=$((installed + 1))
}

echo
for agent in claude codex; do
  if [ ! -d "$HOME/.$agent" ]; then
    echo "·  未检测到 ${agent}（无 $HOME/.$agent），跳过"
    missing=$((missing + 1))
    continue
  fi
  for skill_dir in "${SKILL_DIRS[@]}"; do
    install_for "$agent" "$(basename "$skill_dir")" "$skill_dir"
  done
done

# --- 3. 汇总 --------------------------------------------------------------
echo
echo "—— 安装汇总：新增 ${installed}，跳过 ${skipped}，未检测到 agent ${missing} ——"
if [ "$installed" = "0" ] && [ "$skipped" = "0" ]; then
  echo "⚠ 没找到 Claude Code（~/.claude）或 Codex（~/.codex）的任何安装。"
  echo "  请先安装其一，或手动把各 skill 目录软链到对应的 skills/ 下。"
  exit 1
fi
skill_names="$(for s in "${SKILL_DIRS[@]}"; do basename "$s"; done | paste -sd'、' -)"
echo "完成。重启 CC / Codex 后，skill「${skill_names}」即可用（需手动触发，不会自动调用）。"
