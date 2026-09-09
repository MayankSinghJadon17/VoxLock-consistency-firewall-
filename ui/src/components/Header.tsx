import StatusPip from './StatusPip'

export default function Header() {
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <div className="brand-mark">
          VX<span />
        </div>

        <div>
          <div className="brand-name">VOXLOCK</div>
          <div className="brand-subtitle">
            CONSISTENCY FIREWALL FOR VOICE AGENTS
          </div>
        </div>
      </div>

      <div className="system-status">
        <StatusPip tone="active" />
        <span>LIVE</span>
        <span className="system-online">SYSTEM ONLINE</span>
      </div>
    </header>
  )
}