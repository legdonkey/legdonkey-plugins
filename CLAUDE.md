# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

privatize-fork 是一个跨 Claude Code 与 Codex 的「插件 + 技能」仓库，同时作为 CC 插件与 Codex 插件分发（底层是开放标准 SKILL.md，技能本身也可独立使用）。没有包管理 / CI / 构建系统——内容是 Markdown + bash + python。文档与提交信息用简体中文。

收录两个技能：
- `skills/privatize-fork/` — 开源 fork 一次性私有化脚手架。
- `skills/codex-context-doctor/` — 审计 Codex 安装的插件 / App / MCP / 技能 / 市场源。

## 关键约定（改动前必读）

### 版本号必须在 3 个文件同步
改版本时同时改：`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`（`plugins[0].version`）、`.codex-plugin/plugin.json`。三者必须一致。用 `/bump-version <x.y.z>` 一步搞定。

### 新增技能要双平台对齐
每个 `skills/<name>/` 都要：
- `SKILL.md` frontmatter 加 `disable-model-invocation: true`（CC 禁自动调用）
- `agents/openai.yaml` 写 `allow_implicit_invocation: false`（Codex 等价）

两者缺一不可，否则一个平台会漏掉「禁自动调用」。

### 两套插件清单格式并存（别混淆）
- CC：`.claude-plugin/{plugin.json, marketplace.json}`，自动发现 `skills/`。
- Codex：`.agents/plugins/marketplace.json`（`source.path: "./"`）+ `.codex-plugin/plugin.json`（`skills: "./skills/"`）。这种「仓库根即插件」布局需 Codex ≥ 0.142.0。

两边都是「一个插件打包全部 skills」。新增技能 = 在 `skills/` 下加一个目录，两个插件都会自动发现，无需改清单。

### assets SVG 是生成物
`assets/*.svg` 由 `assets/src/build-svg.sh` 从 `assets/src/*.svg` 生成。改图要改 src 再重跑脚本，别手改产物。

## 验证（无 CI，本地自查）

```bash
shellcheck install-plugins.sh skills/*/scripts/*.sh assets/src/*.sh   # shell 静态检查（应零告警）
python3 -m json.tool .claude-plugin/plugin.json           # 每个 JSON 清单都验一遍
python3 -m json.tool .claude-plugin/marketplace.json
python3 -m json.tool .codex-plugin/plugin.json
python3 -m json.tool .agents/plugins/marketplace.json
python3 -B skills/codex-context-doctor/scripts/codex_context_doctor.py --help   # doctor 可跑
```

Codex 插件端到端校验（本机装了 Codex 时）：`codex plugin marketplace add . && codex plugin list --marketplace legdonkey --available`，验证完用 `codex plugin marketplace remove legdonkey` 清理。

## 提交与发布

- 提交信息：Conventional Commits 前缀（`feat:` / `fix:` / `chore:` / `docs:`）+ 简体中文描述。
- 不在 `main` 直接提交，先开分支再 PR。
- 发布：`/bump-version` 改版本 → 上面的验证 → `git tag` → 推送 → 在 GitHub 发 release。
