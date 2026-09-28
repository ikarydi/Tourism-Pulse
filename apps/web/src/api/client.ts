// Vite's dev server proxies /api/* to the backend (vite.config.ts) and
// strips the prefix - same convention the previous version of this app
// used, kept because it works and needs no CORS config for local dev
// (the backend now has CORSMiddleware too, for a real deploy where this
// proxy doesn't exist - see apps/api/src/tourism_pulse_api/main.py).
const API_BASE = '/api'

type ErrorDetail = string | { msg?: string }[]

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: ErrorDetail }
      if (typeof body.detail === 'string') detail = body.detail
      // FastAPI validation errors arrive as a list of {msg, loc, ...}.
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = body.detail[0].msg
    } catch {
      // Keep the status-based message when the server doesn't return JSON.
    }
    throw new Error(detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
