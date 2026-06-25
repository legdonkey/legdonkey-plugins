#!/usr/bin/env bash
#
# privatize-fork · 阶段5「判断待翻清单」的确定性实现（只读，不翻译）
#
# 为什么固化成脚本：判断「哪些译文过期」要读每篇译文 frontmatter 的 source_version，
# 再跑 git diff 跟当前 upstream 基线比对——模型最容易在这里偷懒，凭印象说「应该没变」
# 而不真比对，导致译文悄悄过期。脚本把比对做实，输出待翻/待重译/跳过清单；真正的
# 翻译正文仍交给模型。
#
# 用法：translate-plan.sh <src1.md> [<src2.md> ...]
#   入参为白名单源文件（模型从 CONVENTIONS.md 的白名单区块读出后传入）。
#   译文目标为 private/translations/<源相对路径去扩展，'/'换成'-'>.zh.md
#   （顶层文件即 README.zh.md；子目录文件如 docs/api.md → docs-api.zh.md，避免同名冲突）。
#
set -uo pipefail

if [ $# -eq 0 ]; then
  echo "✗ 未传入白名单文件。用法：translate-plan.sh <src1.md> [<src2.md> ...]" >&2
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ 当前目录不是 git 仓库，终止。" >&2
  exit 1
fi

# 当前 upstream 基线版本（本轮译文的 source_version 应对齐到它）。
# upstream 默认分支可能叫 main 或 master，依次探测，避免硬编码 main 导致基线总为空。
resolve_baseline() {
  local cand
  for cand in "$(git rev-parse --abbrev-ref upstream/HEAD 2>/dev/null || true)" upstream/main upstream/master; do
    [ -z "$cand" ] && continue
    if git rev-parse --verify --quiet "${cand}^{commit}" >/dev/null 2>&1; then
      git describe --tags --abbrev=0 "$cand" 2>/dev/null && return 0
    fi
  done
  return 1
}
BASELINE="$(resolve_baseline || true)"
if [ -z "$BASELINE" ]; then
  echo "!  无法确定 upstream 基线（upstream/main 无 tag？先 git fetch upstream --tags）。" >&2
  echo "   仍可判断「译文缺失」，但「是否过期」无法比对，存量译文一律标记为 NEEDS-CHECK。" >&2
fi
echo "# upstream 基线：${BASELINE:-（未知）}"
printf '# 状态\t源文件\t译文\t说明\n'

n_translate=0; n_retranslate=0; n_skip=0; n_check=0
for src in "$@"; do
  # 译文名编码源的相对路径以避免同名冲突：顶层 README.md→README.zh.md；
  # 子目录 docs/README.md→docs-README.zh.md（译文仍平铺在 translations/ 顶层，资源相对路径改写规则不变）。
  rel="${src#./}"
  dst="private/translations/$(printf '%s' "${rel%.*}" | tr '/' '-').zh.md"

  if [ ! -f "$src" ]; then
    printf 'MISSING-SRC\t%s\t%s\t源文件不存在，跳过\n' "$src" "$dst"
    continue
  fi

  if [ ! -f "$dst" ]; then
    printf 'TRANSLATE\t%s\t%s\t译文不存在，待翻译\n' "$src" "$dst"
    n_translate=$((n_translate + 1))
    continue
  fi

  # 译文已存在：读其 frontmatter 的 source_version
  prev="$(grep -m1 '^source_version:' "$dst" | sed 's/^source_version:[[:space:]]*//' | tr -d '"' || true)"

  if [ -z "$BASELINE" ]; then
    printf 'NEEDS-CHECK\t%s\t%s\t无基线，无法比对（旧版本=%s）\n' "$src" "$dst" "${prev:-未知}"
    n_check=$((n_check + 1))
    continue
  fi

  if [ -z "$prev" ]; then
    printf 'RETRANSLATE\t%s\t%s\t译文缺 source_version，建议重译\n' "$src" "$dst"
    n_retranslate=$((n_retranslate + 1))
    continue
  fi

  if [ "$prev" = "$BASELINE" ]; then
    printf 'SKIP\t%s\t%s\t已是最新（%s）\n' "$src" "$dst" "$BASELINE"
    n_skip=$((n_skip + 1))
    continue
  fi

  # prev 与 baseline 不同：先确认 prev 在本地可解析，否则没法可靠比对
  if ! git rev-parse --verify --quiet "${prev}^{commit}" >/dev/null 2>&1; then
    printf 'RETRANSLATE\t%s\t%s\t旧版本 %s 本地不可解析（tag 丢失？），建议重译\n' "$src" "$dst" "$prev"
    n_retranslate=$((n_retranslate + 1))
    continue
  fi

  # 源文件在 prev..BASELINE 间有无改动
  diffstat="$(git diff --stat "$prev".."$BASELINE" -- "$src" 2>/dev/null || true)"
  if [ -n "$diffstat" ]; then
    printf 'RETRANSLATE\t%s\t%s\t源文件 %s→%s 有改动，待重译\n' "$src" "$dst" "$prev" "$BASELINE"
    n_retranslate=$((n_retranslate + 1))
  else
    printf 'SKIP\t%s\t%s\t%s→%s 源文件无改动\n' "$src" "$dst" "$prev" "$BASELINE"
    n_skip=$((n_skip + 1))
  fi
done

echo
echo "—— 汇总：待翻译 ${n_translate}，待重译 ${n_retranslate}，跳过 ${n_skip}，待人工确认 ${n_check} ——"
if [ $((n_translate + n_retranslate + n_check)) -eq 0 ]; then
  echo "全部最新，无需翻译。"
fi
