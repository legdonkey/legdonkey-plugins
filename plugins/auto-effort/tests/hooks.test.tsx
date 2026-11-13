import { expect, mock, test } from 'claude-code/testing'
import type { Engine, MockClock } from 'claude-code/testing'
import type { On, TurnStepInput } from 'claude-code'
import type { Decision } from '../hooks/core'

const MODEL = 'claude-opus-5-5'
const USAGE = { input_tokens: 5, output_tokens: 5, cache_read_input_tokens: 10000, cache_creation_input_tokens: 100 }

function setup(on: On, model = MODEL, env: Record<string, string> = {}, entries: Record<string, unknown> = {}) {
  const clock = mock.clock(on, { now: 1794600000000 })
  mock.store(on, entries)
  mock.env(on, env)
  const calls: TurnStepInput[] = []
  const statuses: (string | undefined)[] = []
  const toasts: string[] = []
  const prompts: string[] = []
  const configWrites: { key: string; value: unknown }[] = []
  let classification = '{"effort":"high","confidence":0.9,"reason":"验证","suggestModel":false}'
  let delay = 0
  let usage = { ...USAGE }
  let sessionId = 'test-session'
  let beforeStep = async () => {}
  on('session.model', () => ({ value: model }))
  on('session.id', () => ({ value: sessionId }))
  on('session.messages', () => ({ value: [] }))
  on('command.register', () => ({ value: { command: 'auto-effort' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.end', (_, e) => ({ sessionId: e.sessionId }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', (_, e) => ({ text: e.answer, usage: e.usage }))
  on('ui.status', (_, e) => { statuses.push(e.text); return { value: undefined } })
  on('ui.toast', (_, e) => { toasts.push(e.text); return { value: undefined } })
  let tail: string | undefined
  on('ui.render', ($, e) => {
    if (e.component === 'PromptHint') tail = e.props.tail
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  on('config.set', (_, e) => { configWrites.push(e); return { value: e.value } })
  on('model.complete', async (_, e) => {
    prompts.push(e.prompt)
    if (delay) await clock.sleep(delay)
    return { value: { isAnswered: true, text: classification, usage: USAGE } }
  })
  on('turn.step', async function* (_, e) {
    await beforeStep()
    calls.push(e)
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'end_turn', usage: { ...usage, model } }
  })
  return { clock, calls, statuses, toasts, prompts, configWrites, tail: () => tail,
    sessionId: (id: string) => { sessionId = id },
    holdStep: (wait: () => Promise<void>) => { beforeStep = wait },
    answer: (text: string) => { classification = text }, delay: (ms: number) => { delay = ms }, usage: (u: typeof USAGE) => { usage = u } }
}

// 终端上状态接在提示行末尾：挂载 PromptHint，读插件追加的 tail。
async function hint($: Engine, m: { tail: () => string | undefined }) {
  const ui = await $.ui.mount({ plugin: 'auto-effort', component: 'PromptHint', requestId: 'hint', surface: 'terminal', props: { isDraft: false, isWorking: false, hint: '? for shortcuts' } })
  await ui.unmount()
  return m.tail()
}

async function submit($: Engine, clock: MockClock, text: string, turnId = 't1', flags: { command?: { name: string; args: string }; isMeta?: true; midTurn?: boolean } = {}) {
  await $.prompt.submit({ text, wait: false, origin: { kind: 'composer' }, command: flags.command, isMeta: flags.isMeta, turnId: flags.midTurn ? turnId : undefined })
  if (!flags.midTurn) await $.turn.start({ text, turnId })
  await clock.settle()
}

async function step($: Engine, turnId = 't1', index = 0, effort: 'low' | 'medium' | 'high' | 'xhigh' = 'medium', agentId?: string, model = MODEL) {
  const stream = $.turn.step({ turnId, index, effort, model, messageCount: 2, agentId })
  while (!(await stream.next()).done) { /* 转发测试流直到返回结果。 */ }
}

async function complete($: Engine, turnId = 't1', isAborted = false) {
  await $.turn.complete({ turnId, answer: '', durationMs: 1, isAborted, reason: isAborted ? 'aborted' : 'answer', usage: { ...USAGE, model: MODEL } })
}

async function report($: Engine) {
  const result = await $.command.run({ command: 'auto-effort', args: 'status', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
  return JSON.parse(result.text!) as { paused: string | null; lastFinal: string | null;
    lastDecision: { at: string; turnId: string; index: number } | null;
    summary: { effort?: string; toolCalls: number; interrupted: boolean }; decisions: Decision[] }
}

function savedDecision(): Decision {
  return { at: '2026-11-13T00:00:00.000Z', sessionId: 'test-session', turn: 2, turnId: 'saved-turn', index: 0,
    model: MODEL, judge: 'haiku', final: 'low', confidence: 0.9, reason: '简单问答或机械任务', ms: 10, rewritten: true }
}

test('进程恢复从持久决策找回档位、来源和摘要，低置信度沿用它', async ($, on) => {
  const saved = { ...savedDecision(), summary: { effort: 'low' as const, toolCalls: 3, interrupted: true } }
  const m = setup(on, MODEL, {}, { decisions: [saved, { ...saved, sessionId: 'other', final: 'xhigh' }] })
  await $.session.start({ cwd: '/test', surface: null, isInteractive: false })
  const restored = await report($)
  expect(restored.lastFinal).toBe('low')
  expect(restored.lastDecision).toEqual({ at: saved.at, turnId: saved.turnId, index: 0 })
  expect(restored.summary).toEqual(saved.summary)
  m.answer('{"effort":"xhigh","confidence":0.2,"reason":"不确定","suggestModel":false}')
  await submit($, m.clock, '下一项')
  await step($)
  expect(m.calls.at(-1)?.effort).toBe('low')
  expect(m.prompts[0]).toMatch('工具调用次数=3；是否被中断=是')
  expect((await report($)).decisions.at(-1)?.previousFinal).toBe('low')
})

test('旧格式决策没有摘要仍可恢复，Fable 继续使用恢复的档位升档', async ($, on) => {
  const m = setup(on, 'claude-fable-5-2', {}, { decisions: [savedDecision()] })
  expect((await report($)).summary).toEqual({ effort: 'low', toolCalls: 0, interrupted: false })
  await submit($, m.clock, '继续')
  await step($, 't1', 0, 'medium', undefined, 'claude-fable-5-2')
  expect(m.calls.at(-1)?.effort).toBe('high')
  expect(m.prompts.length).toBe(0)
  expect((await report($)).decisions.at(-1)?.reason).toBe('Fable 继续任务升档')
})

test('/clear 删除本会话持久状态，保留其他会话，新 id 不沿用旧状态', async ($, on) => {
  const saved = savedDecision()
  const m = setup(on, MODEL, {}, { decisions: [saved, { ...saved, sessionId: 'other' }] })
  expect((await report($)).lastFinal).toBe('low')
  await $.session.end({ reason: 'clear', sessionId: 'test-session', resume: { id: 'test-session' } })
  expect((await report($)).lastFinal).toBe(null)
  expect((await report($)).decisions).toEqual([])
  m.sessionId('other')
  expect((await report($)).lastFinal).toBe('low')
  m.sessionId('new-session')
  expect((await report($)).lastFinal).toBe(null)
  m.sessionId('test-session')
  expect((await report($)).lastFinal).toBe(null)
})

test('完成轮次把摘要写回持久决策', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '任务')
  await step($)
  await complete($, 't1', true)
  const rows = (await report($)).decisions
  expect(rows.length).toBe(1)
  expect(rows[0]?.summary).toEqual({ effort: 'high', toolCalls: 0, interrupted: true })
})

test('/clear 后旧请求返回不得写回已清空的决策或状态', async ($, on) => {
  const m = setup(on)
  let started!: () => void
  let release!: () => void
  const entered = new Promise<void>(resolve => { started = resolve })
  const waiting = new Promise<void>(resolve => { release = resolve })
  m.holdStep(async () => {
    started()
    await waiting
  })
  await submit($, m.clock, '任务')
  const running = step($)
  await entered
  await $.session.end({ reason: 'clear', sessionId: 'test-session', resume: { id: 'test-session' } })
  release()
  await running
  expect((await report($)).lastFinal).toBe(null)
  expect((await report($)).decisions).toEqual([])
})

test('后台判档不阻塞提交，只改写主会话首步，短回复也结合前文判档', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '修复并验证问题')
  await step($)
  await step($, 't1', 1)
  await step($, 't1', 0, 'medium', 'child')
  expect(m.calls.map(c => c.effort)).toEqual(['high', 'medium', 'medium'])
  await complete($)
  await submit($, m.clock, 'ok', 't2')
  await step($, 't2')
  expect(m.prompts.length).toBe(2)
  expect(m.prompts.at(-1)).toMatch('当前用户消息：\nok')
  expect(m.calls.at(-1)?.effort).toBe('high')
  expect((await report($)).decisions.length).toBe(2)
})

test('OpenRouter 复用 Pi 的 key，模板变量取自条目的 env', { options: { judge: 'jev' } }, async ($, on) => {
  const m = setup(on, MODEL, { HOME: '/home/tester' })
  const reads: string[] = []
  const auth: string[] = []
  let stored = '{"openrouter":{"type":"api_key","key":"pi-literal-key"}}'
  on('fs.read', (_, e) => { reads.push(e.path); return { value: stored } })
  on('http.fetch', (_, e) => {
    auth.push(e.init!.headers!.Authorization!)
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: { effort: { type: 'choice', choice: 'low', probabilities: { low: 0.9 }, confidence: 1 } } }) } }
  })
  await submit($, m.clock, '任务')
  await step($)
  stored = '{"openrouter":{"type":"api_key","key":"${PI_TEST_KEY}","env":{"PI_TEST_KEY":"from-env"}}}'
  await complete($)
  await submit($, m.clock, '下一项', 't2')
  await step($, 't2')
  expect(reads[0]).toBe('/home/tester/.pi/agent/auth.json')
  expect(auth).toEqual(['Bearer pi-literal-key', 'Bearer from-env'])
  expect(m.prompts.length).toBe(0)
  expect(m.calls.map(c => c.effort)).toEqual(['low', 'low'])
})

