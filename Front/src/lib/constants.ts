const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  if (envUrl) return envUrl
  if (import.meta.env.PROD) return ''
  return 'http://localhost:8000'
}

const getWsUrl = () => {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) return envUrl
  
  if (import.meta.env.PROD) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws`
  }
  
  return 'ws://localhost:8000/ws'
}

export const API_BASE_URL = getApiBaseUrl()
export const WS_URL = getWsUrl()

export const API_ROUTES = {
  students: `${API_BASE_URL}/api/v1/students`,
  dashboard: `${API_BASE_URL}/api/v1/dashboard`,
  settings: `${API_BASE_URL}/api/v1/settings`,
} as const

