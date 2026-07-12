# Context Doctor：Codex 桌面端远程插件审计修复设计

## 背景与问题

Context Doctor 3.0 目前把 `codex plugin list --json --available` 当作 Codex 插件的完整来源。实际检查发现，该命令只列出已配置的 marketplace snapshot，不能完整反映 Codex 桌面端“插件 → 管理”页面中的远程插件安装状态，也没有覆盖桌面端远程 catalog 的全部可安装插件。

Codex 桌面端远程插件涉及两个本地数据源：

```text
~/.codex/plugins/cache/openai-curated-remote/<plugin>/<version>/
~/.codex/cache/remote_plugin_catalog/*.json
```

本机远程缓存中的 8 个插件与桌面端管理页面逐项一致；最新远程 catalog 包含 1763 条记录，其中 86 条带至少 1 个 Skill，按裸名称去重后为 85 个远程技能插件。

当前报告因此存在三类错误：

- `data-analytics`、`openai-templates` 等桌面端已安装插件漏报。
- `openai-developers`、`build-web-data-visualization` 等远程已安装插件，被 CLI 另一个来源下的同名“可装”记录误导。
- 远程 catalog 中带 Skills 的可安装插件没有完整进入报告。

## 目标

1. 将桌面端远程缓存作为远程插件安装状态的本地证据。
2. 将远程 catalog 中带至少 1 个 Skill 的全部唯一插件加入报告。
3. CLI 与远程 catalog 的同名插件按市场来源分别保留，不互相覆盖。
4. 只有完整插件 ID 相同时才合并，避免未来 CLI 也返回远程市场后出现完全重复节点。
5. 已安装远程插件展示完整本地组件；可安装远程插件展示 catalog 级元数据。
6. 全部远程技能插件使用 catalog 完整描述，并进入现有中文翻译缓存。
7. 使用桌面端友好名称，同时保留内部插件名用于搜索和审计。
8. 不把“缓存存在”扩张解释为“当前已启用”。

## 非目标

- 不通过 UI 自动化抓取 Codex 桌面端管理页面。
- 不读取或修改账号鉴权信息、远程服务状态或私有配置。
- 不把没有 Skills 的纯 App/连接器条目加入插件报告。
- 不在可安装插件节点中展开 catalog 的全部技能和 app 详情。
- 不在本次修复中增加 Codex token 成本计算。

## 方案选择

### 采用方案：CLI 与远程技能插件并行保留

CLI marketplace snapshot 与桌面端远程技能插件是两个独立来源。报告同时采集、分别归入市场，不按裸插件名互相覆盖：

```text
CLI marketplace snapshots ──────────────┐
                                        ├─ 按完整插件 ID 合并到报告
远程 catalog（仅带 Skills）             │
        ↑                               │
远程缓存（覆盖远程内部的安装状态与组件）─┘
```

同名但市场不同的插件保留为两个节点，例如：

```text
openai-developers@openai-curated
openai-developers@openai-curated-remote
```

这样既能反映桌面端远程安装状态，也不会丢掉 CLI 市场的真实记录。

### 未采用方案一：远程同名覆盖 CLI

该方案页面更简洁，但会隐藏 CLI 市场中确实存在的另一个发行来源，破坏 Context Doctor 的跨来源审计能力。

### 未采用方案二：依赖会话快照声明已安装插件

会话快照只保证当前模型可见的工具和技能，不能覆盖没有当前可见技能的 app-only 插件，因此不能作为完整安装清单。

### 未采用方案三：UI 自动化读取管理页面

UI 自动化依赖窗口状态、页面结构和登录态，不适合只读、可重复的命令行审计。

## 数据来源与判定规则

### 远程 catalog

从以下目录选择修改时间最新且 JSON 可解析的 catalog：

```text
~/.codex/cache/remote_plugin_catalog/*.json
```

catalog 必须包含数组字段 `plugins`。每个有效条目至少包含非空 `name`，且 `release.skills` 必须是非空数组。没有 Skills 的纯 App/连接器条目不进入报告。同一 catalog 内出现重复裸名称时，保留 catalog 顺序中的第一条；当前唯一重复项 `metabase` 的较新版本位于前面，因此该规则稳定选择较新记录，同时不依赖版本字符串格式。

每个通过 Skills 过滤的 catalog 条目生成一个远程插件候选，使用：

