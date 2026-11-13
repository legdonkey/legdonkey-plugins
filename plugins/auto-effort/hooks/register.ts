import type { EngineInterface, Register, Timer } from 'claude-code'
import type { AutoEffortSession } from '../types/index'
import { FABLE_FINISH_PROMPT } from './policy-text'
import type { Effort, SupportedModel } from './policy-text'
import { cacheRebuilt, clampEffort, configOf, isContinue, isEffort, isUltra, JUDGES, judgeInput, retainedDecisions, supportedModel } from './core'
import type { Config, Decision, JudgeResult } from './core'
import { classify } from './judge'
import { runBench } from './bench'

type Pending = {
  model: SupportedModel; midTurn: boolean; ultra: boolean; skip: boolean
  started: number; promise?: Promise<JudgeResult>; result?: JudgeResult; timer?: Timer; abort: AbortController
  fableContinue?: boolean; turnId?: string
}

function freshSession(sessionId: string): AutoEffortSession {
  return { sessionId, previousEngineSeen: false, currentUltra: false, skipTurn: false, turnNo: 0, toolCalls: 0,
    rewritten: false, warnedThisTurn: false, previousCacheRead: 0, latestCacheRead: 0, cacheWarnings: 0,
    suggested: false, fallbackWarned: false, steps: [], summary: { toolCalls: 0, interrupted: false } }
}

async function providerPause($: EngineInterface): Promise<string | undefined> {
  const [bedrock, vertex, foundry, platform, base, disabled] = await Promise.all([
    $.env.get('CLAUDE_CODE_USE_BEDROCK'), $.env.get('CLAUDE_CODE_USE_VERTEX'), $.env.get('CLAUDE_CODE_USE_FOUNDRY'),
    $.env.get('CLAUDE_CODE_USE_AGENT_PLATFORM'), $.env.get('ANTHROPIC_BASE_URL'), $.env.get('CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS'),
  ])
  if ([bedrock, vertex, foundry, platform].some(v => v === '1' || v?.toLowerCase() === 'true')
    || disabled !== undefined || (base !== undefined && base !== '' && !/^https:\/\/api\.anthropic\.com\/?$/.test(base)))
    return '会重建缓存，已暂停'
  return undefined
}

async function saveSession($: EngineInterface, state: AutoEffortSession): Promise<void> {
  await $.state.set({ plugin: 'auto-effort', key: 'session' }, state)
}

// 终端把状态接在提示行（「auto mode on」那一行）末尾；其他界面不画 PromptHint 的 tail，仍用独立状态行。
const hint: { text?: string; terminal: boolean } = { terminal: true }

function show($: EngineInterface, text: string | undefined): void {
  if (!hint.terminal) { $.ui.status(text); return }
  if (text === hint.text) return
  hint.text = text
  $.ui.invalidate('ui.render')
}

function status($: EngineInterface, state: AutoEffortSession, config: Config, environment?: string, detail?: string): void {
  if (detail) state.statusDetail = detail
  const paused = environment ?? state.paused ?? (!config.enabled ? '开关已关闭' : undefined)
  show($, paused ? `⏸ 自动选档已暂停：${paused}` : state.statusDetail ?? `🧠 ${state.lastFinal ?? 'medium'} · 自动`)
}

type Runtime = {
  state?: AutoEffortSession
  loading?: Promise<AutoEffortSession>
  loadingId?: string
  writes: Promise<void>
}

