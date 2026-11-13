import type { EngineInterface } from 'claude-code'
import type { SupportedModel } from './policy-text'
import { haikuSystemPrompt, systemOneQuestion } from './policy-text'
import { expandPiKey, httpFailure, parseHaiku, parseSystemOne, record } from './core'
import type { Config, JudgeResult } from './core'

/** 复用 Pi 为 OpenRouter 保存的 key（`<agent 目录>/auth.json` 的 openrouter 条目）。只读，不写回，不记录。 */
async function piOpenRouterKey($: EngineInterface): Promise<string | undefined> {
  try {
    const home = await $.env.get('HOME')
    const configured = await $.env.get('PI_CODING_AGENT_DIR')
    const dir = configured ? configured.replace(/^~(?=\/|$)/, home ?? '~') : home ? `${home}/.pi/agent` : undefined
    if (!dir) return undefined
    const data: unknown = JSON.parse(String(await $.fs.read(`${dir}/auth.json`)))
    const entry = record(data) ? data.openrouter : undefined
    if (!record(entry) || entry.type !== 'api_key' || typeof entry.key !== 'string') return undefined
    return expandPiKey(entry.key, record(entry.env) ? entry.env : {})
  } catch { return undefined }
}

export const SYSTEM_ONE_MODELS = {
  jev: 'typesafe/jev-1.14', 'd1-ultra': 'liquid/d1-ultra',
  'mammoth-27b': 'baseten/mammoth-1', decider: 'perplexity/pplx-decider-v1.2',
} as const

export async function classify($: EngineInterface, config: Config, model: SupportedModel, prompt: string,
  fallback: (reason: string) => Promise<void>, signal?: AbortSignal): Promise<JudgeResult> {
  const started = await $.clock.now()
  let failure: string | undefined
  if (config.judge !== 'haiku') {
    const key = config.openrouterApiKey || await $.env.get('OPENROUTER_API_KEY') || await piOpenRouterKey($)
    if (!key) failure = '未找到 OpenRouter API key'
    else {
      let timer: ReturnType<typeof $.clock.after> | undefined
      try {
        // 给 Haiku 回退留出时间；底层 HTTP 接口没有取消参数。
        const timeout = new Promise<undefined>(resolve => {
          timer = $.clock.after(Math.min(2000, config.judgeTimeoutMs / 2), () => resolve(undefined))
        })
        const response = await Promise.race([$.http.fetch('https://openrouter.ai/api/v1/systemone', {
          method: 'POST', headers: { Authorization: `Bearer ${key}`, 'content-type': 'application/json' },
          body: JSON.stringify({ model: SYSTEM_ONE_MODELS[config.judge], state: { prompt }, questions: { effort: systemOneQuestion(model) } }),
        }), timeout])
        if (!response) failure = '服务请求超时'
        else if (!response.ok) failure = httpFailure(response.status)
        else {
          const result = parseSystemOne(response.text)
          if (result && result.confidence >= 0.5) return { result, judge: config.judge, ms: await $.clock.now() - started }
          failure = result ? '判档置信度不足' : '分类响应格式无效'
        }
      } catch { failure = '网络连接失败' }
      finally { timer?.cancel() }
    }
    if (signal?.aborted) return { judge: config.judge, ms: await $.clock.now() - started, failure: '判档超时' }
    await fallback(failure)
  }
  try {
    const remaining = Math.max(1, config.judgeTimeoutMs - (await $.clock.now() - started))
    const reply = await $.model.complete({ model: 'claude-haiku-5-5', system: haikuSystemPrompt(model),
      prompt, maxTokens: 200, effort: 'low', timeoutMs: remaining }, { signal })
    const result = reply.isAnswered ? parseHaiku(reply.text) : undefined
    const reason = reply.isAnswered ? result ? result.confidence < 0.5 ? '判档置信度不足' : undefined : '判档结果无效'
      : reply.reason === 'aborted' ? '判档超时' : reply.reason === 'api-error' ? httpFailure(reply.status ?? 0) : '判档无回答'
    return { result, judge: 'haiku', ms: await $.clock.now() - started, failure: reason, usage: reply.usage }
  } catch { return { judge: 'haiku', ms: await $.clock.now() - started, failure: '判档服务不可用' } }
}