- `name`
- `release.display_name`
- `release.version`
- `release.description`
- `installation_policy`
- app 与 skill 数量摘要

可安装节点不携带 catalog 内的完整 skills/apps 数组，避免组件明细把单文件报告膨胀到不可用；已安装节点仍从本地插件包读取完整组件。

### 远程安装状态

满足以下条件的目录视为桌面端远程插件安装证据：

```text
~/.codex/plugins/cache/openai-curated-remote/<plugin>/<version>/.codex-plugin/plugin.json
```

要求 `plugin.json` 可解析，且包含非空 `name`。如果同一插件存在多个有效版本目录，选择 `.codex-plugin/plugin.json` 修改时间最新的一份，并使用清单中的真实版本号。

远程缓存中的插件覆盖 catalog 同名候选并写入：

```json
{
  "installed": true,
  "enabled": null,
  "install_state_source": "desktop-cache"
}
```

`INSTALLED_BY_DEFAULT` 是 catalog 的安装策略，不单独当作当前用户安装证据；没有有效缓存时仍按可安装节点展示，并保留该策略字段。当前 `Default templates` 有有效远程缓存，因此会正确显示为已安装。

### 中文用途

远程 catalog 按裸名称去重后的 85 个技能插件全部使用 `release.description` 完整描述作为用途文本，并调用现有 `register_translatable()` 登记到用户级翻译缓存。

首次审计最多产生约 85 条待译内容。继续沿用 Context Doctor 技能的既有规则：待译超过 30 条时按每批约 40 条拆分，由并行子代理翻译，主流程统一写回缓存并二次渲染。后续审计命中缓存，不重复翻译。

完整描述缺失时退回 `release.interface.short_description`；两者都缺失时不登记翻译，报告只显示名称和版本。

## 合并流程

Codex 采集顺序调整为：

1. 调用 `codex plugin list --json --available`，解析 CLI 已装与可装记录。
2. 加载最新远程 catalog，并按裸名称去重。
3. 扫描远程缓存，生成远程已安装记录。
4. 远程已安装记录只覆盖远程 catalog 内部的同名可安装候选。
5. 将 CLI 与远程记录按完整插件 ID 合并；同名但不同市场的节点全部保留。
6. 如果 CLI 将来也返回完全相同的 `name@openai-curated-remote`，以远程缓存/catalog 记录为准，避免完全重复。
7. 新增或更新 `openai-curated-remote` 市场节点，来源类型标记为 `desktop-remote-catalog`。
8. 继续执行 MCP 归属、会话可见态标记、翻译登记、建议生成和 HTML 渲染。

## 报告呈现

远程已安装插件显示：

- 桌面端友好名称，例如 `Data Analytics`、`Default templates`。
- 状态徽标为“已安装”。
- 市场为 `openai-curated-remote`。
- 展开后显示本地清单中的完整技能、MCP 和 app 组件。
- 内部裸名称、版本和安装状态来源保留在 inventory 与搜索字段中。

远程可安装插件显示：

- 友好名称、版本、中文完整用途。
- 状态徽标为“可装”。
- skill/app 数量摘要，不展开完整组件。
- catalog 安装策略。

CLI 与远程同名插件都进入 inventory 和 HTML，分别归属各自市场。搜索裸名称时会同时命中，用户可通过市场和完整 ID 区分来源。

报告模板的安装状态改为三态：

- `enabled: true` → 已启用
- `enabled: false` → 已禁用
- `enabled: null` 且 `installed: true` → 已安装

## 性能与体积控制

- 只解析最新一个 catalog 文件。
- catalog 先过滤到 85 个唯一技能插件，再构建报告节点。
- catalog 可安装插件只保留渲染所需字段，不复制完整 skills/apps 对象。
- 85 个唯一技能插件的完整描述合计约 2 万字符，直接使用完整描述，不复制 catalog 中与渲染无关的其他长字段。
- GitHub stars 只对具有明确源码仓库 URL 的插件查询；远程 catalog 可装节点不额外推断源码地址。
- HTML 仍保持单文件、离线可打开；搜索和过滤继续在浏览器端完成。

## 错误处理与审计边界

