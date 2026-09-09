import type { VoiceMetrics } from '../events/types'
import { padMetric } from '../utils/format'
import Metric from './Metric'

export default function MetricsStrip({ metrics }: { metrics: VoiceMetrics }) {
  return (
    <section className="metrics-strip section-rule">
      <Metric label="REQUESTS" value={padMetric(metrics.requests)} />
      <Metric label="SUPERSEDED" value={padMetric(metrics.superseded)} />
      <Metric
        label="STALE AUDIO BLOCKED"
        value={padMetric(metrics.blocked)}
      />
      <Metric label="ACTUALLY HEARD" value={metrics.heard} suffix=" chunks" />
      <Metric label="GHOST TASKS" value={padMetric(metrics.ghostTasks)} />
    </section>
  )
}
