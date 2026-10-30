#!/usr/bin/env bash
# 把画面与混好的主音轨封装成成片，并报告规格与响度。画面不重编码（-c:v copy）。
# 用法：finalize.sh <video 目录> <成片路径.mp4> [画面文件，默认 renders/visual_pass.mp4]
# 只换 BGM 或音效时：重跑 mix_audio.py，再跑本脚本即可，不用重渲画面。
set -euo pipefail
V=$1
OUT=$2
PIC=${3:-$V/renders/visual_pass.mp4}
ffmpeg -v error -y -i "$PIC" -i "$V/assets/audio/mix.wav" -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -b:a 320k -ar 48000 -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
  -of compact "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -A14 "Summary:" | grep -E "I:|LRA:|Peak:"
