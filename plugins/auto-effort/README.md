# auto-effort

auto-effort 是 Claude Code 的函数钩子 mod。它为每条主会话消息选择最低够用的 effort，支持升档和降档。默认使用 Haiku 5.5 判档，也支持 OpenRouter System One。普通轮次只在首个 `turn.step` 改写 effort；运行中插入消息在下一步单独处理。Claude Code 用追加的逐消息 effort 保留已有提示缓存。

支持 `claude-opus-5-5`、`claude-sonnet-5-5`、`claude-fable-5-2`。模型 ID 末尾的 `[1m]` 后缀不影响识别。子代理保持引擎原有行为。

## 安装

只支持 Claude Code（2.1.323 起的函数钩子接口），不提供 Codex 和 Pi 版本，无需额外环境变量。

```bash
claude plugin marketplace add legdonkey/legdonkey-plugins
claude plugin install auto-effort@legdonkey
```

本地开发时把市场换成仓库目录：`claude plugin marketplace add <仓库路径>`，或只对本次会话加载：`claude --plugin-dir <仓库路径>/plugins/auto-effort`。安装后重启 Claude Code，运行 `/auto-effort status` 有返回即表示已生效。函数钩子由插件模块直接订阅事件，不会出现在 `settings.json` 的 hooks 里，`claude plugin details` 也显示 Hooks (0)。

## 行为

- `prompt.submit` 后台判档，不改用户文本。首步等待剩余判档时间；超时不改写，沿用引擎档位。
- 斜杠命令和 `isMeta` 消息不判档。包含独立单词 `ultrathink` 的消息交给引擎。
- 确认、批准、选择等短回复和普通消息一样交给判档器，按近期对话里这条回复将要启动的工作判断（参照 Pi 的 inline-effort）。唯一的规则捷径：Fable 在 low/medium 后收到整条 `继续`、`continue`、`go on`、`keep going` 时直接升至 high（官方：Fable 5.2 在低档更容易提前收工）。
- 判档无效或置信度低于 0.5 时沿用上一轮。没有上一轮时不改写。结果受上下限与 max 开关约束；上下限冲突时以上限为准。
- `--resume` 按 session id 从持久决策恢复上一轮最终档位和摘要；低置信度沿用与 Fable「继续」升档照常使用恢复出的档位。`/clear` 删除本会话的持久决策和内存状态，其他会话不受影响。
- 每轮首步比较引擎原始 effort。相邻非 ultrathink 轮的档位发生变化时，视为用户手动改档并暂停。用 `/auto-effort on` 恢复。
- Bedrock、Vertex/Agent Platform、Foundry、自定义 `ANTHROPIC_BASE_URL` 或设置 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 时暂停，状态栏说明「会重建缓存，已暂停」。官方 `https://api.anthropic.com` 地址不算自定义网关。
- 只在改写过档位的轮次检查缓存：上一轮读取大于 0，且本次读取减少时，提示「检测到缓存读取减少，可能是切档导致缓存重建」。写入变大不计数。每轮最多计一次，同一会话累计两次后暂停；`/auto-effort on` 恢复并清零。
- 距上一个主会话请求结束超过 5 分钟、主会话压缩后、切换模型后和 `/clear` 后第一轮跳过判断，并重新建立读取基线。Claude Code 主会话实测使用 1 小时缓存 TTL，5 分钟是排除缓存过期的保守值。子代理压缩、预计算压缩和跳过的压缩不影响主会话的判断。

终端里状态接在输入框下方提示行（`auto mode on` 那一行）的末尾，行宽不够时截断；桌面端等其他界面仍显示为插件独立状态行。状态示例：`🧠 high · 自动 · Haiku 0.8s`、`🧠 medium · 沿用（判档超时）`、`⏸ 自动选档已暂停：你手动改了档位，/auto-effort on 恢复`。

## 配置

在 `/config` 修改非敏感字段，或通过 Claude Code 的 `pluginConfigs["auto-effort"].options` 配置。敏感字段使用 Claude Code 安全存储。

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `enabled` | `true` | 自动选档开关 |
| `judge` | `haiku` | `haiku`、`jev`、`d1-ultra`、`mammoth-27b`、`decider` |
| `openrouterApiKey` | 空 | 敏感字段；为空时依次读取环境变量 `OPENROUTER_API_KEY`、Pi 的 `auth.json`（`$PI_CODING_AGENT_DIR` 或 `~/.pi/agent`）中的 openrouter 条目 |
| `floor` | `low` | 最低档位 |
| `ceiling` | `xhigh` | 最高档位 |
| `allowMax` | `false` | 只有同时设置 `ceiling=max` 才会输出 max |
| `judgeTimeoutMs` | `5000` | 从提交到等待判档的总时限，限定在 1–60000 毫秒 |
| `fableFinishPrompt` | `false` | 为 Fable 追加官方收尾提示 |
| `debugLogPath` | 空 | JSON Lines 请求摘要日志的绝对路径；相对路径忽略 |

