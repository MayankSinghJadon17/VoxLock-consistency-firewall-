export const formatEventTime = (timestamp: number, origin?: number): string => {
  if (origin === undefined) return '+0.00s'
  const elapsed = Math.max(0, timestamp - origin)
  return `+${elapsed.toFixed(2)}s`
}

export const formatDuration = (start: number, end: number): string => {
  const elapsed = Math.max(0, end - start)
  const minutes = Math.floor(elapsed / 60)
  const seconds = Math.floor(elapsed % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export const formatRequestId = (id: number): string =>
  `REQ ${String(id).padStart(3, '0')}`

export const padMetric = (value: number): string =>
  String(value).padStart(2, '0')
