export type RequestState = 'IDLE' | 'LISTENING' | 'THINKING' | 'TOOL' | 'RESPONDING' | 'SUPERSEDED'

export type EventType =
  | 'request_started'
  | 'state_changed'
  | 'interrupt'
  | 'superseded'
  | 'audio_generated'
  | 'audio_played'
  | 'audio_blocked'
  | 'ghost_task'
  | 'request_completed'
  | 'tool_started'
  | 'tool_completed'
  | 'tool_cancelled'

export interface VoiceEvent {
  id: string
  type: EventType
  requestId?: number
  text?: string
  detail?: string
  timestamp: number
  metric?: number
  stage?: string
}

export interface VoiceRequest {
  id: number
  text: string
  state: RequestState
  startedAt: number
  relative: string
  isCurrent: boolean
}

export interface VoiceMetrics {
  requests: number
  superseded: number
  blocked: number
  heard: number
  ghostTasks: number
  generated: number
}

export interface VoiceGuardSnapshot {
  currentRequest: VoiceRequest | null
  requests: VoiceRequest[]
  events: VoiceEvent[]
  metrics: VoiceMetrics
  demoStep: number
  isRunning: boolean
  serverTime?: number
}
