// Vite's dev server proxies /api/* to the backend (vite.config.ts) and
// strips the prefix - same convention the previous version of this app
// used, kept because it works and needs no CORS config for local dev
// (the backend now has CORSMiddleware too, for a real deploy where this
// proxy doesn't exist - see apps/api/src/tourism_pulse_api/main.py).
const API_BASE = '/api'

export async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the status-based message when the server doesn't return JSON.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}