test('ultrathink、斜杠命令和隐藏消息不判档', async ($, on) => {
  const m = setup(on)
  for (const [text, flags] of [
    ['ULTRATHINK!', {}], ['/anything', { command: { name: 'anything', args: '' } }], ['隐藏消息', { isMeta: true as const }],
  ] as const) {
    await submit($, m.clock, text, text, flags)
    await step($, text)
    await complete($, text)
  }
  expect(m.prompts.length).toBe(0)
  expect(m.calls.map(c => c.effort)).toEqual(['medium', 'medium', 'medium'])
})

test('手动改档暂停，on 持久化配置并恢复', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '普通任务')
  await step($)
  await complete($)
  await submit($, m.clock, '下一项', 't2')
  await step($, 't2', 0, 'low')
  expect(m.calls.at(-1)?.effort).toBe('low')
  expect((await report($)).paused).toMatch('手动改了档位')
  await $.command.run({ command: 'auto-effort', args: 'on', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
  expect(m.configWrites.at(-1)?.key).toBe('auto-effort.enabled')
  expect((await report($)).paused).toBe(null)
})

test('ultrathink 两侧的引擎档位变化不触发手动暂停', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '普通任务')
  await step($)
  await complete($)
  await submit($, m.clock, 'ultrathink', 't2')
  await step($, 't2', 0, 'xhigh')
  await complete($, 't2')
  await submit($, m.clock, '普通任务', 't3')
  await step($, 't3')
  expect((await report($)).paused).toBe(null)
})

