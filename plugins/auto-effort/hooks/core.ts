import { EFFORTS, MODEL_RULES } from './policy-text'
import type { Effort, SupportedModel } from './policy-text'
import type { PluginOptions, PromptAutocompleteInput, PromptAutocompleteSuggestion, SessionMessage } from 'claude-code'

export const JUDGES = ['haiku', 'jev', 'd1-ultra', 'mammoth-27b', 'decider'] as const
export type Judge = typeof JUDGES[number]
export type Config = ReturnType<typeof configOf>
export type Classification = { effort: Effort; confidence: number; reason: string; suggestModel: boolean }
export type JudgeResult = { result?: Classification; judge: Judge; ms: number; failure?: string; usage?: Usage }
export type Usage = { input_tokens: number; output_tokens: number; cache_read_input_tokens: number; cache_creation_input_tokens: number }
export type Decision = {
  at: string; sessionId: string; turn: number; turnId: string; index: number; model: SupportedModel
  judge: string; judged?: Effort; final?: Effort; confidence?: number; reason: string; ms: number
  rewritten: boolean; cacheRead?: number; cacheWrite?: number; judgeUsage?: Usage
  previousFinal?: Effort
  summary?: { effort?: Effort; toolCalls: number; interrupted: boolean }
}

/** 新旧决策共用一个存储键；每会话 200 条、最近 50 个会话，UTF-8 最多 3 MiB。 */
export function retainedDecisions(value: unknown): Decision[] {
  if (!Array.isArray(value)) return []
  const counts = new Map<string, number>()
  const kept: Decision[] = []
  let size = 2
  for (const row of value.slice().reverse()) {
    if (!record(row) || typeof row.sessionId !== 'string' || typeof row.at !== 'string'
      || typeof row.turnId !== 'string' || typeof row.turn !== 'number' || typeof row.index !== 'number'
      || (row.final !== undefined && !isEffort(row.final))) continue
    const count = counts.get(row.sessionId) ?? 0
    if (count >= 200 || (!count && counts.size >= 50)) continue
    // 每个 UTF-16 单元最多占三个 UTF-8 字节，给 store 的 4 MiB 总限额留余量。
    const length = JSON.stringify(row).length + 1
    if (size + length > 1024 * 1024) continue
    size += length
    counts.set(row.sessionId, count + 1)
    kept.push(row as Decision)
  }
  return kept.reverse()
}

export function isEffort(value: unknown): value is Effort {
  return typeof value === 'string' && EFFORTS.includes(value as Effort)
}

const VERBS: [string, string][] = [
  ['status', '查看开关、判档器、上下限和最近决策'],
  ['on', '开启自动选档（也用于暂停后恢复）'],
  ['off', '关闭自动选档'],
  ['judge', '切换判档器'],
  ['floor', '设置最低档位'],
  ['ceiling', '设置最高档位'],
  ['max', '是否允许输出 max（还需 ceiling=max）'],
  ['test', '只判档、不改档：test <文本>'],
  ['bench', '对内置用例测评判档器'],
]
const VALUES: Record<string, [string, string][]> = {
  judge: [['haiku', 'Haiku 5.5（默认）'], ['jev', 'OpenRouter Jev'], ['d1-ultra', 'OpenRouter D1 Ultra'],
    ['mammoth-27b', 'OpenRouter Mammoth'], ['decider', 'OpenRouter Decider']],
  floor: EFFORTS.map(e => [e, '最低档位']),
  ceiling: EFFORTS.map(e => [e, '最高档位']),
  max: [['on', '允许 max'], ['off', '不允许 max']],
  bench: [['opus', '只测 Opus'], ['sonnet', '只测 Sonnet'], ['fable', '只测 Fable'], ['all', '三个模型都测']],
}

