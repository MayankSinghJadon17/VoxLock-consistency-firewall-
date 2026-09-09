import StatusPip from './StatusPip'

export default function DemoControls({
  isRunning,
  onStart,
  onInterrupt,
  onGhost,
  onReset,
}: {
  isRunning: boolean
  onStart: () => void
  onInterrupt: () => void
  onGhost: () => void
  onReset: () => void
}) {
  return (
    <footer className="demo-footer">
      <div className="footer-note">
        <span className="pulse-ring">
          <StatusPip tone={isRunning ? 'active' : 'neutral'} />
        </span>
        <span>{isRunning ? 'DEMO IN PROGRESS' : 'MOCK EVENT SOURCE'}</span>
      </div>
      <div className="demo-controls">
        <button onClick={onStart} disabled={isRunning}>
          START DEMO <span>↗</span>
        </button>
        <button onClick={onInterrupt}>INTERRUPT</button>
        <button onClick={onGhost}>GHOST TASK COMPLETE</button>
        <button className="reset-button" onClick={onReset}>
          RESET
        </button>
      </div>
    </footer>
  )
}