test('切换模型和 skill 斜杠命令改变引擎档位时不触发手动暂停', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '普通任务')
  await step($)
  await complete($)
  await submit($, m.clock, '换到 Fable 后的任务', 't2')
  await step($, 't2', 0, 'high', undefined, 'claude-fable-5-2')
  await complete($, 't2')
  await submit($, m.clock, '/some-skill', 't3', { command: { name: 'some-skill', args: '' } })
  await step($, 't3', 0, 'xhigh')
  await complete($, 't3')
  await submit($, m.clock, '回到 Opus', 't4')
  await step($, 't4')
  expect((await report($)).paused).toBe(null)
})

test('ultrathink 的档位不会被后续沿用', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '修复并验证问题')
  await step($)
  await complete($)
  await submit($, m.clock, 'ultrathink 再想想', 't2')
  await step($, 't2', 0, 'xhigh')
  await complete($, 't2')
  m.answer('{"effort":"low","confidence":0.2,"reason":"不确定","suggestModel":false}')
  await submit($, m.clock, 'ok', 't3')
  await step($, 't3')
  expect(m.calls.at(-1)?.effort).toBe('high')
})

test('超时不改写，晚到结果不污染下一轮', { options: { judgeTimeoutMs: 100 } }, async ($, on) => {
  const m = setup(on)
  m.delay(200)
  await submit($, m.clock, '复杂任务')
  const running = step($)
  await m.clock.advance(101)
  await running
  expect(m.calls.at(-1)?.effort).toBe('medium')
  expect((await report($)).decisions.at(-1)?.reason).toBe('判档超时')
  await m.clock.advance(200)
  await complete($)
  // 第二轮判档无效时退回上一轮档位：迟到的 high 不能被记成上一轮档位。
  m.delay(0)
  m.answer('invalid')
  await submit($, m.clock, 'ok', 't2')
  await step($, 't2')
  expect(m.calls.at(-1)?.effort).toBe('medium')
})

