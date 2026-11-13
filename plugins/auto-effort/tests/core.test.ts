import { expect, test } from 'claude-code/testing'
import { cacheRebuilt, clampEffort, configOf, expandPiKey, httpFailure, isContinue, isUltra, judgeInput, parseContext, parseHaiku, parseSystemOne, retainedDecisions, supportedModel } from '../hooks/core'

test('持久记录保留最近 50 会话、每会话 200 条和 UTF-8 安全上限，旧记录可读', () => {
  const row = { at: '2026-11-13', sessionId: 's', turnId: 't', index: 0, turn: 1, final: 'low' }
  const many = retainedDecisions(Array.from({ length: 201 }, (_, turn) => ({ ...row, turn })))
  expect(many.length).toBe(200)
  expect(many[0]?.turn).toBe(1)
  const sessions = retainedDecisions(Array.from({ length: 51 }, (_, turn) => ({ ...row, sessionId: `s${turn}` })))
  expect(sessions.length).toBe(50)
  expect(sessions[0]?.sessionId).toBe('s1')
  expect(retainedDecisions([null, {}, { ...row, final: 'invalid' }, row])).toEqual([row])
  const large = retainedDecisions(Array.from({ length: 200 }, (_, turn) => ({ ...row, turn, reason: '中'.repeat(10000) })))
  expect(JSON.stringify(large).length * 3).toBeLessThan(3 * 1024 * 1024)
  expect(large.at(-1)?.turn).toBe(199)
  expect(retainedDecisions(null)).toEqual([])
})

test('模型白名单与连续后缀规范化', () => {
  for (const model of ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-fable-5-2'])
    expect(supportedModel(`${model}[1m][fast]`)).toBe(model)
  for (const model of ['opus', 'claude-haiku-5-5', 'claude-opus-5-5-extra', 'claude-sonnet-5-5[1m]evil']) expect(supportedModel(model)).toBe(undefined)
})

test('上下限与 max 开关同时生效，冲突时以上限为准', () => {
  const config = { floor: 'medium', ceiling: 'xhigh', allowMax: false } as const
  expect(clampEffort('low', config)).toBe('medium')
  expect(clampEffort('max', config)).toBe('xhigh')
  expect(clampEffort('max', { ...config, ceiling: 'max' })).toBe('xhigh')
  expect(clampEffort('max', { ...config, ceiling: 'max', allowMax: true })).toBe('max')
  expect(clampEffort('low', { ...config, floor: 'max', ceiling: 'low' })).toBe('low')
  expect(clampEffort('max', { ...config, floor: 'max', ceiling: 'max' })).toBe('xhigh')
})

test('只把整条「继续」识别为继续请求，其他短回复交给判档器', () => {
  for (const text of ['继续！', 'continue', 'Go on.', 'keep going', '接着做']) expect(isContinue(text)).toBe(true)
  for (const text of ['OK!', 'yes', '好', '继续修复 bug', 'go to school', '']) expect(isContinue(text)).toBe(false)
  const env = { A: 'x', B: 'y' }
  expect(expandPiKey('plain-key', env)).toBe('plain-key')
  expect(expandPiKey('$A-${B}-$$-$!', env)).toBe('x-y-$-!')
  expect(expandPiKey('$MISSING', env)).toBe(undefined)
  expect(expandPiKey('!op read key', env)).toBe(undefined)
  const history = parseContext('user: 要不要先做 A？\nassistant: 两件事先定。\n1. 范围\n2. 测试。可以的话我就开始实现。')
  expect(history.map(r => r.role)).toEqual(['user', 'assistant'])
  expect(history[1]!.text).toMatch('我就开始实现')
  const input = judgeInput('claude-opus-5-5', 'medium', { toolCalls: 0, interrupted: false }, history, 'yes')
  expect(input).toMatch('近期对话（用于补全当前消息省略的目标、约束和交付要求；新任务不继承）')
  expect(input).toMatch('助手: 两件事先定。')
  expect(input.endsWith('当前用户消息：\nyes')).toBe(true)
  expect(isUltra('请 ultrathink 一下')).toBe(true)
  expect(isUltra('ULTRATHINK!')).toBe(true)
  expect(isUltra('请ultrathink一下')).toBe(true)
  expect(isUltra('notultrathink')).toBe(false)
  expect(isUltra('ultrathinking')).toBe(false)
})

test('Haiku JSON 容错、结构与置信度校验', () => {
  const good = '{"effort":"high","confidence":0.9,"reason":"必须验证","suggestModel":false}'
  expect(parseHaiku(good)?.effort).toBe('high')
  expect(parseHaiku(` \n\`\`\`json\n${good}\n\`\`\`\n `)?.confidence).toBe(0.9)
  expect(parseHaiku(good.replace('0.9', '0.3'))?.confidence).toBe(0.3)
  for (const text of ['broken', 'null', '{}', good.replace('high', 'extreme'), good.replace('0.9', '2')]) expect(parseHaiku(text)).toBe(undefined)
  expect(parseHaiku(good.replace('必须验证', 'sk-secret 用户原文'))?.reason).toBe('复杂任务或结果验证')
})

test('System One 取 choice 对应概率，忽略响应中的置信度', () => {
  const good = JSON.stringify({ answers: { effort: { type: 'choice', choice: 'high', probabilities: { high: 0.75 }, confidence: 0.1 } } })
  expect(parseSystemOne(good)?.confidence).toBe(0.75)
  for (const text of ['secret 原始报错', '{}', good.replace('0.75', '2'), good.replace('"high":0.75', '"low":0.75')]) expect(parseSystemOne(text)).toBe(undefined)
  for (const status of [400, 401, 402, 403, 404, 408, 413, 429, 500, 529, 599, 418]) {
    expect(httpFailure(status)).toMatch(/[\u4e00-\u9fa5]/)
    expect(httpFailure(status).includes('secret')).toBe(false)
  }
})

test('输入取最近十条文本，历史最多 24000 字符，当前消息最多 12000 字符', () => {
  const input = judgeInput('claude-opus-5-5', 'medium', { effort: 'low', toolCalls: 2, interrupted: true },
    Array.from({ length: 8 }, (_, i) => ({ role: 'user' as const, text: String(i).repeat(4000) })), 'Z'.repeat(14000))
  expect(input.includes('0'.repeat(100))).toBe(false)
  expect(input.includes('1'.repeat(100))).toBe(false)
  expect(input.match(/Z/g)?.length).toBe(12000)
  expect(input.length).toBeLessThan(36500)
  const many = judgeInput('claude-opus-5-5', 'medium', { toolCalls: 0, interrupted: false },
    Array.from({ length: 12 }, (_, i) => ({ role: 'assistant' as const, text: `第${i}条` })), 'x')
  expect(many.includes('第1条')).toBe(false)
  expect(many.includes('第2条')).toBe(true)
  expect(input).toMatch('工具调用次数=2；是否被中断=是')
  expect(configOf({ debugLogPath: 'relative.jsonl' }).debugLogPath).toBe('')
})

test('缓存守护只在已有缓存且读归零或大幅重建时触发', () => {
  const usage = { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 9000 }
  expect(cacheRebuilt(0, usage)).toBe(false)
  expect(cacheRebuilt(10000, usage)).toBe(true)
  expect(cacheRebuilt(10000, { ...usage, cache_read_input_tokens: 10000, cache_creation_input_tokens: 5000 })).toBe(false)
  expect(cacheRebuilt(10000, { ...usage, cache_read_input_tokens: 10000, cache_creation_input_tokens: 5001 })).toBe(true)
})
