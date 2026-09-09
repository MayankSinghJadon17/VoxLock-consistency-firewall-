import type { VoiceEvent, VoiceRequest } from '../events/types'
import { formatDuration, formatEventTime, formatRequestId } from '../utils/format'
import StatusPip from './StatusPip'

export default function GhostTasks({
  ghostTask,
  ghostRequest,
}: {
  ghostTask: VoiceEvent | undefined
  ghostRequest: VoiceRequest | undefined
}) {
  return (
    <section className="ghost-section section-rule">
      <div className="section-kicker">
        <span>05</span>
        <span>GHOST TASKS</span>
        <span className="kicker-note">OBSOLETE WORK / RETAINED AS EVIDENCE</span>
      </div>
      {ghostTask ? (
        <div className="ghost-card">
          <div className="ghost-card-top">
            <span className="ghost-label">
              <StatusPip tone="muted" />
              OBSOLETE WORK
            </span>
            <span className="ghost-time">
              OBSERVED {formatEventTime(ghostTask.timestamp, ghostRequest?.startedAt)}
            </span>
          </div>
          <div className="ghost-request">{formatRequestId(ghostTask.requestId ?? 0)}</div>
          <div className="ghost-title">{ghostTask.stage ?? 'Background task'}</div>
          <p>{ghostTask.detail ?? 'Work completed after supersession and was fenced from the user.'}</p>
          {ghostRequest && (
            <div className="ghost-detail">
              <div>
                <span>STARTED</span>
                <strong>{formatEventTime(ghostRequest.startedAt, ghostRequest.startedAt)}</strong>
              </div>
              <div>
                <span>OBSERVED</span>
                <strong>{formatEventTime(ghostTask.timestamp, ghostRequest.startedAt)}</strong>
              </div>
              <div>
                <span>ELAPSED</span>
                <strong>{formatDuration(ghostRequest.startedAt, ghostTask.timestamp)}</strong>
              </div>
            </div>
          )}
          <div className="disposition">
            <span>DISPOSITION</span>
            <strong>SUPERSEDED — NOT SPOKEN</strong>
          </div>
        </div>
      ) : (
        <div className="ghost-empty">No obsolete tasks currently retained.</div>
      )}
      {ghostRequest && (
        <div className="subdued-note">
          {formatRequestId(ghostRequest.id)} remains visible so the system's decision can be verified.
        </div>
      )}
    </section>
  )
}
