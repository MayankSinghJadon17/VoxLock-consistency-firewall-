import type { VoiceGuardSnapshot } from '../events/types'
import { formatRequestId } from '../utils/format'

type Props = {
  snapshot: VoiceGuardSnapshot
}

export default function IntentFlow({ snapshot }: Props) {
  const current = snapshot.currentRequest
  const requestText = current?.text || 'Waiting for voice input.'
  const state = current?.state || 'IDLE'

  const generated = snapshot.metrics.generated
  const heard = snapshot.metrics.heard
  const blocked = snapshot.metrics.blocked

  const hasCurrentRequest = current !== null
  const isBlocked = hasCurrentRequest && blocked > 0
  const isHeard = hasCurrentRequest && heard > 0
  const displayState = state.split('_').join(' ')


  return (
    <section
      className="intent-flow"
      aria-label="Intent computation reality"
    >
      <div className="intent-flow-header">
        <div className="section-kicker">
          <span>03A</span>
          <span>INTENT → COMPUTATION → REALITY</span>
        </div>

        <div className="intent-flow-status">
          CONSISTENCY BOUNDARY
        </div>
      </div>

      <div className="intent-flow-grid">
        <article className="intent-flow-card intent-card">
          <div className="intent-flow-number">01</div>

          <div className="intent-flow-label">INTENT</div>

          <h3>
            What the user
            <br />
            actually asked.
          </h3>

          <div className="intent-flow-request-id">
            {current ? formatRequestId(current.id) : '#--'}
          </div>

          <div className="intent-flow-value">
            {requestText}
          </div>
        </article>

        <div className="intent-flow-arrow" aria-hidden="true">
          →
        </div>

        <article className="intent-flow-card computation-card">
          <div className="intent-flow-number">02</div>

          <div className="intent-flow-label">COMPUTATION</div>

          <h3>
            Work may continue.
            <br />
            Intent cannot drift.
          </h3>

          <div className="intent-flow-request-id">
            {current ? formatRequestId(current.id) : '#--'}
          </div>

          <div
            className={`intent-flow-value ${
              isBlocked
                ? 'flow-value-blocked'
                : isHeard
                  ? 'flow-value-heard'
                  : ''
            }`}
          >
            <span className="flow-state-dot" />
            {!hasCurrentRequest
              ? 'EVIDENCE RETAINED'
              : isBlocked
                ? 'STALE OUTPUT BLOCKED'
                : isHeard
                  ? 'ACTUALLY HEARD'
                  : 'SPEECH BOUNDARY READY'}
          </div>
        </article>

        <div className="intent-flow-arrow" aria-hidden="true">
          →
        </div>

        <article className="intent-flow-card reality-card">
          <div className="intent-flow-number">03</div>

          <div className="intent-flow-label">REALITY</div>

          <h3>
            Only valid output
            <br />
            can be heard.
          </h3>

          <div className="intent-flow-request-id">
            {current ? formatRequestId(current.id) : '#--'}
          </div>

          <div
            className={`intent-flow-value ${
              isBlocked
                ? 'flow-value-blocked'
                : isHeard
                  ? 'flow-value-heard'
                  : ''
            }`}
          >
            <span className="flow-state-dot" />

            {isBlocked
              ? 'STALE OUTPUT BLOCKED'
              : isHeard
                ? 'ACTUALLY HEARD'
                : 'SPEECH BOUNDARY READY'}
          </div>
        </article>
      </div>

      <div className="intent-flow-principle">
        <span>VOXLOCK PRINCIPLE</span>

        <strong>
          Superseded computation may finish.
          Superseded intent must not become reality.
        </strong>
      </div>
    </section>
  )
}