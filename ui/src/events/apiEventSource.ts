import type { VoiceGuardSnapshot } from './types'

const API_BASE = (import.meta.env.VITE_VOICEGUARD_API_URL ?? '').replace(/\/$/, '')

export function createApiEventSource(onUpdate: (snapshot: VoiceGuardSnapshot) => void) {
  let stopped = false
  let timer: number | undefined

  const poll = async () => {
    if (stopped) return
    try {
      const response = await fetch(`${API_BASE}/api/state`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      onUpdate((await response.json()) as VoiceGuardSnapshot)
    } catch {
      // Keep the last known state while the backend is starting/restarting.
    } finally {
      if (!stopped) timer = window.setTimeout(poll, 350)
    }
  }

  void poll()
  return {
    stop() {
      stopped = true
      if (timer !== undefined) window.clearTimeout(timer)
    },
  }
}
