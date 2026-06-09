#!/usr/bin/env bash
#
# 从 assets/src/*.svg（可编辑源，含文字/字体）生成 assets/*.svg（outline 矢量产物）。
# README 引用的是产物：文字已转成路径，自包含、无外部字体依赖，GitHub 上各平台渲染一致、矢量清晰。
#
# 改图流程：编辑 assets/src/<name>.svg → 跑本脚本重生成 → 提交。
# 依赖：usvg（resvg 项目，`brew install resvg` 或 `cargo install usvg`）。
#
set -euo pipefail
cd "$(dirname "$0")/.."   # → assets/

# Futura 用文件喂入以保住标题字形；其余字体在 usvg 字体库里会回退到 Arial Unicode MS（观感干净）。
FUTURA="/System/Library/Fonts/Supplemental/Futura.ttc"
FONT_ARGS=()
[ -f "$FUTURA" ] && FONT_ARGS+=(--use-font-file "$FUTURA")

for name in banner features; do
  usvg "src/$name.svg" "$name.svg" "${FONT_ARGS[@]}" 2>/dev/null
  # usvg 不输出 viewBox，补回以保证 <img width="100%"> 时按容器宽度等比缩放、矢量清晰
  sed -i '' -E 's/<svg width="([0-9]+)" height="([0-9]+)"/<svg width="\1" height="\2" viewBox="0 0 \1 \2"/' "$name.svg"
  echo "✓ 生成 assets/$name.svg"
done