/** /auto-effort 的参数补全：按已输入的词给出子命令或取值。 */
export function commandCompletions(e: PromptAutocompleteInput): PromptAutocompleteSuggestion[] {
  const head = /^\s*\/auto-effort\s+(.*)$/s.exec(e.text.slice(0, e.start))
  if (!head) return []
  const words = head[1]!.split(/\s+/).filter(Boolean)
  const rows = words.length === 0 ? VERBS
    : words.length === 1 ? VALUES[words[0]!] ?? []
    : words.length === 2 && words[0] === 'bench' ? [['holdout', '只测 holdout 用例']] as [string, string][]
    : []
  return rows.filter(([text]) => text.startsWith(e.token) && text !== e.token).map(([text, description]) => ({ text, description }))
}

export function supportedModel(value: string): SupportedModel | undefined {
  const model = value.replace(/(?:\[[^\]]*\])+$/, '')
  return Object.hasOwn(MODEL_RULES, model) ? model as SupportedModel : undefined
}

export function configOf(options: PluginOptions) {
  return {
    enabled: options.enabled !== false,
    judge: JUDGES.includes(options.judge as Judge) ? options.judge as Judge : 'haiku' as Judge,
    openrouterApiKey: typeof options.openrouterApiKey === 'string' ? options.openrouterApiKey : '',
    floor: isEffort(options.floor) ? options.floor : 'low' as Effort,
    ceiling: isEffort(options.ceiling) ? options.ceiling : 'xhigh' as Effort,
    allowMax: options.allowMax === true,
    judgeTimeoutMs: typeof options.judgeTimeoutMs === 'number' && Number.isFinite(options.judgeTimeoutMs)
      ? Math.max(1, Math.min(60000, options.judgeTimeoutMs)) : 5000,
    fableFinishPrompt: options.fableFinishPrompt === true,
    debugLogPath: typeof options.debugLogPath === 'string' && /^(?:\/|[A-Za-z]:[\\/])/.test(options.debugLogPath) ? options.debugLogPath : '',
  }
}

export function clampEffort(effort: Effort, config: Pick<Config, 'floor' | 'ceiling' | 'allowMax'>): Effort {
  const top = Math.min(EFFORTS.indexOf(config.ceiling), config.allowMax ? 4 : 3)
  const bottom = Math.min(EFFORTS.indexOf(config.floor), top)
  return EFFORTS[Math.min(top, Math.max(bottom, EFFORTS.indexOf(effort)))]!
}

export function isUltra(text: string): boolean {
  return /\bultrathink\b/i.test(text)
}

/** 整条消息只是「继续」类请求。只用于 Fable 提前收工后的升档规则，其他短回复都交给判档器结合前文判断。 */
export function isContinue(text: string): boolean {
  const words = text.toLowerCase().replace(/[\p{P}\p{S}]/gu, ' ').trim().replace(/\s+/g, ' ')
  return ['继续', '继续吧', '接着', '接着做', 'continue', 'go on', 'keep going'].includes(words)
}

/** 按 Pi 的规则展开 auth.json 里的 key：`$NAME`、`${NAME}` 取变量，`$$`、`$!` 转义。 */
export function expandPiKey(key: string, env: Record<string, unknown>): string | undefined {
  // shortcut: `!命令` 形式要执行 shell，模板变量只从 auth.json 条目自带的 env 取（mod 只能按字面量名读环境变量）；有人用到时再扩展。
  if (key.startsWith('!')) return undefined
  let out = ''
  let last = 0
  for (const m of key.matchAll(/\$(?:([$!])|\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))/g)) {
    out += key.slice(last, m.index)
    if (m[1]) out += m[1]
    else {
      const value = env[(m[2] ?? m[3])!]
      if (typeof value !== 'string' || !value) return undefined
      out += value
    }
    last = m.index + m[0].length
  }
  return out + key.slice(last) || undefined
}

// 不保存模型的自由文本，防止理由复述消息原文或凭据。
export function safeReason(effort: Effort, reason: unknown): string {
  const text = typeof reason === 'string' ? reason : ''
  for (const [pattern, label] of [
    [/安全|竞态|并发|兼容/, '安全、并发或兼容边界'],
    [/验证|测试|评审|审查/, '验证、测试或评审'],
    [/排查|故障|修复|bug/i, '故障排查或修复'],
    [/设计|方案|权衡/, '方案设计与权衡'],
    [/研究|证明|数学/, '研究或证明'],
  ] as const) if (pattern.test(text)) return label
  return { low: '简单问答或机械任务', medium: '常规工程与知识工作', high: '复杂任务或结果验证', xhigh: '密集边界与系统验证', max: '最高投入任务' }[effort]
}

