import type { VoiceEvent, VoiceGuardSnapshot, VoiceMetrics, VoiceRequest, RequestState } from './types'

const event = (id: string, type: VoiceEvent['type'], timestamp: number, values: Partial<VoiceEvent> = {}): VoiceEvent => ({
  id,
  type,
  timestamp,
  ...values,
})

const makeSnapshot = (events: VoiceEvent[], demoStep: number, isRunning: boolean): VoiceGuardSnapshot => {
  const req2 = events.find((item) => item.type === 'request_started' && item.requestId === 2)
  const req3 = events.find((item) => item.type === 'request_started' && item.requestId === 3)
  const req2Superseded = events.some((item) => item.type === 'superseded' && item.requestId === 2)
  const req3States = events.filter(
  (item) => item.requestId === 3 && item.type === 'state_changed'
)

const req3State = req3States[req3States.length - 1]?.detail
  const req3StateValue: RequestState = req3State?.toLowerCase().includes('respond') ? 'RESPONDING' : 'TOOL'

  let currentRequest: VoiceRequest | null = null
  if (req3) {
    currentRequest = {
      id: 3,
      text: req3.text ?? 'Actually, Hyderabad to Bombay.',
      state: req3StateValue,
      startedAt: req3.timestamp,
      relative: 'just now',
      isCurrent: true,
    }
  } else if (req2 && !req2Superseded) {
    currentRequest = {
      id: 2,
      text: req2.text ?? 'Find trains from Bombay to Delhi.',
      state: events.some((item) => item.type === 'state_changed' && item.requestId === 2) ? 'TOOL' : 'THINKING',
      startedAt: req2.timestamp,
      relative: 'just now',
      isCurrent: true,
    }
  }

  const requests: VoiceRequest[] = []
  if (req3) requests.push({ id: 3, text: req3.text ?? 'Actually, Hyderabad to Bombay.', state: req3StateValue, startedAt: req3.timestamp, relative: 'just now', isCurrent: true })
  if (req2) requests.push({ id: 2, text: req2.text ?? 'Find trains from Bombay to Delhi.', state: req2Superseded ? 'SUPERSEDED' : 'TOOL', startedAt: req2.timestamp, relative: 'earlier', isCurrent: false })

  const metrics: VoiceMetrics = {
    requests: events.filter((item) => item.type === 'request_started').length,
    superseded: events.filter((item) => item.type === 'superseded').length,
    blocked: events.filter((item) => item.type === 'audio_blocked').reduce((sum, item) => sum + (item.metric ?? 0), 0),
    heard: events.filter((item) => item.type === 'audio_played').reduce((sum, item) => sum + (item.metric ?? 0), 0),
    ghostTasks: events.filter((item) => item.type === 'ghost_task').length,
    generated: events.filter((item) => item.type === 'audio_generated').reduce((sum, item) => sum + (item.metric ?? 0), 0),
  }

  return { currentRequest, requests, events, metrics, demoStep, isRunning }
}

export const createMockEventSource = (onUpdate: (snapshot: VoiceGuardSnapshot) => void) => {
  let events: VoiceEvent[] = []
  let demoStep = 0
  let runToken = 0
  let running = false

  const publish = () => onUpdate(makeSnapshot(events, demoStep, running))

  const reset = () => {
    runToken += 1
    events = []
    demoStep = 0
    running = false
    publish()
  }

  const addEvent = (newEvent: VoiceEvent) => {
    events = [...events, newEvent]
    publish()
  }

  const start = () => {
    reset()
    running = true
    const token = runToken
    const started = Date.now()
    const sequence: Array<{ delay: number; type: VoiceEvent['type']; requestId?: number; text?: string; detail?: string; metric?: number }> = [
      { delay: 350, type: 'request_started', requestId: 2, text: 'Find trains from Bombay to Delhi.' },
      { delay: 1200, type: 'state_changed', requestId: 2, detail: 'Tool search started' },
      { delay: 3000, type: 'interrupt', requestId: 2, detail: 'User started speaking' },
      { delay: 3900, type: 'superseded', requestId: 2, detail: 'Request invalidated by REQ 003' },
      { delay: 4500, type: 'audio_blocked', requestId: 2, metric: 38, detail: 'Audio belonged to superseded request' },
      { delay: 5600, type: 'request_started', requestId: 3, text: 'Actually, Hyderabad to Bombay.' },
      { delay: 6600, type: 'state_changed', requestId: 3, detail: 'Tool search started' },
      { delay: 7700, type: 'audio_generated', requestId: 3, metric: 124 },
      { delay: 8500, type: 'audio_played', requestId: 3, metric: 78 },
      { delay: 9800, type: 'ghost_task', requestId: 2, detail: 'Train search finished after supersession' },
      { delay: 10500, type: 'state_changed', requestId: 3, detail: 'Responding' },
    ]

    sequence.forEach((step, index) => {
      window.setTimeout(() => {
        if (token !== runToken) return
        demoStep = index + 1
        addEvent(event(`d-${index + 1}`, step.type, started + step.delay, {
          requestId: step.requestId,
          text: step.text,
          detail: step.detail,
          metric: step.metric,
        }))
        if (index === sequence.length - 1) {
          running = false
          publish()
        }
      }, step.delay)
    })
  }

  const interrupt = () => {
    addEvent(event(`manual-${Date.now()}`, 'interrupt', Date.now(), { requestId: 2, detail: 'User started speaking' }))
    addEvent(event(`manual-super-${Date.now()}`, 'superseded', Date.now() + 1, { requestId: 2, detail: 'Request invalidated by the replacement request' }))
  }

  const ghost = () => addEvent(event(`ghost-${Date.now()}`, 'ghost_task', Date.now(), { requestId: 2, detail: 'Train search finished after supersession' }))

  publish()
  return { start, reset, interrupt, ghost }
}

export type MockEventSource = ReturnType<typeof createMockEventSource>
