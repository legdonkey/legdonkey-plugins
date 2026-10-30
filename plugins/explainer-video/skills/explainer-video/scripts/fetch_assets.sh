#!/usr/bin/env bash
# 下载 HyperFrames 官方技能文档（只读参考）和 media-use 自带的 Pixabay 音效。
# 用法：fetch_assets.sh <video 目录> [HyperFrames 标签，默认 v0.8.198]
#
# 文档放在 ~/.cache/explainer-video/hf-skills/<标签>/skills/，按标签缓存，与 CLI 版本对齐；
# 不写入 ~/.claude、~/.agents（不安装 HyperFrames 技能，只给子代理当参考读）。
# 音效复制到 <video>/assets/sfx/，含 manifest.json 与 CREDITS.md（Pixabay Content License，可商用，无需署名）。
# 走 gh api（GitHub），需要已登录的 gh。
set -euo pipefail
V=$1
TAG=${2:-v0.8.198}
REPO=heygen-com/hyperframes
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/explainer-video/hf-skills/$TAG
# GitHub API 偶尔断连（EOF），每个文件最多重试 3 次；先写临时文件，成功后再改名，避免留下半截文件
raw() {
  local i
  for i in 1 2 3; do
    if gh api "repos/$REPO/contents/$1?ref=$TAG" -H "Accept: application/vnd.github.raw" > "$2.part" 2>/dev/null; then
      mv "$2.part" "$2"; return 0
    fi
    sleep $((i * 2))
  done
  rm -f "$2.part"; echo "下载失败：$1" >&2; return 1
}

if [ ! -f "$CACHE/.complete" ]; then
  mkdir -p "$CACHE"
  gh api "repos/$REPO/git/trees/$TAG?recursive=1" --jq '.tree[] | select(.type=="blob") | .path' \
    | grep -E '^skills/(hyperframes|hyperframes-cli|hyperframes-registry|media-use)/' \
    | grep -E '\.md$' | grep -v '/frame-presets/' > "$CACHE/files.txt"
  while read -r p; do
    mkdir -p "$CACHE/$(dirname "$p")"
    [ -s "$CACHE/$p" ] || raw "$p" "$CACHE/$p"
  done < "$CACHE/files.txt"
  touch "$CACHE/.complete"
  echo "文档：$(wc -l < "$CACHE/files.txt") 个文件 → $CACHE/skills"
else
  echo "文档已缓存：$CACHE/skills"
fi

SFX="whoosh whoosh-short whoosh-cinematic pop riser impact-bass-1 impact-bass-2 click click-soft key-press sparkle glitch-1 typing chime"
mkdir -p "$V/assets/sfx"
for f in $SFX; do
  [ -s "$V/assets/sfx/$f.mp3" ] || raw "skills/media-use/audio/assets/sfx/$f.mp3" "$V/assets/sfx/$f.mp3"
done
for f in manifest.json CREDITS.md; do
  [ -s "$V/assets/sfx/$f" ] || raw "skills/media-use/audio/assets/sfx/$f" "$V/assets/sfx/$f"
done
echo "音效：$(find "$V/assets/sfx" -maxdepth 1 -name '*.mp3' | wc -l | tr -d ' ') 个 → $V/assets/sfx"