async function load($: EngineInterface, runtime: Runtime): Promise<AutoEffortSession> {
  const sessionId = await $.session.id()
  if (runtime.state?.sessionId === sessionId) return runtime.state
  if (!runtime.loading || runtime.loadingId !== sessionId) {
    runtime.loadingId = sessionId
    runtime.loading = (async () => {
      await runtime.writes
      const held = await $.state.get({ plugin: 'auto-effort', key: 'session' })
      // shortcut: 消息读取不含 uuid，暂按会话末条决策恢复；接口提供稳定标识后再支持回退定位。
      const rows = retainedDecisions(await $.store.get('decisions')).filter(row => row.sessionId === sessionId)
      const last = rows.findLast(row => row.final !== undefined)
      runtime.state = {
        ...freshSession(sessionId), lastFinal: last?.final,
        lastDecision: last && { at: last.at, turnId: last.turnId, index: last.index },
        turnNo: rows.at(-1)?.turn ?? 0,
        summary: last?.summary ?? { effort: last?.final, toolCalls: 0, interrupted: false },
        ...(held.value?.sessionId === sessionId ? held.value : {}),
      }
      return runtime.state
    })()
  }
  return runtime.loading
}

async function fallback($: EngineInterface, runtime: Runtime, reason: string): Promise<void> {
  const s = await load($, runtime)
  if (!s.fallbackWarned) {
    s.fallbackWarned = true
    $.ui.toast(`已回退 Haiku：${reason}`)
    await saveSession($, s)
  }
}

function remember($: EngineInterface, runtime: Runtime, decision?: Decision, clearSessionId?: string): Promise<void> {
  const snapshot = decision && { ...decision }
  runtime.writes = runtime.writes.catch(() => {}).then(async () => {
    const rows = retainedDecisions(await $.store.get('decisions')).filter(row => row.sessionId !== clearSessionId)
    const index = snapshot ? rows.findIndex(row => row.sessionId === snapshot.sessionId
      && row.turnId === snapshot.turnId && row.index === snapshot.index && row.at === snapshot.at) : -1
    if (snapshot) {
      if (index < 0) rows.push(snapshot)
      else rows[index] = snapshot
    }
    await $.store.set('decisions', retainedDecisions(rows))
  })
  return runtime.writes
}

