import { expect, mock, test } from 'claude-code/testing'

const HINT = { plugin: 'auto-effort', component: 'PromptHint', requestId: 'hint', props: { isDraft: false, isWorking: false, hint: '⏵⏵ auto mode on (shift+tab to cycle)' } } as const

test('状态接在终端提示行末尾，不再占独立一行', async ($, on) => {
  mock.clock(on, { now: 1794600000000 })
  mock.store(on, {})
  mock.env(on, { CLAUDE_CODE_USE_BEDROCK: '1' })
  const statuses: (string | undefined)[] = []
  let tail: string | undefined
  on('session.model', () => ({ value: 'claude-opus-5-5' }))
  on('session.id', () => ({ value: 's' }))
  on('config.set', (_, e) => ({ value: e.value }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('command.register', () => ({ value: { command: 'auto-effort' } }))
  on('ui.status', (_, e) => { statuses.push(e.text); return { value: undefined } })
  on('ui.render', ($, e) => {
    if (e.component === 'PromptHint') tail = e.props.tail
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.command.run({ command: 'auto-effort', args: 'on', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } })
  const ui = await $.ui.mount({ ...HINT, surface: 'terminal' })
  expect(tail).toBe(' · ⏸ 自动选档已暂停：会重建缓存，已暂停')
  expect(statuses).toEqual([])
  await ui.unmount()
})
