export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const WS_URL =
  import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws'

export const API_ROUTES = {
  students: `${API_BASE_URL}/api/v1/students`,
  dashboard: `${API_BASE_URL}/api/v1/dashboard`,
  settings: `${API_BASE_URL}/api/v1/settings`,
} as const