test('首步较晚时仍可用按时完成的判档，丢弃超时完成的判档', { options: { judgeTimeoutMs: 100 } }, async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '任务')
  await m.clock.advance(200)
  await step($)
  expect(m.calls.at(-1)?.effort).toBe('high')
  await complete($)
  m.delay(200)
  await submit($, m.clock, '下一项', 't2')
  await m.clock.advance(201)
  await step($, 't2')
  expect(m.calls.at(-1)?.effort).toBe('medium')
  expect((await report($)).decisions.at(-1)?.reason).toBe('判档超时')
})

test('无效和低置信度沿用上一轮，首轮无结果不改写', async ($, on) => {
  const m = setup(on)
  m.answer('invalid')
  await submit($, m.clock, '第一项')
  await step($)
  expect(m.calls.at(-1)?.effort).toBe('medium')
  await complete($)
  m.answer('{"effort":"xhigh","confidence":0.3,"reason":"验证","suggestModel":false}')
  await submit($, m.clock, '第二项', 't2')
  await step($, 't2')
  expect(m.calls.at(-1)?.effort).toBe('medium')
})

test('低置信度沿用也遵守新设置的上限', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '第一项')
  await step($)
  await complete($)
  await $.command.run({ command: 'auto-effort', args: 'ceiling low', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
  m.answer('{"effort":"xhigh","confidence":0.3,"reason":"验证","suggestModel":false}')
  await submit($, m.clock, '第二项', 't2')
  await step($, 't2')
  expect(m.calls.at(-1)?.effort).toBe('low')
})

