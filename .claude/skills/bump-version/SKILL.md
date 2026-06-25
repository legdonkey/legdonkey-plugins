---
name: bump-version
description: 把某个插件的版本号同步改到指定值，同时更新该插件的 .claude-plugin/plugin.json、.codex-plugin/plugin.json，以及根 .claude-plugin/marketplace.json 里它的条目，并提示后续验证与发布步骤。
disable-model-invocation: true
---

# bump-version

把**某一个插件**的版本号一次性同步到指定值。本仓库有两个独立插件（`privatize-fork`、`codex-context-doctor`），版本各走各的；每个插件的版本号分散在 3 处，这个技能确保不漏改。

参数：`$ARGUMENTS` = `<插件名> <x.y.z>`，例如 `privatize-fork 1.6.0`。

## 步骤

1. 解析 `$ARGUMENTS`：第一个词是插件名（必须是 `plugins/` 下已存在的目录，如 `privatize-fork` 或 `codex-context-doctor`），第二个词是合法 semver（`x.y.z`）。缺参数或插件名不存在就停下来问用户。
2. 用 Edit 把以下三处的版本号都改成新值（**只改这个插件的版本，别动其它字段、别动另一个插件**）：
   - `plugins/<插件名>/.claude-plugin/plugin.json` → 顶层 `"version"`
   - `plugins/<插件名>/.codex-plugin/plugin.json` → 顶层 `"version"`
   - `.claude-plugin/marketplace.json` → `plugins[]` 里 `name` 等于该插件的那一条的 `version`（Codex 的 `.agents/plugins/marketplace.json` 不带 version，不用改）
3. 校验该插件三处一致、所有 JSON 合法：
   ```bash
   P=<插件名>
   grep -h '"version"' "plugins/$P/.claude-plugin/plugin.json" "plugins/$P/.codex-plugin/plugin.json"
   python3 -c "import json; m=json.load(open('.claude-plugin/marketplace.json')); print([p['version'] for p in m['plugins'] if p['name']=='$P'])"
   for f in .claude-plugin/marketplace.json .agents/plugins/marketplace.json plugins/*/.claude-plugin/plugin.json plugins/*/.codex-plugin/plugin.json; do
     python3 -m json.tool "$f" >/dev/null && echo "OK $f" || echo "BAD $f"
   done
   ```
   确认该插件三处版本号一致、全部 `OK`。
4. **不要**自动提交、打 tag 或发布。改完告诉用户接下来手动做：开分支提交 → 打**插件专属** tag（如 `<插件名>-v<x.y.z>`，两个插件版本独立，别用裸 `v<x.y.z>` 以免歧义）→ 推送 → 在 GitHub 发 release。