export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function parseHaiku(text: string): Classification | undefined {
  try {
    const value: unknown = JSON.parse(text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, ''))
    if (!record(value) || !isEffort(value.effort) || typeof value.confidence !== 'number'
      || !Number.isFinite(value.confidence) || value.confidence < 0 || value.confidence > 1
      || typeof value.reason !== 'string' || typeof value.suggestModel !== 'boolean') return undefined
    return { effort: value.effort, confidence: value.confidence, reason: safeReason(value.effort, value.reason), suggestModel: value.suggestModel }
  } catch { return undefined }
}

export function parseSystemOne(text: string): Classification | undefined {
  try {
    const data: unknown = JSON.parse(text)
    if (!record(data) || !record(data.answers) || !record(data.answers.effort)) return undefined
    const value = data.answers.effort
    if (value.type !== 'choice' || !isEffort(value.choice) || !record(value.probabilities)) return undefined
    const confidence = value.probabilities[value.choice]
    if (typeof confidence !== 'number' || !Number.isFinite(confidence) || confidence < 0 || confidence > 1) return undefined
    return { effort: value.choice, confidence, reason: safeReason(value.choice, ''), suggestModel: false }
  } catch { return undefined }
}

export function httpFailure(status: number): string {
  const reasons: Record<number, string> = {
    400: '分类请求被拒绝', 401: '认证失败', 402: '额度不足', 403: '权限或策略限制',
    404: '模型或端点不可用', 408: '服务请求超时', 413: '分类输入过大', 429: '服务限流',
  }
  return reasons[status] ?? (status >= 500 && status <= 599 ? '上游服务异常' : '分类服务异常')
}

/**
 * 判档输入，写法参照 Pi 的 inline-effort：当前消息最多 12,000 字符；近期对话取最近 10 条 user/assistant 文本，
 * 合计最多 24,000 字符，越新的越优先保留（每条保留结尾，助手回复的结尾通常是它提出的问题或计划）。不含工具结果和图片。
 */
export function judgeInput(model: SupportedModel, current: Effort | undefined,
  summary: { effort?: Effort; toolCalls: number; interrupted: boolean },
  history: readonly Pick<SessionMessage, 'role' | 'text'>[], text: string): string {
  let left = 24000
  const recent: string[] = []
  for (const row of history.filter(row => row.text.trim()).slice(-10).reverse()) {
    const part = row.text.slice(-left)
    recent.unshift(`${row.role === 'user' ? '用户' : '助手'}: ${part}`)
    left -= part.length
    if (left === 0) break
  }
  const context = recent.length
    ? `近期对话（用于补全当前消息省略的目标、约束和交付要求；新任务不继承）：\n${recent.join('\n')}`
    : '近期对话：无'
  return `当前模型：${model}\n会话当前档位：${current ?? '未设置'}\n上一轮摘要：档位=${summary.effort ?? '无'}；工具调用次数=${summary.toolCalls}；是否被中断=${summary.interrupted ? '是' : '否'}\n\n${context}\n\n当前用户消息：\n${text.slice(0, 12000)}`
}

/** 测评用例的 context 是「user: …\nassistant: …」文本，拆回对话行。 */
export function parseContext(context: string): Pick<SessionMessage, 'role' | 'text'>[] {
  return context.split(/^(?=(?:user|assistant):)/m).flatMap(part => {
    const m = part.match(/^(user|assistant):\s?([\s\S]*)$/)
    return m ? [{ role: m[1] as 'user' | 'assistant', text: m[2]!.trim() }] : part.trim() ? [{ role: 'assistant' as const, text: part.trim() }] : []
  })
}

export function cacheRebuilt(previousRead: number, usage: Usage): boolean {
  return previousRead > 0 && usage.cache_read_input_tokens < previousRead
}
