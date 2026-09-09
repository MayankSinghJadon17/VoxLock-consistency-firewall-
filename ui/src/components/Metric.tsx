export default function Metric({
  label,
  value,
  suffix,
  quiet = false,
}: {
  label: string
  value: string | number
  suffix?: string
  quiet?: boolean
}) {
  return (
    <div className={`metric ${quiet ? 'metric--quiet' : ''}`}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">
        {value}
        <small>{suffix}</small>
      </span>
    </div>
  )
}