- catalog 目录不存在或全部损坏：仍扫描远程缓存中的已安装插件，并用 CLI 补缺；只缺少 catalog 可安装清单，同时在 Codex 审计说明中标注远程 catalog 不可用。
- 单个 catalog 条目损坏：只跳过该条目。
- 单个远程缓存损坏：该插件退回 catalog 的可安装状态，不影响其他插件。
- 远程缓存中存在 catalog 没有的插件：仍作为远程已安装插件加入报告。
- 远程缓存只能证明插件包已落地，不能独立证明启用状态。
- catalog 是展示与可安装清单来源，不代表其中全部插件已安装。

## 测试设计

使用 Python 标准库 `unittest`，不增加第三方依赖。测试通过临时 home 构造 CLI 返回、远程缓存和 catalog，不依赖本机真实 `~/.codex`。

覆盖以下行为：

1. 最新有效 catalog 被选中，损坏文件被安全忽略。
2. catalog 中所有带 Skills 的唯一名称都生成远程插件节点，纯 App 条目被排除。
3. catalog 重名条目保留第一条。
4. 有效远程缓存把同名 catalog 节点覆盖为已安装，启用状态为未知。
5. 同一插件多个缓存版本时选择最新有效清单。
6. CLI 与远程同名、不同市场的插件同时保留。
7. 完整插件 ID 相同时只保留远程来源的一份记录。
8. 远程缓存有、catalog 没有的插件仍作为已安装加入。
9. 远程可安装插件只保留完整描述和数量摘要，不复制完整组件数组。
10. 全部远程技能插件的完整描述都登记翻译，缺失完整描述时按规则回退。
11. catalog 缺失时仍保留远程缓存已安装插件和 CLI 独有插件，并生成边界说明。
12. HTML 对 `enabled: null` 显示“已安装”，不误写“已启用”。

## 文档更新

同步更新：

- `plugins/context-doctor/README.md`：Codex 插件数据源、双来源保留规则、Skills 过滤与首次翻译成本。
- `plugins/context-doctor/skills/context-doctor/SKILL.md`：采集、翻译和审计边界说明。
- 报告内置审计边界：区分 CLI marketplace snapshot、桌面端远程 catalog 与远程缓存。

本次不修改插件版本号，不提交、不推送；版本发布仍按仓库现有发布流程单独处理。

## 补充设计：插件自带 MCP 归属

### 问题

新版 `codex mcp list --json` 会把插件自带 MCP 以裸服务名返回，例如 `computer-use`、`event-stream`、`github`、`oppo-omni` 和 `sites-design-picker`。现有归属逻辑只识别旧格式 `plugin:<插件>:<服务>`，导致这些 MCP 一方面已经从插件 `.mcp.json` 出现在 `components.mcp`，另一方面又被重复列入“独立 MCP 服务器”。

### 采用方案

保持旧格式兼容，并增加基于已安装插件声明的保守匹配：

1. `plugin:<插件>:<服务>` 继续按显式插件名归属。
2. 裸服务名只与 `section.plugins` 中已安装插件的 `components.mcp` 比较，不使用可安装插件候选。
3. 只有一个插件声明该服务名时，直接归属。
4. 多个已安装插件声明同名服务时，先用 `codex mcp list` 的非敏感 `transport.cwd` 对照 `<marketplace>/<plugin>` 安装路径，再用非空且完全相同的 `target` 缩小候选。
5. 缩小后仍不能唯一确定时，保留在独立 MCP 列表，不猜测归属。
6. 归属成功后，用 CLI 返回的传输类型、鉴权/状态和完整服务名补充插件组件，并从独立列表移除。

不读取 `transport.env`、参数或鉴权令牌。`cwd` 只用于插件归属，不渲染为凭据。

### 未采用方案

- **全部按裸名称强制归属**：同名 MCP 可能由多个插件声明，会产生误归属。
- **只看 `cwd`**：HTTP MCP 通常没有 `cwd`，例如 GitHub。
- **只看目标地址**：多个插件可能复用同一可执行程序或网关，不能单独作为充分证据。

### 验收

- 上述 5 个 MCP 分别归入 `computer-use`、`record-and-replay`、`github`、`oppo-omni-mcp`、`sites` 插件。
- `claudeCodeDocs`、`node_repl`、`openaiDeveloperDocs` 继续保留为非插件 MCP。
- 同名声明有歧义且 `cwd`/`target` 无法唯一判定时，服务仍留在独立列表。
- 旧式 `plugin:<插件>:<服务>` 行为不回退。
