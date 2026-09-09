import type { RequestState } from '../events/types'
import StatusPip from './StatusPip'

const STATE_LABELS: Record<RequestState, string> = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  THINKING: 'THINKING',
  TOOL: 'TOOL',
  RESPONDING: 'RESPONDING',
  SUPERSEDED: 'SUPERSEDED',
}

function toneFor(state: RequestState): 'neutral' | 'active' | 'muted' {
  if (state === 'SUPERSEDED') return 'muted'
  if (state === 'RESPONDING') return 'active'
  return 'neutral'
}

export default function StateBadge({ state }: { state: RequestState }) {
  const tone = toneFor(state)
  return (
    <span className={`state-badge state-badge--${tone}`}>
      <StatusPip tone={tone} />
      {STATE_LABELS[state]}
    </span>
  )
}
