#!/usr/bin/env bash
# 准备 Noto Sans SC（400/500/700/900）woff2 与 @font-face 片段。
# 用法：setup_fonts.sh <video 目录>
#
# 为什么要自带字体：渲染用的无头 Chrome 看不到系统的 PingFang（local('PingFang SC') 实测加载失败），
# 不声明 @font-face 中文会掉到宋体。Inter、JetBrains Mono 是 HyperFrames 内置字体，不用准备。
#
# 来源：npmmirror 上的 @fontsource/noto-sans-sc（npm pack 会按镜像返回的 integrity 校验包）。
# 想再对一次官方源：npm view @fontsource/noto-sans-sc@<版本> dist.integrity --registry https://registry.npmjs.org
# fonttools/brotli 装在 ~/.cache/explainer-video/fontvenv（阿里云 PyPI 镜像），不碰系统 Python。
# 合并结果按版本缓存，第二个项目起直接复制。
set -euo pipefail
V=$1
HERE=$(cd "$(dirname "$0")" && pwd)
VER=${NOTO_VER:-5.3.1}
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/explainer-video
PKG=$CACHE/noto-$VER
OUT=$PKG/merged
mkdir -p "$V/assets/fonts"

if [ ! -f "$OUT/noto-sans-sc-900.woff2" ]; then
  if [ ! -d "$PKG/package" ]; then
    mkdir -p "$PKG"
    (cd "$PKG" && npm pack "@fontsource/noto-sans-sc@$VER" --registry https://registry.npmmirror.com >/dev/null \
      && tar xzf "fontsource-noto-sans-sc-$VER.tgz")
  fi
  VENV=$CACHE/fontvenv
  if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -i https://mirrors.aliyun.com/pypi/simple/ fonttools brotli
  fi
  mkdir -p "$OUT"
  "$VENV/bin/python" -I "$HERE/merge_font.py" "$PKG/package" "$OUT"
fi
cp "$OUT"/noto-sans-sc-*.woff2 "$V/assets/fonts/"
cp "$PKG/package/LICENSE" "$V/assets/fonts/OFL-NotoSansSC.txt" 2>/dev/null || true

{
  cat <<'EOF'
/* 字体片段：原样复制进每个场景文件 <template> 内 <style> 的顶部。
   每个文件都要复制：只有 <template> 里的样式会保留；lint 规则 font_family_without_font_face 按文件检查。
   运行时所有场景内联进同一个文档，重复声明同一 src 不会重复下载。
   Inter 与 JetBrains Mono 是 HyperFrames 内置字体，按名使用，不需要 @font-face。 */
EOF
  for w in 400 500 700 900; do
    echo "@font-face { font-family: 'Noto Sans SC'; font-style: normal; font-weight: $w; font-display: block; src: url('assets/fonts/noto-sans-sc-$w.woff2') format('woff2'); }"
  done
} > "$V/assets/fonts/fonts.css.txt"
ls -la "$V/assets/fonts"
