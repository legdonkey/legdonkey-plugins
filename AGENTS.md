# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 这是什么

这是一个跨 Claude Code 与 Codex 的插件市场仓库，含**三个独立插件、各 1 个技能**（互不依赖）；其中 bailian-tts 还作为 Pi 包发布。没有包管理 / CI / 构建系统——内容是 Markdown + bash + python。文档与提交信息用简体中文。

- `plugins/privatize-fork/` — 开源 fork 一次性私有化脚手架。
- `plugins/context-doctor/` — 跨平台审计 Claude Code 与 Codex 的插件 / MCP / 市场源 / 技能（调官方 CLI 治理入口，技能走目录）。
- `plugins/bailian-tts/` — 阿里百炼 Qwen-Audio 配音脚手架（固定 `qwen-audio-3.1-tts-flash` 与其音色 catalog；含脚本批量配音、SRT 字幕与声音复刻）。

每个插件目录含 `.claude-plugin/plugin.json`（CC）+ `.codex-plugin/plugin.json`（Codex）+ `skills/<name>/`。两个市场清单在仓库根：`.claude-plugin/marketplace.json`（CC）、`.agents/plugins/marketplace.json`（Codex），各列出这三个插件。

## 关键约定（改动前必读）

### 每个插件版本号要 3 处同步（各插件彼此独立）
改某个插件版本时，同步它的 3 处：`plugins/<plugin>/.claude-plugin/plugin.json`、`plugins/<plugin>/.codex-plugin/plugin.json`、以及 `.claude-plugin/marketplace.json` 里该插件条目的 `version`（Codex 市场清单不带 version，版本只在 plugin.json）。各插件版本**独立**、互不牵连。用 `/bump-version <plugin> <x.y.z>` 一步搞定。

### 每个技能要双平台对齐
每个 `plugins/<plugin>/skills/<name>/` 都要：
- `SKILL.md` frontmatter 加 `disable-model-invocation: true`（CC 禁自动调用）
- `agents/openai.yaml` 写 `allow_implicit_invocation: false`（Codex 等价）

两者缺一不可，否则一个平台会漏掉「禁自动调用」。

### 两套插件清单格式并存（别混淆）
- CC：根 `.claude-plugin/marketplace.json` 列插件；每个 `plugins/<plugin>/.claude-plugin/plugin.json` 是插件清单（自动发现同目录 `skills/`）。
- Codex：根 `.agents/plugins/marketplace.json` 列插件（每条 `source.path` 指向 `./plugins/<plugin>`）；每个 `plugins/<plugin>/.codex-plugin/plugin.json` 的 `skills` 指 `./skills/`。

标准子目录布局，任意 Codex 版本可装（不再用「仓库根即插件」那种需 ≥0.142.0 的写法）。**加新插件** = 在 `plugins/` 下建目录（两个 plugin.json + `skills/<name>/`，再在两个 marketplace.json 各加一条）。

### Pi 包入口只暴露 bailian-tts
根 `package.json` 是 Pi 包清单（`pi install git:github.com/legdonkey/legdonkey-plugins`），`pi.skills` 只列 `./plugins/bailian-tts/skills`，`extensions` / `prompts` / `themes` 显式置空以免约定目录被自动发现。它不是 npm 项目，不加依赖、不加 `version`（Pi 的 git 包按 ref 更新）。新插件只有在与宿主无关时才加进 `pi.skills`；context-doctor 审计 CC / Codex 配置，不暴露给 Pi。Pi 读 `disable-model-invocation`，手动触发名为 `/skill:<name>`。

### assets SVG 是生成物
每个插件的 `plugins/<plugin>/assets/*.svg` 由根 `assets/build-svg.sh` 从该插件的 `assets/src/*.svg` 生成（脚本遍历所有插件）。改图要改 src 再重跑脚本，别手改产物。安装截图 `assets/install-*.png` 是市场级共享、手动维护。每个插件还各有自己的 `README.md`（被根 README 引用）。

## 验证（无 CI，本地自查）

```bash
shellcheck install-plugins.sh assets/build-svg.sh plugins/*/skills/*/scripts/*.sh   # shell 静态检查（应零告警）
for f in package.json .claude-plugin/marketplace.json .agents/plugins/marketplace.json \
         plugins/*/.claude-plugin/plugin.json plugins/*/.codex-plugin/plugin.json; do
  python3 -m json.tool "$f" >/dev/null && echo "OK $f"      # 每个清单都验一遍
done
python3 -B plugins/context-doctor/skills/context-doctor/scripts/context_doctor.py --help   # doctor 可跑
```

Codex 插件端到端校验（本机装了 Codex 时）：`codex plugin marketplace add . && codex plugin list --marketplace legdonkey --available`（应列出 3 个插件），验证完用 `codex plugin marketplace remove legdonkey` 清理。

Pi 包端到端校验（本机装了 Pi 时）：`pi install "$PWD"` 后在其它目录跑 `pi --no-session --no-tools -p "/skill:bailian-tts 只回答你是否收到了技能说明文档"`（应回答是；把技能名换成 context-doctor / privatize-fork 应回答否），验证完用 `pi remove "$PWD"` 清理。

## 提交与发布

- 提交信息：Conventional Commits 前缀（`feat:` / `fix:` / `chore:` / `docs:`）+ 简体中文描述。
- 不在 `main` 直接提交，先开分支再 PR。
- 发布：`/bump-version <plugin>` 改某个插件版本 → 上面的验证 → `git tag` → 推送 → 在 GitHub 发 release。
