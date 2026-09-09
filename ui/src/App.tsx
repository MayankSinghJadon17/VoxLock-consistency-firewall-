import { useEffect, useState } from 'react'
import { createApiEventSource } from './events/apiEventSource'
import type { VoiceGuardSnapshot } from './events/types'
import Header from './components/Header'
import GuaranteeBanner from './components/GuaranteeBanner'
import CurrentRequest from './components/CurrentRequest'
import Timeline from './components/Timeline'
import OutputIntegrity from './components/OutputIntegrity'
import GhostTasks from './components/GhostTasks'
import MetricsStrip from './components/MetricsStrip'
import IntentFlow from './components/IntentFlow'

function App() {
  const [snapshot, setSnapshot] = useState<VoiceGuardSnapshot>({
    currentRequest: null,
    requests: [],
    events: [],
    metrics: { requests: 0, superseded: 0, blocked: 0, heard: 0, ghostTasks: 0, generated: 0 },
    demoStep: 0,
    isRunning: false,
    serverTime: 0,
  })
  const [showReason, setShowReason] = useState(true)

  const [demoStarting, setDemoStarting] = useState(false)

  const startDemo = async () => {
    if (demoStarting || snapshot.isRunning) return

    setDemoStarting(true)

    try {
      const response = await fetch('/api/start_demo', {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
    } catch (error) {
      console.error('Failed to start demo', error)
    } finally {
      setDemoStarting(false)
    }
  }

  const [demoStopping, setDemoStopping] = useState(false)

  const stopDemo = async () => {
    if (demoStopping) return

    setDemoStopping(true)

    try {
      const response = await fetch('/api/stop_demo', {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
    } catch (error) {
      console.error('Failed to stop demo', error)
    } finally {
      setDemoStopping(false)
    }
  }
  useEffect(() => {
    const source = createApiEventSource(setSnapshot)
    return () => source.stop()
  }, [])

  if (!snapshot) return null

  const current = snapshot.currentRequest
  const ghostTask = [...snapshot.events].reverse().find((e) => e.type === 'ghost_task')
  const ghostRequest = ghostTask
    ? snapshot.requests.find((r) => r.id === ghostTask.requestId)
    : undefined

  return (
    <main className="app-shell">
      <div className="grid-texture" aria-hidden="true" />

      <Header />

      <GuaranteeBanner />

      <section className="demo-launch section-rule">
        <div>
          <div className="section-kicker">
            <span>01</span>
            <span>DEMO CONTROL</span>
          </div>
          <div className="demo-launch-copy">
            {snapshot.isRunning
              ? 'DEMO ACTIVE'
              : demoStarting
                ? 'STARTING VOICEGUARD...'
                : 'SYSTEM READY — START WHEN YOU ARE READY'}
          </div>
        </div>

        <div className="demo-launch-actions">
          <button
            className="demo-launch-button"
            onClick={startDemo}
            disabled={demoStarting || snapshot.isRunning}
          >
            {snapshot.isRunning ? 'DEMO ACTIVE' : 'START DEMO'} <span>↗</span>
          </button>

          <button
            className="demo-stop-button"
            onClick={stopDemo}
            disabled={!snapshot.isRunning || demoStopping}
          >
            {demoStopping ? 'STOPPING...' : 'STOP DEMO'}
          </button>
        </div>
      </section>

      <section className="current-section section-rule">
        <div className="section-kicker">
          <span>02</span>
          <span>CURRENT REQUEST</span>
        </div>
        <CurrentRequest request={current} serverTime={snapshot.serverTime} />
      </section>

      <section className="timeline-section section-rule">
        <IntentFlow snapshot={snapshot} />
        <Timeline events={snapshot.events} />
      </section>

      <div className="lower-grid">
        <OutputIntegrity
          metrics={snapshot.metrics}
          events={snapshot.events}
          showReason={showReason}
          onToggleReason={() => setShowReason((open) => !open)}
        />
        <GhostTasks ghostTask={ghostTask} ghostRequest={ghostRequest} />
      </div>

      <MetricsStrip metrics={snapshot.metrics} />
    </main>
  )
}

export default App
