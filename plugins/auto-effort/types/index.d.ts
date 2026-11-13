export type AutoEffortLevel = 'low' | 'medium' | 'high' | 'xhigh' | 'max'

export type AutoEffortSession = {
  sessionId: string
  paused?: string
  lastFinal?: AutoEffortLevel
  lastDecision?: { at: string; turnId: string; index: number }
  previousEngine?: AutoEffortLevel | number
  previousEngineSeen: boolean
  previousEngineModel?: string
  currentUltra: boolean
  skipTurn: boolean
  activeTurn?: string
  turnNo: number
  toolCalls: number
  rewritten: boolean
  warnedThisTurn: boolean
  previousCacheRead: number
  previousRequestEndedAt?: number
  previousRequestModel?: string
  latestCacheRead: number
  cacheWarnings: number
  suggested: boolean
  fallbackWarned: boolean
  statusDetail?: string
  firstStepCache?: { read: number; write: number }
  steps: { turnId: string; index: number; model: string; read: number; write: number; input: number; output: number }[]
  summary: { effort?: AutoEffortLevel; toolCalls: number; interrupted: boolean }
}

declare module 'claude-code' {
  interface PluginState {
    'auto-effort': { session: AutoEffortSession }
  }
}