test('Fable 的继续消息从 low 或 medium 直接升 high', async ($, on) => {
  const m = setup(on, 'claude-fable-5-2')
  m.answer('{"effort":"low","confidence":0.9,"reason":"简单","suggestModel":false}')
  await submit($, m.clock, '事实问答')
  let stream = $.turn.step({ turnId: 't1', index: 0, effort: 'medium', model: 'claude-fable-5-2', messageCount: 2 })
  while (!(await stream.next()).done) {}
  await complete($)
  await submit($, m.clock, '继续', 't2')
  stream = $.turn.step({ turnId: 't2', index: 0, effort: 'medium', model: 'claude-fable-5-2', messageCount: 4 })
  while (!(await stream.next()).done) {}
  expect(m.calls.map(c => c.effort)).toEqual(['low', 'high'])
  expect(m.prompts.length).toBe(1)
})

test('运行中插入消息可在后续工具步改档', async ($, on) => {
  const m = setup(on)
  await submit($, m.clock, '普通任务')
  await step($)
  m.answer('{"effort":"low","confidence":0.9,"reason":"简单","suggestModel":false}')
  await submit($, m.clock, '简短问题', 't1', { midTurn: true })
  await step($, 't1', 2)
  await step($, 't1', 3)
  expect(m.calls.map(c => c.effort)).toEqual(['high', 'low', 'medium'])
  expect((await report($)).decisions.at(-1)?.index).toBe(2)
})

for (const [label, env] of Object.entries<Record<string, string>>({
  bedrock: { CLAUDE_CODE_USE_BEDROCK: '1' }, vertex: { CLAUDE_CODE_USE_VERTEX: 'true' },
  foundry: { CLAUDE_CODE_USE_FOUNDRY: '1' }, platform: { CLAUDE_CODE_USE_AGENT_PLATFORM: '1' },
  gateway: { ANTHROPIC_BASE_URL: 'https://gateway.invalid' }, betas: { CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS: '1' },
})) test(`${label} 暂停自动选档`, async ($, on) => {
  const m = setup(on, MODEL, env)
  await submit($, m.clock, '复杂任务')
  await step($)
  expect(m.prompts.length).toBe(0)
  expect(m.statuses).toEqual([])
  expect(await hint($, m)).toBe(' · ⏸ 自动选档已暂停：会重建缓存，已暂停')
})

test('不支持的模型清空状态栏', async ($, on) => {
  const m = setup(on, 'claude-haiku-5-5')
  await submit($, m.clock, '任务')
  const stream = $.turn.step({ turnId: 't1', index: 0, effort: 'medium', model: 'claude-haiku-5-5', messageCount: 2 })
  while (!(await stream.next()).done) {}
  expect(m.prompts.length).toBe(0)
  expect(await hint($, m)).toBe(undefined)
})

test('缓存重建两轮后暂停，同一轮只告警一次', async ($, on) => {
  const m = setup(on)
  for (let i = 1; i <= 3; i++) {
    const id = `t${i}`
    m.usage(i === 1 ? USAGE : { ...USAGE, cache_creation_input_tokens: 6000 })
    await submit($, m.clock, '任务', id)
    await step($, id)
    await step($, id, 1)
    await complete($, id)
  }
  expect(m.toasts.filter(t => t === '检测到缓存重建').length).toBe(2)
  expect((await report($)).paused).toMatch('两次缓存重建')
})

test('OpenRouter HTTP 错误回退 Haiku 且不泄露原文', { options: { judge: 'jev', openrouterApiKey: 'fake-test-key' } }, async ($, on) => {
  const m = setup(on)
  const requests: unknown[] = []
  on('http.fetch', (_, e) => {
    requests.push(JSON.parse(e.init!.body as string))
    return { value: { status: 401, ok: false, headers: {}, text: 'secret-server-original' } }
  })
  for (const id of ['t1', 't2']) {
    await submit($, m.clock, '任务', id)
    await step($, id)
    await complete($, id)
  }
  expect(m.calls.every(c => c.effort === 'high')).toBe(true)
  expect(m.toasts.filter(t => t === '已回退 Haiku：认证失败').length).toBe(1)
  expect(JSON.stringify(await report($)).includes('secret-server-original')).toBe(false)
  expect(JSON.stringify(requests[0])).toMatch('typesafe/jev-1.14')
})