OpenRouter 模型：Jev 为 `typesafe/jev-1.14`，D1 Ultra 为 `liquid/d1-ultra`，Mammoth 为 `baseten/mammoth-1`，Decider 为 `perplexity/pplx-decider-v1.2`。调用 `https://openrouter.ai/api/v1/systemone`。失败、超时、无 key、无效结果或低置信度时，回退 Haiku 一次。会话中只提示首次回退原因。OpenRouter 等待最多占用总时限的一半，且不超过 2 秒。

`fableFinishPrompt` 是稳定的会话级系统段落。中途切换这个开关会改变系统提示，并在引擎重载提示时重建缓存。请在会话开始前设置。

## 命令

```text
/auto-effort
/auto-effort status
/auto-effort on
/auto-effort off
/auto-effort judge haiku
/auto-effort judge jev
/auto-effort floor medium
/auto-effort ceiling xhigh
/auto-effort max on
/auto-effort test <文本>
/auto-effort bench [opus|sonnet|fable|all] [holdout]
```

输入 `/auto-effort ` 后，命令名旁会灰显可用子命令；再敲子命令或取值的首字母，补全列表会列出候选和中文说明，Tab 选中。

`status` 返回开关、判档器、上下限和本会话最近 10 次决策。`lastFinal` 是上一轮最终档位；`lastDecision` 用时间、`turnId` 和步数标识来源决策；`summary` 是上一轮档位、工具次数与中断标记，不含消息原文。决策含时间、模型、判档器、判出档位、最终档位、置信度、中文理由、耗时与该次请求的缓存读写。`previousFinal` 记录决策使用的上一轮档位。修改开关、判档器和上下限会通过 `$.config.set` 写回 userConfig。

`test` 只判档，不改主会话 effort。`bench` 对插件内 `bench/judge-cases.json` 判档，返回全部与 holdout 命中率、偏低数、偏高数、无效数及中位耗时。明细写入 `bench/results/<时间戳>-<judge>.json`，不复制用例文本。测评直接比较判档器的原始结果，不用运行时上下限调整答案。

## 规则与隐私

规则及官方依据集中在 [hooks/policy-text.ts](hooks/policy-text.ts)。派生测评用例及第三方许可见 [bench/THIRD_PARTY.md](bench/THIRD_PARTY.md)。

判档器接收当前消息最多 12000 字符，之前最近十条 user/assistant 文本合计最多 24000 字符（越新越优先，每条保留结尾），以及上一轮档位、工具次数和中断标记。不发送工具结果和图片。选择 OpenRouter 时，这些文本会发送给 OpenRouter；默认只使用会话凭据调用 Anthropic Haiku。

本插件不持久化消息、回答、API key 或服务端错误原文。决策记录只保存固定中文分类理由，不保存模型自由文本理由。`$.store` 保留最近 50 个会话，每个会话最多 200 条；决策数组另限制在 1 Mi 个 UTF-16 单元内，因此 UTF-8 不超过 3 MiB，给 store 的 4 MiB 总限额留余量。空间不足时优先保留新记录。旧格式的决策数组仍可读取；没有摘要的旧记录恢复档位，工具次数按 0、中断标记按 false 处理。`$.state` 跨插件重载保留，但不跨进程重启保留。API key 只从安全配置或环境变量读取。

请求摘要日志只记录 `model`、顶层 effort、逐消息 effort 的下标与档位、消息数，不记录请求头和内容。日志写入失败只提示一次，不阻断主请求。

## 验证与限制

```bash
bash scripts/check.sh
python3 -I scripts/e2e.py claude-opus-5-5
python3 -I scripts/e2e.py claude-sonnet-5-5
python3 -I scripts/e2e.py claude-fable-5-2
python3 -I scripts/e2e.py claude-opus-5-5 --bench
python3 -I scripts/e2e.py claude-opus-5-5 --insertion
python3 -I scripts/e2e.py claude-fable-5-2 --resume
```

