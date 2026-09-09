import type { VoiceEvent } from '../events/types'
import TimelineEvent from './TimelineEvent'

const VISIBLE_TYPES: VoiceEvent['type'][] = [
  'request_started',
  'interrupt',
  'superseded',
  'tool_cancelled',
  'audio_blocked',
  'audio_played',
]

function compactEvents(events: VoiceEvent[]): VoiceEvent[] {
  const visible = events.filter((event) =>
    VISIBLE_TYPES.includes(event.type),
  )

  const compacted: VoiceEvent[] = []

  for (const event of visible) {
    const previous = compacted[compacted.length - 1]

    const isAudioEvent =
      event.type === 'audio_played' ||
      event.type === 'audio_blocked'

    const previousIsSameAudio =
      previous &&
      previous.type === event.type &&
      previous.requestId === event.requestId

    if (isAudioEvent && previousIsSameAudio) {
      previous.metric = (previous.metric ?? 1) + (event.metric ?? 1)
      previous.timestamp = event.timestamp
      previous.detail =
        event.type === 'audio_played'
          ? `${previous.metric} audio chunks actually played`
          : `${previous.metric} audio chunks blocked`

      continue
    }

    compacted.push({
      ...event,
      metric:
        isAudioEvent && event.metric === undefined
          ? 1
          : event.metric,
      detail:
        event.type === 'audio_played'
          ? `${event.metric ?? 1} audio chunks actually played`
          : event.type === 'audio_blocked'
            ? `${event.metric ?? 1} audio chunks blocked`
            : event.detail,
    })
  }

  return compacted
}

export default function Timeline({
  events,
}: {
  events: VoiceEvent[]
}) {
  const visible = compactEvents(events)

  const origin = visible.length
    ? Math.min(...visible.map((item) => item.timestamp))
    : undefined

  return (
    <div className="timeline">
      {visible.map((item, index) => (
        <TimelineEvent
          key={item.id}
          item={item}
          origin={origin}
          isLast={index === visible.length - 1}
        />
      ))}
    </div>
  )
}