for (const kind of ['missing', 'invalid', 'low', 'timeout', 'network'] as const)
  test(`OpenRouter ${kind} 只回退 Haiku 一次`, { options: { judge: 'jev', judgeTimeoutMs: 500 } }, async ($, on) => {
    const m = setup(on, MODEL, kind === 'missing' ? {} : { OPENROUTER_API_KEY: 'fake-test-key' })
    on('http.fetch', async () => {
      if (kind === 'network') throw new Error('secret-server-original')
      if (kind === 'timeout') await m.clock.sleep(1000)
      return { value: { status: 200, ok: true, headers: {}, text: kind === 'invalid' ? '{}' : JSON.stringify({ answers: { effort: { type: 'choice', choice: 'low', probabilities: { low: 0.1 }, confidence: 1 } } }) } }
    })
    await submit($, m.clock, '任务')
    if (kind === 'timeout') await m.clock.advance(251)
    await step($)
    expect(m.prompts.length).toBe(1)
    expect(m.calls.at(-1)?.effort).toBe('high')
    expect(m.toasts.length).toBe(1)
  })

test('System One 成功不调用 Haiku，概率才是置信度', { options: { judge: 'jev', openrouterApiKey: 'fake' } }, async ($, on) => {
  const m = setup(on)
  on('http.fetch', () => ({ value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: { effort: { type: 'choice', choice: 'low', probabilities: { low: 0.9 }, confidence: 0.1 } } }) } }))
  await submit($, m.clock, '任务')
  await step($)
  expect(m.prompts.length).toBe(0)
  expect(m.calls.at(-1)?.effort).toBe('low')
})

test('Fable 收尾提示是稳定会话段落', { options: { fableFinishPrompt: true } }, async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: '固定前缀', scope: 'shared' }] }))
  const input = { model: 'claude-fable-5-2[1m]', promptModel: 'claude-fable-5-2', surfaces: [], tools: [], outputStyle: null, traits: [] } as const
  const first = await $.prompt.compose(input)
  const second = await $.prompt.compose(input)
  expect(first).toEqual(second)
  expect(first.sections.at(-1)?.id).toBe('auto-effort:finish')
  expect(first.sections.at(-1)?.scope).toBe('session')
  expect((await $.prompt.compose({ ...input, model: MODEL })).sections.length).toBe(1)
})

test('更强模型提示每个会话只显示一次', async ($, on) => {
  const m = setup(on)
  m.answer('{"effort":"high","confidence":0.9,"reason":"验证","suggestModel":true}')
  for (const id of ['t1', 't2']) {
    await submit($, m.clock, '任务', id)
    await step($, id)
    await complete($, id)
  }
  expect(m.toasts.length).toBe(1)
})

test('test 不改会话档位或决策，bench 输出脱敏明细', async ($, on) => {
  const m = setup(on)
  const files = new Map<string, string>()
  on('fs.read', () => ({ value: JSON.stringify({ cases: [{ id: 'case1', message: '不得记录的消息', currentEffort: 'medium', holdout: true,
    ok: { 'claude-opus-5-5': ['high'], 'claude-sonnet-5-5': ['high'], 'claude-fable-5-2': ['high'] } }] }) }))
  on('fs.write', (_, e) => { files.set(e.path, e.text); return { value: undefined } })
  const before = await report($)
  const command = { command: 'auto-effort', origin: { kind: 'composer' as const }, presentation: { isFullscreen: false, columns: 80 } }
  const result = await $.command.run({ ...command, args: 'test 私密测试消息' })
  expect(result.text).toMatch('high')
  expect(await report($)).toEqual(before)
  const bench = await $.command.run({ ...command, args: 'bench all holdout' })
  expect(JSON.parse(bench.text!).summaries.length).toBe(3)
  expect(m.prompts.length).toBe(4)
  expect(files.size).toBe(1)
  expect([...files.values()][0]!.includes('不得记录的消息')).toBe(false)
})
