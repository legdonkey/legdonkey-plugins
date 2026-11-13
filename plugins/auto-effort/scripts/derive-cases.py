"""从 effortless 的 judge-cases.json 派生三个模型的标注。

规则（依据 policy-text.ts 引用的官方指南）：
- Sonnet 5.5：沿用原标注（原标注以 Sonnet 为主）。原标注是 Opus 的用例，按「同一任务 Sonnet 比 Opus 高一档」上移。
- Fable 5.2：与 Sonnet 同一刻度（官方：medium 对应交互式编程，high 对应难编程和长任务）。
- Opus 5.5：Sonnet 标注下移一档，并接受原标注中 high 及以下的档位（官方：Opus 5.5 的 medium 已超过 Opus 5 的 high；
  Claude Code 档位表「修已有代码的 bug 用 high」不分模型；Opus 指南要求 xhigh 只用在测得收益处，所以不接受原标注的 xhigh）。
- follow-up 类（沿用当前档）和明确要求深入思考的 meta 用例，三个模型使用同一标注。
"""
import json, sys

LEVELS = ["low", "medium", "high", "xhigh", "max"]
def shift(labels, step):
    return sorted({LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(l) + step))] for l in labels}, key=LEVELS.index)
def order(labels):
    return sorted(set(labels), key=LEVELS.index)

src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src))
out = []
for c in data["cases"]:
    ok = c["ok"]
    same_for_all = c["kind"] == "follow-up" or c["id"] in ("m03", "h19")
    if same_for_all:
        sonnet = fable = opus = order(ok)
    elif c["current"]["model"] == "opus":
        opus = order(ok)
        sonnet = order(shift(ok, +1) + [max(ok, key=LEVELS.index)])
        fable = sonnet
    else:
        sonnet = order(ok)
        fable = sonnet
        opus = order(shift(ok, -1) + [l for l in ok if LEVELS.index(l) <= LEVELS.index("high")])
    case = {k: v for k, v in c.items() if k not in ("ok", "current")}
    case["currentEffort"] = c["current"]["effort"]
    case["ok"] = {"claude-sonnet-5-5": sonnet, "claude-opus-5-5": opus, "claude-fable-5-2": fable}
    case["source"] = {"model": c["current"]["model"], "ok": ok}
    out.append(case)

json.dump({
    "about": "派生自 HeyCubit/effortless 的 bench/judge-cases.json（MIT，见 bench/THIRD_PARTY.md）。ok 按模型列出可接受的档位，第一个是最低可接受档；派生规则见 scripts/derive-cases.py。holdout 用例不用于调整提示词。",
    "cases": out,
}, open(dst, "w"), ensure_ascii=False, indent=1)
print(len(out), "cases written")
