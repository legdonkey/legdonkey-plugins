# 项目维护规则

auto-effort 是一个 Claude Code mod：每条用户消息由判档器（默认 Haiku 5.5，可选 OpenRouter 上的 System One 分类模型）按官方指南选 effort，在 `turn.step` 改写本轮首个请求的 effort。只支持 `claude-opus-5-5`、`claude-sonnet-5-5`、`claude-fable-5-2`。

## 语言

- 注释、文档、提交说明、给用户的提示使用简体中文；代码标识符和外部协议保持原名。

## 判档规则

- 判档规则和提示词只在 `hooks/policy-text.ts` 维护，依据写在文件头部。改规则前先核对官方文档，不凭印象改。
- 测评用例 `bench/judge-cases.json` 由 `scripts/derive-cases.py` 从 `bench/effortless-judge-cases.json` 派生，不要手改派生文件；第三方许可见 `bench/THIRD_PARTY.md`。

## mod 接口

- 接口以 `dev/plugin-authoring/types/claude-code.d.ts` 为准，说明见 `dev/plugin-authoring/reference.md` 和 `examples/`。这些文件由 Claude Code 生成，不提交。
- 接收 `$` 的辅助函数必须是文件顶层的函数声明，否则 `claude plugin validate` 拒绝。
- 模块里不能用 `import()`；文件间用 `import` 声明。

## 隐私和凭据

- 不记录、不显示用户消息原文和 API key；日志只记长度、档位、置信度、耗时和缓存用量。
- OpenRouter key 只从 `userConfig` 的敏感字段、环境变量 `OPENROUTER_API_KEY` 或 Pi 的 `auth.json`（只读）获取，不写进任何文件，不出现在日志和提示里。
- 错误信息按白名单转成中文原因，不显示服务端原文。

## 交付前检查

```bash
bash scripts/check.sh
```

会产生费用的检查（真实调用模型）：

```bash
python3 -I scripts/e2e.py claude-opus-5-5      # 端到端：判档 + 缓存
python3 -I scripts/cache-probe.py claude-opus-5-5  # 固定档位序列的缓存探针
```
