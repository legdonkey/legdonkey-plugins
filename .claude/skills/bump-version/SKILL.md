---
name: bump-version
description: 把仓库版本号同步改到指定值，同时更新 .claude-plugin/plugin.json、.claude-plugin/marketplace.json、.codex-plugin/plugin.json 三个清单文件，并提示后续验证与发布步骤。
disable-model-invocation: true
---

# bump-version

把本仓库版本号一次性同步到 `$ARGUMENTS`（形如 `1.5.0`）。本仓库版本号分散在 3 个文件，必须保持一致——这个技能确保不漏改。

## 步骤

1. 校验 `$ARGUMENTS` 是合法 semver（`x.y.z`）。若为空，停下来问用户要目标版本号。
2. 用 Edit 把以下三处版本号都改成新值（**只改版本，别动其它字段**）：
   - `.claude-plugin/plugin.json` → 顶层 `"version"`
   - `.claude-plugin/marketplace.json` → `plugins[0].version`
   - `.codex-plugin/plugin.json` → 顶层 `"version"`
3. 校验三者一致且所有 JSON 清单合法：
   ```bash
   grep -h '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json
   for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json; do
     python3 -m json.tool "$f" >/dev/null && echo "OK $f" || echo "BAD $f"
   done
   ```
   确认三行版本号一致、全部 `OK`。
4. **不要**自动提交、打 tag 或发布。改完告诉用户接下来手动做：开分支提交 → `git tag v$ARGUMENTS` → 推送 → 在 GitHub 发 release。
