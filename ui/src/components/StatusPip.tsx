type Tone = 'neutral' | 'active' | 'blocked' | 'muted'

export default function StatusPip({ tone = 'neutral' }: { tone?: Tone }) {
  return <span className={`status-pip status-pip--${tone}`} aria-hidden="true" />
}
