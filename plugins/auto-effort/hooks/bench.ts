import type { EngineInterface } from 'claude-code'
import type { Effort, SupportedModel } from './policy-text'
import { EFFORTS, MODEL_RULES } from './policy-text'
import { classify } from './judge'
import { isEffort, judgeInput, parseContext } from './core'
import type { Config, Usage } from './core'

type Case = { id: string; message: string; context?: string; currentEffort: Effort; holdout?: boolean; ok: Record<SupportedModel, Effort[]> }

export async function runBench($: EngineInterface, config: Config, args: string[], fallback: (reason: string) => Promise<void>): Promise<string> {
  const aliases = { opus: 'claude-opus-5-5', sonnet: 'claude-sonnet-5-5', fable: 'claude-fable-5-2' } as const
  const target = args[0] ?? 'all'
  if (!(target === 'all' || Object.hasOwn(aliases, target)) || args.length > 2 || (args[1] !== undefined && args[1] !== 'holdout'))
    return '用法：/auto-effort bench [opus|sonnet|fable|all] [holdout]'
  const raw = JSON.parse(await $.fs.read(`${$.plugin.root}/bench/judge-cases.json`)) as { cases: Case[] }
  if (!Array.isArray(raw.cases) || raw.cases.some(c => typeof c.id !== 'string' || typeof c.message !== 'string' || !isEffort(c.currentEffort)))
    return '测评用例格式无效'
  const models: SupportedModel[] = target === 'all' ? Object.keys(MODEL_RULES) as SupportedModel[] : [aliases[target as keyof typeof aliases]]
  const cases = raw.cases.filter(c => args[1] !== 'holdout' || c.holdout)
  const rows: { id: string; model: SupportedModel; holdout: boolean; expected: Effort[]; actual: Effort | null; hit: boolean; direction: string; confidence?: number; reason?: string; ms: number; judge: string }[] = []
  const usage: Usage = { input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 }
  for (const model of models) {
    for (const c of cases) {
      const history = c.context ? parseContext(c.context) : []
      const prompt = judgeInput(model, c.currentEffort, { effort: c.currentEffort, toolCalls: 0, interrupted: false }, history, c.message)
      const answer = await classify($, config, model, prompt, fallback)
      if (answer.usage) for (const key of Object.keys(usage) as (keyof Usage)[]) usage[key] += answer.usage[key]
      const actual = answer.result && answer.result.confidence >= 0.5 ? answer.result.effort : undefined
      const expected = c.ok[model]
      rows.push({ id: c.id, model, holdout: c.holdout === true, expected, actual: actual ?? null,
        hit: actual !== undefined && expected.includes(actual),
        direction: !actual ? 'invalid' : expected.includes(actual) ? 'hit' : EFFORTS.indexOf(actual) < Math.min(...expected.map(e => EFFORTS.indexOf(e))) ? 'low' : 'high',
        confidence: answer.result?.confidence, reason: answer.failure ?? answer.result?.reason, ms: answer.ms, judge: answer.judge })
    }
  }
  const summaries = models.map(model => {
    const all = rows.filter(row => row.model === model)
    const held = all.filter(row => row.holdout)
    const times = all.map(row => row.ms).sort((a, b) => a - b)
    const median = times.length ? (times[Math.floor((times.length - 1) / 2)]! + times[Math.floor(times.length / 2)]!) / 2 : 0
    return { model, total: all.length, hits: all.filter(row => row.hit).length, holdoutTotal: held.length,
      holdoutHits: held.filter(row => row.hit).length, low: all.filter(row => row.direction === 'low').length,
      high: all.filter(row => row.direction === 'high').length, invalid: all.filter(row => row.direction === 'invalid').length, medianMs: median }
  })
  const path = `${$.plugin.root}/bench/results/${new Date(await $.clock.now()).toISOString().replace(/[:.]/g, '-')}-${config.judge}.json`
  await $.fs.write(path, JSON.stringify({ judge: config.judge, summaries, usage, rows }, null, 2) + '\n')
  return JSON.stringify({ summaries, usage, path })
}
