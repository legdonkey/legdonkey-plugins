import type { EngineInterface, Register } from 'claude-code'

// 缓存探针：主会话第 N 轮的首个请求固定改写为 SEQ[N-1]，记录实际发出的 effort 和每步缓存用量。
const SEQ = ['low', 'high', 'medium', 'low', 'xhigh'] as const

const lines: string[] = []
async function log($: EngineInterface, row: Record<string, unknown>) {
  // 日志路径由 scripts/cache-probe.py 通过环境变量传入。
  const log = await $.env.get('AUTO_EFFORT_PROBE_LOG')
  if (!log) return
  lines.push(JSON.stringify({ at: Date.now(), ...row }))
  await $.fs.write(log, lines.join('\n') + '\n')
}

export const register: Register = on => {
  let turnNo = 0

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) turnNo += 1
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) return yield* next(e)
    const wanted = e.index === 0 ? SEQ[(turnNo - 1) % SEQ.length] : undefined
    const sent = wanted ? { ...e, effort: wanted } : e
    const result = yield* next(sent)
    await log($, {
      kind: 'step', turn: turnNo, index: e.index, model: e.model,
      engineEffort: e.effort, rewrittenTo: wanted ?? null,
      usage: result.usage, stopReason: result.stopReason,
    })
    return result
  })

  // 只读取与 effort 相关的字段，不记录消息内容和凭据。
  on('http.fetch', async ($, e, next) => {
    if (next.origin.plugin === 'engine' && /\/v1\/messages(\?|$)/.test(e.url)) {
      try {
        const body = typeof e.init?.body === 'string' ? JSON.parse(e.init.body) : undefined
        if (body) {
          const msgs: Array<{ role?: string; output_config?: { effort?: string }; content?: unknown }> = body.messages ?? []
          await log($, {
            kind: 'request', turn: turnNo, model: body.model, maxTokens: body.max_tokens,
            topEffort: body.output_config?.effort ?? null,
            thinking: body.thinking ?? null,
            perMessageEffort: msgs.flatMap((m, i) => (m.role === 'system' && m.output_config?.effort ? [[i, m.output_config.effort]] : [])),
            messageCount: msgs.length,
            beta: e.init?.headers?.['anthropic-beta'] ?? null,
          })
        } else {
          await log($, { kind: 'request', turn: turnNo, note: 'body not a string', bodyType: typeof e.init?.body })
        }
      } catch (err) {
        await log($, { kind: 'request', turn: turnNo, note: 'parse failed', error: String(err).slice(0, 120) })
      }
    }
    return next(e)
  })
}
