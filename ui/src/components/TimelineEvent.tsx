import type { VoiceEvent } from '../events/types'
import { formatEventTime, formatRequestId } from '../utils/format'

interface EventMeta {
  title: string | ((e: VoiceEvent) => string)
  className: string | ((e: VoiceEvent) => string)
}

type ConstraintDiffEvent = {
  id: string
  type: 'constraint_diff'
  requestId?: number
  previousRequestId?: number
  oldText?: string
  newText?: string
  changes?: Array<{
    tag?: string
    old?: string
    new?: string
  }>
  timestamp: number
  text?: string
  detail?: string
  metric?: number
  stage?: string
}

type InterruptLatencyEvent = {
  id: string
  type: 'interrupt_latency'
  requestId?: number
  timestamp: number
  latencyMs?: number
  text?: string
  detail?: string
  metric?: number
  stage?: string
}

type TimelineItem =
  | VoiceEvent
  | ConstraintDiffEvent
  | InterruptLatencyEvent

type TimelineEventType = TimelineItem['type']

const EVENT_META: Record<TimelineEventType, EventMeta> = {
  request_started: { title: 'REQUEST', className: '' },

  state_changed: {
    title: (e) => e.detail ?? 'STATE CHANGED',
    className: '',
  },

  tool_started: {
    title: 'TOOL RUNNING',
    className: '',
  },

  tool_completed: {
    title: 'TOOL RESULT ACCEPTED',
    className: '',
  },

  tool_cancelled: {
    title: 'TOOL CANCELLED',
    className: 'timeline-alert',
  },

  interrupt: {
    title: 'INTERRUPT',
    className: 'timeline-alert',
  },

  superseded: {
    title: 'SUPERSEDED',
    className: 'timeline-muted',
  },

  audio_generated: {
    title: 'RIME AUDIO GENERATED',
    className: '',
  },

  audio_played: {
    title: 'AUDIO HEARD',
    className: 'timeline-new',
  },

  audio_blocked: {
    title: 'AUDIO BLOCKED',
    className: 'timeline-alert',
  },

  constraint_diff: {
    title: 'CONSTRAINTS CHANGED',
    className: 'timeline-alert',
  },

  interrupt_latency: {
    title: 'INTERRUPT HANDLED',
    className: 'timeline-new',
  },

  ghost_task: {
    title: 'GHOST WORK RECONCILED',
    className: 'timeline-muted',
  },

  request_completed: {
    title: 'REQUEST COMPLETE',
    className: '',
  },
}

function resolve(
  value: string | ((e: VoiceEvent) => string),
  e: VoiceEvent,
): string {
  return typeof value === 'function' ? value(e) : value
}

function ConstraintDiff({
  event,
}: {
  event: ConstraintDiffEvent
}) {
  const oldText = event.oldText || '—'
  const newText = event.newText || '—'

  return (
    <div className="constraint-diff">
      <div className="constraint-diff-row">
        <span className="constraint-diff-label">
          {event.previousRequestId !== undefined
            ? formatRequestId(event.previousRequestId)
            : 'PREVIOUS'}
        </span>

        <span className="constraint-diff-old">
          {oldText}
        </span>
      </div>

      <div
        className="constraint-diff-arrow"
        aria-hidden="true"
      >
        ↓
      </div>

      <div className="constraint-diff-row">
        <span className="constraint-diff-label">
          {event.requestId !== undefined
            ? formatRequestId(event.requestId)
            : 'CURRENT'}
        </span>

        <span className="constraint-diff-new">
          {newText}
        </span>
      </div>
    </div>
  )
}

export default function TimelineEvent({
  item,
  origin,
  isLast,
}: {
  item: TimelineItem
  origin?: number
  isLast: boolean
}) {
  const meta = EVENT_META[item.type]

  const title = resolve(
    meta.title,
    item as VoiceEvent,
  )

  const className = resolve(
    meta.className,
    item as VoiceEvent,
  )

  const body =
    item.type === 'audio_blocked' ||
    item.type === 'audio_played'
      ? ''
      : item.text ??
        item.detail ??
        ''

  return (
    <div className={`timeline-item ${className}`}>
      <div className="timeline-rail">
        <span className="timeline-marker" />
        {!isLast && (
          <span className="timeline-line" />
        )}
      </div>

      <div className="timeline-content">
        <div className="timeline-heading">
          <span>{title}</span>

          <time>
            {formatEventTime(
              item.timestamp,
              origin,
            )}
          </time>
        </div>

        {item.requestId !== undefined &&
          item.type !== 'constraint_diff' && (
            <div className="timeline-request">
              {formatRequestId(item.requestId)}
            </div>
          )}

        {item.type === 'constraint_diff' ? (
          <ConstraintDiff
            event={item}
          />
        ) : (
          <p>{body}</p>
        )}

        {item.type === 'audio_blocked' && (
          <span className="timeline-count">
            {item.metric ?? 0} audio chunks blocked
          </span>
        )}

        {item.type === 'audio_played' && (
          <span className="timeline-count">
            {item.metric ?? 0} audio chunks actually played
          </span>
        )}

        {item.type === 'interrupt_latency' &&
          item.latencyMs !== undefined && (
            <span className="timeline-count">
              {item.latencyMs?.toFixed(2)} ms
            </span>
          )}
      </div>
    </div>
  )
}