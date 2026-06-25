# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

这是一个跨 Claude Code 与 Codex 的插件市场仓库，含**两个独立插件、各 1 个技能**（互不依赖）。没有包管理 / CI / 构建系统——内容是 Markdown + bash + python。文档与提交信息用简体中文。

- `plugins/privatize-fork/` — 开源 fork 一次性私有化脚手架。
- `plugins/codex-context-doctor/` — 审计 Codex 安装的插件 / App / MCP / 技能 / 市场源。

每个插件目录含 `.claude-plugin/plugin.json`（CC）+ `.codex-plugin/plugin.json`（Codex）+ `skills/<name>/`。两个市场清单在仓库根：`.claude-plugin/marketplace.json`（CC）、`.agents/plugins/marketplace.json`（Codex），各列出这两个插件。

## 关键约定（改动前必读）

### 每个插件版本号要 3 处同步（两个插件各自独立）
改某个插件版本时，同步它的 3 处：`plugins/<plugin>/.claude-plugin/plugin.json`、`plugins/<plugin>/.codex-plugin/plugin.json`、以及 `.claude-plugin/marketplace.json` 里该插件条目的 `version`（Codex 市场清单不带 version，版本只在 plugin.json）。两个插件版本**独立**、互不牵连。用 `/bump-version <plugin> <x.y.z>` 一步搞定。

### 每个技能要双平台对齐
每个 `plugins/<plugin>/skills/<name>/` 都要：
- `SKILL.md` frontmatter 加 `disable-model-invocation: true`（CC 禁自动调用）
- `agents/openai.yaml` 写 `allow_implicit_invocation: false`（Codex 等价）

两者缺一不可，否则一个平台会漏掉「禁自动调用」。

### 两套插件清单格式并存（别混淆）
- CC：根 `.claude-plugin/marketplace.json` 列插件；每个 `plugins/<plugin>/.claude-plugin/plugin.json` 是插件清单（自动发现同目录 `skills/`）。
- Codex：根 `.agents/plugins/marketplace.json` 列插件（每条 `source.path` 指向 `./plugins/<plugin>`）；每个 `plugins/<plugin>/.codex-plugin/plugin.json` 的 `skills` 指 `./skills/`。

标准子目录布局，任意 Codex 版本可装（不再用「仓库根即插件」那种需 ≥0.142.0 的写法）。**加新插件** = 在 `plugins/` 下建目录（两个 plugin.json + `skills/<name>/`，再在两个 marketplace.json 各加一条）。

### assets SVG 是生成物
每个插件的 `plugins/<plugin>/assets/*.svg` 由根 `assets/build-svg.sh` 从该插件的 `assets/src/*.svg` 生成（脚本遍历所有插件）。改图要改 src 再重跑脚本，别手改产物。安装截图 `assets/install-*.png` 是市场级共享、手动维护。每个插件还各有自己的 `README.md`（被根 README 引用）。

## 验证（无 CI，本地自查）

```bash
shellcheck install-plugins.sh assets/build-svg.sh plugins/*/skills/*/scripts/*.sh   # shell 静态检查（应零告警）
for f in .claude-plugin/marketplace.json .agents/plugins/marketplace.json \
         plugins/*/.claude-plugin/plugin.json plugins/*/.codex-plugin/plugin.json; do
  python3 -m json.tool "$f" >/dev/null && echo "OK $f"      # 每个清单都验一遍
done
python3 -B plugins/codex-context-doctor/skills/codex-context-doctor/scripts/codex_context_doctor.py --help   # doctor 可跑
```

Codex 插件端到端校验（本机装了 Codex 时）：`codex plugin marketplace add . && codex plugin list --marketplace legdonkey --available`（应列出 2 个插件），验证完用 `codex plugin marketplace remove legdonkey` 清理。

## 提交与发布

- 提交信息：Conventional Commits 前缀（`feat:` / `fix:` / `chore:` / `docs:`）+ 简体中文描述。
- 不在 `main` 直接提交，先开分支再 PR。
- 发布：`/bump-version <plugin>` 改某个插件版本 → 上面的验证 → `git tag` → 推送 → 在 GitHub 发 release。