模拟测试不调用真实模型。e2e、bench 和 `test` 会产生费用。`$.model.complete` 的费用不包含在 headless 的 `total_cost_usd` 中，决策与测评结果另记 `usage`，核算时必须加上这些 Haiku token 的费用。

运行中插入的普通消息会后台判档，并在主会话下一个 `turn.step` 应用一次，可以是非首步。Claude Code 2.1.323 实测在 `index=1` 追加逐消息 effort，证据见下方验收记录。

手动改档检测只比较同一模型相邻两个普通轮的引擎 effort；切换模型、斜杠命令（含带 effort 的 skill）和 ultrathink 轮不参与比较，也不会被后续确认消息沿用。它仍无法区分用户、环境配置或其他插件对原始 effort 的修改。复用 Pi 的 key 时只读取 `auth.json`，不写回；`!命令` 形式的 key 不支持，`$NAME` 模板只从该条目自带的 `env` 取值（mod 接口只能按字面量名读环境变量），这两种情况请改用 `openrouterApiKey` 或 `OPENROUTER_API_KEY`。插件重载会丢失尚未完成的后台判档，当前轮沿用引擎 effort；已完成的档位与暂停状态继续保留。底层 HTTP 接口没有取消参数，OpenRouter 超时后丢弃晚到回答，网络请求仍可能在服务端完成。

Claude Code 2.1.323 的消息读取接口不提供可用于回退定位的稳定标识：`session.append.uuid` 只在追加事件中出现（`dev/plugin-authoring/types/claude-code.d.ts:11838`），`SessionMessage` 只有 role、text、工具摘要和压缩时的临时 handle（同文件 `12446–12471`）；`handle` 明确不出现在 `$.session.messages()` 中。恢复时也不重放旧消息的追加事件。此次按接口限制只实现按会话恢复，无法在 `/rewind` 后选择当前分支的最后一条决策，也无法把新 fork 的 session id 关联回原会话。恢复采用该 session id 最近写入的有效档位。跨进程只恢复档位、来源、轮次和摘要；暂停状态与缓存守护计数仍属于进程内状态。`--continue` 与交互式恢复未实测。

摘要在 `turn.complete` 时写回决策；进程在轮次完成前退出时，保留发送请求前的档位，工具次数与中断标记没有完整摘要。存储裁剪后的旧会话无法恢复。

## 测评结果（2026-11-14）

`/auto-effort bench all`，每个模型 75 个用例，其中 20 个 holdout。

Haiku 判档器：

| 模型 | 全部命中 | holdout 命中 | 偏低 | 偏高 | 中位耗时 |
| --- | --- | --- | --- | --- | --- |
| `claude-opus-5-5` | 75/75（100.0%） | 20/20 | 0 | 0 | 817 ms |
| `claude-fable-5-2` | 71/75（94.7%） | 20/20 | 3 | 1 | 841 ms |
| `claude-sonnet-5-5` | 70/75（93.3%） | 18/20 | 4 | 1 | 844 ms |

明细见 [测评 JSON](bench/results/2026-11-13T17-14-39-062Z-haiku.json)。

Jev 判档器（225 次中 5 次因置信度不足回退 Haiku）：

| 模型 | 全部命中 | holdout 命中 | 偏低 | 偏高 | 中位耗时 |
| --- | --- | --- | --- | --- | --- |
| `claude-opus-5-5` | 75/75（100.0%） | 20/20 | 0 | 0 | 418 ms |
| `claude-fable-5-2` | 71/75（94.7%） | 20/20 | 3 | 1 | 409 ms |
| `claude-sonnet-5-5` | 68/75（90.7%） | 18/20 | 5 | 2 | 407 ms |

明细见 [测评 JSON](bench/results/2026-11-13T17-16-25-429Z-jev.json)。「批准计划」类用例（a08–a10）在 Fable 和 Sonnet 上判为 medium，派生标注要求 high/xhigh；这些标注按「Sonnet 比 Opus 高一档」推出，而 Sonnet 5.5 官方起点是 agent 编程用 medium，标注可能偏严，未据此修改规则。

端到端实测（Opus、Sonnet、Fable 各五轮，含运行中插入消息与 `--resume` 恢复）均通过：第 2 轮以后每轮缓存写入小于 2000 token，变档不重建缓存。运行记录不随仓库发布，可用上文 `scripts/e2e.py` 在本机重跑（会产生费用）。
