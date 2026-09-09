import type { VoiceEvent, VoiceMetrics } from '../events/types'
import Metric from './Metric'
import StatusPip from './StatusPip'
import { formatRequestId } from '../utils/format'

export default function OutputIntegrity({
  metrics,
  events,
  showReason,
  onToggleReason,
}: {
  metrics: VoiceMetrics
  events: VoiceEvent[]
  showReason: boolean
  onToggleReason: () => void
}) {
  const latestBlocked = [...events]
    .reverse()
    .find((e) => e.type === 'audio_blocked')

  const blockedRequestId = latestBlocked?.requestId

  const blockedIndex = latestBlocked
    ? events.findIndex((e) => e.id === latestBlocked.id)
    : -1

  const replacement =
    blockedRequestId !== undefined
      ? events
          .slice(blockedIndex + 1)
          .find(
            (e) =>
              e.type === 'request_started' &&
              (e.requestId ?? 0) > blockedRequestId,
          )
      : undefined

  const generatedEvents = events.filter(
    (e) => e.type === 'audio_generated',
  )

  const playedEvents = events.filter(
    (e) => e.type === 'audio_played',
  )

  const blockedEvents = events.filter(
    (e) => e.type === 'audio_blocked',
  )

  const generatedCount = generatedEvents.reduce(
    (total, event) => total + (event.metric ?? 1),
    0,
  )

  const playedCount = playedEvents.reduce(
    (total, event) => total + (event.metric ?? 1),
    0,
  )

  const blockedCount = blockedEvents.reduce(
    (total, event) => total + (event.metric ?? 1),
    0,
  )

  return (
    <section className="heard-section section-rule">
      <div className="section-kicker">
        <span>04</span>
        <span>OUTPUT INTEGRITY</span>
      </div>

      <div className="heard-header">
        <h2>
          GENERATED <span>≠</span> HEARD
        </h2>

        <span className="integrity-mark">
          FIREWALL PROTECTED
        </span>
      </div>

      <div className="heard-metrics">
        <Metric
          label="GENERATED"
          value={generatedCount || metrics.generated}
          suffix=" chunks"
          quiet
        />

        <Metric
          label="ACTUALLY HEARD"
          value={playedCount || metrics.heard}
          suffix=" chunks"
        />

        <Metric
          label="STALE AUDIO BLOCKED"
          value={blockedCount || metrics.blocked}
          suffix=" chunks"
          quiet
        />
      </div>

      <div className="ledger-flow">
        <div className="ledger-step">
          <span className="ledger-index">01</span>
          <div>
            <strong>GENERATED</strong>
            <span>Rime audio produced</span>
          </div>
        </div>

        <div className="ledger-arrow">→</div>

        <div className="ledger-step ledger-step--heard">
          <span className="ledger-index">02</span>
          <div>
            <strong>HEARD</strong>
            <span>Audio actually played</span>
          </div>
        </div>

        <div className="ledger-arrow">→</div>

        <div className="ledger-step ledger-step--blocked">
          <span className="ledger-index">03</span>
          <div>
            <strong>BLOCKED</strong>
            <span>Superseded audio rejected</span>
          </div>
        </div>
      </div>

      <div className="blocked-callout">
        <div className="blocked-title">
          <StatusPip tone="blocked" />

          {latestBlocked
            ? 'STALE AUDIO BLOCKED'
            : 'FIREWALL READY'}
        </div>

        {latestBlocked ? (
          <>
            <p>
              Audio belonged to superseded request{' '}
              <strong>
                {formatRequestId(blockedRequestId!)}
              </strong>.
            </p>

            <button
              className="disclosure"
              onClick={onToggleReason}
              aria-expanded={showReason}
            >
              WHY WAS THIS BLOCKED?
              <span>{showReason ? '−' : '+'}</span>
            </button>

            {showReason && (
              <div className="reason-copy">
                Request{' '}
                <strong>
                  {formatRequestId(blockedRequestId!)}
                </strong>{' '}
                was invalidated before playback.

                {replacement && (
                  <>
                    {' '}
                    It was superseded by{' '}
                    <strong>
                      {formatRequestId(
                        replacement.requestId!,
                      )}
                    </strong>
                    .
                  </>
                )}

                <br />

                The consistency firewall rejected the stale
                audio chunk before it became spoken output.
              </div>
            )}
          </>
        ) : (
          <p>
            No stale audio has been observed in this run.
          </p>
        )}
      </div>
    </section>
  )
}