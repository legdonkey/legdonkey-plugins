# 把 fontsource 的 chinese-simplified 子集与包含常用符号（①–④、→、✓、≥、全角标点等）的分片
# 合并成每个字重一个 woff2。由 setup_fonts.sh 调用：python -I merge_font.py <package 目录> <输出目录>
import sys, glob, os
from fontTools.ttLib import TTFont
from fontTools.merge import Merger, Options

pkg, out = sys.argv[1], sys.argv[2]
EXTRA = set()
for a, b in [(0x2010, 0x205E), (0x2190, 0x21FF), (0x2200, 0x22FF), (0x2460, 0x24FF),
             (0x2500, 0x257F), (0x25A0, 0x25FF), (0x2700, 0x27BF), (0x27E8, 0x27E9),
             (0x3000, 0x303F), (0xFF00, 0xFFEF), (0x00A0, 0x00FF)]:
    EXTRA.update(range(a, b + 1))

for w in (400, 500, 700, 900):
    base = f"{pkg}/files/noto-sans-sc-chinese-simplified-{w}-normal.woff"
    have = set(TTFont(base).getBestCmap())
    need = EXTRA - have
    picks = []
    for p in sorted(glob.glob(f"{pkg}/files/noto-sans-sc-[0-9]*-{w}-normal.woff")):
        cm = set(TTFont(p).getBestCmap())
        hit = cm & need
        if hit:
            picks.append(p); need -= hit
    print(w, "extra slices:", [os.path.basename(p) for p in picks])
    m = Merger(options=Options(drop_tables=["vhea", "vmtx", "VORG", "GSUB", "GPOS", "GDEF", "BASE"]))
    f = m.merge([base] + picks)
    f.flavor = "woff2"
    dst = f"{out}/noto-sans-sc-{w}.woff2"
    f.save(dst)
    cm = TTFont(dst).getBestCmap()
    print(w, "glyph cmap entries:", len(cm), "size:", os.path.getsize(dst))