export const register: Register = (on, options) => {
  const config = configOf(options)
  const runtime: Runtime = { writes: Promise.resolve() }
  let pending: Pending | undefined
  let logs = Promise.resolve()
  let debugText: string | undefined
  let debugWarned = false

  hint.text = undefined
  hint.terminal = true

  on('ui.render', { component: 'PromptHint' }, ($, e, next) => {
    if (!hint.text) return next(e)
    return next({ ...e, props: { ...e.props, tail: `${e.props.tail ?? ''} · ${hint.text}` } })
  })

  on('session.start', async ($, e, next) => {
    hint.terminal = e.surface === 'terminal'
    await load($, runtime)
    await $.command.register({ name: 'auto-effort', description: '查看、切换或测评自动选档' })
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    pending?.abort.abort()
    pending?.timer?.cancel()
    pending = undefined
    if (e.reason === 'clear') {
      await remember($, runtime, undefined, e.sessionId)
      runtime.state = freshSession(await $.session.id())
      runtime.loading = undefined
      await saveSession($, runtime.state)
      show($, undefined)
    }
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    const model = supportedModel(await $.session.model())
    if (!model) { show($, undefined); return next(e) }
    const s = await load($, runtime)
    if (e.command || e.isMeta) {
      if (!e.turnId) { pending?.abort.abort(); pending?.timer?.cancel(); pending = undefined; s.skipTurn = true }
      return next(e)
    }
    pending?.abort.abort()
    pending?.timer?.cancel()
    const job: Pending = { model, midTurn: e.turnId !== undefined, ultra: isUltra(e.text), skip: false,
      started: await $.clock.now(), abort: new AbortController(), turnId: e.turnId,
      // 官方：Fable 5.2 在 low/medium 下长任务更容易提前收工，用户要求继续时直接给 high，不等判档。
      fableContinue: model === 'claude-fable-5-2' && isContinue(e.text) && (s.lastFinal === 'low' || s.lastFinal === 'medium') }
    pending = job
    s.skipTurn = false
    const environment = await providerPause($)
    if (environment || s.paused || !config.enabled || job.ultra || job.fableContinue) {
      status($, s, config, environment, job.ultra ? '🧠 ultrathink · 引擎决定' : undefined)
      return next(e)
    }
    // 定时器把判档放在独立 dispatch 中，prompt.submit 不等待模型回答。
    job.promise = new Promise(resolve => {
      job.timer = $.clock.after(0, () => {
        void (async () => {
          const history = await $.session.messages()
          // 某些宿主在提交事件前已存入当前消息，剔除末尾这一条。
          if (history.at(-1)?.role === 'user' && history.at(-1)?.text === e.text) history.pop()
          const prompt = judgeInput(model, s.lastFinal, s.summary, history, e.text)
          const result = await classify($, config, model, prompt, reason => fallback($, runtime, reason), job.abort.signal)
          return await $.clock.now() - job.started > config.judgeTimeoutMs
            ? { ...result, result: undefined, failure: '判档超时' } : result
        })().then(result => { job.result = result; resolve(result) }, () => {
          job.result = { judge: config.judge, ms: 0, failure: '判档服务不可用' }
          resolve(job.result)
        })
      })
    })
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    const s = await load($, runtime)
    s.activeTurn = e.turnId
    s.currentUltra = isUltra(e.text) || (pending?.ultra ?? false)
    s.turnNo += 1
    s.toolCalls = 0
    s.rewritten = false
    s.warnedThisTurn = false
    s.latestCacheRead = 0
    s.firstStepCache = undefined
    if (pending) { pending.midTurn = false; pending.turnId = e.turnId }
    await saveSession($, s)
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) return yield* next(e)
    const model = supportedModel(e.model)
    if (!model) { show($, undefined); return yield* next(e) }
    const s = await load($, runtime)
    const environment = await providerPause($)
    // Claude Code 按模型保存档位，skill 和 ultrathink 只改本轮：只在同一模型的普通轮之间比较引擎档位。
    if (e.index === 0 && !s.skipTurn && !s.currentUltra) {
      if (s.previousEngineSeen && s.previousEngineModel === model && e.effort !== s.previousEngine)
        s.paused = '你手动改了档位，/auto-effort on 恢复'
      s.previousEngine = e.effort
      s.previousEngineModel = model
      s.previousEngineSeen = true
    }
    const job = pending
    const eligible = job && job.model === model && (e.index === 0 || (job.midTurn && job.turnId === e.turnId))
    let wanted: Effort | undefined
    let decision: Decision | undefined
    if (eligible) {
      pending = undefined
      let answer: JudgeResult | undefined
      let reason = ''
      if (environment || s.paused || !config.enabled || s.skipTurn || s.currentUltra || job.ultra) {
        reason = job.ultra || s.currentUltra ? 'ultrathink 交给引擎' : environment ?? s.paused ?? '自动选档已关闭'
        job.abort.abort(); job.timer?.cancel()
      } else if (job.fableContinue) {
        wanted = clampEffort('high', config)
        reason = 'Fable 继续任务升档'
      } else if (job.promise) {
        let timer: Timer | undefined
        const remaining = config.judgeTimeoutMs - (await $.clock.now() - job.started)
        if (job.result) answer = job.result
        else if (remaining > 0) {
          try {
            answer = await Promise.race([job.promise, new Promise<undefined>(resolve => {
              timer = $.clock.after(remaining, () => resolve(undefined))
            })])
          } finally { timer?.cancel() }
        }
        if (!answer || answer.failure === '判档超时') {
          reason = '判档超时'
          job.abort.abort(); job.timer?.cancel()
        } else {
          if (answer.result?.suggestModel && !s.suggested) {
            s.suggested = true
            $.ui.toast('上下文已齐全但结果仍不对，可能需要更强的模型')
          }
          if (answer.result && answer.result.confidence >= 0.5) {
            wanted = clampEffort(answer.result.effort, config)
            reason = answer.result.reason
          } else {
            wanted = s.lastFinal === undefined ? undefined : clampEffort(s.lastFinal, config)
            reason = answer.failure ?? '判档结果无效'
          }
        }
      } else reason = '没有待用判档'
      const previousFinal = s.lastFinal
      if (wanted) s.lastFinal = wanted
      // ultrathink 只作用于本轮，不让后续确认消息沿用它的档位。
      else if (isEffort(e.effort) && !s.currentUltra && !job.ultra) s.lastFinal = e.effort
      decision = { at: new Date(await $.clock.now()).toISOString(), sessionId: s.sessionId, turn: s.turnNo,
        turnId: e.turnId, index: e.index, model, judge: job.fableContinue ? '规则' : answer?.judge ?? config.judge,
        judged: answer?.result?.effort, final: s.lastFinal, confidence: answer?.result?.confidence,
        reason, ms: answer?.ms ?? await $.clock.now() - job.started, rewritten: wanted !== undefined, judgeUsage: answer?.usage,
        previousFinal }
      s.lastDecision = { at: decision.at, turnId: decision.turnId, index: decision.index }
      await remember($, runtime, decision)
      const automatic = answer?.result && answer.result.confidence >= 0.5 && wanted ? answer : undefined
      status($, s, config, environment, `🧠 ${s.lastFinal ?? 'medium'} · ${automatic ? `自动 · ${automatic.judge === 'haiku' ? 'Haiku' : automatic.judge} ${(automatic.ms / 1000).toFixed(1)}s` : `沿用（${reason}）`}`)
    } else status($, s, config, environment)
    s.rewritten ||= wanted !== undefined
    await saveSession($, s)
    const result = yield* next(wanted ? { ...e, effort: wanted } : e)
    if (runtime.state !== s) return result
    s.toolCalls += result.toolUses.length
    if (result.usage) {
      s.latestCacheRead = result.usage.cache_read_input_tokens
      if (e.index === 0) s.firstStepCache = { read: result.usage.cache_read_input_tokens, write: result.usage.cache_creation_input_tokens }
      s.steps.push({ turnId: e.turnId, index: e.index, model, read: result.usage.cache_read_input_tokens,
        write: result.usage.cache_creation_input_tokens, input: result.usage.input_tokens, output: result.usage.output_tokens })
      s.steps = s.steps.slice(-200)
      if (s.rewritten && !s.warnedThisTurn && cacheRebuilt(s.previousCacheRead, result.usage)) {
        s.warnedThisTurn = true
        s.cacheWarnings += 1
        $.ui.toast('检测到缓存重建')
        if (s.cacheWarnings >= 2) { s.paused = '检测到两次缓存重建，/auto-effort on 恢复'; status($, s, config, environment) }
      }
      if (decision) { decision.cacheRead = s.firstStepCache?.read; decision.cacheWrite = s.firstStepCache?.write }
    }
    if (decision) await remember($, runtime, decision)
    await saveSession($, s)
    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      const s = await load($, runtime)
      s.summary = { effort: s.lastFinal, toolCalls: s.toolCalls, interrupted: e.isAborted }
      await runtime.writes
      const last = retainedDecisions(await $.store.get('decisions')).findLast(row => row.sessionId === s.sessionId
        && row.turnId === s.lastDecision?.turnId && row.index === s.lastDecision.index && row.at === s.lastDecision.at)
      if (last) await remember($, runtime, { ...last, summary: s.summary })
      if (s.latestCacheRead > 0 || e.usage) s.previousCacheRead = s.latestCacheRead
      s.activeTurn = undefined
      s.skipTurn = false
      await saveSession($, s)
    }
    return next(e)
  })

  on('prompt.compose', async ($, e, next) => {
    const result = await next(e)
    return config.fableFinishPrompt && supportedModel(e.model) === 'claude-fable-5-2'
      ? { sections: [...result.sections, { id: 'auto-effort:finish', text: FABLE_FINISH_PROMPT, scope: 'session' }] } : result
  })

  on('http.fetch', async ($, e, next) => {
    if (config.debugLogPath && next.origin.plugin === 'engine' && /\/v1\/messages(?:\?|$)/.test(e.url)) {
      try {
        const body = typeof e.init?.body === 'string' ? JSON.parse(e.init.body) : undefined
        if (body && Array.isArray(body.messages)) {
          const row = { model: typeof body.model === 'string' ? body.model : null,
            topEffort: isEffort(body.output_config?.effort) ? body.output_config.effort : null,
            perMessageEffort: body.messages.flatMap((m: { output_config?: { effort?: unknown } }, i: number) =>
              isEffort(m?.output_config?.effort) ? [[i, m.output_config.effort]] : []), messageCount: body.messages.length }
          logs = logs.catch(() => {}).then(async () => {
            if (debugText === undefined) debugText = await $.fs.read(config.debugLogPath).catch(() => '')
            debugText += JSON.stringify(row) + '\n'
            await $.fs.write(config.debugLogPath, debugText)
          })
          await logs
        }
      } catch { if (!debugWarned) { debugWarned = true; $.ui.toast('请求摘要日志写入失败') } }
    }
    return next(e)
  })

  on('command.run', { command: 'auto-effort' }, async ($, e) => {
    try {
      const s = await load($, runtime)
      const [verb = 'status', arg, extra, ...rest] = e.args.trim().split(/\s+/).filter(Boolean)
      if (verb === 'status') {
        await runtime.writes
        const rows = retainedDecisions(await $.store.get('decisions'))
        return { text: JSON.stringify({ enabled: config.enabled, paused: await providerPause($) ?? s.paused ?? null,
          judge: config.judge, floor: config.floor, ceiling: config.ceiling, allowMax: config.allowMax,
          lastFinal: s.lastFinal ?? null, lastDecision: s.lastDecision ?? null, summary: s.summary,
          decisions: rows.filter(row => row.sessionId === s.sessionId).slice(-10) }) }
      }
      if (verb === 'test') {
        const text = e.args.trim().replace(/^test\s*/, '')
        if (!text) return { text: '用法：/auto-effort test <文本>' }
        const model = supportedModel(await $.session.model())
        if (!model) return { text: '当前模型不支持自动选档' }
        const prompt = judgeInput(model, s.lastFinal, s.summary, await $.session.messages(), text)
        return { text: JSON.stringify(await classify($, config, model, prompt, async () => {})) }
      }
      if (verb === 'bench') return { text: await runBench($, config, [arg, extra, ...rest].filter((v): v is string => v !== undefined), reason => fallback($, runtime, reason)) }
      let field: 'enabled' | 'judge' | 'floor' | 'ceiling' | 'allowMax'
      let value: boolean | string
      if ((verb === 'on' || verb === 'off') && !arg) { field = 'enabled'; value = verb === 'on' }
      else if (verb === 'judge' && JUDGES.includes(arg as typeof JUDGES[number]) && !extra) { field = 'judge'; value = arg! }
      else if ((verb === 'floor' || verb === 'ceiling') && isEffort(arg) && !extra) { field = verb; value = arg }
      else if (verb === 'max' && (arg === 'on' || arg === 'off') && !extra) { field = 'allowMax'; value = arg === 'on' }
      else return { text: '用法：/auto-effort [status|on|off|judge <haiku|jev|d1-ultra|mammoth-27b|decider>|floor <档位>|ceiling <档位>|max on|off|test <文本>|bench [opus|sonnet|fable|all] [holdout]]' }
      const changed = await $.config.set({ key: `auto-effort.${field}`, value })
      if (changed.deny) return { text: '配置未写入：当前配置不允许修改' }
      Object.assign(config, { [field]: value })
      if (verb === 'on') { s.paused = undefined; s.cacheWarnings = 0; s.previousEngineSeen = false; pending?.abort.abort(); pending?.timer?.cancel(); pending = undefined }
      await saveSession($, s)
      status($, s, config, await providerPause($))
      return { text: `自动选档配置：${field}=${value}` }
    } catch { return { text: '自动选档命令失败：无法读取或写入配置、用例或结果' } }
  })
}
