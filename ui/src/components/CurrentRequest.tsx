import type { VoiceRequest } from '../events/types'
import { formatDuration, formatRequestId } from '../utils/format'
import StateBadge from './StateBadge'

export default function CurrentRequest({
  request,
  serverTime,
}: {
  request: VoiceRequest | null
  serverTime?: number
}) {
  if (!request) {
    return (
      <div className="ready-state">
        <span className="ready-line" />
        <div>
          <div className="request-text">SYSTEM READY</div>
          <p>Waiting for voice input.</p>
        </div>
      </div>
    )
  }

  const elapsed = formatDuration(request.startedAt, serverTime ?? request.startedAt)

  return (
    <div className="request-layout">
      <div className="request-main">
        <div className="request-id">
          {formatRequestId(request.id)} <span>· {request.relative}</span>
        </div>
        <div className="request-text">“{request.text}”</div>
      </div>
      <div className="current-state">
        <span className="field-label">CURRENT STATE</span>
        <StateBadge state={request.state} />
        <span className="technical-time">
          ACTIVE / {elapsed}
        </span>
      </div>
    </div>
  )
}
