# CLAUDE.md

这个仓库是一个插件市场，同时支持 Claude Code（下文简称 CC）、Codex 和 Pi。插件之间不引用对方的文件；要用另一个技能，按技能名调用。

## 关键约定（改动前必读）

### 版本号

各插件的版本号相互独立，用 semver（`x.y.z`）。改一个插件的版本号时，把它的 3 处改成同一个值：
1. `plugins/<plugin>/.claude-plugin/plugin.json` 的顶层 `version`
2. `plugins/<plugin>/.codex-plugin/plugin.json` 的顶层 `version`
3. `.claude-plugin/marketplace.json` 里这个插件条目的 `version`

Codex 市场清单不写 version。

### 自动调用开关：三个平台要一致

要禁止模型自动调用一个技能，两处同时写：
- `SKILL.md` 的 frontmatter：`disable-model-invocation: true`。CC 和 Pi 读这一项。
- `agents/openai.yaml`：`allow_implicit_invocation: false`。Codex 读这一项。

### 加一个新插件

1. 在 `plugins/` 下建插件目录。
2. 在目录里放 `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json` 和 `skills/<name>/`。
3. 在 `.claude-plugin/marketplace.json` 和 `.agents/plugins/marketplace.json` 里各加一条。
4. 满足下面两条时，把 `./plugins/<plugin>/skills` 加进 `package.json` 的 `pi.skills`，再运行下文的 Pi 端到端校验：
   - **不写死宿主路径。** 技能引用自己的文件时，用相对技能目录的路径，不写 `~/.claude/...` 或 `~/.codex/...`。
   - **为宿主专有能力写好退化方案。** Pi 核心没有提问弹窗、子代理和后台命令通知。提问弹窗和子代理可以由扩展提供。技能用到这些能力时，写明「有就用，没有就怎样」。例如：用普通消息提问；由主会话按顺序执行；用 `nohup … &` 启动后查日志。

### package.json 是 Pi 包清单

- `extensions`、`prompts`、`themes` 显式置空，这样 Pi 不会自动发现约定目录。
- 这个文件不是 npm 项目清单。不加依赖，不加 `version`。Pi 的 git 包按 ref 更新。

### assets 里的 SVG 是生成物

每个插件的 `plugins/<plugin>/assets/*.svg` 由根目录的 `assets/build-svg.sh` 生成。改图时，改 `assets/src/` 里的源文件，再重跑脚本。不要直接改生成的 SVG。

## 验证（无 CI，本地自查）

```bash
shellcheck install-plugins.sh assets/build-svg.sh plugins/*/skills/*/scripts/*.sh   # shell 静态检查（应零告警）
for f in package.json .claude-plugin/marketplace.json .agents/plugins/marketplace.json \
         plugins/*/.claude-plugin/plugin.json plugins/*/.codex-plugin/plugin.json; do
  python3 -m json.tool "$f" >/dev/null && echo "OK $f"      # 每个清单都验一遍
done
```

Claude Code 插件校验（本机装了 Claude Code 时）：
1. 运行 `claude plugin validate .`，再对每个插件运行 `claude plugin validate plugins/<plugin>`。确认都显示 `Validation passed`。这一步检查清单字段和技能 frontmatter，不调用模型。
2. 换到其它目录，对每个插件的每个技能运行 `claude -p --plugin-dir <仓库>/plugins/<plugin> "/<plugin>:<skill> 只回答你是否收到了技能说明文档"`。确认每次都回答「是」。`--plugin-dir` 只在这次会话里加载插件，不用清理。本机已装同名插件时，回答可能来自已装的那份。

Codex 插件端到端校验（本机装了 Codex 时）：
1. 运行 `codex plugin marketplace list`，看本机是否已登记 `legdonkey`。
2. 没登记时，运行 `codex plugin marketplace add .`；已登记时跳过这一步。
3. 运行 `codex plugin list --json --marketplace legdonkey --available`，确认输出列出 `plugins/` 下的全部插件。
4. 只有第 2 步做了 add 时，才运行 `codex plugin marketplace remove legdonkey` 清理。已登记的不要 remove：remove 会把从它装的插件一起卸载。

Pi 包端到端校验（本机装了 Pi 时）：
1. 运行 `pi install "$PWD"`。
2. 换到其它目录，对 `pi.skills` 里的每个技能运行 `pi --no-session --no-tools -p "/skill:<name> 只回答你是否收到了技能说明文档"`。
3. 确认 Pi 每次都回答「是」。
4. 运行 `pi remove "$PWD"` 清理。

## 提交与发布

- 提交信息用 Conventional Commits 前缀（`feat:`、`fix:`、`chore:`、`docs:`），后接简体中文描述。
- 不直接在 `main` 上提交。先开分支，再提 PR。
- 发布步骤：
  1. 改这个插件的版本号（见上文「版本号」）。改完代码马上发布时，版本号和代码放在同一个 PR 里改；先合进 `main`、以后再发布时，才另提一个 `chore: 升级 <plugin> 至 x.y.z` 的 PR。
  2. 运行上文的验证。
  3. 打 tag，名字是 `<plugin>-v<x.y.z>`。各插件版本号相互独立，所以不用裸的 `v<x.y.z>`。
  4. 推送。
  5. 在 GitHub 发 release。
